"""Companies API: список, карточка, обновление CRM-полей."""
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import String, text as sa_text
from sqlalchemy.orm import Session

from granite.api.deps import get_db
from granite.api.schemas import (
    UpdateCompanyRequest, CompanyResponse, OkResponse,
    PaginatedResponse,
)
from granite.database import (
    CompanyRow, EnrichedCompanyRow, CrmContactRow, CrmEmailLogRow,
)
from loguru import logger

__all__ = ["router"]

router = APIRouter()


def _build_company_response(company: CompanyRow, enriched: EnrichedCompanyRow | None,
                            contact: CrmContactRow | None) -> dict:
    """Собрать полный ответ по компании."""
    messengers = enriched.messengers or {} if enriched else {}
    return {
        "id": company.id,
        "name": company.name_best,
        "phones": company.phones or [],
        "website": company.website,
        "emails": company.emails or [],
        "city": company.city,
        "region": getattr(company, "region", ""),
        "messengers": messengers,
        "telegram": messengers.get("telegram"),
        "whatsapp": messengers.get("whatsapp"),
        "vk": messengers.get("vk"),
        "segment": enriched.segment if enriched else None,
        "crm_score": enriched.crm_score if enriched else 0,
        "cms": enriched.cms if enriched else None,
        "has_marquiz": enriched.has_marquiz if enriched else False,
        "is_network": enriched.is_network if enriched else False,
        "tg_trust": enriched.tg_trust if enriched else {},
        "funnel_stage": contact.funnel_stage if contact else "new",
        "email_sent_count": contact.email_sent_count if contact else 0,
        "email_opened_count": contact.email_opened_count if contact else 0,
        "tg_sent_count": contact.tg_sent_count if contact else 0,
        "wa_sent_count": contact.wa_sent_count if contact else 0,
        "last_contact_at": contact.last_contact_at.isoformat() if contact and contact.last_contact_at else None,
        "notes": contact.notes if contact else "",
        "stop_automation": bool(contact.stop_automation) if contact else False,
    }


@router.get("/companies", response_model=PaginatedResponse)
def list_companies(
    db: Session = Depends(get_db),
    city: Optional[List[str]] = Query(None),
    region: Optional[str] = None,
    segment: Optional[str] = None,
    funnel_stage: Optional[str] = None,
    has_telegram: Optional[int] = None,
    has_whatsapp: Optional[int] = None,
    has_email: Optional[int] = None,
    min_score: Optional[int] = None,
    search: Optional[str] = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    order_by: str = Query("crm_score", pattern="^(crm_score|name_best|city|funnel_stage)$"),
    order_dir: str = Query("desc", pattern="^(asc|desc)$"),
):
    """Список компаний с join enriched+crm. Пагинация, фильтры, сортировка."""
    q = (
        db.query(CompanyRow, EnrichedCompanyRow, CrmContactRow)
        .outerjoin(EnrichedCompanyRow, CompanyRow.id == EnrichedCompanyRow.id)
        .outerjoin(CrmContactRow, CompanyRow.id == CrmContactRow.company_id)
    )

    if city:
        city = [c for c in city if c.strip()]
        if len(city) == 1:
            q = q.filter(CompanyRow.city == city[0])
        elif len(city) > 1:
            q = q.filter(CompanyRow.city.in_(city))
    if region:
        q = q.filter(CompanyRow.region == region)
    if segment:
        q = q.filter(EnrichedCompanyRow.segment == segment)
    if funnel_stage:
        q = q.filter(CrmContactRow.funnel_stage == funnel_stage)

    # JSON-фильтры через json_extract (надёжный подход для SQLite 3.38+)
    if has_telegram == 1:
        q = q.filter(sa_text(
            "json_extract(enriched_companies.messengers, '$.telegram') IS NOT NULL"
            " AND json_extract(enriched_companies.messengers, '$.telegram') != ''"
        ))
    if has_telegram == 0:
        q = q.filter(sa_text(
            "json_extract(enriched_companies.messengers, '$.telegram') IS NULL"
            " OR json_extract(enriched_companies.messengers, '$.telegram') = ''"
        ))
    if has_whatsapp == 1:
        q = q.filter(sa_text(
            "json_extract(enriched_companies.messengers, '$.whatsapp') IS NOT NULL"
            " AND json_extract(enriched_companies.messengers, '$.whatsapp') != ''"
        ))
    if has_whatsapp == 0:
        q = q.filter(sa_text(
            "json_extract(enriched_companies.messengers, '$.whatsapp') IS NULL"
            " OR json_extract(enriched_companies.messengers, '$.whatsapp') = ''"
        ))

    if has_email == 1:
        q = q.filter(
            CompanyRow.emails.isnot(None),
            CompanyRow.emails.cast(String) != "[]",
        )
    if min_score is not None:
        q = q.filter(EnrichedCompanyRow.crm_score >= min_score)
    if search:
        # FIX 3.7: Экранируем LIKE-спецсимволы (% и _) в пользовательском вводе
        escaped = search.replace("%", r"\%").replace("_", r"\_")
        q = q.filter(CompanyRow.name_best.ilike(f"%{escaped}%", escape="\\"))

    order_col = {
        "crm_score": EnrichedCompanyRow.crm_score,
        "name_best": CompanyRow.name_best,
        "city": CompanyRow.city,
        "funnel_stage": CrmContactRow.funnel_stage,
    }[order_by]
    if order_dir == "desc":
        q = q.order_by(order_col.desc().nullslast())
    else:
        q = q.order_by(order_col.asc().nullsfirst())

    total = q.count()
    rows = q.offset((page - 1) * per_page).limit(per_page).all()

    items = [_build_company_response(c, e, crm) for c, e, crm in rows]
    return {"items": items, "total": total, "page": page, "per_page": per_page}


@router.get("/companies/{company_id}", response_model=CompanyResponse)
def get_company(company_id: int, db: Session = Depends(get_db)):
    """Карточка компании."""
    company = db.get(CompanyRow, company_id)
    if not company:
        raise HTTPException(404, "Company not found")
    enriched = db.get(EnrichedCompanyRow, company_id)
    contact = db.get(CrmContactRow, company_id)
    return _build_company_response(company, enriched, contact)


@router.patch("/companies/{company_id}", response_model=OkResponse)
def update_company(company_id: int, data: UpdateCompanyRequest, db: Session = Depends(get_db)):
    """Обновить CRM-поля компании (funnel_stage, notes, stop_automation)."""
    contact = db.get(CrmContactRow, company_id)
    if not contact:
        contact = CrmContactRow(company_id=company_id)
        db.add(contact)

    # B3: при stop_automation=True — логировать активные email_logs (не блокировать)
    if data.stop_automation is True:
        active_emails = db.query(CrmEmailLogRow).filter_by(
            company_id=company_id, status="sent"
        ).count()
        if active_emails:
            logger.info(
                f"stop_automation set for company {company_id} "
                f"with {active_emails} sent email(s)"
            )

    updates = data.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(contact, key, value)
    contact.updated_at = datetime.now(timezone.utc)
    return {"ok": True}
