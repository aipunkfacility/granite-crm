"""Bounce parser — обработка bounce-уведомлений из IMAP.

Задача 6: process_bounces() подключается к IMAP, находит bounce-письма,
определяет DSN-код и обновляет статусы в БД.

Логика:
- DSN 5.1.1 (User unknown) → bounced + funnel_stage="unreachable"
- DSN 5.2.2 (Mailbox full) → bounced, funnel НЕ меняется (soft bounce)
- DSN 5.7.1 (Blocked) → bounced + stop_automation=1
- Другие 5.x.x → bounced + funnel_stage="unreachable" (по умолчанию)
- IMAP connection error → graceful, не крашится
"""
from datetime import datetime, timezone
from loguru import logger

from granite.email.imap_helpers import (
    extract_email, extract_body, is_bounce,
    extract_bounced_email, extract_dsn, fetch_imap_messages,
)

__all__ = ["process_bounces"]

# DSN-коды, при которых НЕ меняем funnel_stage (soft bounce)
_SOFT_BOUNCE_DSN = {"5.2.2"}  # Mailbox full

# DSN-коды, при которых ставим stop_automation=1
_BLOCK_DSN = {"5.7.1"}  # Blocked / rejected by policy


def _extract_all_text(msg) -> str:
    """Извлечь текст из ВСЕХ частей письма (для парсинга DSN).

    В отличие от extract_body() — собирает все text/plain и text/*
    части в одну строку, разделённую переводами строки.
    """
    parts = []
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            if content_type.startswith("text/"):
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    try:
                        parts.append(payload.decode(charset, errors="replace"))
                    except (LookupError, UnicodeDecodeError):
                        parts.append(payload.decode("utf-8", errors="replace"))
                else:
                    raw = part.get_payload()
                    if isinstance(raw, str):
                        parts.append(raw)
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            charset = msg.get_content_charset() or "utf-8"
            try:
                return payload.decode(charset, errors="replace")
            except (LookupError, UnicodeDecodeError):
                return payload.decode("utf-8", errors="replace")
        raw = msg.get_payload()
        return str(raw) if raw else ""
    return "\n".join(parts)


def process_bounces(db_session) -> int:
    """Обработать bounce-уведомления из IMAP.

    Returns:
        Количество обработанных bounce-уведомлений.
    """
    from granite.database import CrmEmailLogRow, CrmContactRow

    try:
        messages = fetch_imap_messages()
    except Exception as e:
        logger.error(f"process_bounces: IMAP connection error: {e}")
        return 0

    if not messages:
        return 0

    processed = 0

    for mid, msg in messages:
        try:
            if not is_bounce(msg):
                continue

            # Извлечь полный текст для парсинга DSN — все текстовые части
            # (DSN может быть во второй MIME-части после уведомления)
            full_text = _extract_all_text(msg)

            bounced_email = extract_bounced_email(full_text)
            dsn_code = extract_dsn(full_text)

            if not bounced_email:
                # FIX P3-H3: cascade fallback через X-Failed-Recipients → Return-Path → From
                # X-Failed-Recipients — стандартный заголовок для bounce (Gmail, Exchange)
                x_failed = msg.get("X-Failed-Recipients", "") or ""
                if x_failed:
                    # Может содержать несколько адресов через запятую
                    bounced_email = x_failed.split(",")[0].strip()
                if not bounced_email:
                    return_path = msg.get("Return-Path", "") or ""
                    if return_path:
                        bounced_email = extract_email(return_path)
                if not bounced_email:
                    from_header = msg.get("From", "") or ""
                    bounced_email = extract_email(from_header)

            if not bounced_email:
                logger.debug(f"process_bounces: cannot extract bounced email from message {mid}")
                continue

            # Найти лог отправленного письма по email_to
            log = (
                db_session.query(CrmEmailLogRow)
                .filter_by(email_to=bounced_email)
                .order_by(CrmEmailLogRow.sent_at.desc())
                .first()
            )

            if not log:
                logger.debug(f"process_bounces: no log for {bounced_email}")
                continue

            if log.status == "bounced":
                continue  # Уже обработан

            # Обновить лог
            now = datetime.now(timezone.utc)
            log.status = "bounced"
            log.bounced_at = now
            log.error_message = f"DSN {dsn_code}" if dsn_code else "Bounce"

            # Обновить контакт
            contact = db_session.get(CrmContactRow, log.company_id)
            if contact:
                if dsn_code in _BLOCK_DSN:
                    # 5.7.1 — заблокировано, стоп автоматизация
                    contact.stop_automation = 1
                    logger.info(
                        f"company_id={contact.company_id}: stop_automation=1 "
                        f"(DSN {dsn_code})"
                    )
                elif dsn_code in _SOFT_BOUNCE_DSN:
                    # 5.2.2 — почтовый ящик полон, не меняем стадию
                    logger.info(
                        f"company_id={contact.company_id}: soft bounce (DSN {dsn_code}), "
                        f"funnel_stage unchanged"
                    )
                else:
                    # Hard bounce (5.1.1 и другие) — unreachable
                    contact.funnel_stage = "unreachable"
                    logger.info(
                        f"company_id={contact.company_id}: funnel_stage=unreachable "
                        f"(DSN {dsn_code})"
                    )

            db_session.commit()
            processed += 1
            logger.info(f"process_bounces: {bounced_email} → bounced (DSN {dsn_code})")

        except Exception as e:
            logger.error(f"process_bounces: error processing message {mid}: {e}")
            continue

    return processed
