"""Touches API: лог касаний компании."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional

from fastapi import HTTPException

from granite.api.deps import get_db
from granite.api.schemas import (
    CreateTouchRequest, OkResponse, OkWithIdResponse, TouchResponse,
    PaginatedResponse,
)
from granite.api.stage_transitions import apply_outgoing_touch, apply_incoming_touch
from granite.database import CrmTouchRow, CrmContactRow, CompanyRow

__all__ = ["router"]

router = APIRouter()


@router.post("/companies/{company_id}/touches", response_model=OkWithIdResponse, status_code=201)
def create_touch(company_id: int, data: CreateTouchRequest, db: Session = Depends(get_db)):
    """Залогировать касание.

    Body: {channel: email|tg|wa|manual, direction: outgoing|incoming, body?: str, subject?: str}
    """
    # FIX H5: Проверяем существование компании перед созданием касания.
    company = db.get(CompanyRow, company_id)
    if not company:
        raise HTTPException(404, "Company not found")

    touch = CrmTouchRow(
        company_id=company_id,
        channel=data.channel,
        direction=data.direction,
        subject=data.subject,
        body=data.body,
        note=data.note,
    )
    db.add(touch)

    contact = db.get(CrmContactRow, company_id)
    if not contact:
        contact = CrmContactRow(company_id=company_id)
        db.add(contact)

    if data.direction == "outgoing":
        apply_outgoing_touch(contact, data.channel)
    elif data.direction == "incoming":
        apply_incoming_touch(contact)

    db.flush()
    return OkWithIdResponse(ok=True, id=touch.id)


@router.get("/companies/{company_id}/touches", response_model=PaginatedResponse)
def get_touches(
    company_id: int,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """История касаний компании (новые первые). Пагинация."""
    q = (
        db.query(CrmTouchRow)
        .filter_by(company_id=company_id)
        .order_by(CrmTouchRow.created_at.desc())
    )
    total = q.count()
    rows = q.offset((page - 1) * per_page).limit(per_page).all()
    items = [
        {
            "id": t.id,
            "channel": t.channel,
            "direction": t.direction,
            "subject": t.subject,
            "body": t.body,
            "note": t.note,
            "created_at": t.created_at.isoformat() if t.created_at else None,
        }
        for t in rows
    ]
    return {"items": items, "total": total, "page": page, "per_page": per_page}


@router.get("/companies/{company_id}/touches/{touch_id}", response_model=TouchResponse)
def get_touch(company_id: int, touch_id: int, db: Session = Depends(get_db)):
    """Получить конкретное касание компании."""
    touch = db.get(CrmTouchRow, touch_id)
    if not touch or touch.company_id != company_id:
        raise HTTPException(404, "Touch not found")
    return {
        "id": touch.id,
        "company_id": touch.company_id,
        "channel": touch.channel,
        "direction": touch.direction,
        "subject": touch.subject,
        "body": touch.body,
        "note": touch.note,
        "created_at": touch.created_at.isoformat() if touch.created_at else None,
    }


@router.delete("/touches/{touch_id}", response_model=OkResponse)
def delete_touch(touch_id: int, db: Session = Depends(get_db)):
    """Удалить касание по ID."""
    touch = db.get(CrmTouchRow, touch_id)
    if not touch:
        raise HTTPException(404, "Touch not found")
    db.delete(touch)
    db.flush()
    return OkResponse(ok=True)
