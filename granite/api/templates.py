"""Templates API: CRUD шаблонов сообщений."""
import re
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional

from granite.api.deps import get_db
from granite.api.schemas import (
    CreateTemplateRequest, UpdateTemplateRequest,
    OkResponse, TemplateResponse, PaginatedResponse,
)
from granite.database import CrmTemplateRow, CrmEmailCampaignRow
from loguru import logger

__all__ = ["router"]

router = APIRouter()

# Плейсхолдеры, которые шаблон может использовать
_KNOWN_PLACEHOLDERS = {
    "from_name", "city", "company_name", "website",
    "contact_name", "phone",
}


def _warn_unknown_placeholders(body: str, template_name: str) -> list[str]:
    """Найти плейсхолдеры в теле шаблона, которых нет в списке известных.

    Возвращает список неизвестных плейсхолдеров (без обёрток {}).
    Это предупреждение, не ошибка — шаблон всё равно сохраняется.
    """
    found = set(re.findall(r'\{(\w+)\}', body))
    unknown = found - _KNOWN_PLACEHOLDERS
    if unknown:
        logger.warning(
            f"Template '{template_name}': unknown placeholders: {unknown}. "
            f"Known: {_KNOWN_PLACEHOLDERS}"
        )
    return sorted(unknown)


@router.get("/templates", response_model=PaginatedResponse[TemplateResponse])
def list_templates(
    channel: Optional[str] = Query(None, pattern="^(email|tg|wa)$"),
    page: int = Query(1, ge=1),
    per_page: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    """Список шаблонов. Опциональный фильтр по каналу: ?channel=email|tg|wa."""
    q = db.query(CrmTemplateRow)
    if channel:
        q = q.filter_by(channel=channel)
    q = q.order_by(CrmTemplateRow.name)

    total = q.count()
    rows = q.offset((page - 1) * per_page).limit(per_page).all()
    items = [
        {
            "name": t.name,
            "channel": t.channel,
            "subject": t.subject,
            "body": t.body,
            "description": t.description,
            "created_at": t.created_at.isoformat() if t.created_at else None,
            "updated_at": t.updated_at.isoformat() if t.updated_at else None,
        }
        for t in rows
    ]
    return {"items": items, "total": total, "page": page, "per_page": per_page}


@router.get("/templates/{template_name}", response_model=TemplateResponse)
def get_template(template_name: str, db: Session = Depends(get_db)):
    """Получить шаблон по имени."""
    t = db.query(CrmTemplateRow).filter_by(name=template_name).first()
    if not t:
        raise HTTPException(404, f"Template '{template_name}' not found")
    return {
        "name": t.name,
        "channel": t.channel,
        "subject": t.subject,
        "body": t.body,
        "description": t.description,
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "updated_at": t.updated_at.isoformat() if t.updated_at else None,
    }


@router.post("/templates", response_model=OkResponse, status_code=201)
def create_template(data: CreateTemplateRequest, db: Session = Depends(get_db)):
    """Создать шаблон. name — уникальный идентификатор."""
    existing = db.query(CrmTemplateRow).filter_by(name=data.name).first()
    if existing:
        raise HTTPException(409, f"Template '{data.name}' already exists")

    unknown = _warn_unknown_placeholders(data.body, data.name)

    t = CrmTemplateRow(
        name=data.name,
        channel=data.channel,
        subject=data.subject,
        body=data.body,
        description=data.description,
    )
    db.add(t)
    db.flush()
    return OkResponse(ok=True, warnings=unknown)


@router.put("/templates/{template_name}", response_model=OkResponse)
def update_template(template_name: str, data: UpdateTemplateRequest, db: Session = Depends(get_db)):
    """Обновить шаблон (полная замена переданных полей)."""
    t = db.query(CrmTemplateRow).filter_by(name=template_name).first()
    if not t:
        raise HTTPException(404, f"Template '{template_name}' not found")

    updates = data.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(t, key, value)

    # FIX MISS-1: Явно обновляем updated_at при PUT.
    # onupdate в SQLAlchemy ORM не работает при setattr + session.commit().
    t.updated_at = datetime.now(timezone.utc)

    # FIX BUG-C1: warnings теперь List[str] (совместимо с OkResponse schema)
    warnings = None
    if data.body is not None:
        unknown = _warn_unknown_placeholders(data.body, template_name)
        if unknown:
            warnings = unknown  # list[str]

    return OkResponse(ok=True, warnings=warnings)


@router.delete("/templates/{template_name}", response_model=OkResponse)
def delete_template(template_name: str, db: Session = Depends(get_db)):
    """Удалить шаблон.

    Нельзя удалить, если он используется в активной кампании (status='running').
    """
    t = db.query(CrmTemplateRow).filter_by(name=template_name).first()
    if not t:
        raise HTTPException(404, f"Template '{template_name}' not found")

    # Проверяем активные кампании
    active = (
        db.query(CrmEmailCampaignRow)
        .filter_by(template_name=template_name, status="running")
        .count()
    )
    if active:
        raise HTTPException(
            409,
            f"Template '{template_name}' is used in {active} active campaign(s). "
            f"Stop campaigns before deleting.",
        )

    db.delete(t)
    db.flush()
    return OkResponse(ok=True)
