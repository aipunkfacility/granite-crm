"""Campaigns API: email-рассылки по сегментам."""
import json
import os
import threading
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import or_, String, text as sa_text, func, case

from granite.api.deps import get_db
from granite.api.schemas import (
    CreateCampaignRequest, UpdateCampaignRequest, OkResponse,
    OkWithIdResponse, CampaignResponse, CampaignDetailResponse,
    CampaignStatsResponse, PaginatedResponse, StaleCampaignsResponse,
    CampaignFilters, AddRecipientsRequest, RemoveRecipientsRequest,
)
from granite.database import (
    CompanyRow, EnrichedCompanyRow, CrmContactRow,
    CrmEmailLogRow, CrmEmailCampaignRow, CampaignRecipientRow,
    CompanyEmailRow,
)
from loguru import logger

__all__ = ["router"]

def _get_active_email(company_id: int, db: Session) -> str | None:
    """Get the first active email for a company (primary first, then oldest)."""
    row = (
        db.query(CompanyEmailRow.email)
        .filter(
            CompanyEmailRow.company_id == company_id,
            CompanyEmailRow.is_active == True,
        )
        .order_by(CompanyEmailRow.is_primary.desc(), CompanyEmailRow.id)
        .first()
    )
    return row[0].lower().strip() if row else None


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


def _release_campaign_lock(campaign_id: int):
    """Освободить Lock и очистить storage (P4R-M1: предотвращаем утечку памяти)."""
    with _campaign_locks_meta:
        lock = _campaign_locks_storage.get(campaign_id)
        if lock and not lock.locked():
            del _campaign_locks_storage[campaign_id]


# P4R-M4: Общая функция построения запроса получателей по фильтрам.
# Ранее логика дублировалась между preview_recipients и _get_campaign_recipients.
def _build_recipients_query(filters: dict, db: Session):
    """Построить базовый запрос получателей с фильтрами.

    Общая логика для preview_recipients и _get_campaign_recipients:
    - JOIN CompanyRow + EnrichedCompanyRow + CrmContactRow
    - Фильтр по наличию email и не-удалённым компаниям
    - Фильтр по city/cities, segment, min_score
    - Фильтр stop_automation
    """
    q = (
        db.query(CompanyRow, EnrichedCompanyRow, CrmContactRow)
        .outerjoin(EnrichedCompanyRow, CompanyRow.id == EnrichedCompanyRow.id)
        .outerjoin(CrmContactRow, CompanyRow.id == CrmContactRow.company_id)
        .filter(CompanyRow.deleted_at.is_(None))
    )
    q = q.filter(
        or_(
            db.query(CompanyEmailRow.id)
            .filter(
                CompanyEmailRow.company_id == CompanyRow.id,
                CompanyEmailRow.is_active == True,
            )
            .exists(),
            (CompanyRow.emails.isnot(None))
            & (CompanyRow.emails.cast(String) != "[]"),
        )
    )

    if filters.get("city"):
        q = q.filter(CompanyRow.city == filters["city"])
    elif filters.get("cities"):
        cities_list = filters["cities"]
        if len(cities_list) == 1:
            q = q.filter(CompanyRow.city == cities_list[0])
        elif len(cities_list) > 1:
            q = q.filter(CompanyRow.city.in_(cities_list))
    if filters.get("segment"):
        q = q.filter(EnrichedCompanyRow.segment == filters["segment"])
    if filters.get("min_score"):
        q = q.filter(EnrichedCompanyRow.crm_score >= filters["min_score"])

    # Фильтруем stop_automation
    q = q.filter(
        (CrmContactRow.stop_automation == 0)
        | (CrmContactRow.stop_automation.is_(None))
    )
    return q


@router.post("/campaigns/preview-recipients")
def preview_recipients(data: CampaignFilters, db: Session = Depends(get_db)):
    """Phase 4: Предпросмотр кол-ва получателей по фильтрам (без создания кампании).

    Позволяет wizard показать «Будет отправлено: N компаниям» до создания.
    Возвращает количество и первые 5 компаний-получателей для проверки.

    P4R-M6: Число приблизительное — preview не применяет dedup и validate_recipients.
    """
    filters = data.model_dump(exclude_none=True)

    # P4R-M4: Используем общую функцию _build_recipients_query
    q = _build_recipients_query(filters, db)

    total = q.count()

    # Первые 5 для превью
    sample_rows = q.limit(5).all()
    sample = [
        {
            "id": c.id,
            "name": c.name_best,
            "city": c.city,
            "emails": c.emails or [],
            "segment": e.segment if e else None,
            "crm_score": e.crm_score if e else 0,
        }
        for c, e, crm in sample_rows
    ]

    return {
        "total": total,
        "sample": sample,
        "is_approximate": True,  # P4R-M6: помечаем как приблизительное
    }


@router.post("/campaigns", status_code=201)
def create_campaign(data: CreateCampaignRequest, request: Request, db: Session = Depends(get_db)):
    """Создать кампанию. Body: {name, template_name, filters?, recipient_mode?, company_ids?}

    FIX HIGH-7: Валидация template_name — проверяем существование шаблона
    до создания кампании, чтобы ошибка обнаружилась сразу, а не при запуске.

    Поддержка manual-режима: если recipient_mode='manual' и передан company_ids,
    компании добавляются в campaign_recipients.
    """
    template = request.app.state.template_registry.get(data.template_name)
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
        subject_a=data.subject_a,
        subject_b=data.subject_b,
        recipient_mode=data.recipient_mode,
    )
    db.add(campaign)
    db.flush()

    result = {"ok": True, "id": campaign.id}
    if data.recipient_mode == "filter":
        filters = data.filters.model_dump(exclude_none=True)
        q = _build_recipients_query(filters, db)
        company_ids = [row[0] for row in q.with_entities(CompanyRow.id).all()]
        if company_ids:
            result.update(_add_recipients_to_campaign(campaign, company_ids, db))
    elif data.recipient_mode == "manual" and data.company_ids:
        add_result = _add_recipients_to_campaign(campaign, data.company_ids, db)
        result.update(add_result)

    return result


