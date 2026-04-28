"""Follow-up логика: создание задач, инкремент счётчиков.

Задача 5: follow-up при открытии + total_opened++ для кампании.

Функции:
    maybe_create_followup_task()  — создать CrmTaskRow при первом открытии письма
    increment_campaign_opened()   — инкремент campaign.total_opened
"""
from datetime import datetime, timedelta, timezone

from loguru import logger

__all__ = [
    "maybe_create_followup_task",
    "increment_campaign_opened",
]

# Через сколько дней отправить follow-up
FOLLOWUP_DELAY_DAYS = 7


def maybe_create_followup_task(contact, campaign_id: int, db_session) -> None:
    """Создать follow-up задачу при первом открытии письма.

    Не создаёт дубликат: если pending follow-up для этого company_id
    в рамках кампании уже есть — пропускаем.

    Args:
        contact: CrmContactRow — контакт компании.
        campaign_id: ID кампании.
        db_session: сессия БД.
    """
    from granite.database import CrmTaskRow

    # Проверяем — нет ли уже pending follow-up для этого company_id
    existing = (
        db_session.query(CrmTaskRow)
        .filter(
            CrmTaskRow.company_id == contact.company_id,
            CrmTaskRow.task_type == "follow_up",
            CrmTaskRow.status == "pending",
        )
        .first()
    )
    if existing:
        logger.debug(
            f"company_id={contact.company_id}: follow-up already pending (id={existing.id})"
        )
        return

    due_date = datetime.now(timezone.utc) + timedelta(days=FOLLOWUP_DELAY_DAYS)
    task = CrmTaskRow(
        company_id=contact.company_id,
        title=f"Follow-up email (campaign #{campaign_id})",
        task_type="follow_up",
        status="pending",
        due_date=due_date,
        priority="normal",
    )
    db_session.add(task)
    logger.info(
        f"company_id={contact.company_id}: follow-up task created "
        f"(due={due_date.date()}, campaign={campaign_id})"
    )


def increment_campaign_opened(campaign_id: int, db_session) -> None:
    """Инкремент campaign.total_opened на 1.

    Args:
        campaign_id: ID кампании.
        db_session: сессия БД.
    """
    from granite.database import CrmEmailCampaignRow

    campaign = db_session.get(CrmEmailCampaignRow, campaign_id)
    if campaign:
        campaign.total_opened = (campaign.total_opened or 0) + 1
        logger.debug(f"campaign_id={campaign_id}: total_opened={campaign.total_opened}")
