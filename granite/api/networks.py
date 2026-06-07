"""API для ручной верификации сетей/дублей."""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from loguru import logger

from granite.api.deps import get_db
from granite.api.schemas import (
    NetworkCandidatesResponse, NetworkCandidateGroup, OkResponse,
    ResolveNetworkGroupRequest,
    NetworkListResponse, NetworkSummary, NetworkDetail,
)
from granite.database import Database, EnrichedCompanyRow, CompanyRow
from granite.enrichers.network_detector import NetworkDetector

router = APIRouter()


@router.get("/network-candidates", response_model=NetworkCandidatesResponse)
def list_network_candidates(
    db: Session = Depends(get_db),
    signal_type: str | None = Query(None, pattern="^(email_domain|website|phone)$"),
    min_companies: int = Query(3, ge=2, le=100),
    include_resolved: bool = Query(False),
):
    """Вернуть группы кандидатов на сеть/дубль."""
    detector = NetworkDetector(Database())
    groups = detector.find_candidate_groups(
        db, threshold=min_companies,
        signal_type=signal_type,
        include_resolved=include_resolved,
    )
    return NetworkCandidatesResponse(
        groups=[NetworkCandidateGroup(**g) for g in groups],
        total=len(groups),
    )


@router.post("/network-candidates/resolve", response_model=OkResponse)
def resolve_network_group(
    body: ResolveNetworkGroupRequest,
    db: Session = Depends(get_db),
):
    """Разрешить группу кандидатов: пометить как сеть или как дубли."""
    detector = NetworkDetector(Database())
    groups = detector.find_candidate_groups(db)

    target_group = None
    for g in groups:
        if g["group_id"] == body.group_id:
            target_group = g
            break

    if not target_group:
        raise HTTPException(404, f"Group {body.group_id} not found")

    company_ids = target_group["company_ids"]

    if body.action == "network":
        updated = db.query(EnrichedCompanyRow).filter(
            EnrichedCompanyRow.id.in_(company_ids)
        ).update(
            {EnrichedCompanyRow.is_network: True},
            synchronize_session=False,
        )
        db.query(CompanyRow).filter(
            CompanyRow.id.in_(company_ids),
            CompanyRow.needs_review == True,
        ).update(
            {CompanyRow.needs_review: False},
            synchronize_session=False,
        )
        logger.info(f"network-candidates resolve: {len(company_ids)} companies -> network (group={body.group_id})")
        return {"ok": True, "message": f"Помечено как сеть: {updated} компаний"}

    elif body.action == "duplicate":
        if not body.target_id:
            raise HTTPException(400, "target_id is required for action=duplicate")
        if body.target_id not in company_ids:
            raise HTTPException(400, "target_id must be a member of the group")

        source_ids = [i for i in company_ids if i != body.target_id]
        merged_count = 0

        for source_id in source_ids:
            source = db.get(CompanyRow, source_id)
            if not source or source.deleted_at is not None:
                continue

            target = db.get(CompanyRow, body.target_id)
            if not target:
                continue

            source.merged_into = body.target_id
            source.deleted_at = datetime.now(timezone.utc)
            source.review_reason = f"merged_into_{body.target_id}"

            if source.phones:
                target_phones = set(target.phones or [])
                added = [p for p in source.phones if p not in target_phones]
                if added:
                    target_phones.update(added)
                    target.phones = list(target_phones)

            if source.emails:
                target_emails = set(target.emails or [])
                added = [e for e in source.emails if e not in target_emails]
                if added:
                    target_emails.update(added)
                    target.emails = list(target_emails)

            merged_from = list(target.merged_from or [])
            if source_id not in merged_from:
                merged_from.append(source_id)
            target.merged_from = merged_from

            source_sources = source.sources or []
            target_sources = set(target.sources or [])
            for s in source_sources:
                target_sources.add(s)
            target.sources = sorted(target_sources)

            target.updated_at = datetime.now(timezone.utc)
            merged_count += 1

        target = db.get(CompanyRow, body.target_id)
        if target and target.needs_review:
            target.needs_review = False

        logger.info(
            f"network-candidates resolve: {merged_count} companies merged into "
            f"{body.target_id} (group={body.group_id})"
        )
        return {"ok": True, "message": f"Слито {merged_count} компаний в #{body.target_id}"}


@router.get("/networks", response_model=NetworkListResponse)
def list_networks(
    db: Session = Depends(get_db),
    signal_type: str | None = Query(None, pattern="^(website|phone|email_domain)$"),
    min_companies: int = Query(2, ge=2, le=100),
):
    """Вернуть список всех обнаруженных сетей со статистикой."""
    detector = NetworkDetector(Database())
    groups = detector.list_networks(
        db,
        signal_type=signal_type,
        min_company_count=min_companies,
    )
    return NetworkListResponse(
        items=[NetworkSummary(**g) for g in groups],
        total=len(groups),
    )


@router.get("/networks/{group_id:path}", response_model=NetworkDetail)
def get_network_detail(
    group_id: str,
    db: Session = Depends(get_db),
):
    """Вернуть детальную информацию о сети со списком компаний."""
    detector = NetworkDetector(Database())
    detail = detector.get_network_detail(db, group_id)
    if not detail:
        raise HTTPException(404, f"Network {group_id} not found")
    return NetworkDetail(**detail)


@router.post("/networks/{group_id:path}/unmark", response_model=OkResponse)
def unmark_network(
    group_id: str,
    db: Session = Depends(get_db),
):
    """Снять пометку is_network со всех компаний сети."""
    detector = NetworkDetector(Database())
    detail = detector.get_network_detail(db, group_id)
    if not detail:
        raise HTTPException(404, f"Network {group_id} not found")

    company_ids = [c["id"] for c in detail["companies"]]
    if not company_ids:
        raise HTTPException(400, "Network has no companies")

    updated = db.query(EnrichedCompanyRow).filter(
        EnrichedCompanyRow.id.in_(company_ids)
    ).update(
        {EnrichedCompanyRow.is_network: False},
        synchronize_session=False,
    )
    logger.info(f"networks unmark: {updated} companies unmarked (group={group_id})")
    return {"ok": True, "message": f"Снята пометка сети с {updated} компаний"}
