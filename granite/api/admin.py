"""Admin API: login, batch operations."""
import hashlib
import hmac
import os
import time
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from loguru import logger

from granite.api.deps import get_db
from granite.database import (
    CompanyRow, EnrichedCompanyRow, CrmContactRow, CrmTouchRow,
)

__all__ = ["router"]

router = APIRouter()

# HMAC token TTL (30 minutes)
_TOKEN_TTL = 30 * 60


class AdminLoginRequest(BaseModel):
    password: str


class BatchApproveRequest(BaseModel):
    company_ids: List[int] = Field(..., min_length=1)


class BatchSpamRequest(BaseModel):
    company_ids: List[int] = Field(..., min_length=1)
    reason: str = Field("aggregator", pattern="^(aggregator|closed|wrong_category|duplicate_contact|other)$")


def _generate_token(password: str) -> str:
    """Сгенерировать HMAC-токен с TTL."""
    expires_at = int(time.time()) + _TOKEN_TTL
    payload = f"{expires_at}:{password}"
    sig = hmac.new(password.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{expires_at}:{sig}"


def _verify_token(token: str, password: str) -> bool:
    """Проверить HMAC-токен."""
    try:
        parts = token.split(":", 1)
        if len(parts) != 2:
            return False
        expires_at = int(parts[0])
        if time.time() > expires_at:
            return False
        payload = f"{expires_at}:{password}"
        expected_sig = hmac.new(password.encode(), payload.encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(parts[1], expected_sig)
    except (ValueError, IndexError):
        return False


def _check_admin(request: Request) -> None:
    """Проверить X-Admin-Token из заголовка запроса."""
    admin_password = os.environ.get("GRANITE_ADMIN_PASSWORD", "")
    if not admin_password:
        raise HTTPException(403, "Admin mode not configured")
    token = request.headers.get("X-Admin-Token", "")
    if not token or not _verify_token(token, admin_password):
        raise HTTPException(401, "Invalid or expired admin token")


@router.post("/admin/login")
def admin_login(body: AdminLoginRequest):
    """Получить HMAC-токен для batch-операций."""
    admin_password = os.environ.get("GRANITE_ADMIN_PASSWORD", "")
    if not admin_password:
        raise HTTPException(403, "Admin mode not configured (set GRANITE_ADMIN_PASSWORD)")
    if not hmac.compare_digest(body.password, admin_password):
        raise HTTPException(401, "Wrong password")
    token = _generate_token(admin_password)
    return {"token": token, "expires_in": _TOKEN_TTL}


@router.post("/companies/batch/approve")
def batch_approve(
    request: Request,
    body: BatchApproveRequest,
    db: Session = Depends(get_db),
):
    """Batch-approve: очистить needs_review для списка компаний."""
    _check_admin(request)

    processed = 0
    for cid in body.company_ids:
        company = db.get(CompanyRow, cid)
        if not company or company.deleted_at is not None:
            continue
        company.needs_review = False
        company.review_reason = ""
        company.updated_at = datetime.now(timezone.utc)
        processed += 1

    db.commit()
    logger.info(f"batch-approve: {processed}/{len(body.company_ids)} companies")
    return {"ok": True, "processed": processed}


@router.post("/companies/batch/spam")
def batch_spam(
    request: Request,
    body: BatchSpamRequest,
    db: Session = Depends(get_db),
):
    """Batch-spam: пометить список компаний как спам."""
    _check_admin(request)

    processed = 0
    for cid in body.company_ids:
        company = db.get(CompanyRow, cid)
        if not company or company.deleted_at is not None:
            continue
        prev_segment = company.segment or "unknown"
        company.segment = "spam"
        company.status = "spam"
        company.deleted_at = datetime.now(timezone.utc)
        company.review_reason = f"mark-spam:{body.reason}:prev_segment={prev_segment}"
        company.needs_review = False
        company.updated_at = datetime.now(timezone.utc)

        enriched = db.get(EnrichedCompanyRow, cid)
        if enriched:
            enriched.segment = "spam"

        contact = db.get(CrmContactRow, cid)
        if contact:
            contact.stop_automation = 1
            contact.updated_at = datetime.now(timezone.utc)

        processed += 1

    db.commit()
    logger.info(f"batch-spam: {processed}/{len(body.company_ids)} companies, reason={body.reason}")
    return {"ok": True, "processed": processed}
