"""Touches API: лог касаний компании."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from granite.api.deps import get_db
from granite.database import CrmTouchRow, CrmContactRow

__all__ = ["router"]

router = APIRouter()


@router.post("/companies/{company_id}/touches")
def create_touch(company_id: int, data: dict, db: Session = Depends(get_db)):
    """Залогировать касание.

    Body: {channel: email|tg|wa|manual, direction: outgoing|incoming, body?: str, subject?: str}
    """
    touch = CrmTouchRow(
        company_id=company_id,
        channel=data.get("channel", "manual"),
        direction=data.get("direction", "outgoing"),
        subject=data.get("subject", ""),
        body=data.get("body", ""),
        note=data.get("note", ""),
    )
    db.add(touch)

    contact = db.get(CrmContactRow, company_id)
    if not contact:
        contact = CrmContactRow(company_id=company_id)
        db.add(contact)

    now = datetime.now(timezone.utc)
    channel = data.get("channel", "")
    direction = data.get("direction", "outgoing")

    contact.contact_count = (contact.contact_count or 0) + 1
    contact.last_contact_at = now
    contact.last_contact_channel = channel
    if not contact.first_contact_at:
        contact.first_contact_at = now

    if direction == "outgoing":
        if channel == "email":
            contact.email_sent_count = (contact.email_sent_count or 0) + 1
            contact.last_email_sent_at = now
            if contact.funnel_stage == "new":
                contact.funnel_stage = "email_sent"
        elif channel == "tg":
            contact.tg_sent_count = (contact.tg_sent_count or 0) + 1
            contact.last_tg_at = now
            if contact.funnel_stage in ("new", "email_sent", "email_opened"):
                contact.funnel_stage = "tg_sent"
        elif channel == "wa":
            contact.wa_sent_count = (contact.wa_sent_count or 0) + 1
            contact.last_wa_at = now
            if contact.funnel_stage not in ("replied", "interested", "not_interested"):
                contact.funnel_stage = "wa_sent"
    elif direction == "incoming":
        contact.stop_automation = 1
        if contact.funnel_stage not in ("interested", "not_interested"):
            contact.funnel_stage = "replied"

    db.flush()
    return {"ok": True, "touch_id": touch.id}


@router.get("/companies/{company_id}/touches")
def get_touches(company_id: int, db: Session = Depends(get_db)):
    """История касаний компании (новые первые)."""
    touches = (
        db.query(CrmTouchRow)
        .filter_by(company_id=company_id)
        .order_by(CrmTouchRow.created_at.desc())
        .all()
    )
    return [
        {
            "id": t.id,
            "channel": t.channel,
            "direction": t.direction,
            "subject": t.subject,
            "body": t.body,
            "note": t.note,
            "created_at": t.created_at.isoformat() if t.created_at else None,
        }
        for t in touches
    ]
