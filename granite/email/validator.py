"""Валидация получателей перед отправкой.

Задача 4: Фильтрация агрегаторов, невалидных email, дедупликация,
проверка интервала между письмами, признаки блокировки Gmail.
"""
import re
from datetime import datetime, timezone

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

__all__ = ["validate_recipients", "AGGREGATOR_DOMAINS"]


def validate_recipients(
    recipients: list[tuple],
) -> tuple[list[tuple], list[dict]]:
    """Валидация списка получателей перед отправкой.

    Args:
        recipients: список кортежей (company, enriched, contact, email_to).

    Returns:
        Кортеж (valid, warnings):
        - valid: список кортежей получателей, прошедших валидацию.
        - warnings: список словарей с информацией о пропущенных получателях.
    """
    valid = []
    warnings = []
    seen_emails: set[str] = set()

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

        reason = _check_recipient(company, contact, email_to)
        if reason:
            warnings.append({
                "company_id": company.id,
                "name": getattr(company, "name_best", ""),
                "reason": reason,
            })
        else:
            valid.append((company, enriched, contact, email_to))

    return valid, warnings


def _check_recipient(company, contact, email_to: str) -> str | None:
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
        gap = datetime.now(timezone.utc) - contact.last_email_sent_at.replace(tzinfo=timezone.utc)
        if gap.total_seconds() < EMAIL_SESSION_GAP_HRS * 3600:
            hrs_left = EMAIL_SESSION_GAP_HRS - gap.total_seconds() / 3600
            return f"письмо недавно ({hrs_left:.1f}ч до следующего)"

    return None
