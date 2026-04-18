"""Фабрики тестовых данных.

Используют list/dict напрямую — Column(JSON) сам сериализует через json.dumps.
"""
from granite.database import CompanyRow, EnrichedCompanyRow, CrmContactRow, CrmTaskRow

# Поля, которые допустимо передавать в create_company
_COMPANY_ALLOWED_KEYS = frozenset({
    "name_best", "city", "website", "emails", "phones", "messengers",
    "region", "segment", "status",
})


def create_company(db, **overrides) -> int:
    """Создать CompanyRow + EnrichedCompanyRow + CrmContactRow.

    Возвращает company.id. Данные доступны только после db.commit()
    (или db.flush(), но flush не виден через другую сессию).
    """
    defaults = {
        "name_best": "Test Company",
        "city": "Москва",
        "website": "https://test.ru",
        "emails": ["info@test.ru"],
        "phones": ["79001234567"],
        "messengers": {},
        "region": "Москва",
    }
    defaults.update({
        k: v for k, v in overrides.items() if k in _COMPANY_ALLOWED_KEYS
    })

    company = CompanyRow(**defaults)
    db.add(company)
    db.flush()

    enriched = EnrichedCompanyRow(
        id=company.id,
        name=defaults["name_best"],  # NOT NULL
        city=defaults["city"],
        messengers=overrides.get("messengers", {}),
        crm_score=overrides.get("crm_score", 50),
        segment=overrides.get("segment", "B"),
        emails=defaults["emails"],
        phones=defaults["phones"],
    )
    db.add(enriched)

    contact = CrmContactRow(
        company_id=company.id,
        funnel_stage=overrides.get("funnel_stage", "new"),
        stop_automation=overrides.get("stop_automation", 0),
    )
    db.add(contact)
    db.flush()
    return company.id


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
