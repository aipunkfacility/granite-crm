"""Companies API: список, карточка, обновление CRM-полей, similar, merge."""
from datetime import datetime, timezone
from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import String, text as sa_text
from sqlalchemy.orm import Session

from granite.api.deps import get_db
from granite.api.schemas import (
    UpdateCompanyRequest, CompanyResponse, OkResponse,
    PaginatedResponse, MergeRequest, SimilarCompaniesResponse,
    ReEnrichPreviewResponse, ReEnrichApplyRequest,
)
from granite.database import (
    CompanyRow, EnrichedCompanyRow, CrmContactRow, CrmEmailLogRow,
)
from granite.utils import (
    extract_domain, normalize_phones, fetch_page, extract_phones, 
    extract_emails, is_seo_title,
)
from loguru import logger
from bs4 import BeautifulSoup

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
        "address": company.address or None,
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


@router.get("/companies", response_model=PaginatedResponse[CompanyResponse])
def list_companies(
    db: Session = Depends(get_db),
    city: Annotated[Optional[List[str]], Query()] = None,
    region: Optional[str] = None,
    segment: Annotated[Optional[List[str]], Query()] = None,
    funnel_stage: Optional[str] = None,
    has_telegram: Optional[int] = None,
    has_whatsapp: Optional[int] = None,
    has_email: Optional[int] = None,
    is_network: Optional[int] = None,
    has_website: Optional[int] = None,
    has_vk: Optional[int] = None,
    has_address: Optional[int] = None,
    min_score: Optional[int] = None,
    max_score: Optional[int] = None,
    needs_review: Optional[int] = None,
    stop_automation: Optional[int] = None,
    cms: Optional[str] = None,
    has_marquiz: Optional[int] = None,
    search: Optional[str] = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    order_by: str = Query("crm_score", pattern="^(crm_score|name_best|city|funnel_stage|segment|is_network)$"),
    order_dir: str = Query("desc", pattern="^(asc|desc)$"),
):
    """Список компаний с join enriched+crm. Пагинация, фильтры, сортировка."""
    q = (
        db.query(CompanyRow, EnrichedCompanyRow, CrmContactRow)
        .outerjoin(EnrichedCompanyRow, CompanyRow.id == EnrichedCompanyRow.id)
        .outerjoin(CrmContactRow, CompanyRow.id == CrmContactRow.company_id)
        .filter(CompanyRow.deleted_at.is_(None))
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
        segment = [s for s in segment if s.strip()]
        if len(segment) == 1:
            q = q.filter(EnrichedCompanyRow.segment == segment[0])
        elif len(segment) > 1:
            q = q.filter(EnrichedCompanyRow.segment.in_(segment))
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
    if has_email == 0:
        q = q.filter(
            CompanyRow.emails.is_(None) | (CompanyRow.emails.cast(String) == "[]")
        )

    # --- is_network (ORM) ---
    if is_network == 1:
        q = q.filter(EnrichedCompanyRow.is_network == True)
    if is_network == 0:
        q = q.filter(
            (EnrichedCompanyRow.is_network.is_(None))
            | (EnrichedCompanyRow.is_network == False)
        )

    # --- has_website (ORM) ---
    if has_website == 1:
        q = q.filter(
            CompanyRow.website.isnot(None),
            CompanyRow.website != "",
        )
    if has_website == 0:
        q = q.filter(
            (CompanyRow.website.is_(None)) | (CompanyRow.website == "")
        )

    # --- has_vk (sa_text — JSON-поле) ---
    if has_vk == 1:
        q = q.filter(sa_text(
            "json_extract(enriched_companies.messengers, '$.vk') IS NOT NULL"
            " AND json_extract(enriched_companies.messengers, '$.vk') != ''"
        ))
    if has_vk == 0:
        q = q.filter(sa_text(
            "json_extract(enriched_companies.messengers, '$.vk') IS NULL"
            " OR json_extract(enriched_companies.messengers, '$.vk') = ''"
        ))

    # --- has_address (ORM) ---
    if has_address == 1:
        q = q.filter(
            CompanyRow.address.isnot(None),
            CompanyRow.address != "",
        )
    if has_address == 0:
        q = q.filter(
            (CompanyRow.address.is_(None)) | (CompanyRow.address == "")
        )

    if min_score is not None:
        q = q.filter(EnrichedCompanyRow.crm_score >= min_score)
    if max_score is not None:
        q = q.filter(EnrichedCompanyRow.crm_score <= max_score)

    # --- needs_review (ORM) ---
    if needs_review == 1:
        q = q.filter(CompanyRow.needs_review == True)
    if needs_review == 0:
        q = q.filter(
            (CompanyRow.needs_review.is_(None))
            | (CompanyRow.needs_review == False)
        )

    # --- stop_automation (ORM) ---
    if stop_automation == 1:
        q = q.filter(CrmContactRow.stop_automation == 1)
    if stop_automation == 0:
        q = q.filter(
            (CrmContactRow.stop_automation.is_(None))
            | (CrmContactRow.stop_automation == 0)
        )

    # --- cms (ORM, точное совпадение) ---
    if cms:
        q = q.filter(EnrichedCompanyRow.cms == cms)

    # --- has_marquiz (ORM) ---
    if has_marquiz == 1:
        q = q.filter(EnrichedCompanyRow.has_marquiz == True)
    if has_marquiz == 0:
        q = q.filter(
            (EnrichedCompanyRow.has_marquiz.is_(None))
            | (EnrichedCompanyRow.has_marquiz == False)
        )

    if search:
        # FIX 3.7: Экранируем LIKE-спецсимволы (% и _) в пользовательском вводе
        escaped = search.replace("%", r"\%").replace("_", r"\_")
        q = q.filter(CompanyRow.name_best.ilike(f"%{escaped}%", escape="\\"))

    order_col = {
        "crm_score": EnrichedCompanyRow.crm_score,
        "name_best": CompanyRow.name_best,
        "city": CompanyRow.city,
        "funnel_stage": CrmContactRow.funnel_stage,
        "segment": EnrichedCompanyRow.segment,
        "is_network": EnrichedCompanyRow.is_network,
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
    company = db.query(CompanyRow).filter(
        CompanyRow.id == company_id,
        CompanyRow.deleted_at.is_(None),
    ).first()
    if not company:
        raise HTTPException(404, "Company not found")
    enriched = db.get(EnrichedCompanyRow, company_id)
    contact = db.get(CrmContactRow, company_id)
    return _build_company_response(company, enriched, contact)


@router.patch("/companies/{company_id}", response_model=OkResponse)
def update_company(company_id: int, data: UpdateCompanyRequest, db: Session = Depends(get_db)):
    """Обновить данные компании и её CRM-поля."""
    company = db.get(CompanyRow, company_id)
    if not company:
        raise HTTPException(404, "Company not found")
        
    contact = db.get(CrmContactRow, company_id)
    if not contact:
        contact = CrmContactRow(company_id=company_id)
        db.add(contact)

    # 1. Обновляем базовые данные (CompanyRow)
    company_updates = data.model_dump(
        include={"name", "phones", "website", "address", "emails", "city"},
        exclude_unset=True
    )
    if "name" in company_updates:
        company.name_best = company_updates["name"]
    for key, value in company_updates.items():
        if key == "name":
            pass  # уже обработано выше
        elif key == "phones" and value:
            # Нормализация телефонов при ручном вводе
            setattr(company, key, normalize_phones(value))
        elif key == "website" and value:
            # FIX: нормализуем URL к корню домена
            from urllib.parse import urlparse
            parsed = urlparse(value if "://" in value else f"https://{value}")
            root = f"{parsed.scheme}://{parsed.netloc}/"
            setattr(company, key, root)
            # Синхронизируем в EnrichedCompanyRow
            enriched_row = db.get(EnrichedCompanyRow, company_id)
            if enriched_row:
                enriched_row.website = root
        else:
            setattr(company, key, value)
            # Если меняем город — синхронизируем регион и в EnrichedCompanyRow тоже
            if key == "city":
                from granite.pipeline.region_resolver import lookup_region
                new_region = lookup_region(value) or ""
                company.region = new_region
                
                enriched_row = db.get(EnrichedCompanyRow, company_id)
                if enriched_row:
                    enriched_row.city = value
                    enriched_row.region = new_region
    
    # 1.1 Обновляем messengers (EnrichedCompanyRow)
    if data.messengers is not None:
        enriched = db.get(EnrichedCompanyRow, company_id)
        if not enriched:
            enriched = EnrichedCompanyRow(
                id=company_id, 
                city=company.city, 
                region=company.region,
                messengers={}
            )
            db.add(enriched)
        
        # Нормализация мессенджеров при ручном вводе
        from granite.utils import normalize_messenger_url
        normalized = {}
        for m_type, m_url in data.messengers.items():
            if m_url:
                normalized[m_type] = normalize_messenger_url(m_url, m_type)
        
        enriched.messengers = normalized
        # Также дублируем в базовую таблицу для целостности (stats/funnel)
        company.messengers = normalized

    if company_updates or data.messengers is not None:
        company.updated_at = datetime.now(timezone.utc)

    # 2. Обновляем CRM-поля (CrmContactRow)
    crm_updates = data.model_dump(
        include={"funnel_stage", "notes", "stop_automation"},
        exclude_unset=True
    )
    # B3: при stop_automation=True — логировать активные email_logs (не блокировать)
    if crm_updates.get("stop_automation") is True:
        active_emails = db.query(CrmEmailLogRow).filter_by(
            company_id=company_id, status="sent"
        ).count()
        if active_emails:
            logger.info(
                f"stop_automation set for company {company_id} "
                f"with {active_emails} sent email(s)"
            )

    for key, value in crm_updates.items():
        setattr(contact, key, value)
    
    if crm_updates:
        contact.updated_at = datetime.now(timezone.utc)
        
    db.commit()
    return {"ok": True}


@router.post("/companies/{company_id}/re-enrich-preview", response_model=ReEnrichPreviewResponse)
def re_enrich_preview(company_id: int, db: Session = Depends(get_db)):
    """Предпросмотр обновления данных с сайта компании (скрапинг)."""
    company = db.get(CompanyRow, company_id)
    if not company or not company.website:
        raise HTTPException(400, "Company website not found")

    # 1. Скрапинг сайта
    try:
        html = fetch_page(company.website, timeout=15)
        if not html:
            raise HTTPException(502, f"Could not fetch {company.website}")
    except Exception as e:
        raise HTTPException(502, f"Error fetching website: {e}")

    soup = BeautifulSoup(html, "html.parser")
    
    # 2. Извлечение данных (используем логику аналогичную скраперам)
    # Имя (из Title/H1)
    new_name = None
    title = soup.find("title")
    if title:
        name_cand = title.get_text(strip=True)
        # Очистка от SEO (базовая)
        for sep in [" | ", " — ", " - "]:
            if sep in name_cand:
                name_cand = name_cand.split(sep)[0].strip()
                break
        if not is_seo_title(name_cand):
            new_name = name_cand
    
    if not new_name:
        h1 = soup.find("h1")
        if h1:
            new_name = h1.get_text(strip=True)

    # Телефоны и Email
    new_phones = normalize_phones(extract_phones(html))
    new_emails = extract_emails(html)

    before = {
        "name": company.name_best,
        "phones": company.phones or [],
        "emails": company.emails or [],
    }
    after = {
        "name": new_name or company.name_best,
        "phones": list(set(before["phones"] + new_phones)),
        "emails": list(set(before["emails"] + new_emails)),
    }
    
    has_changes = (
        after["name"] != before["name"] or 
        len(after["phones"]) > len(before["phones"]) or
        len(after["emails"]) > len(before["emails"])
    )

    return {
        "company_id": company_id,
        "before": before,
        "after": after,
        "has_changes": has_changes
    }


@router.post("/companies/{company_id}/re-enrich-apply", response_model=OkResponse)
def re_enrich_apply(company_id: int, data: ReEnrichApplyRequest, db: Session = Depends(get_db)):
    """Применить данные, полученные после пересканирования."""
    company = db.get(CompanyRow, company_id)
    if not company:
        raise HTTPException(404, "Company not found")

    updates = data.model_dump(exclude_unset=True)
    for key, value in updates.items():
        if key == "name":
            company.name_best = value
        elif key == "messengers":
            # Нормализация мессенджеров
            from granite.utils import normalize_messenger_url
            normalized = {}
            for m_type, m_url in value.items():
                if m_url:
                    normalized[m_type] = normalize_messenger_url(m_url, m_type)
            
            company.messengers = normalized
            # Обновляем также в обогащенной таблице
            enriched = db.get(EnrichedCompanyRow, company_id)
            if enriched:
                enriched.messengers = normalized
        else:
            setattr(company, key, value)

    company.updated_at = datetime.now(timezone.utc)
    db.commit()
    return {"ok": True}


@router.get("/companies/{company_id}/similar", response_model=SimilarCompaniesResponse)
def get_similar_companies(
    company_id: int,
    db: Session = Depends(get_db),
    limit: int = Query(20, ge=1, le=100),
):
    """Найти компании, похожие на данную.

    Критерии similar:
    - Общий номер телефона (любой из списка)
    - Общий домен сайта
    Возвращает список похожих компаний (без текущей).
    """
    company = db.get(CompanyRow, company_id)
    if not company:
        raise HTTPException(404, "Company not found")

    similar_ids = set()

    # 1. Общие телефоны (json_each для SQLite JSON-массивов)
    if company.phones:
        for phone in company.phones:
            phone_matches = db.execute(
                sa_text(
                    "SELECT c.id FROM companies c, json_each(c.phones) AS j "
                    "WHERE j.value = :phone AND c.id != :cid AND c.deleted_at IS NULL"
                ),
                {"phone": phone, "cid": company_id},
            ).fetchall()
            for row in phone_matches:
                similar_ids.add(row[0])

    # 2. Общий домен сайта
    if company.website:
        domain = extract_domain(company.website)
        if domain:
            all_companies = db.query(CompanyRow).filter(
                CompanyRow.id != company_id,
                CompanyRow.website.isnot(None),
                CompanyRow.website != "",
                CompanyRow.deleted_at.is_(None),
            ).all()
            for c in all_companies:
                if c.website and extract_domain(c.website) == domain:
                    similar_ids.add(c.id)

    if not similar_ids:
        return {"company_id": company_id, "similar": [], "total": 0}

    # Загружаем похожие компании с enriched данными
    rows = (
        db.query(CompanyRow, EnrichedCompanyRow)
        .outerjoin(EnrichedCompanyRow, CompanyRow.id == EnrichedCompanyRow.id)
        .filter(CompanyRow.id.in_(similar_ids))
        .limit(limit)
        .all()
    )

    similar = []
    for c, e in rows:
        entry = {
            "id": c.id,
            "name": c.name_best,
            "phones": c.phones or [],
            "website": c.website,
            "city": c.city,
            "segment": e.segment if e else None,
            "crm_score": e.crm_score if e else 0,
        }

        # Определяем причину similar
        reasons = []
        if company.phones and c.phones:
            shared = set(company.phones) & set(c.phones)
            if shared:
                reasons.append("shared_phone")
        if company.website and c.website:
            if extract_domain(company.website) == extract_domain(c.website):
                reasons.append("shared_domain")
        entry["match_reason"] = reasons
        similar.append(entry)

    return {"company_id": company_id, "similar": similar, "total": len(similar)}


@router.patch("/companies/{company_id}/merge", response_model=OkResponse)
def merge_companies(
    company_id: int,
    body: MergeRequest,
    db: Session = Depends(get_db),
):
    """Слить указанные компании в текущую (target).

    Операция:
    1. Source компании помечаются merged_into = target_id
    2. Телефоны и emails из source добавляются в target
    3. CRM-контакты source переносятся на target (если нет)
    4. Raw-записи source помечаются
    """
    target = db.get(CompanyRow, company_id)
    if not target:
        raise HTTPException(404, "Target company not found")

    merged_count = 0
    for source_id in body.source_ids:
        if source_id == company_id:
            continue  # Нельзя слить саму с собой

        source = db.get(CompanyRow, source_id)
        if not source:
            logger.warning(f"merge: source {source_id} not found, skipping")
            continue

        # 1. Помечаем source как merged
        source.merged_into = company_id
        source.deleted_at = datetime.now(timezone.utc)
        source.review_reason = f"merged_into_{company_id}"

        # 2. Добавляем уникальные телефоны в target
        if source.phones:
            target_phones = set(target.phones or [])
            added_phones = [p for p in source.phones if p not in target_phones]
            if added_phones:
                target_phones.update(added_phones)
                target.phones = list(target_phones)

        # 3. Добавляем уникальные emails в target
        if source.emails:
            target_emails = set(target.emails or [])
            added_emails = [e for e in source.emails if e not in target_emails]
            if added_emails:
                target_emails.update(added_emails)
                target.emails = list(target_emails)

        # 4. Добавляем merged_from в target
        merged_from = list(target.merged_from or [])
        if source_id not in merged_from:
            merged_from.append(source_id)
        target.merged_from = merged_from

        # 5. Переносим CRM-контакт source на target
        source_contact = db.get(CrmContactRow, source_id)
        if source_contact:
            target_contact = db.get(CrmContactRow, company_id)
            if target_contact:
                # Суммируем метрики
                target_contact.contact_count = (
                    (target_contact.contact_count or 0)
                    + (source_contact.contact_count or 0)
                )
            # Source-контакт оставляем для истории (не удаляем)

        # 6. Обновляем enriched (если есть)
        source_enriched = db.get(EnrichedCompanyRow, source_id)
        if source_enriched:
            source_enriched.city = target.city  # Переносим в город target

        merged_count += 1
        logger.info(f"merge: {source_id} ({source.name_best}) -> {company_id} ({target.name_best})")

    target.updated_at = datetime.now(timezone.utc)

    return {"ok": True, "message": f"Слито {merged_count} компаний в #{company_id}"}


@router.get("/cities", response_model=PaginatedResponse[str])
def list_cities(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    per_page: int = Query(500, ge=1, le=2000),
):
    """Список уникальных городов для фильтра на фронтенде.

    Возвращает города, в которых есть хотя бы одна компания.
    Сортировка по алфавиту. PaginatedResponse для единообразия API.
    """
    rows = (
        db.query(CompanyRow.city)
        .filter(CompanyRow.city.isnot(None), CompanyRow.city != "", CompanyRow.deleted_at.is_(None))
        .distinct()
        .order_by(CompanyRow.city)
        .all()
    )
    all_cities = [r[0] for r in rows]
    total = len(all_cities)
    start = (page - 1) * per_page
    items = all_cities[start:start + per_page]
    return {"items": items, "total": total, "page": page, "per_page": per_page}


@router.get("/regions", response_model=PaginatedResponse[str])
def list_regions(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    per_page: int = Query(500, ge=1, le=2000),
):
    """Список уникальных регионов для фильтра на фронтенде.

    Возвращает регионы, в которых есть хотя бы одна компания.
    Сортировка по алфавиту. PaginatedResponse для единообразия API.
    """
    rows = (
        db.query(CompanyRow.region)
        .filter(CompanyRow.region.isnot(None), CompanyRow.region != "", CompanyRow.deleted_at.is_(None))
        .distinct()
        .order_by(CompanyRow.region)
        .all()
    )
    all_regions = [r[0] for r in rows]
    total = len(all_regions)
    start = (page - 1) * per_page
    items = all_regions[start:start + per_page]
    return {"items": items, "total": total, "page": page, "per_page": per_page}


@router.get("/cms-types")
def list_cms_types(db: Session = Depends(get_db)):
    """Список уникальных CMS для фильтра на фронтенде."""
    rows = (
        db.query(EnrichedCompanyRow.cms)
        .filter(
            EnrichedCompanyRow.cms.isnot(None),
            EnrichedCompanyRow.cms != "",
            EnrichedCompanyRow.cms != "unknown",
        )
        .distinct()
        .order_by(EnrichedCompanyRow.cms)
        .all()
    )
    return {"items": [r[0] for r in rows]}
