"""Stats API: агрегированная статистика по CRM.

FIX H7: Все агрегации заменены на SQL-запросы вместо загрузки всей БД
в память. Ранее base.all() загружал N×(CompanyRow+EnrichedCompanyRow+CrmContactRow)
объектов — при 10K компаний это потребляло сотни мегабайт RAM.
"""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, text as sa_text, String
from sqlalchemy.orm import Session

from granite.api.deps import get_db
from granite.api.schemas import StatsResponse
from granite.database import (
    CompanyRow, EnrichedCompanyRow, CrmContactRow,
)

__all__ = ["router"]

router = APIRouter()


@router.get("/stats", response_model=StatsResponse)
def get_stats(
    db: Session = Depends(get_db),
    city: Optional[str] = None,
):
    """Агрегированная статистика: воронка, сегменты, топ-города, мессенджеры.

    ?city=Москва — фильтрация по городу.

    Все агрегации выполняются на стороне SQL (func.count, GROUP BY) —
    не загружаем данные в память Python.
    """
    # Базовый фильтр по городу (если указан)
    city_filter = [CompanyRow.city == city] if city else []

    # --- Total companies ---
    total = db.query(func.count(CompanyRow.id)).filter(*city_filter).scalar()

    # --- Воронка: count по funnel_stage из crm_contacts ---
    funnel_q = (
        db.query(CrmContactRow.funnel_stage, func.count())
        .join(CompanyRow, CrmContactRow.company_id == CompanyRow.id)
        .filter(*city_filter)
        .group_by(CrmContactRow.funnel_stage)
        .all()
    )
    funnel = {stage: cnt for stage, cnt in funnel_q}

    # --- Сегменты: count по segment из enriched_companies ---
    segment_q = (
        db.query(EnrichedCompanyRow.segment, func.count())
        .join(CompanyRow, EnrichedCompanyRow.id == CompanyRow.id)
        .filter(*city_filter)
        .group_by(EnrichedCompanyRow.segment)
        .all()
    )
    segments = {seg: cnt for seg, cnt in segment_q}

    # --- Топ-10 городов ---
    city_q = (
        db.query(CompanyRow.city, func.count().label("cnt"))
        .filter(CompanyRow.city.isnot(None), CompanyRow.city != "")
        .group_by(CompanyRow.city)
        .order_by(func.count().desc())
        .limit(10)
        .all()
    )
    top_cities = [{"city": c, "count": n} for c, n in city_q]

    # --- Мессенджеры и email ---
    # Telegram: JOIN enriched_companies + json_extract (SQLite 3.38+)
    with_telegram = (
        db.query(func.count(CompanyRow.id))
        .outerjoin(EnrichedCompanyRow, CompanyRow.id == EnrichedCompanyRow.id)
        .filter(
            sa_text("json_extract(enriched_companies.messengers, '$.telegram') IS NOT NULL"),
            sa_text("json_extract(enriched_companies.messengers, '$.telegram') != ''"),
            *city_filter,
        )
        .scalar()
    )

    with_whatsapp = (
        db.query(func.count(CompanyRow.id))
        .outerjoin(EnrichedCompanyRow, CompanyRow.id == EnrichedCompanyRow.id)
        .filter(
            sa_text("json_extract(enriched_companies.messengers, '$.whatsapp') IS NOT NULL"),
            sa_text("json_extract(enriched_companies.messengers, '$.whatsapp') != ''"),
            *city_filter,
        )
        .scalar()
    )

    # Email: проверяем что JSON-массив не пустой
    with_email = (
        db.query(func.count(CompanyRow.id))
        .filter(
            CompanyRow.emails.isnot(None),
            CompanyRow.emails.cast(String) != "[]",
            CompanyRow.emails.cast(String) != "",
            *city_filter,
        )
        .scalar()
    )

    return {
        "total_companies": total or 0,
        "funnel": funnel,
        "segments": segments,
        "top_cities": top_cities,
        "with_telegram": with_telegram or 0,
        "with_whatsapp": with_whatsapp or 0,
        "with_email": with_email or 0,
    }