@router.get("/campaigns", response_model=PaginatedResponse[CampaignResponse])
def list_campaigns(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
):
    """Список кампаний с пагинацией. Сортировка: новые первые."""
    # P4R-M2: total считаем БЕЗ order_by — бессмысленная сортировка для COUNT
    total = db.query(CrmEmailCampaignRow).count()
    rows = (
        db.query(CrmEmailCampaignRow)
        .order_by(CrmEmailCampaignRow.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    items = [
        {
            "id": c.id, "name": c.name, "template_name": c.template_name,
            "status": c.status,
            "recipient_mode": c.recipient_mode or "filter",
            "subject_a": c.subject_a, "subject_b": c.subject_b,
            "total_sent": c.total_sent,
            "total_opened": c.total_opened, "total_replied": c.total_replied,
            "total_errors": c.total_errors or 0,
            "total_recipients": c.total_recipients,  # P4R-M5: включаем в ответ
            "created_at": c.created_at.isoformat() if c.created_at else None,
        }
        for c in rows
    ]
    return {"items": items, "total": total, "page": page, "per_page": per_page}


def _get_campaign_recipients(campaign: CrmEmailCampaignRow, db: Session) -> tuple[list, list]:
    """Найти получателей кампании.

    Поддерживает два режима:
    - filter: получатели по фильтрам (существующее поведение)
    - manual: получатели из campaign_recipients (новое)

    Дедупликация:
    - По campaign_id (не отправлять дважды в одну кампанию).
    - По email-адресу (один info@granit.ru у разных компаний).

    FIX-3: После базовой фильтрации применяется validate_recipients()
    для проверки агрегаторов, невалидных email, SESSION_GAP.

    Returns: tuple[list, list]: (valid_recipients, warnings_list)
    """
    # Manual-режим — получатели из junction-таблицы
    if campaign.recipient_mode == "manual":
        return _get_manual_recipients(campaign, db)

    # Filter-режим — существующее поведение
    # AUDIT #15: filters теперь JSON-колонка (не Text), читаем напрямую
    filters = campaign.filters if isinstance(campaign.filters, dict) else json.loads(campaign.filters or "{}")

    sent_company_ids = {
        row[0] for row in
        db.query(CrmEmailLogRow.company_id)
        .filter(CrmEmailLogRow.campaign_id == campaign.id)
        .all()
    }

    # P4R-M4: Используем общую функцию _build_recipients_query
    q = _build_recipients_query(filters, db)

    # Задача 18: батч-итерация вместо .all() с учётом SQLite.
    # PostgreSQL: yield_per + stream_results для потоковой обработки.
    # SQLite: yield_per работает, stream_results не поддерживается.
    # P4R-L4: Ловим конкретные исключения вместо bare except Exception
    from sqlalchemy.exc import StatementError
    try:
        rows_iter = q.yield_per(100).execution_options(stream_results=True)
    except StatementError:
        # SQLite fallback — yield_per без stream_results
        try:
            rows_iter = q.yield_per(100)
        except StatementError:
            rows_iter = q.all()

    raw_recipients = []
    seen_emails = set()
    for company, enriched, contact in rows_iter:
        if company.id in sent_company_ids:
            continue
        if contact and contact.stop_automation:
            continue
        email_to = _get_active_email(company.id, db)
        if not email_to:
            continue
        if email_to in seen_emails:
            continue
        seen_emails.add(email_to)
        raw_recipients.append((company, enriched, contact, email_to))

    # FIX-3: Валидация получателей (агрегаторы, невалидный email, SESSION_GAP, SEO-мусор)
    # FIX-4: Передаём db_session для проверки признаков блокировки Gmail
    from granite.email.validator import validate_recipients
    valid, warnings = validate_recipients(raw_recipients, db_session=db)
    if warnings:
        logger.warning(
            f"Campaign {campaign.id}: {len(warnings)} recipients filtered by validator: "
            + "; ".join(f"{w.get('name', '?')} ({w.get('reason', '?')})" for w in warnings[:5])
            + (f"... +{len(warnings) - 5} more" if len(warnings) > 5 else "")
        )
    return valid, warnings


def _get_manual_recipients(campaign: CrmEmailCampaignRow, db: Session) -> tuple[list, list]:
    """Получатели из campaign_recipients (manual mode).

    Берёт email напрямую из CampaignRecipientRow, не вызывает _get_active_email().
    SESSION_GAP пропускается для manual-режима (аудит, п.4).
    Агрегаторы и Gmail-блок остаются (техническая защита).
    """
    # 1. Получить (company_id, email) пары из junction-таблицы
    recipient_rows = (
        db.query(
            CampaignRecipientRow.company_id,
            CampaignRecipientRow.email,
        )
        .filter(CampaignRecipientRow.campaign_id == campaign.id)
        .all()
    )

    if not recipient_rows:
        return [], []

    # 2. Группируем email'ы по company_id
    company_emails: dict[int, list[str]] = {}
    for company_id, email in recipient_rows:
        company_emails.setdefault(company_id, []).append(email)

    company_ids = list(company_emails.keys())

    # 3. Один JOIN-запрос вместо N+1
    q = (
        db.query(CompanyRow, EnrichedCompanyRow, CrmContactRow)
        .outerjoin(EnrichedCompanyRow, EnrichedCompanyRow.id == CompanyRow.id)
        .outerjoin(CrmContactRow, CrmContactRow.company_id == CompanyRow.id)
        .filter(CompanyRow.id.in_(company_ids))
        .filter(CompanyRow.deleted_at.is_(None))
    )

    # Batch iteration
    from sqlalchemy.exc import StatementError
    try:
        rows_iter = q.yield_per(100).execution_options(stream_results=True)
    except StatementError:
        try:
            rows_iter = q.yield_per(100)
        except StatementError:
            rows_iter = q.all()

    # 4. Дедуп по уже отправленным — per-email (не per-company)
    sent_emails_in_campaign = {
        row[0].lower() for row in
        db.query(CrmEmailLogRow.email_to)
        .filter(CrmEmailLogRow.campaign_id == campaign.id)
        .all()
    }

    raw_recipients = []
    seen_emails = set()
    for company, enriched, contact in rows_iter:
        if contact and contact.stop_automation:
            continue
        emails = company_emails.get(company.id, [])
        for email_to in emails:
            email_clean = email_to.lower().strip()
            if not email_clean:
                continue
            if email_clean in sent_emails_in_campaign:
                continue
            if email_clean in seen_emails:
                continue
            seen_emails.add(email_clean)
            raw_recipients.append((company, enriched, contact, email_clean))

    # 5. Валидация: агрегаторы + Gmail-блок, БЕЗ SESSION_GAP
    from granite.email.validator import validate_recipients
    valid, warnings = validate_recipients(
        raw_recipients,
        db_session=db,
        skip_session_gap=True,
        skip_sent_count=True,
    )
    if warnings:
        logger.warning(
            f"Campaign {campaign.id} (manual): {len(warnings)} recipients filtered by validator: "
            + "; ".join(f"{w.get('name', '?')} ({w.get('reason', '?')})" for w in warnings[:5])
            + (f"... +{len(warnings) - 5} more" if len(warnings) > 5 else "")
        )
    return valid, warnings


@router.get("/campaigns/{campaign_id}", response_model=CampaignDetailResponse)
def get_campaign(campaign_id: int, request: Request, db: Session = Depends(get_db)):
    """Детали кампании + предпросмотр получателей + статистика.

    FIX-A6: Для completed/paused кампаний — не вызываем тяжёлый
    _get_campaign_recipients(), используем total_recipients из БД.
    """
    campaign = db.get(CrmEmailCampaignRow, campaign_id)
    if not campaign:
        raise HTTPException(404, "Campaign not found")

    # FIX-A6: Оптимизация — для завершённых/приостановленных кампаний
    # берём total_recipients из БД, не пересчитываем получателей.
    if campaign.status in ("completed",) and (campaign.total_recipients or campaign.total_sent):
        preview_recipients_count = campaign.total_recipients or campaign.total_sent or 0
    elif campaign.status in ("paused", "paused_daily_limit") and campaign.total_recipients:
        preview_recipients_count = campaign.total_recipients
    else:
        # Для draft и running — считаем реальных получателей
        recipients, _ = _get_campaign_recipients(campaign, db)
        preview_recipients_count = len(recipients)

    open_rate = round(campaign.total_opened / campaign.total_sent * 100, 1) if campaign.total_sent else 0

    # P4R-M3: Шаблон из TemplateRegistry (JSON — единственный source of truth)
    tmpl = request.app.state.template_registry.get(campaign.template_name)

    # Phase 4: Validator warnings — предупреждения для draft кампаний
    validator_warnings: list[str] = []
    if campaign.status == "draft":
        # Проверяем тему письма
        if not campaign.subject_a and not campaign.subject_b:
            if tmpl and not tmpl.subject:
                validator_warnings.append("Шаблон не содержит тему письма — задайте subject_a вручную")
        # Проверяем получателей
        if preview_recipients_count == 0:
            validator_warnings.append("Нет получателей по заданным фильтрам")
        # Проверяем A/B: только один вариант заполнен
        if campaign.subject_a and not campaign.subject_b:
            pass  # Это нормально — только вариант A
        elif campaign.subject_b and not campaign.subject_a:
            validator_warnings.append("A/B тест: задан только вариант B — укажите также вариант A")

    # recipient_count — только в detail, не в списке (аудит, п.7: N+1)
    recipient_count = None
    if campaign.recipient_mode == "manual":
        recipient_count = db.query(func.count(CampaignRecipientRow.campaign_id)).filter(
            CampaignRecipientRow.campaign_id == campaign.id
        ).scalar() or 0

    return {
        "id": campaign.id, "name": campaign.name,
        "template_name": campaign.template_name,
        "status": campaign.status,
        "recipient_mode": campaign.recipient_mode or "filter",
        "recipient_count": recipient_count,
        "filters": campaign.filters if isinstance(campaign.filters, dict) else json.loads(campaign.filters or "{}"),
        "subject_a": campaign.subject_a,
        "subject_b": campaign.subject_b,
        "total_sent": campaign.total_sent,
        "total_opened": campaign.total_opened,
        "total_replied": campaign.total_replied,
        "total_errors": campaign.total_errors or 0,
        "open_rate": open_rate,
        "preview_recipients": preview_recipients_count,
        "validator_warnings": validator_warnings,
        "started_at": campaign.started_at.isoformat() if campaign.started_at else None,
        "completed_at": campaign.completed_at.isoformat() if campaign.completed_at else None,
    }


@router.patch("/campaigns/{campaign_id}", response_model=OkResponse)
def update_campaign(campaign_id: int, data: UpdateCampaignRequest, request: Request, db: Session = Depends(get_db)):
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
        template = request.app.state.template_registry.get(updates["template_name"])
        if not template:
            raise HTTPException(
                404,
                f"Template '{updates['template_name']}' not found",
            )

    # Phase 4: Поддержка обновления subject_a, subject_b, filters
    # FIX A5: filters теперь CampaignFilters (не dict) — типобезопасно
    if "filters" in updates:
        from granite.api.schemas import CampaignFilters
        cf = updates["filters"]
        if isinstance(cf, CampaignFilters):
            campaign.filters = cf.model_dump(exclude_none=True)
        elif isinstance(cf, dict):
            campaign.filters = CampaignFilters(**cf).model_dump(exclude_none=True)
        updates.pop("filters")

    # Валидируем допустимые поля (защита от произвольного setattr)
    _ALLOWED_UPDATE_FIELDS = {"name", "template_name", "subject_a", "subject_b"}
    for key in list(updates.keys()):
        if key not in _ALLOWED_UPDATE_FIELDS:
            updates.pop(key)

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


def _run_campaign_send_loop(
    campaign_id: int,
    session_factory,
    config: dict,
    template_registry,
    lock: threading.Lock,
):
    """Фоновая отправка писем кампании (без SSE, fire-and-forget).

    Создаёт собственную сессию БД, читает config/template из параметров.
    При ошибке — логирует и переводит кампанию в 'paused'.
    В finally — освобождает lock.
    """
    import time as _time
    from granite.database import CrmEmailLogRow, CrmEmailCampaignRow, CrmTouchRow, CompanyEmailRow
    from granite.email.sender import EmailSender

    _email_cfg = config.get("email", {})
    SEND_DELAY_MIN = int(_email_cfg.get("send_delay_min", 3))
    SEND_DELAY_MAX = int(_email_cfg.get("send_delay_max", 3))
    import random as _random
    EMAIL_DAILY_LIMIT = int(_email_cfg.get("daily_limit", 50))
    MAX_SENDS_PER_RUN = int(_email_cfg.get("max_sends_per_run", 100))

    from granite.email.ab import determine_ab_variant
    from sqlalchemy import func as _func

    campaign = None
    session = None
    try:
        session = session_factory()
        campaign = session.get(CrmEmailCampaignRow, campaign_id)
        if campaign:
            logger.info(f"Campaign {campaign_id} loaded: template_name={campaign.template_name!r}")
        if not campaign:
            logger.error(f"Campaign {campaign_id}: not found in send loop")
            return

        if campaign.status == "completed":
            logger.warning(f"Campaign {campaign_id}: already completed, cannot restart")
            return

        template = template_registry.get(campaign.template_name)
        if not template:
            campaign.status = "paused"
            session.commit()
            logger.error(f"Campaign {campaign_id}: template '{campaign.template_name}' not found — paused")
            return

        recipients, recipient_warnings = _get_campaign_recipients(campaign, session)

        from granite.constants import get_sender_field
        from_name = get_sender_field("from_name")
        whatsapp_number = get_sender_field("whatsapp")
        telegram_link = get_sender_field("telegram")
        sender = EmailSender()
        sent = campaign.total_sent or 0
        total = len(recipients)
        was_truncated = total > MAX_SENDS_PER_RUN

        # Заморозка total_recipients: устанавливается только при первом старте
        # (когда поле ещё 0). После первого запуска поле не меняется.
        if not campaign.total_recipients:
            campaign.total_recipients = total

        if was_truncated:
            recipients = recipients[:MAX_SENDS_PER_RUN]
            logger.warning(f"Campaign {campaign_id}: truncated to {MAX_SENDS_PER_RUN} (total: {total})")

        campaign.started_at = datetime.now(timezone.utc)
        session.commit()
        logger.info(f"Campaign {campaign_id}: started, {len(recipients)} recipients")

        for company, enriched, contact, email_to in recipients:
            session.refresh(campaign)
            if campaign.status != "running":
                logger.info(f"Campaign {campaign_id}: status changed to '{campaign.status}', exiting")
                return

            if not contact:
                logger.warning(
                    f"Campaign {campaign_id}: skipping company {company.id} — "
                    f"no contact (unsubscribe unavailable)"
                )
                campaign.total_errors = (campaign.total_errors or 0) + 1
                session.commit()
                continue

            last_24h = datetime.now(timezone.utc) - timedelta(hours=24)
            sent_today = (
                session.query(_func.count(CrmEmailLogRow.id))
                .filter(CrmEmailLogRow.sent_at >= last_24h)
                .scalar()
            )
            if sent_today >= EMAIL_DAILY_LIMIT:
                campaign.status = "paused_daily_limit"
                campaign.updated_at = datetime.now(timezone.utc)
                session.commit()
                logger.info(f"Campaign {campaign_id}: daily limit reached ({EMAIL_DAILY_LIMIT})")
                return

            city = company.city or ""
            from granite.city_declensions import get_locative
            render_kwargs = {
                "from_name": from_name,
                "whatsapp_number": whatsapp_number,
                "whatsapp_link": get_sender_field("whatsapp_link"),
                "telegram_link": telegram_link,
                "landing_url": get_sender_field("landing"),
                "city": city,
                "city_locative": get_locative(city),
                "company_name": company.name_best or "",
                "website": company.website or "",
                "unsubscribe_url": f"{sender.base_url}/api/v1/unsubscribe/{contact.unsubscribe_token}",
            }

            subject_a = template.render_subject(subject_override=campaign.subject_a, **render_kwargs)
            subject_b = template.render_subject(subject_override=campaign.subject_b, **render_kwargs) if campaign.subject_b else None
            ab_variant, subject = determine_ab_variant(
                company_id=company.id,
                subject_a=subject_a,
                subject_b=subject_b,
            )
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
                    rendered_body=body_text,
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
                    rendered_body=rendered,
                    db_session=session,
                    campaign_id=campaign.id,
                    ab_variant=ab_variant,
                )

            if tracking_id:
                sent += 1
                campaign.total_sent = sent
                session.add(CrmTouchRow(
                    company_id=company.id, channel="email", direction="outgoing",
                    subject=subject, body=f"[tracking_id={tracking_id}] [ab={ab_variant}]",
                ))
                from granite.api.stage_transitions import apply_outgoing_touch
                apply_outgoing_touch(contact, "email")

                # Deactivate the sent email address for this company
                sent_email_row = (
                    session.query(CompanyEmailRow)
                    .filter(
                        CompanyEmailRow.company_id == company.id,
                        CompanyEmailRow.email == email_to,
                        CompanyEmailRow.is_active == True,
                    )
                    .first()
                )
                if sent_email_row:
                    sent_email_row.is_active = False
                    sent_email_row.sent_count = (sent_email_row.sent_count or 0) + 1
                    sent_email_row.last_sent_at = datetime.now(timezone.utc)
                    if sent_email_row.is_primary:
                        sent_email_row.is_primary = False
                        next_active = (
                            session.query(CompanyEmailRow)
                            .filter(
                                CompanyEmailRow.company_id == company.id,
                                CompanyEmailRow.is_active == True,
                                CompanyEmailRow.id != sent_email_row.id,
                            )
                            .order_by(CompanyEmailRow.id)
                            .first()
                        )
                        if next_active:
                            next_active.is_primary = True

                # Cross-company deactivation: same email at other companies
                other_emails = (
                    session.query(CompanyEmailRow)
                    .filter(
                        CompanyEmailRow.email == email_to,
                        CompanyEmailRow.company_id != company.id,
                        CompanyEmailRow.is_active == True,
                    )
                    .all()
                )
                for oe in other_emails:
                    oe.is_active = False
                    if oe.is_primary:
                        oe.is_primary = False
                        next_active = (
                            session.query(CompanyEmailRow)
                            .filter(
                                CompanyEmailRow.company_id == oe.company_id,
                                CompanyEmailRow.is_active == True,
                                CompanyEmailRow.id != oe.id,
                            )
                            .order_by(CompanyEmailRow.id)
                            .first()
                        )
                        if next_active:
                            next_active.is_primary = True

                campaign.updated_at = datetime.now(timezone.utc)
                session.commit()
            else:
                campaign.total_errors = (campaign.total_errors or 0) + 1
                session.commit()

            delay = _random.randint(SEND_DELAY_MIN, SEND_DELAY_MAX)
            _time.sleep(delay)

        if was_truncated:
            campaign.status = "paused"
            session.commit()
            logger.info(f"Campaign {campaign_id}: paused after batch ({sent}/{total} sent, max per run)")
        else:
            campaign.status = "completed"
            campaign.completed_at = datetime.now(timezone.utc)
            session.commit()
            logger.info(f"Campaign {campaign_id}: completed ({sent} sent)")
    except Exception:
        logger.exception(f"Campaign {campaign_id}: error in send loop")
        if campaign:
            try:
                camp = session.get(CrmEmailCampaignRow, campaign_id)
                if camp and camp.status == "running":
                    camp.status = "paused"
                    session.commit()
            except Exception:
                pass
    finally:
        if session:
            session.close()
        lock.release()
        _release_campaign_lock(campaign_id)


@router.post("/campaigns/{campaign_id}/run")
def run_campaign(campaign_id: int, request: Request):
    """Запустить кампанию (fire-and-forget).

    Проверяет валидность и статус, выполняет атомарный UPDATE
    в 'running', запускает фоновый поток отправки и возвращает
    OkResponse. Прогресс — через GET /campaigns/{id}/progress.
    """
    SessionFactory = request.app.state.Session
    check_session = SessionFactory()
    try:
        db_campaign = check_session.get(CrmEmailCampaignRow, campaign_id)
        if not db_campaign:
            raise HTTPException(404, "Campaign not found")
        if db_campaign.status == "running":
            raise HTTPException(409, "Campaign already running")
    finally:
        check_session.close()

    lock = _get_campaign_lock(campaign_id)
    if not lock.acquire(blocking=False):
        raise HTTPException(409, "Campaign already running")

    try:
        pre_session = SessionFactory()
        try:
            result = pre_session.execute(
                sa_text(
                    "UPDATE crm_email_campaigns SET status='running', updated_at=:now "
                    "WHERE id=:id AND status != 'running'"
                ).bindparams(id=campaign_id, now=datetime.now(timezone.utc)),
            )
            pre_session.commit()
            if result.rowcount == 0:
                raise HTTPException(409, "Campaign is already running")
        finally:
            pre_session.close()
    except HTTPException:
        # Lock was acquired but atomic UPDATE failed or campaign can't start.
        # Release the lock so the campaign can be retried.
        lock.release()
        _release_campaign_lock(campaign_id)
        raise

    thread = threading.Thread(
        target=_run_campaign_send_loop,
        args=(
            campaign_id,
            SessionFactory,
            request.app.state.config,
            request.app.state.template_registry,
            lock,
        ),
        daemon=True,
    )
    thread.start()

    return OkResponse(ok=True)


@router.post("/campaigns/{campaign_id}/pause", response_model=OkResponse, response_model_exclude_none=True)
def pause_campaign(campaign_id: int, request: Request):
    """Приостановить running-кампанию.

    Атомарный UPDATE: status='paused' WHERE id=:id AND status='running'.
    Если строка не обновлена (rowcount == 0) — кампания не в статусе running,
    возвращаем 409 Conflict.
    """
    SessionFactory = request.app.state.Session
    session = SessionFactory()
    try:
        campaign = session.get(CrmEmailCampaignRow, campaign_id)
        if not campaign:
            raise HTTPException(404, "Campaign not found")

        result = session.execute(
            sa_text(
                "UPDATE crm_email_campaigns SET status='paused', updated_at=:now "
                "WHERE id=:id AND status='running'"
            ).bindparams(id=campaign_id, now=datetime.now(timezone.utc)),
        )
        session.commit()

        if result.rowcount == 0:
            raise HTTPException(
                409,
                f"Cannot pause campaign in status '{campaign.status}'. "
                f"Only 'running' campaigns can be paused.",
            )

        return OkResponse(ok=True)
    finally:
        session.close()


@router.get("/campaigns/{campaign_id}/progress")
def campaign_progress(campaign_id: int, db: Session = Depends(get_db)):
    """FIX-P2: Прогресс кампании через SSE (без запуска отправки).

    FIX-A3: Использует total_recipients из БД вместо дорогостоящего
    _get_campaign_recipients(). Для completed — total_sent, для draft — 0.

    Возвращает Server-Sent Events с текущим статусом кампании.
    Фронтенд может подключиться к этому эндпоинту после обрыва SSE
    от POST /run — без перезапуска кампании.

    Формат SSE:
        data: {"status": "running", "sent": N, "total": M, "errors": E}
    """
    campaign = db.get(CrmEmailCampaignRow, campaign_id)
    if not campaign:
        raise HTTPException(404, "Campaign not found")

    # FIX-A3: Берём total из сохранённого total_recipients (быстро),
    # fallback — COUNT(*) из crm_email_logs (для кампаний, запущенных до FIX-A5).
    recipients_count = campaign.total_recipients or 0
    if not recipients_count and campaign.status in ("running", "paused", "paused_daily_limit"):
        # Fallback: считаем количество отправленных + оставшихся логов
        sent_count = campaign.total_sent or 0
        if sent_count > 0:
            # Если уже отправляли — total = sent + ещё не отправленные
            # Приблизительная оценка: берём максимум из sent и кол-ва логов
            log_count = db.query(func.count(CrmEmailLogRow.id)).filter(
                CrmEmailLogRow.campaign_id == campaign_id
            ).scalar() or 0
            recipients_count = max(sent_count, log_count)
        else:
            # Последний fallback — тяжёлый запрос (только если нет данных)
            try:
                recipients, _ = _get_campaign_recipients(campaign, db)
                recipients_count = len(recipients)
            except Exception:
                pass

    # Если кампания завершена — используем total_recipients если есть,
    # иначе total_sent (все отправлены)
    if campaign.status == "completed":
        recipients_count = campaign.total_recipients or campaign.total_sent or 0

    def _stream():
        """Отправить одно SSE-событие с текущим прогрессом."""
        payload = {
            "status": campaign.status,
            "sent": campaign.total_sent or 0,
            "total": recipients_count,
            "errors": campaign.total_errors or 0,
            "started_at": campaign.started_at.isoformat() if campaign.started_at else None,
            "completed_at": campaign.completed_at.isoformat() if campaign.completed_at else None,
        }
        yield f"data: {json.dumps(payload)}\n\n"

    return StreamingResponse(_stream(), media_type="text/event-stream")


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
        # FIX A8: Берём МАКСИМАЛЬНЫЙ (самый свежий) timestamp из всех доступных.
        # updated_at теперь всегда заполнен (default=), но для running кампаний
        # важен самый свежий индикатор активности (updated_at обновляется при
        # каждом письме, started_at — при запуске, created_at — при создании).
        candidates = [
            c.updated_at,
            c.started_at,
            c.created_at,
        ]
        last_activity = max(
            (ts.replace(tzinfo=timezone.utc) if ts and ts.tzinfo is None else ts
             for ts in candidates if ts is not None),
            default=None,
        )
        if last_activity and last_activity < threshold:
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

    P4R-L6: Переписано с raw SQL на ORM-запрос.
    """
    campaign = db.get(CrmEmailCampaignRow, campaign_id)
    if not campaign:
        raise HTTPException(404, "Campaign not found")

    if not campaign.subject_b:
        return {"variants": {}, "winner": None, "note": "Не A/B тест"}

    rows = (
        db.query(
            CrmEmailLogRow.ab_variant,
            func.count(CrmEmailLogRow.id).label("sent"),
            func.sum(case((CrmEmailLogRow.opened_at.isnot(None), 1), else_=0)).label("opened"),
            func.sum(case((CrmEmailLogRow.status == "replied", 1), else_=0)).label("replied"),
        )
        .filter(
            CrmEmailLogRow.campaign_id == campaign_id,
            CrmEmailLogRow.ab_variant.isnot(None),
        )
        .group_by(CrmEmailLogRow.ab_variant)
        .all()
    )

    result = {}
    for row in rows:
        v = row.ab_variant
        sent_count = row.sent
        result[v] = {
            "subject": campaign.subject_a if v == "A" else campaign.subject_b,
            "sent": sent_count,
            "opened": row.opened,
            "replied": row.replied,
            "reply_rate": round(row.replied / sent_count * 100, 1) if sent_count else 0,
        }

    return {
        "variants": result,
        "winner": None,
        "note": "Победитель — по количеству ответов (см. раздел 6.4 плана)",
    }


# ============================================================
# Manual campaign recipients — ручной отбор компаний
# ============================================================

_EDITABLE_STATUSES = {"draft", "paused", "paused_daily_limit"}


def _add_recipients_to_campaign(
    campaign: CrmEmailCampaignRow,
    company_ids: list[int],
    db: Session,
) -> dict:
    """Добавить компании в кампанию. Возвращает {added, skipped, skipped_details}.

    Для каждой компании добавляются ВСЕ активные email-адреса
    как отдельные получатели (по одному CampaignRecipientRow на email).

    Проверки:
    - Уже в кампании (такая компания уже есть — хотя бы один её email)
    - Компания существует и не deleted
    - Есть хотя бы один активный email
    - stop_automation
    - email_sent_count > 0 (уже получал письмо)
    - email уже есть в CrmEmailLogRow (от любой компании)
    """
    added = 0
    skipped_details: list[dict] = []

    existing_ids = {
        r[0] for r in
        db.query(CampaignRecipientRow.company_id)
        .filter(CampaignRecipientRow.campaign_id == campaign.id)
        .distinct()
        .all()
    }

    # Batch: email_sent_count + stop_automation для всех контактов
    contact_rows = {}
    stop_automation_ids: set[int] = set()
    for r in db.query(CrmContactRow).filter(CrmContactRow.company_id.in_(company_ids)).all():
        contact_rows[r.company_id] = r.email_sent_count or 0
        if r.stop_automation:
            stop_automation_ids.add(r.company_id)

    # Batch: все активные email-адреса для всех компаний
    company_emails: dict[int, list[str]] = {}
    companies_data = {}
    for row in db.query(CompanyRow).filter(CompanyRow.id.in_(company_ids)).all():
        companies_data[row.id] = row
        emails = [
            e[0] for e in
            db.query(CompanyEmailRow.email)
            .filter(
                CompanyEmailRow.company_id == row.id,
                CompanyEmailRow.is_active == True,
            )
            .all()
        ]
        if emails:
            company_emails[row.id] = emails

    # Batch: какие email-адреса уже получали письмо (любая кампания, любая компания)
    all_emails = {e for emails in company_emails.values() for e in emails}
    already_sent_emails: set[str] = set()
    if all_emails:
        log_rows = db.query(CrmEmailLogRow.email_to).filter(
            CrmEmailLogRow.email_to.in_(list(all_emails)),
            CrmEmailLogRow.status.in_(("sent", "opened", "replied", "bounced")),
        ).all()
        already_sent_emails = {row[0].lower() for row in log_rows}

    # existing_emails: все email, уже добавленные в эту кампанию (для дедупа)
    existing_emails_set: set[str] = set()
    if existing_ids:
        existing_email_rows = db.query(CampaignRecipientRow).filter(
            CampaignRecipientRow.campaign_id == campaign.id
        ).all()
        for r in existing_email_rows:
            existing_emails_set.add(r.email.lower().strip())

    for cid in company_ids:
        if cid in existing_ids:
            skipped_details.append({"company_id": cid, "reason": "уже в кампании"})
            continue

        company = companies_data.get(cid)
        if not company or company.deleted_at:
            skipped_details.append({"company_id": cid, "reason": "компания не найдена или удалена"})
            continue

        emails = company_emails.get(cid)
        if not emails:
            skipped_details.append({"company_id": cid, "reason": "нет активных email"})
            continue

        if cid in stop_automation_ids:
            skipped_details.append({"company_id": cid, "reason": "отписан"})
            continue

        contact_sent = contact_rows.get(cid, 0)
        if contact_sent > 0:
            skipped_details.append({"company_id": cid, "reason": "уже получал письмо"})
            continue

        added_any = False
        for email_to in emails:
            email_clean = email_to.lower().strip()
            if email_clean in existing_emails_set:
                continue
            if email_clean in already_sent_emails:
                continue
            existing_emails_set.add(email_clean)
            db.add(CampaignRecipientRow(
                campaign_id=campaign.id,
                company_id=cid,
                email=email_clean,
            ))
            added_any = True

        if added_any:
            existing_ids.add(cid)
            added += 1
        else:
            skipped_details.append({"company_id": cid, "reason": "все email уже отправлялись"})

    campaign.total_recipients = (
        db.query(func.count(CampaignRecipientRow.campaign_id))
        .filter(CampaignRecipientRow.campaign_id == campaign.id)
        .scalar() or 0
    )
    db.flush()
    return {"added": added, "skipped": len(skipped_details), "skipped_details": skipped_details}


def add_network_to_campaign(
    campaign: CrmEmailCampaignRow,
    network_id: int,
    db: Session,
) -> dict:
    """Добавить уникальные email сети в кампанию.

    Проверки:
    - email отключен тогглом → пропуск
    - email уже отправлялся (CrmEmailLogRow) → пропуск
    - email уже в этой кампании → пропуск
    """
    from granite.database import NetworkRow, NetworkEmailToggleRow, CrmEmailLogRow

    nw = db.get(NetworkRow, network_id)
    if not nw:
        return {"added": 0, "skipped": 0, "skipped_details": [{"reason": "сеть не найдена"}]}

    emails = nw.emails or []
    if not emails:
        return {"added": 0, "skipped": 0, "skipped_details": [{"reason": "нет email в сети"}]}

    # Тогглы
    disabled_emails: set[str] = set()
    for t in db.query(NetworkEmailToggleRow).filter(
        NetworkEmailToggleRow.network_id == network_id,
        NetworkEmailToggleRow.is_disabled,
    ).all():
        disabled_emails.add(t.email.lower())

    # Уже отправленные
    already_sent: set[str] = set()
    if emails:
        logs = db.query(CrmEmailLogRow.email_to).filter(
            CrmEmailLogRow.email_to.in_(emails),
            CrmEmailLogRow.status.in_(("sent", "opened", "replied", "bounced")),
        ).all()
        already_sent = {row[0].lower() for row in logs}

    # Уже в кампании
    existing_emails: set[str] = set()
    existing_rows = db.query(CampaignRecipientRow.email).filter(
        CampaignRecipientRow.campaign_id == campaign.id
    ).all()
    existing_emails = {row[0].lower() for row in existing_rows}

    added = 0
    skipped_details = []

    with db.no_autoflush:
        for email in emails:
            email_clean = email.lower().strip()

            if email_clean in disabled_emails:
                skipped_details.append({"email": email_clean, "reason": "email отключен тогглом"})
                continue
            if email_clean in already_sent:
                skipped_details.append({"email": email_clean, "reason": "email уже отправлялся"})
                continue
            if email_clean in existing_emails:
                skipped_details.append({"email": email_clean, "reason": "email уже в кампании"})
                continue

            # Находим company_id для этого email
            from granite.database import CompanyRow
            company = db.query(CompanyRow).filter(
                CompanyRow.emails.contains(email_clean),
                CompanyRow.deleted_at.is_(None),
            ).first()
            company_id = company.id if company else 0

            db.add(CampaignRecipientRow(
                campaign_id=campaign.id,
                company_id=company_id,
                email=email_clean,
                network_id=network_id,
            ))
            existing_emails.add(email_clean)
            added += 1

    campaign.total_recipients = (
        db.query(func.count(CampaignRecipientRow.campaign_id))
        .filter(CampaignRecipientRow.campaign_id == campaign.id)
        .scalar() or 0
    )
    db.flush()
    return {"added": added, "skipped": len(skipped_details), "skipped_details": skipped_details}


class AddNetworkRequest(BaseModel):
    network_id: int


@router.post("/campaigns/{campaign_id}/add-network")
def add_network_recipients(
    campaign_id: int,
    body: AddNetworkRequest,
    db: Session = Depends(get_db),
):
    """Добавить уникальные email сети в кампанию."""
    campaign = db.get(CrmEmailCampaignRow, campaign_id)
    if not campaign:
        raise HTTPException(404, "Campaign not found")
    if campaign.status not in _EDITABLE_STATUSES:
        raise HTTPException(400, f"Campaign status '{campaign.status}' is not editable")

    result = add_network_to_campaign(campaign, body.network_id, db)
    return {
        "ok": True,
        "added": result["added"],
        "skipped": result["skipped"],
        "skipped_details": result["skipped_details"],
    }


@router.post("/campaigns/{campaign_id}/recipients")
def add_recipients(
    campaign_id: int,
    data: AddRecipientsRequest,
    db: Session = Depends(get_db),
):
    """Добавить компании в кампанию (manual mode).

    Если кампания в filter-режиме — требуется force=true для переключения на manual.
    """
    campaign = db.get(CrmEmailCampaignRow, campaign_id)
    if not campaign:
        raise HTTPException(404, "Campaign not found")

    if campaign.status not in _EDITABLE_STATUSES:
        raise HTTPException(
            409,
            f"Cannot modify recipients for campaign in status '{campaign.status}'. "
            f"Only {', '.join(sorted(_EDITABLE_STATUSES))} campaigns can be modified.",
        )

    # Аудит, п.2: автопереключение filter→manual убрано
    if campaign.recipient_mode == "filter":
        if not data.force:
            raise HTTPException(
                409,
                "Кампания в режиме фильтров. Передайте force=true для переключения "
                "в ручной режим или создайте новую кампанию с recipient_mode='manual'.",
            )
        campaign.recipient_mode = "manual"
        db.flush()

    result = _add_recipients_to_campaign(campaign, data.company_ids, db)
    return {"ok": True, **result}


@router.post("/campaigns/{campaign_id}/recipients/remove")
def remove_recipients(
    campaign_id: int,
    data: RemoveRecipientsRequest,
    db: Session = Depends(get_db),
):
    """Удалить компании из кампании (POST /remove — аудит, п.6: DELETE с body нестандартен)."""
    campaign = db.get(CrmEmailCampaignRow, campaign_id)
    if not campaign:
        raise HTTPException(404, "Campaign not found")

    if campaign.status not in _EDITABLE_STATUSES:
        raise HTTPException(
            409,
            f"Cannot modify recipients for campaign in status '{campaign.status}'.",
        )

    removed = (
        db.query(CampaignRecipientRow)
        .filter(
            CampaignRecipientRow.campaign_id == campaign.id,
            CampaignRecipientRow.company_id.in_(data.company_ids),
        )
        .delete(synchronize_session="fetch")
    )
    campaign.total_recipients = (
        db.query(func.count(CampaignRecipientRow.campaign_id))
        .filter(CampaignRecipientRow.campaign_id == campaign.id)
        .scalar() or 0
    )
    db.flush()

    return {"ok": True, "removed": removed}


@router.get("/campaigns/{campaign_id}/recipients")
def list_recipients(
    campaign_id: int,
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
):
    """Список получателей в кампании (manual mode). Одна строка на email. Пагинированный."""
    campaign = db.get(CrmEmailCampaignRow, campaign_id)
    if not campaign:
        raise HTTPException(404, "Campaign not found")

    latest_status_subq = (
        db.query(CrmEmailLogRow.status)
        .filter(
            CrmEmailLogRow.campaign_id == campaign_id,
            CrmEmailLogRow.company_id == CompanyRow.id,
            CrmEmailLogRow.email_to == CampaignRecipientRow.email,
        )
        .order_by(CrmEmailLogRow.sent_at.desc().nullslast())
        .limit(1)
        .correlate(CompanyRow, CampaignRecipientRow)
        .scalar_subquery()
    )

    q = (
        db.query(CompanyRow, EnrichedCompanyRow, latest_status_subq, CampaignRecipientRow.email)
        .join(CampaignRecipientRow, CampaignRecipientRow.company_id == CompanyRow.id)
        .outerjoin(EnrichedCompanyRow, EnrichedCompanyRow.id == CompanyRow.id)
        .filter(CampaignRecipientRow.campaign_id == campaign_id)
    )

    total = q.count()

    rows = (
        q.order_by(CampaignRecipientRow.added_at.desc(), CampaignRecipientRow.email)
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )

    items = [
        {
            "id": c.id,
            "name": c.name_best,
            "city": c.city,
            "email": email,
            "emails": c.emails or [],
            "segment": e.segment if e else None,
            "crm_score": e.crm_score if e else 0,
            "send_status": status,
            "email": email,
        }
        for c, e, status, email in rows
    ]

    return {"items": items, "total": total, "page": page, "per_page": per_page}
