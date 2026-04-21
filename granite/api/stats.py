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


FUNNEL_ORDER = [
    "new", "email_sent", "email_opened", "tg_sent", "wa_sent",
    "replied", "interested", "not_interested", "unreachable",
]


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
    # Базовый фильтр: только активные (не удалённые) компании
    base_filter = [CompanyRow.deleted_at.is_(None)]
    if city:
        base_filter.append(CompanyRow.city == city)

    # --- Total companies ---
    total = db.query(func.count(CompanyRow.id)).filter(*base_filter).scalar()

    # --- Воронка: count по funnel_stage из crm_contacts ---
    # FIX: Используем outerjoin, чтобы учитывать компании без записи в crm_contacts как 'new'
    funnel_q = (
        db.query(
            func.coalesce(CrmContactRow.funnel_stage, "new").label("stage"),
            func.count(CompanyRow.id)
        )
        .outerjoin(CrmContactRow, CompanyRow.id == CrmContactRow.company_id)
        .filter(*base_filter)
        .group_by(func.coalesce(CrmContactRow.funnel_stage, "new"))
        .all()
    )
    # FIX: Заполняем все стадии воронки нулями, если данных нет
    counts = {stage: cnt for stage, cnt in funnel_q}
    funnel = {stage: counts.get(stage, 0) for stage in FUNNEL_ORDER}

    # --- Сегменты: count по segment из enriched_companies ---
    segment_q = (
        db.query(EnrichedCompanyRow.segment, func.count())
        .join(CompanyRow, EnrichedCompanyRow.id == CompanyRow.id)
        .filter(*base_filter)
        .group_by(EnrichedCompanyRow.segment)
        .all()
    )
    segments = {seg or "D": cnt for seg, cnt in segment_q}

    # --- Топ-10 городов ---
    city_q = (
        db.query(CompanyRow.city, func.count().label("cnt"))
        .filter(CompanyRow.city.isnot(None), CompanyRow.city != "", CompanyRow.deleted_at.is_(None))
        .group_by(CompanyRow.city)
        .order_by(func.count().desc())
        .limit(10)
        .all()
    )
    top_cities = [{"city": c, "count": n} for c, n in city_q]

    # --- Мессенджеры и email ---
    # Telegram: проверяем и в CompanyRow (базовый) и в EnrichedCompanyRow (обогащённый)
    # SQLite json_extract() корректно работает с JSON полями.
    with_telegram = (
        db.query(func.count(CompanyRow.id))
        .outerjoin(EnrichedCompanyRow, CompanyRow.id == EnrichedCompanyRow.id)
        .filter(
            (sa_text("json_extract(companies.messengers, '$.telegram') IS NOT NULL") & 
             sa_text("json_extract(companies.messengers, '$.telegram') != ''")) |
            (sa_text("json_extract(enriched_companies.messengers, '$.telegram') IS NOT NULL") & 
             sa_text("json_extract(enriched_companies.messengers, '$.telegram') != ''")),
            *base_filter,
        )
        .scalar()
    )

    with_whatsapp = (
        db.query(func.count(CompanyRow.id))
        .outerjoin(EnrichedCompanyRow, CompanyRow.id == EnrichedCompanyRow.id)
        .filter(
            (sa_text("json_extract(companies.messengers, '$.whatsapp') IS NOT NULL") & 
             sa_text("json_extract(companies.messengers, '$.whatsapp') != ''")) |
            (sa_text("json_extract(enriched_companies.messengers, '$.whatsapp') IS NOT NULL") & 
             sa_text("json_extract(enriched_companies.messengers, '$.whatsapp') != ''")),
            *base_filter,
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
            *base_filter,
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
