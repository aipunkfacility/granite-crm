"""Campaigns API: email-рассылки по сегментам."""
import json
import os
import threading
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import String

from granite.api.deps import get_db
from granite.api.schemas import (
    CreateCampaignRequest, OkResponse,
    OkWithIdResponse, CampaignResponse, CampaignDetailResponse,
    CampaignStatsResponse, PaginatedResponse,
)
from granite.database import (
    CompanyRow, EnrichedCompanyRow, CrmContactRow,
    CrmEmailLogRow, CrmEmailCampaignRow, CrmTemplateRow,
)
from loguru import logger

__all__ = ["router"]

router = APIRouter()

# FIX BUG-3: Потокобезопасное управление блокировками кампаний.
# defaultdict(threading.Lock) НЕ потокобезопасен: при одновременном доступе
# к несуществующему campaign_id оба потока могут пройти через __missing__
# до записи Lock в dict. Решение: мета-лок + явная проверка.
_campaign_locks_storage: dict[int, threading.Lock] = {}
_campaign_locks_meta = threading.Lock()


def _get_campaign_lock(campaign_id: int) -> threading.Lock:
    """Получить или создать Lock для campaign_id (потокобезопасно)."""
    with _campaign_locks_meta:
        if campaign_id not in _campaign_locks_storage:
            _campaign_locks_storage[campaign_id] = threading.Lock()
        return _campaign_locks_storage[campaign_id]


@router.post("/campaigns", response_model=OkWithIdResponse, status_code=201)
def create_campaign(data: CreateCampaignRequest, db: Session = Depends(get_db)):
    """Создать кампанию. Body: {name, template_name, filters?: {city?, segment?, min_score?}}"""
    campaign = CrmEmailCampaignRow(
        name=data.name,
        template_name=data.template_name,
        filters=json.dumps(data.filters),
    )
    db.add(campaign)
    db.flush()
    return OkWithIdResponse(ok=True, id=campaign.id)


@router.get("/campaigns", response_model=list[CampaignResponse])
def list_campaigns(db: Session = Depends(get_db)):
    campaigns = db.query(CrmEmailCampaignRow).order_by(CrmEmailCampaignRow.created_at.desc()).all()
    return [
        {
            "id": c.id, "name": c.name, "template_name": c.template_name,
            "status": c.status, "total_sent": c.total_sent,
            "total_opened": c.total_opened, "total_replied": c.total_replied,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        }
        for c in campaigns
    ]


def _get_campaign_recipients(campaign: CrmEmailCampaignRow, db: Session) -> list:
    """Найти получателей кампании по фильтрам.

    Дедупликация:
    - По campaign_id (не отправлять дважды в одну кампанию).
    - По email-адресу (один info@granit.ru у разных компаний).
    """
    filters = json.loads(campaign.filters or "{}")

    sent_company_ids = {
        row[0] for row in
        db.query(CrmEmailLogRow.company_id)
        .filter(CrmEmailLogRow.campaign_id == campaign.id)
        .all()
    }

    q = (
        db.query(CompanyRow, EnrichedCompanyRow, CrmContactRow)
        .outerjoin(EnrichedCompanyRow, CompanyRow.id == EnrichedCompanyRow.id)
        .outerjoin(CrmContactRow, CompanyRow.id == CrmContactRow.company_id)
        .filter(
            CompanyRow.emails.isnot(None),
            CompanyRow.emails.cast(String) != "[]",
            CompanyRow.emails.cast(String) != "",
        )
    )

    if filters.get("city"):
        q = q.filter(CompanyRow.city == filters["city"])
    if filters.get("segment"):
        q = q.filter(EnrichedCompanyRow.segment == filters["segment"])
    if filters.get("min_score"):
        q = q.filter(EnrichedCompanyRow.crm_score >= filters["min_score"])

    rows = q.all()
    recipients = []
    seen_emails = set()
    for company, enriched, contact in rows:
        if company.id in sent_company_ids:
            continue
        if contact and contact.stop_automation:
            continue
        emails = company.emails or []
        if not emails:
            continue
        email_to = emails[0].lower().strip()
        if email_to in seen_emails:
            continue
        seen_emails.add(email_to)
        recipients.append((company, enriched, contact, email_to))
    return recipients


@router.get("/campaigns/{campaign_id}", response_model=CampaignDetailResponse)
def get_campaign(campaign_id: int, db: Session = Depends(get_db)):
    """Детали кампании + предпросмотр получателей."""
    campaign = db.get(CrmEmailCampaignRow, campaign_id)
    if not campaign:
        raise HTTPException(404, "Campaign not found")
    recipients = _get_campaign_recipients(campaign, db)
    return {
        "id": campaign.id, "name": campaign.name,
        "template_name": campaign.template_name,
        "status": campaign.status,
        "filters": json.loads(campaign.filters or "{}"),
        "total_sent": campaign.total_sent,
        "total_opened": campaign.total_opened,
        "preview_recipients": len(recipients),
    }


