"""Campaigns API: email-рассылки по сегментам."""
import json
import os
import threading
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import String, text as sa_text

from granite.api.deps import get_db
from granite.api.schemas import (
    CreateCampaignRequest, UpdateCampaignRequest, OkResponse,
    OkWithIdResponse, CampaignResponse, CampaignDetailResponse,
    CampaignStatsResponse, PaginatedResponse, StaleCampaignsResponse,
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
    """Создать кампанию. Body: {name, template_name, filters?: {city?, segment?, min_score?}}

    FIX HIGH-7: Валидация template_name — проверяем существование шаблона
    до создания кампании, чтобы ошибка обнаружилась сразу, а не при запуске.
    """
    template = db.query(CrmTemplateRow).filter_by(name=data.template_name).first()
    if not template:
        raise HTTPException(404, f"Template '{data.template_name}' not found")

    # Валидация: кампании поддерживают только email-шаблоны
    if template.channel != "email":
        raise HTTPException(
            400,
            f"Template '{data.template_name}' has channel='{template.channel}'. "
            f"Campaigns only support email templates."
        )

    # AUDIT #15: filters хранится как JSON-колонка, Pydantic→dict для ORM.
    # AUDIT #21: data.filters теперь CampaignFilters (Pydantic model), конвертируем в dict.
    campaign = CrmEmailCampaignRow(
        name=data.name,
        template_name=data.template_name,
        filters=data.filters.model_dump(exclude_none=True),
    )
    db.add(campaign)
    db.flush()
    return OkWithIdResponse(ok=True, id=campaign.id)


@router.get("/campaigns", response_model=PaginatedResponse[CampaignResponse])
def list_campaigns(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
):
    """Список кампаний с пагинацией. Сортировка: новые первые."""
    q = db.query(CrmEmailCampaignRow).order_by(CrmEmailCampaignRow.created_at.desc())
    total = q.count()
    rows = q.offset((page - 1) * per_page).limit(per_page).all()
    items = [
        {
            "id": c.id, "name": c.name, "template_name": c.template_name,
            "status": c.status, "total_sent": c.total_sent,
            "total_opened": c.total_opened, "total_replied": c.total_replied,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        }
        for c in rows
    ]
    return {"items": items, "total": total, "page": page, "per_page": per_page}


def _get_campaign_recipients(campaign: CrmEmailCampaignRow, db: Session) -> list:
    """Найти получателей кампании по фильтрам.

    Дедупликация:
    - По campaign_id (не отправлять дважды в одну кампанию).
    - По email-адресу (один info@granit.ru у разных компаний).
    """
    # AUDIT #15: filters теперь JSON-колонка (не Text), читаем напрямую
    filters = campaign.filters if isinstance(campaign.filters, dict) else json.loads(campaign.filters or "{}")

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
            CompanyRow.deleted_at.is_(None),
        )
    )

    if filters.get("city"):
        q = q.filter(CompanyRow.city == filters["city"])
    if filters.get("segment"):
        q = q.filter(EnrichedCompanyRow.segment == filters["segment"])
    if filters.get("min_score"):
        q = q.filter(EnrichedCompanyRow.crm_score >= filters["min_score"])

    # Задача 18: батч-итерация вместо .all() с учётом SQLite.
    # PostgreSQL: yield_per + stream_results для потоковой обработки.
    # SQLite: yield_per работает, stream_results не поддерживается.
    try:
        rows_iter = q.yield_per(100).execution_options(stream_results=True)
    except Exception:
        # SQLite fallback — yield_per без stream_results
        try:
            rows_iter = q.yield_per(100)
        except Exception:
            rows_iter = q.all()

    recipients = []
    seen_emails = set()
    for company, enriched, contact in rows_iter:
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
    """Детали кампании + предпросмотр получателей + статистика."""
    campaign = db.get(CrmEmailCampaignRow, campaign_id)
    if not campaign:
        raise HTTPException(404, "Campaign not found")
    recipients = _get_campaign_recipients(campaign, db)
    open_rate = round(campaign.total_opened / campaign.total_sent * 100, 1) if campaign.total_sent else 0
    return {
        "id": campaign.id, "name": campaign.name,
        "template_name": campaign.template_name,
        "status": campaign.status,
        "filters": campaign.filters if isinstance(campaign.filters, dict) else json.loads(campaign.filters or "{}"),
        "total_sent": campaign.total_sent,
        "total_opened": campaign.total_opened,
        "total_replied": campaign.total_replied,
        "open_rate": open_rate,
        "preview_recipients": len(recipients),
        "started_at": campaign.started_at.isoformat() if campaign.started_at else None,
        "completed_at": campaign.completed_at.isoformat() if campaign.completed_at else None,
    }


