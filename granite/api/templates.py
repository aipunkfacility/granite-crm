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
    include_retired: int = Query(0, description="0=hide retired, 1=show all"),
    page: int = Query(1, ge=1),
    per_page: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    """Список шаблонов. Опциональный фильтр по каналу: ?channel=email|tg|wa.

    Задача 12: по умолчанию скрыты retired-шаблоны (используются
    в отправленных письмах, не должны меняться).
    """
    q = db.query(CrmTemplateRow)
    if channel:
        q = q.filter_by(channel=channel)
    # Задача 12: скрываем retired по умолчанию
    if not include_retired:
        q = q.filter(CrmTemplateRow.retired == False)  # noqa: E712
    q = q.order_by(CrmTemplateRow.name)

    total = q.count()
    rows = q.offset((page - 1) * per_page).limit(per_page).all()
    items = [
        {
            "name": t.name,
            "channel": t.channel,
            "subject": t.subject,
            "body": t.body,
            "body_type": t.body_type,
            "description": t.description,
            "retired": bool(t.retired),
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
        "body_type": t.body_type,
        "description": t.description,
        "retired": bool(t.retired),
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
        body_type=data.body_type,
        description=data.description,
    )
    db.add(t)
    db.flush()
    return OkResponse(ok=True, warnings=unknown)


@router.put("/templates/{template_name}", response_model=OkResponse)
def update_template(template_name: str, data: UpdateTemplateRequest, db: Session = Depends(get_db)):
    """Обновить шаблон (полная замена переданных полей).

    Задача 12: retired-шаблоны нельзя обновлять — они используются
    в отправленных письмах, изменение исказит историю.
    """
    t = db.query(CrmTemplateRow).filter_by(name=template_name).first()
    if not t:
        raise HTTPException(404, f"Template '{template_name}' not found")

    # Задача 12: immutable-шаблон нельзя изменить
    if t.retired:
        raise HTTPException(
            409,
            f"Template '{template_name}' is retired (immutable). "
            f"Create a new template instead."
        )

    updates = data.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(t, key, value)

    # Валидация: body_type=html + channel != email → 400
    if data.body_type is not None or data.channel is not None:
        new_body_type = data.body_type if data.body_type is not None else t.body_type
        new_channel = data.channel if data.channel is not None else t.channel
        if new_body_type == "html" and new_channel != "email":
            raise HTTPException(400, "HTML templates are only supported for email channel")

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
    """Удалить шаблон или пометить как retired.

    Задача 12: если шаблон используется в отправленных письмах
    (crm_email_logs), он не удаляется, а помечается retired=True.
    Это гарантирует целостность истории отправок.
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

    # Задача 12: проверяем, есть ли отправленные письма с этим шаблоном
    from granite.database import CrmEmailLogRow
    sent_count = db.query(CrmEmailLogRow).filter_by(template_name=template_name).count()
    if sent_count > 0:
        # Не удаляем — помечаем как retired
        t.retired = True
        t.updated_at = datetime.now(timezone.utc)
        db.flush()
        return OkResponse(
            ok=True,
            message=f"Template '{template_name}' retired (used in {sent_count} sent emails). "
                    f"It will no longer appear in template lists."
        )

    db.delete(t)
    db.flush()
    return OkResponse(ok=True)
