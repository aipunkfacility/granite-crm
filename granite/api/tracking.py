"""Tracking pixel endpoint для отслеживания открытий email."""
import re
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session

from granite.api.deps import get_db
from granite.database import CrmEmailLogRow, CrmContactRow
from granite.email.sender import TRANSPARENT_PNG

__all__ = ["router"]

router = APIRouter()

_BOT_USER_AGENTS = ("bot", "crawler", "spider", "curl", "wget", "python-requests", "go-http")

# AUDIT #20: Валидация формата tracking_id — UUID-подобный паттерн.
# Отбрасываем заведомо невалидные значения (путь-траверсинг, SQL-инъекции).
_TRACKING_ID_PATTERN = re.compile(r"^[a-zA-Z0-9\-_]{8,64}$")


@router.get("/track/open/{tracking_id}.png")
def track_open(tracking_id: str, request: Request, db: Session = Depends(get_db)):
    """Tracking pixel: 1x1 PNG. При открытии письма — обновляет статус в БД.

    Защита от ложных срабатываний:
    - AUDIT #20: Валидация формата tracking_id (alphanumeric, 8-64 символа).
    - Игнорирует повторные открытия (opened_at уже есть).
    - Игнорирует известные боты по User-Agent.
    """
    # AUDIT #20: Валидация tracking_id
    if not _TRACKING_ID_PATTERN.match(tracking_id):
        return Response(
            content=TRANSPARENT_PNG,
            media_type="image/png",
            headers={"Cache-Control": "no-store, no-cache, must-revalidate"},
        )

    user_agent = request.headers.get("user-agent", "").lower()
    if any(bot in user_agent for bot in _BOT_USER_AGENTS):
        return Response(
            content=TRANSPARENT_PNG,
            media_type="image/png",
            headers={"Cache-Control": "no-store, no-cache, must-revalidate"},
        )

    log = db.query(CrmEmailLogRow).filter_by(tracking_id=tracking_id).first()

    if log and log.opened_at is None:
        now = datetime.now(timezone.utc)
        log.opened_at = now
        log.status = "opened"

        contact = db.get(CrmContactRow, log.company_id)
        if contact:
            contact.email_opened_count = (contact.email_opened_count or 0) + 1
            contact.last_email_opened_at = now
            if contact.funnel_stage == "email_sent":
                contact.funnel_stage = "email_opened"

            # Задача 5: создать follow-up задачу при первом открытии
            from granite.email.followup_logic import maybe_create_followup_task
            maybe_create_followup_task(contact, log.campaign_id, db)

        # Задача 5: инкремент total_opened для кампании
        if log.campaign_id:
            from granite.email.followup_logic import increment_campaign_opened
            increment_campaign_opened(log.campaign_id, db)

    return Response(
        content=TRANSPARENT_PNG,
        media_type="image/png",
        headers={"Cache-Control": "no-store, no-cache, must-revalidate"},
    )