@router.post("/campaigns/{campaign_id}/run")
def run_campaign(campaign_id: int, request: Request):
    """Запустить кампанию с SSE прогресс-баром.

    Возвращает Server-Sent Events: data: {"sent": N, "total": M, "current": "email"}

    FIX 2.4: Используем Session из app.state (общий engine с WAL),
    вместо создания второго Database() с отдельным engine.

    Rate limiting: 3 сек между отправками.
    Batch commits: каждые 10 отправок.
    Interruption: try/finally ставит status="paused" при обрыве SSE.
    """
    # FIX BUG-3: Проверяем, не запущена ли уже эта кампания
    lock = _get_campaign_lock(campaign_id)
    if not lock.acquire(blocking=False):
        return StreamingResponse(
            iter([f"data: {json.dumps({'error': 'Campaign already running'})}\n\n"]),
            media_type="text/event-stream",
        )

    SessionFactory = request.app.state.Session

    def generate():
        import time as _time
        from granite.database import CrmEmailLogRow, CrmEmailCampaignRow, CrmTemplateRow, CrmTouchRow
        from granite.email.sender import EmailSender

        SEND_DELAY = 3
        BATCH_COMMIT = 10
        MAX_SENDS_PER_RUN = 100

        campaign = None
        session = SessionFactory()
        try:
            campaign = session.get(CrmEmailCampaignRow, campaign_id)
            if not campaign:
                yield f"data: {json.dumps({'error': 'Campaign not found'})}\n\n"
                return

            # FIX MISS-10: Запрещаем перезапуск завершённых и активных кампаний
            if campaign.status in ("running", "completed"):
                yield f"data: {json.dumps({'error': f'Cannot restart campaign in status {campaign.status}'})}\n\n"
                return

            template = session.query(CrmTemplateRow).filter_by(name=campaign.template_name).first()
            if not template:
                yield f"data: {json.dumps({'error': 'Template not found'})}\n\n"
                return

            recipients = _get_campaign_recipients(campaign, session)

            from_name = os.environ.get("FROM_NAME", "")
            sender = EmailSender()
            sent = 0
            total = len(recipients)

            if total > MAX_SENDS_PER_RUN:
                recipients = recipients[:MAX_SENDS_PER_RUN]
                logger.warning(f"Campaign {campaign_id}: truncated to {MAX_SENDS_PER_RUN} (total: {total})")

            campaign.status = "running"
            campaign.started_at = datetime.now(timezone.utc)
            session.commit()

            yield f"data: {json.dumps({'status': 'started', 'total': len(recipients)})}\n\n"

            for company, enriched, contact, email_to in recipients:
                city = company.city or ""
                render_kwargs = {
                    "from_name": from_name,
                    "city": city,
                    "company_name": company.name_best or "",
                    "website": company.website or "",
                }
                subject = template.render_subject(**render_kwargs)
                body = template.render(**render_kwargs)
                tracking_id = sender.send(
                    company_id=company.id,
                    email_to=email_to,
                    subject=subject,
                    body_text=body,
                    template_name=template.name,
                    db_session=session,
                    campaign_id=campaign.id,
                )
                if tracking_id:
                    sent += 1
                    campaign.total_sent = sent

                    # FIX K3: Используем apply_outgoing_touch() вместо ручного обновления.
                    # Ранее были пропущены: contact_count, last_contact_at,
                    # last_contact_channel, first_contact_at, updated_at.
                    session.add(CrmTouchRow(
                        company_id=company.id, channel="email", direction="outgoing",
                        subject=subject, body=f"[tracking_id={tracking_id}]",
                    ))
                    if contact:
                        from granite.api.stage_transitions import apply_outgoing_touch
                        apply_outgoing_touch(contact, "email")
                    if sent % BATCH_COMMIT == 0:
                        session.commit()

                yield f"data: {json.dumps({'sent': sent, 'total': len(recipients), 'current': email_to})}\n\n"
                _time.sleep(SEND_DELAY)

            session.commit()

            campaign.status = "completed"
            campaign.completed_at = datetime.now(timezone.utc)
            session.commit()
            yield f"data: {json.dumps({'status': 'completed', 'sent': sent, 'total': len(recipients)})}\n\n"
        except GeneratorExit:
            if campaign:
                try:
                    camp = session.get(CrmEmailCampaignRow, campaign_id)
                    if camp and camp.status == "running":
                        camp.status = "paused"
                        session.commit()
                except Exception:
                    pass
            logger.info(f"Campaign {campaign_id}: SSE disconnected, status set to 'paused'")
        finally:
            session.close()
            lock.release()

    return StreamingResponse(generate(), media_type="text/event-stream")


@router.get("/campaigns/{campaign_id}/stats", response_model=CampaignStatsResponse)
def campaign_stats(campaign_id: int, db: Session = Depends(get_db)):
    """Статистика кампании."""
    campaign = db.get(CrmEmailCampaignRow, campaign_id)
    if not campaign:
        raise HTTPException(404, "Campaign not found")
    return {
        "id": campaign.id, "name": campaign.name, "status": campaign.status,
        "total_sent": campaign.total_sent,
        "total_opened": campaign.total_opened,
        "total_replied": campaign.total_replied,
        "open_rate": round(campaign.total_opened / campaign.total_sent * 100, 1)
                     if campaign.total_sent else 0,
    }


@router.post("/campaigns/stale")
def check_stale_campaigns(db: Session = Depends(get_db)):
    """D1: Сбросить застрявшие кампании (status=running без активности).

    Кампания считается застрявшей, если её последнее обновление (updated_at,
    started_at или created_at) старше STALE_CAMPAIGN_MINUTES (дефолт: 10 мин).
    Застрявшие кампании переводятся в status='paused'.
    """
    stale_minutes = int(os.environ.get("STALE_CAMPAIGN_MINUTES", "10"))
    threshold = datetime.now(timezone.utc) - timedelta(minutes=stale_minutes)

    running = db.query(CrmEmailCampaignRow).filter_by(status="running").all()
    reset = []
    for c in running:
        last_activity = c.updated_at or c.started_at or c.created_at
        if last_activity and last_activity.replace(tzinfo=timezone.utc) < threshold:
            c.status = "paused"
            reset.append({"id": c.id, "name": c.name})

    if reset:
        logger.info(
            f"Campaign watchdog: reset {len(reset)} stale campaigns "
            f"(threshold={stale_minutes}min)"
        )

    return {"reset": reset, "count": len(reset)}
