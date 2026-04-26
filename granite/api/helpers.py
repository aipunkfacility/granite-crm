"""Общие хелперы для API."""
from loguru import logger
from datetime import datetime, timezone


CANCEL_FOLLOWUP_ON_STAGES = {"replied", "interested", "not_interested", "unreachable"}


def cancel_followup_tasks(company_id: int, new_stage: str, db) -> None:
    """Отменить все pending follow-up задачи при переходе в терминальную стадию.

    Вызывается из:
    - stage_transitions.py (apply_incoming_touch)
    - process_replies.py (обнаружение ответа)
    - unsubscribe.py (отписка)
    """
    from granite.database import CrmTaskRow

    if new_stage not in CANCEL_FOLLOWUP_ON_STAGES:
        return
    cancelled = (
        db.query(CrmTaskRow)
        .filter(
            CrmTaskRow.company_id == company_id,
            CrmTaskRow.status == "pending",
            CrmTaskRow.task_type == "follow_up",
        )
        .update({"status": "cancelled", "completed_at": datetime.now(timezone.utc)})
    )
    if cancelled:
        logger.info(f"company_id={company_id}: отменено {cancelled} follow-up (→ {new_stage})")
