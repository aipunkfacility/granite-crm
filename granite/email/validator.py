"""Валидация получателей перед отправкой.

Задача 4: Фильтрация агрегаторов, невалидных email, дедупликация,
проверка интервала между письмами, признаки блокировки Gmail.

FIX-4: Добавлена проверка признаков блокировки Gmail — если >=5 bounced
на @gmail.com за последние 24ч, домен помечается как заблокированный.
"""
import re
from datetime import datetime, timedelta, timezone
from typing import Optional

# Домены агрегаторов — не мастерские (из scraper-audit A-1)
AGGREGATOR_DOMAINS = frozenset({
    "tsargranit.ru", "alshei.ru", "mipomnim.ru", "uznm.ru",
    "monuments.su", "masterskay-granit.ru", "gr-anit.ru",
    "v-granit.ru", "nbs-granit.ru", "granit-pamiatnik.ru",
    "postament.ru", "uslugio.com", "pqd.ru", "spravker.ru",
    "orgpage.ru", "totadres.ru", "mapage.ru", "zoon.ru",
    "memorial.ru", "vsepamyatniki.ru", "obeliski.ru",
})

_EMAIL_RE = re.compile(r"^[\w.+-]+@[\w.-]+\.\w{2,}$")

# Минимальный интервал между письмами одной компании (часы)
EMAIL_SESSION_GAP_HRS = 4

# FIX-4: Порог bounced для признака блокировки Gmail
GMAIL_BOUNCE_THRESHOLD = 5  # bounced писем
GMAIL_BOUNCE_WINDOW_HRS = 24  # за последние N часов

__all__ = ["validate_recipients", "check_gmail_block_signs", "AGGREGATOR_DOMAINS"]


def validate_recipients(
    recipients: list[tuple],
    db_session=None,
) -> tuple[list[tuple], list[dict]]:
    """Валидация списка получателей перед отправкой.

    Args:
        recipients: список кортежей (company, enriched, contact, email_to).
        db_session: опциональная сессия БД для проверки Gmail block signs.

    Returns:
        Кортеж (valid, warnings):
        - valid: список кортежей получателей, прошедших валидацию.
        - warnings: список словарей с информацией о пропущенных получателях.
    """
    valid = []
    warnings = []
    seen_emails: set[str] = set()

    # FIX-4: Проверяем признаки блокировки Gmail до рассылки
    blocked_domains: set[str] = set()
    if db_session is not None:
        blocked_domains = check_gmail_block_signs(db_session)
        if blocked_domains:
            from loguru import logger
            logger.warning(
                f"Gmail block signs detected for domains: {blocked_domains}. "
                f"Recipients on these domains will be filtered."
            )

    for company, enriched, contact, email_to in recipients:
        # Дедупликация email
        email_lower = email_to.lower().strip()
        if email_lower in seen_emails:
            warnings.append({
                "company_id": company.id,
                "name": getattr(company, "name_best", ""),
                "reason": f"дубль email ({email_lower})",
            })
            continue
        seen_emails.add(email_lower)

        reason = _check_recipient(company, contact, email_to, blocked_domains)
        if reason:
            warnings.append({
                "company_id": company.id,
                "name": getattr(company, "name_best", ""),
                "reason": reason,
            })
        else:
            valid.append((company, enriched, contact, email_to))

    return valid, warnings


def _check_recipient(company, contact, email_to: str, blocked_domains: Optional[set[str]] = None) -> str | None:
    """Проверить одного получателя.

    Returns:
        None = валиден, строка = причина пропуска.
    """
    # Формат email
    if not email_to or not _EMAIL_RE.match(email_to):
        return f"невалидный email ({email_to})"

    # Агрегатор
    domain = email_to.split("@")[-1].lower()
    if domain in AGGREGATOR_DOMAINS:
        return f"агрегатор ({domain})"

    # FIX-4: Блокировка Gmail
    if blocked_domains and domain in blocked_domains:
        return f"блокировка Gmail ({domain})"

    # Отписан
    if contact and getattr(contact, "stop_automation", 0):
        return "отписан"

    # Пустое или слишком длинное название (SEO-мусор)
    name = (getattr(company, "name_best", "") or "").strip()
    if not name:
        return "пустое название"
    if len(name) > 80:
        return "название слишком длинное (SEO?)"

    # Проверка интервала между письмами (EMAIL_SESSION_GAP_HRS)
    if contact and hasattr(contact, "last_email_sent_at") and contact.last_email_sent_at:
        # FIX A2: безопасная конвертация tz — не крашимся на already-aware timestamps (PostgreSQL TIMESTAMPTZ)
        last_sent = contact.last_email_sent_at
        if last_sent.tzinfo is None:
            last_sent = last_sent.replace(tzinfo=timezone.utc)
        else:
            last_sent = last_sent.astimezone(timezone.utc)
        gap = datetime.now(timezone.utc) - last_sent
        if gap.total_seconds() < EMAIL_SESSION_GAP_HRS * 3600:
            hrs_left = EMAIL_SESSION_GAP_HRS - gap.total_seconds() / 3600
            return f"письмо недавно ({hrs_left:.1f}ч до следующего)"

    return None


def check_gmail_block_signs(db_session) -> set[str]:
    """FIX-4: Проверить признаки блокировки Gmail.

    Если >=GMAIL_BOUNCE_THRESHOLD bounced писем на домен за последние
    GMAIL_BOUNCE_WINDOW_HRS часов — домен считается заблокированным.

    Returns:
        Множество заблокированных доменов (например, {"gmail.com"}).
    """
    from granite.database import CrmEmailLogRow
    from sqlalchemy import func

    threshold_time = datetime.now(timezone.utc) - timedelta(hours=GMAIL_BOUNCE_WINDOW_HRS)

    # Подсчитываем bounced по доменам за окно
    # FIX-A1: Используем .label() вместо строки в group_by — совместимо с PostgreSQL
    domain_expr = func.substr(CrmEmailLogRow.email_to, func.instr(CrmEmailLogRow.email_to, "@") + 1).label("domain")
    bounced_by_domain = (
        db_session.query(
            domain_expr,
            func.count(CrmEmailLogRow.id).label("bounce_count"),
        )
        .filter(
            CrmEmailLogRow.status == "bounced",
            CrmEmailLogRow.bounced_at >= threshold_time,
        )
        .group_by(domain_expr)
        .having(func.count(CrmEmailLogRow.id) >= GMAIL_BOUNCE_THRESHOLD)
        .all()
    )

    return {row[0].lower() for row in bounced_by_domain if row[0]}
