"""Funnel API: распределение контактов по стадиям воронки."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from granite.api.deps import get_db
from granite.api.schemas import FunnelResponse
from granite.database import CrmContactRow, CompanyRow

__all__ = ["router"]

router = APIRouter()

FUNNEL_ORDER = [
    "new", "email_sent", "email_opened", "tg_sent", "wa_sent",
    "replied", "interested", "not_interested", "unreachable",
]


@router.get("/funnel", response_model=FunnelResponse)
def get_funnel(db: Session = Depends(get_db)):
    """Количество контактов по каждой стадии воронки."""
    # FIX: Используем outerjoin, чтобы учитывать компании без записи в crm_contacts как 'new'
    rows = (
        db.query(
            func.coalesce(CrmContactRow.funnel_stage, "new").label("stage"),
            func.count(CompanyRow.id)
        )
        .outerjoin(CrmContactRow, CompanyRow.id == CrmContactRow.company_id)
        .filter(CompanyRow.deleted_at.is_(None))
        .group_by(func.coalesce(CrmContactRow.funnel_stage, "new"))
        .all()
    )
    counts = {stage: cnt for stage, cnt in rows}
    return {stage: counts.get(stage, 0) for stage in FUNNEL_ORDER}
