"""Stats API: агрегированная статистика по CRM."""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, text as sa_text
from sqlalchemy.orm import Session

from granite.api.deps import get_db
from granite.database import (
    CompanyRow, EnrichedCompanyRow, CrmContactRow,
)

__all__ = ["router"]

router = APIRouter()


@router.get("/stats")
def get_stats(
    db: Session = Depends(get_db),
    city: Optional[str] = None,
):
    """Агрегированная статистика: воронка, сегменты, топ-города, мессенджеры.

    ?city=Москва — фильтрация по городу.
    """
    # --- Базовый запрос: companies + enriched + crm_contacts ---
    base = (
        db.query(CompanyRow, EnrichedCompanyRow, CrmContactRow)
        .outerjoin(EnrichedCompanyRow, CompanyRow.id == EnrichedCompanyRow.id)
        .outerjoin(CrmContactRow, CompanyRow.id == CrmContactRow.company_id)
    )
    if city:
        base = base.filter(CompanyRow.city == city)

    rows = base.all()

    total = len(rows)

    # --- Воронка ---
    funnel = {}
    for _, _, crm in rows:
        stage = crm.funnel_stage if crm else "new"
        funnel[stage] = funnel.get(stage, 0) + 1

    # --- Сегменты ---
    segments = {}
    for _, enriched, _ in rows:
        seg = enriched.segment if enriched else "D"
        segments[seg] = segments.get(seg, 0) + 1

    # --- Топ-10 городов ---
    city_counts: dict[str, int] = {}
    for company, _, _ in rows:
        c = company.city
        if c:
            city_counts[c] = city_counts.get(c, 0) + 1
    top_cities = sorted(city_counts.items(), key=lambda x: -x[1])[:10]

    # --- Мессенджеры ---
    with_telegram = 0
    with_whatsapp = 0
    with_email = 0
    for _, enriched, _ in rows:
        messengers = enriched.messengers or {} if enriched else {}
        if messengers.get("telegram"):
            with_telegram += 1
        if messengers.get("whatsapp"):
            with_whatsapp += 1
    for company, _, _ in rows:
        emails = company.emails or []
        if emails:
            with_email += 1

    return {
        "total_companies": total,
        "funnel": funnel,
        "segments": segments,
        "top_cities": [{"city": c, "count": n} for c, n in top_cities],
        "with_telegram": with_telegram,
        "with_whatsapp": with_whatsapp,
        "with_email": with_email,
    }