@router.patch("/campaigns/{campaign_id}", response_model=OkResponse)
def update_campaign(campaign_id: int, data: UpdateCampaignRequest, db: Session = Depends(get_db)):
    """Обновить кампанию (name, template_name).

    Можно обновить только черновики (draft) и приостановленные (paused).
    При смене template_name — проверяем существование нового шаблона.
    """
    campaign = db.get(CrmEmailCampaignRow, campaign_id)
    if not campaign:
        raise HTTPException(404, "Campaign not found")

    if campaign.status not in ("draft", "paused", "paused_daily_limit"):
        raise HTTPException(
            409,
            f"Cannot update campaign in status '{campaign.status}'. "
            f"Only 'draft', 'paused', and 'paused_daily_limit' campaigns can be updated.",
        )

    updates = data.model_dump(exclude_unset=True)

    if "template_name" in updates:
        template = db.query(CrmTemplateRow).filter_by(name=updates["template_name"]).first()
        if not template:
            raise HTTPException(
                404,
                f"Template '{updates['template_name']}' not found",
            )

    for key, value in updates.items():
        setattr(campaign, key, value)
    campaign.updated_at = datetime.now(timezone.utc)
    db.flush()
    return OkResponse(ok=True)


@router.delete("/campaigns/{campaign_id}", response_model=OkResponse)
def delete_campaign(campaign_id: int, db: Session = Depends(get_db)):
    """Удалить кампанию-черновик.

    Можно удалить только черновики (draft). Запущенные, завершённые
    и приостановленные кампании удалять нельзя — чтобы сохранить
    историю отправок и статистику.
    """
    campaign = db.get(CrmEmailCampaignRow, campaign_id)
    if not campaign:
        raise HTTPException(404, "Campaign not found")

    if campaign.status != "draft":
        raise HTTPException(
            409,
            f"Cannot delete campaign in status '{campaign.status}'. "
            f"Only 'draft' campaigns can be deleted.",
        )

    db.delete(campaign)
    db.flush()
    return OkResponse(ok=True)


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
    # FIX HIGH-3: Проверяем статус кампании в БД (survives uvicorn restart).
    # В дополнение к in-memory lock — защита от concurrent runs через HTTP.
    SessionFactory = request.app.state.Session
    check_session = SessionFactory()
    try:
        db_campaign = check_session.get(CrmEmailCampaignRow, campaign_id)
        if not db_campaign:
            return StreamingResponse(
                iter([f"data: {json.dumps({'error': 'Campaign not found'})}\n\n"]),
                media_type="text/event-stream",
            )
        if db_campaign.status == "running":
            check_session.close()
            return StreamingResponse(
                iter([f"data: {json.dumps({'error': 'Campaign already running'})}\n\n"]),
                media_type="text/event-stream",
            )
    finally:
        check_session.close()

    # FIX BUG-3: Проверяем, не запущена ли уже эта кампания (in-memory lock)
    lock = _get_campaign_lock(campaign_id)
    if not lock.acquire(blocking=False):
        return StreamingResponse(
            iter([f"data: {json.dumps({'error': 'Campaign already running'})}\n\n"]),
            media_type="text/event-stream",
        )

    # Атомарно обновляем статус в БД ПЕРЕД запуском потока
    # AUDIT #12: Атомарный UPDATE с WHERE — защита от TOCTOU race condition.
    # Ранее проверка и обновление были в разных сессиях, что позволяло
    # параллельным запросам оба пройти проверку (в multi-worker deploy).
    pre_session = SessionFactory()
    try:
        result = pre_session.execute(
            sa_text(
                "UPDATE crm_email_campaigns SET status='running', updated_at=:now "
                "WHERE id=:id AND status NOT IN ('running', 'completed')"
            ),
            {"id": campaign_id, "now": datetime.now(timezone.utc)},
        )
        pre_session.commit()
        if result.rowcount == 0:
            pre_session.close()
            return StreamingResponse(
                iter([f"data: {json.dumps({'error': 'Campaign already running or completed'})}\n\n"]),
                media_type="text/event-stream",
            )
    finally:
        pre_session.close()

    def generate():
        import time as _time
        from granite.database import CrmEmailLogRow, CrmEmailCampaignRow, CrmTemplateRow, CrmTouchRow
        from granite.email.sender import EmailSender

        # Задача 2.3: задержка и лимиты из env (для продакшена 45-120с, для тестов 3с)
        SEND_DELAY_MIN = int(os.environ.get("EMAIL_DELAY_MIN", "3"))
        SEND_DELAY_MAX = int(os.environ.get("EMAIL_DELAY_MAX", "3"))
        import random as _random
        EMAIL_DAILY_LIMIT = int(os.environ.get("EMAIL_DAILY_LIMIT", "50"))
        MAX_SENDS_PER_RUN = int(os.environ.get("MAX_SENDS_PER_RUN", "100"))

        # Задача 2.3: функция A/B темы (задача 3 — полная реализация)
        def get_ab_subject(company_id: int, campaign_row, template_row, render_kw: dict) -> str:
            """Детерминированное A/B распределение по company_id."""
            a = campaign_row.subject_a or template_row.render_subject(**render_kw)
            if not campaign_row.subject_b:
                return a
            import hashlib as _hashlib
            hash_val = int(_hashlib.md5(str(company_id).encode()).hexdigest(), 16)
            return a if hash_val % 2 == 0 else campaign_row.subject_b

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
            sent = campaign.total_sent or 0
            total = len(recipients)

            if total > MAX_SENDS_PER_RUN:
                recipients = recipients[:MAX_SENDS_PER_RUN]
                logger.warning(f"Campaign {campaign_id}: truncated to {MAX_SENDS_PER_RUN} (total: {total})")

            # Статус уже установлен в "running" атомарно перед запуском потока.
            # Здесь только фиксируем started_at в рамках текущей сессии.
            campaign.started_at = datetime.now(timezone.utc)
            session.commit()

            yield f"data: {json.dumps({'status': 'started', 'total': len(recipients)})}\n\n"

            for company, enriched, contact, email_to in recipients:
                # Задача 2.3: проверка паузы/отмены
                session.refresh(campaign)
                if campaign.status != "running":
                    logger.info(f"Campaign {campaign_id}: status '{campaign.status}', exiting")
                    return

                # Задача 2.3: проверка дневного лимита
                from sqlalchemy import func
                last_24h = datetime.now(timezone.utc) - timedelta(hours=24)
                sent_today = (
                    session.query(func.count(CrmEmailLogRow.id))
                    .filter(CrmEmailLogRow.sent_at >= last_24h)
                    .scalar()
                )
                if sent_today >= EMAIL_DAILY_LIMIT:
                    campaign.status = "paused_daily_limit"
                    campaign.updated_at = datetime.now(timezone.utc)
                    session.commit()
                    logger.info(f"Campaign {campaign_id}: daily limit reached ({EMAIL_DAILY_LIMIT})")
                    yield f"data: {json.dumps({'status': 'paused_daily_limit', 'reason': 'daily_limit'})}\n\n"
                    return
                city = company.city or ""
                render_kwargs = {
                    "from_name": from_name,
                    "city": city,
                    "company_name": company.name_best or "",
                    "website": company.website or "",
                    "unsubscribe_url": f"{sender.base_url}/api/v1/unsubscribe/{contact.unsubscribe_token}" if contact else "",
                }

                # Задача 3: A/B тема письма
                subject = get_ab_subject(company.id, campaign, template, render_kwargs)

                # Определяем A/B вариант для лога
                subject_a = campaign.subject_a or template.render_subject(**render_kwargs)
                ab_variant = "A" if subject == subject_a else "B"
                rendered = template.render(**render_kwargs)
                if template.body_type == "html":
                    from granite.utils import html_to_plain_text
                    body_text = html_to_plain_text(rendered)
                    tracking_id = sender.send(
                        company_id=company.id,
                        email_to=email_to,
                        subject=subject,
                        body_text=body_text,
                        body_html=rendered,
                        template_name=template.name,
                        template_id=template.id,
                        db_session=session,
                        campaign_id=campaign.id,
                        ab_variant=ab_variant,
                    )
                else:
                    tracking_id = sender.send(
                        company_id=company.id,
                        email_to=email_to,
                        subject=subject,
                        body_text=rendered,
                        template_name=template.name,
                        template_id=template.id,
                        db_session=session,
                        campaign_id=campaign.id,
                        ab_variant=ab_variant,
                    )
                if tracking_id:
                    sent += 1
                    campaign.total_sent = sent

                    # Задача 2.3: commit после КАЖДОГО письма — не теряем данные при краше
                    session.add(CrmTouchRow(
                        company_id=company.id, channel="email", direction="outgoing",
                        subject=subject, body=f"[tracking_id={tracking_id}] [ab={ab_variant}]",
                    ))
                    if contact:
                        from granite.api.stage_transitions import apply_outgoing_touch
                        apply_outgoing_touch(contact, "email")
                    # Commit после каждого письма
                    campaign.updated_at = datetime.now(timezone.utc)
                    session.commit()

                else:
                    # Ошибка отправки — инкремент total_errors
                    campaign.total_errors = (campaign.total_errors or 0) + 1
                    session.commit()

                # Задача 2.3: задержка из env (случайная в диапазоне MIN-MAX)
                delay = _random.randint(SEND_DELAY_MIN, SEND_DELAY_MAX)

                # AUDIT #11: Маскируем email в SSE — не передаём PII (152-ФЗ/GDPR).
                # Заменяем полный email на company_id для клиента.
                yield f"data: {json.dumps({'sent': sent, 'total': len(recipients), 'company_id': company.id})}\n\n"
                _time.sleep(delay)

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


