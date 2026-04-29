"""Templates API: чтение шаблонов из TemplateRegistry (JSON — source of truth).

POST/PUT/DELETE удалены — шаблоны редактируются напрямую в data/email_templates.json.
Добавлен POST /templates/reload для hot reload без рестарта сервера.
"""
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from typing import Optional

from granite.api.schemas import OkResponse, TemplateResponse, PaginatedResponse
from loguru import logger

__all__ = ["router"]

router = APIRouter()


@router.get("/templates", response_model=PaginatedResponse[TemplateResponse])
def list_templates(
    request: Request,
    channel: Optional[str] = Query(None, pattern="^(email|tg|wa)$"),
    page: int = Query(1, ge=1),
    per_page: int = Query(100, ge=1, le=500),
):
    """Список шаблонов из TemplateRegistry. Опциональный фильтр по каналу: ?channel=email|tg|wa."""
    registry = request.app.state.template_registry
    templates = registry.list(channel=channel)

    total = len(templates)
    start = (page - 1) * per_page
    end = start + per_page
    page_templates = templates[start:end]

    items = [
        {
            "name": t.name,
            "channel": t.channel,
            "subject": t.subject,
            "body": t.body,
            "body_type": t.body_type,
            "description": t.description,
        }
        for t in page_templates
    ]
    return {"items": items, "total": total, "page": page, "per_page": per_page}


@router.get("/templates/{template_name}", response_model=TemplateResponse)
def get_template(template_name: str, request: Request):
    """Получить шаблон по имени из TemplateRegistry."""
    registry = request.app.state.template_registry
    t = registry.get(template_name)
    if not t:
        raise HTTPException(404, f"Template '{template_name}' not found")
    return {
        "name": t.name,
        "channel": t.channel,
        "subject": t.subject,
        "body": t.body,
        "body_type": t.body_type,
        "description": t.description,
    }


@router.post("/templates/reload", response_model=OkResponse)
def reload_templates(request: Request):
    """Перезагрузить шаблоны из JSON без рестарта сервера.

    Полезно после ручного редактирования data/email_templates.json.
    """
    registry = request.app.state.template_registry
    try:
        count = registry.reload()
        return OkResponse(ok=True, message=f"Reloaded {count} templates from {registry.json_path}")
    except Exception as e:
        raise HTTPException(500, f"Failed to reload templates: {e}")
