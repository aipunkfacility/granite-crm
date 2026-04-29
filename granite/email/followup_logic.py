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
    "init_followup_config",
]

# Дефолт — используется если config.yaml не содержит email.followup_delay_days
_FOLLOWUP_DELAY_DAYS_DEFAULT = 7

# Глобальная ссылка на email-конфиг
_email_config: dict = {}


def init_followup_config(config: dict) -> None:
    """Инициализировать followup-конфиг из config.yaml."""
    global _email_config
    _email_config = config.get("email", {})


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

    delay_days = _email_config.get("followup_delay_days", _FOLLOWUP_DELAY_DAYS_DEFAULT)
    due_date = datetime.now(timezone.utc) + timedelta(days=delay_days)
    # FIX P3-M4: не показывать "None" в title для писем без кампании
    title = f"Follow-up email (campaign #{campaign_id})" if campaign_id else "Follow-up email"
    task = CrmTaskRow(
        company_id=contact.company_id,
        title=title,
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
