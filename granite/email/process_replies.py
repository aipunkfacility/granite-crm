"""Reply parser — обработка ответов из IMAP.

Задача 9: process_replies() подключается к IMAP, находит ответы
на отправленные письма и обновляет статусы в БД.

Логика:
- Обычный ответ → funnel_stage="replied", cancel_followup_tasks(),
  total_replied++, CrmTouchRow с текстом ответа
- Автоответ (OOO) → игнорируется
- IMAP connection error → graceful, не крашится
"""
from datetime import datetime, timezone

from loguru import logger
from sqlalchemy import func

from granite.email.imap_helpers import (
    extract_email, extract_body, is_bounce, is_ooo,
    fetch_imap_messages,
)

__all__ = ["process_replies"]


def process_replies(db_session, messages: list | None = None) -> int:
    """Обработать ответы из IMAP.

    Args:
        db_session: SQLAlchemy-сессия.
        messages: опциональный список (mid, msg). Если не передан —
                  загружает из IMAP самостоятельно.

    Returns:
        Количество обработанных ответов.
    """
    from granite.database import (
        CrmEmailLogRow, CrmContactRow, CrmTouchRow, CrmEmailCampaignRow,
    )
    from granite.api.helpers import cancel_followup_tasks

    if messages is None:
        try:
            messages = fetch_imap_messages()
        except Exception as e:
            logger.error(f"process_replies: IMAP connection error: {e}")
            return 0

    if not messages:
        return 0

    processed = 0

    for mid, msg in messages:
        try:
            # Пропускаем bounce — это не ответ
            if is_bounce(msg):
                continue

            # Пропускаем автоответчики
            if is_ooo(msg):
                logger.debug(f"process_replies: OOO ignored for message {mid}")
                continue

            # Извлечь email отправителя
            from_header = msg.get("From", "") or ""
            reply_email = extract_email(from_header)

            if reply_email:
                reply_email = reply_email.lower().strip()

            if not reply_email:
                logger.debug(f"process_replies: cannot extract reply email from message {mid}")
                continue

            # Найти лог отправленного письма по email_to
            log = (
                db_session.query(CrmEmailLogRow)
                .filter(func.lower(CrmEmailLogRow.email_to) == reply_email)
                .order_by(CrmEmailLogRow.sent_at.desc())
                .first()
            )

            if not log:
                logger.debug(f"process_replies: no sent log for {reply_email}")
                continue

            # Извлечь тело ответа
            body = extract_body(msg)
            subject = msg.get("Subject", "") or ""

            contact = db_session.get(CrmContactRow, log.company_id)

            # Обычный ответ
            if log.status != "replied":
                log.status = "replied"
                log.replied_at = datetime.now(timezone.utc)

            if contact:
                contact.funnel_stage = "replied"
                contact.email_replied_count = (contact.email_replied_count or 0) + 1

                # Отменить follow-up задачи
                cancel_followup_tasks(contact.company_id, "replied", db_session)

            # Инкремент total_replied для кампании
            if log.campaign_id:
                campaign = db_session.get(CrmEmailCampaignRow, log.campaign_id)
                if campaign:
                    campaign.total_replied = (campaign.total_replied or 0) + 1

            # Записать входящий touch
            db_session.add(CrmTouchRow(
                company_id=log.company_id,
                channel="email",
                direction="incoming",
                subject=subject,
                body=body[:2000] if body else "",
            ))

            db_session.commit()
            processed += 1
            logger.info(
                f"process_replies: {reply_email} → replied "
                f"(company_id={log.company_id})"
            )

        except Exception as e:
            logger.error(f"process_replies: error processing message {mid}: {e}")
            continue

    return processed



