"""Фабрики тестовых данных.

Используют list/dict напрямую — Column(JSON) сам сериализует через json.dumps.
"""
from datetime import datetime, timezone

from granite.database import (
    CompanyRow, EnrichedCompanyRow, CrmContactRow, CrmTaskRow, CrmTouchRow,
)

# Поля CompanyRow, которые допустимо передавать в create_company
_COMPANY_ALLOWED_KEYS = frozenset({
    "name_best", "city", "website", "emails", "phones", "messengers",
    "region", "segment", "status",
    # Фильтры:
    "address", "needs_review",
    # Новые для spam/duplicate/admin:
    "deleted_at", "merged_into", "review_reason",
})

# Поля EnrichedCompanyRow, которые пробрасываются из overrides
_ENRICHED_ALLOWED_KEYS = frozenset({
    "crm_score", "segment", "messengers", "cms", "is_network",
    "has_marquiz",
    # Новые:
    "tg_trust",
})


def create_company(db, **overrides) -> int:
    """Создать CompanyRow + EnrichedCompanyRow + CrmContactRow.

    Возвращает company.id. Данные доступны только после db.commit()
    (или db.flush(), но flush не виден через другую сессию).
    """
    company_defaults = {
        "name_best": "Test Company",
        "city": "Москва",
        "website": "https://test.ru",
        "emails": ["info@test.ru"],
        "phones": ["79001234567"],
        "messengers": {},
        "region": "Москва",
    }
    company_overrides = {
        k: v for k, v in overrides.items() if k in _COMPANY_ALLOWED_KEYS
    }
    company_defaults.update(company_overrides)

    company = CompanyRow(**company_defaults)
    db.add(company)
    db.flush()

    enriched_overrides = {
        k: v for k, v in overrides.items() if k in _ENRICHED_ALLOWED_KEYS
    }
    enriched_defaults = {
        "id": company.id,
        "name": company_defaults["name_best"],
        "city": company_defaults["city"],
        "messengers": overrides.get("messengers", {}),
        "crm_score": overrides.get("crm_score", 50),
        "segment": overrides.get("segment", "B"),
        "emails": company_defaults["emails"],
        "phones": company_defaults["phones"],
    }
    enriched_defaults.update(enriched_overrides)

    enriched = EnrichedCompanyRow(**enriched_defaults)
    db.add(enriched)

    contact = CrmContactRow(
        company_id=company.id,
        funnel_stage=overrides.get("funnel_stage", "new"),
        stop_automation=overrides.get("stop_automation", 0),
    )
    db.add(contact)
    db.flush()
    return company.id


def get_touches(db, company_id: int) -> list[CrmTouchRow]:
    """Получить все audit-записи (crm_touches) для компании."""
    return db.query(CrmTouchRow).filter_by(company_id=company_id).all()


def create_task(db, company_id: int, **overrides) -> int:
    """Создать CrmTaskRow. Возвращает task.id."""
    defaults = {
        "company_id": company_id,
        "title": "Test task",
        "status": "pending",
        "task_type": "follow_up",
        "priority": "normal",
    }
    defaults.update(overrides)
    task = CrmTaskRow(**defaults)
    db.add(task)
    db.flush()
    return task.id