@router.post("/campaigns/stale", response_model=StaleCampaignsResponse)
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


@router.get("/campaigns/{campaign_id}/ab-stats")
def get_ab_stats(campaign_id: int, db: Session = Depends(get_db)):
    """Задача 3: Статистика A/B теста по вариантам.

    Возвращает статистику отправок, открытий и ответов
    для каждого варианта (A/B) темы письма.
    """
    campaign = db.get(CrmEmailCampaignRow, campaign_id)
    if not campaign:
        raise HTTPException(404, "Campaign not found")

    if not campaign.subject_b:
        return {"variants": {}, "winner": None, "note": "Не A/B тест"}

    rows = db.execute(sa_text("""
        SELECT ab_variant,
               COUNT(*) as sent,
               SUM(CASE WHEN opened_at IS NOT NULL THEN 1 ELSE 0 END) as opened,
               SUM(CASE WHEN status = 'replied' THEN 1 ELSE 0 END) as replied
        FROM crm_email_logs
        WHERE campaign_id = :cid AND ab_variant IS NOT NULL
        GROUP BY ab_variant
    """), {"cid": campaign_id}).fetchall()

    result = {}
    for row in rows:
        v = row[0]
        sent_count = row[1]
        result[v] = {
            "subject": campaign.subject_a if v == "A" else campaign.subject_b,
            "sent": sent_count,
            "opened": row[2],
            "replied": row[3],
            "reply_rate": round(row[3] / sent_count * 100, 1) if sent_count else 0,
        }

    return {
        "variants": result,
        "winner": None,
        "note": "Победитель — по количеству ответов (см. раздел 6.4 плана)",
    }
