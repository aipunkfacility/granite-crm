"""Reply parser — обработка ответов из IMAP.

Задача 9: process_replies() подключается к IMAP, находит ответы
на отправленные письма и обновляет статусы в БД.

Логика:
- Обычный ответ → funnel_stage="replied", cancel_followup_tasks(),
  total_replied++, CrmTouchRow с текстом ответа
- Автоответ (OOO) → игнорируется
- «Это спам» → stop_automation=1
- IMAP connection error → graceful, не крашится
"""
import re
from datetime import datetime, timezone

from loguru import logger

from granite.email.imap_helpers import (
    extract_email, extract_body, is_bounce, is_ooo,
    fetch_imap_messages,
)

__all__ = ["process_replies"]

# Паттерны для распознавания жалобы на спам
_SPAM_PATTERNS = re.compile(
    r"это\s+спам|рассылк[аи].*спам|отпиш|не\s+присылай|удалите|unsubscribe",
    re.IGNORECASE,
)


def process_replies(db_session) -> int:
    """Обработать ответы из IMAP.

    Returns:
        Количество обработанных ответов.
    """
    from granite.database import (
        CrmEmailLogRow, CrmContactRow, CrmTouchRow, CrmEmailCampaignRow,
    )
    from granite.api.helpers import cancel_followup_tasks

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

            if not reply_email:
                logger.debug(f"process_replies: cannot extract reply email from message {mid}")
                continue

            # Найти лог отправленного письма по email_to
            log = (
                db_session.query(CrmEmailLogRow)
                .filter_by(email_to=reply_email)
                .order_by(CrmEmailLogRow.sent_at.desc())
                .first()
            )

            if not log:
                logger.debug(f"process_replies: no sent log for {reply_email}")
                continue

            # Извлечь тело ответа
            body = extract_body(msg)
            subject = msg.get("Subject", "") or ""

            # Проверить на спам-жалобу
            contact = db_session.get(CrmContactRow, log.company_id)

            if contact and _is_spam_complaint(body, subject):
                contact.stop_automation = 1
                logger.info(
                    f"company_id={contact.company_id}: stop_automation=1 "
                    f"(spam complaint from {reply_email})"
                )
                # Также записать touch о спам-жалобе
                db_session.add(CrmTouchRow(
                    company_id=log.company_id,
                    channel="email",
                    direction="incoming",
                    subject=subject,
                    body=body[:2000] if body else "[spam complaint]",
                    note="spam complaint → stop_automation",
                ))
                db_session.commit()
                processed += 1
                continue

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


def _is_spam_complaint(body: str, subject: str) -> bool:
    """Определить, является ли ответ жалобой на спам.

    Проверяет текст тела и тему на ключевые паттерны.
    """
    text = f"{subject} {body}"
    return bool(_SPAM_PATTERNS.search(text))
