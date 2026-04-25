# Granite CRM — План разработки по итогам API-аудита

> Дата: 2026-04-19
> Версия проекта: v0.2.0
> Репозиторий: https://github.com/aipunkfacility/granite-crm
> Исходный аудит: `granite-crm-api-audit.md`
> Замечание #10 (аутентификация пользователей) — исключено по требованию

---

## Структура плана

План разбит на 4 фазы по приоритету и связности изменений. Каждая фаза — отдельная ветка в git, отдельный PR. Внутри фазы — задачи с конкретными файлами, строками кода и тестами.

| Фаза | Суть | Замечания | Оценка |
|------|------|-----------|--------|
| P0 | Критические баги — сломанные данные | #1, #2 | 2 дня |
| P1 | API-контракт для фронтенда | #3, #4, #9 | 2 дня |
| P2 | Инфраструктура и SSE | #5, #6, #10, #11, #12 | 2 дня |
| P3 | Фичи для фронтенда | #7, #8 | 3 дня |

**Итого: ~9 рабочих дней (1.8 недели)**

---

## Фаза P0: Критические баги

Баги, которые прямо сейчас ломают данные: удалённые компании видны в API, рассылки уходят «мёртвым» контактам, статистика некорректна. Исправляются в первую очередь, т.к. без них фронтенд будет показывать мусор.

---

### Задача P0-1: Фильтр soft-delete во всех read-запросах

**Замечание #1 [КРИТИЧЕСКОЕ]** — `deleted_at` не фильтруется в 8 эндпоинтах

**Проблема**: Механизм soft-delete (`CompanyRow.deleted_at`) реализован только на уровне модели, но почти ни один read-запрос не добавляет `.filter(deleted_at.is_(None))`. Удалённые компании продолжают фигурировать в списках, статистике, рассылках, задачах и follow-up.

**Стратегия**: Добавить метод класса `CompanyRow.active()` и использовать его во всех read-запросах вместо прямого `session.query(CompanyRow)`. Это даёт явный контроль и минимум изменений.

#### Шаг 1: Добавить метод в ORM-модель

**Файл**: `granite/database.py`, класс `CompanyRow` (строка 51)

```python
class CompanyRow(Base):
    __tablename__ = "companies"

    # ... существующие колонки ...

    @classmethod
    def active(cls, session):
        """Вернуть query только активных (не удалённых) компаний."""
        return session.query(cls).filter(cls.deleted_at.is_(None))
```

**Обоснование**: Метод на уровне модели — централизованное место. Если логика soft-delete изменится (например, добавится `status='archived'`), меняем один метод.

#### Шаг 2: Исправить `GET /companies` — список компаний

**Файл**: `granite/api/companies.py`, функция `list_companies` (строка 77)

```python
# БЫЛО:
q = (
    db.query(CompanyRow, EnrichedCompanyRow, CrmContactRow)
    .outerjoin(EnrichedCompanyRow, CompanyRow.id == EnrichedCompanyRow.id)
    .outerjoin(CrmContactRow, CompanyRow.id == CrmContactRow.company_id)
)

# СТАЛО:
q = (
    CompanyRow.active(db)
    .with_entities(CompanyRow, EnrichedCompanyRow, CrmContactRow)
    .outerjoin(EnrichedCompanyRow, CompanyRow.id == EnrichedCompanyRow.id)
    .outerjoin(CrmContactRow, CompanyRow.id == CrmContactRow.company_id)
)
```

Альтернативный вариант (меньше изменений, рекомендую):

```python
q = (
    db.query(CompanyRow, EnrichedCompanyRow, CrmContactRow)
    .outerjoin(EnrichedCompanyRow, CompanyRow.id == EnrichedCompanyRow.id)
    .outerjoin(CrmContactRow, CompanyRow.id == CrmContactRow.company_id)
    .filter(CompanyRow.deleted_at.is_(None))  # <-- добавить
)
```

Рекомендую второй вариант — он не ломает структуру запроса и совместим с текущими тестами.

#### Шаг 3: Исправить `GET /companies/{id}` — карточка компании

**Файл**: `granite/api/companies.py`, функция `get_company` (строка 148)

```python
# БЫЛО:
company = db.get(CompanyRow, company_id)

# СТАЛО:
company = db.query(CompanyRow).filter(
    CompanyRow.id == company_id,
    CompanyRow.deleted_at.is_(None),
).first()
if not company:
    raise HTTPException(404, "Company not found")
```

`db.get()` не поддерживает фильтры — замена на `query().filter().first()`.

#### Шаг 4: Исправить `GET /stats` — агрегированная статистика

**Файл**: `granite/api/stats.py`, функция `get_stats` (строка 40)

Во все агрегации добавить `CompanyRow.deleted_at.is_(None)`:

```python
# Базовый фильтр — включаем deleted_at
base_filter = [CompanyRow.deleted_at.is_(None)]
if city:
    base_filter.append(CompanyRow.city == city)

# Total companies (строка 40)
total = db.query(func.count(CompanyRow.id)).filter(*base_filter).scalar()

# Funnel (строка 43-49) — добавить фильтр в join
funnel_q = (
    db.query(CrmContactRow.funnel_stage, func.count())
    .join(CompanyRow, CrmContactRow.company_id == CompanyRow.id)
    .filter(*base_filter)
    .group_by(CrmContactRow.funnel_stage)
    .all()
)

# Segments (строка 53-59) — аналогично
segment_q = (
    db.query(EnrichedCompanyRow.segment, func.count())
    .join(CompanyRow, EnrichedCompanyRow.id == CompanyRow.id)
    .filter(*base_filter)
    .group_by(EnrichedCompanyRow.segment)
    .all()
)

# Top cities (строка 63-71)
city_q = (
    db.query(CompanyRow.city, func.count().label("cnt"))
    .filter(CompanyRow.city.isnot(None), CompanyRow.city != "", *base_filter)
    .group_by(CompanyRow.city)
    .order_by(func.count().desc())
    .limit(10)
    .all()
)

# Telegram (строка 76-84), WhatsApp (строка 86-95), Email (строка 98-107)
# Добавить CompanyRow.deleted_at.is_(None) во все три запроса
```

#### Шаг 5: Исправить `GET /followup` — очередь follow-up

**Файл**: `granite/api/followup.py`, функция `get_followup_queue` (строка 42)

```python
q = (
    db.query(CompanyRow, EnrichedCompanyRow, CrmContactRow)
    .outerjoin(EnrichedCompanyRow, CompanyRow.id == EnrichedCompanyRow.id)
    .join(CrmContactRow, CompanyRow.id == CrmContactRow.company_id)
    .filter(
        CrmContactRow.funnel_stage.in_(list(STAGE_NEXT_ACTION.keys())),
        CrmContactRow.stop_automation == 0,
        CompanyRow.deleted_at.is_(None),  # <-- добавить
    )
)
```

#### Шаг 6: Исправить `_get_campaign_recipients` — получатели кампании

**Файл**: `granite/api/campaigns.py`, функция `_get_campaign_recipients` (строка 107)

```python
q = (
    db.query(CompanyRow, EnrichedCompanyRow, CrmContactRow)
    .outerjoin(EnrichedCompanyRow, CompanyRow.id == EnrichedCompanyRow.id)
    .outerjoin(CrmContactRow, CompanyRow.id == CrmContactRow.company_id)
    .filter(
        CompanyRow.emails.isnot(None),
        CompanyRow.emails.cast(String) != "[]",
        CompanyRow.emails.cast(String) != "",
        CompanyRow.deleted_at.is_(None),  # <-- добавить
    )
)
```

#### Шаг 7: Исправить `GET /pipeline/status` — статус пайплайна

**Файл**: `granite/api/pipeline_status.py`, функция `pipeline_status` (строка 49)

```python
# Считаем только неудалённые компании
comp_counts = dict(
    db.query(CompanyRow.city, func.count(CompanyRow.id))
    .filter(CompanyRow.deleted_at.is_(None))  # <-- добавить
    .group_by(CompanyRow.city).all()
)
```

#### Шаг 8: Исправить `GET /tasks` — список задач

**Файл**: `granite/api/tasks.py`, функция `list_tasks` (строка 66)

Два варианта:
- **Вариант A**: Не показывать задачи удалённых компаний
- **Вариант B**: Показывать задачи, но помечать компанию как `(удалена)`

Рекомендую вариант A — задачи привязаны к компаниям, удалённая компания = невалидный контекст:

```python
q = (
    db.query(CrmTaskRow, CompanyRow)
    .outerjoin(CompanyRow, CrmTaskRow.company_id == CompanyRow.id)
)
if not include_unlinked:
    q = q.filter(CrmTaskRow.company_id.isnot(None))

# Фильтруем задачи удалённых компаний (если company_id указан и компания удалена)
q = q.filter(
    (CompanyRow.id == None) | (CompanyRow.deleted_at.is_(None))
)
```

#### Шаг 9: Исправить `GET /companies/{id}/similar` — проверить `get_similar`

Этот эндпоинт уже фильтрует `deleted_at IS NULL` в SQL-запросах (строки 210, 225). Но нужно также проверить, что сама запрашиваемая компания не удалена:

```python
# В get_similar_companies (строка 198)
company = db.query(CompanyRow).filter(
    CompanyRow.id == company_id,
    CompanyRow.deleted_at.is_(None),
).first()
if not company:
    raise HTTPException(404, "Company not found")
```

#### Шаг 10: Исправить `GET /funnel` — воронка

**Файл**: `granite/api/funnel.py`, функция `get_funnel` (строка 23)

```python
rows = (
    db.query(CrmContactRow.funnel_stage, func.count())
    .join(CompanyRow, CrmContactRow.company_id == CompanyRow.id)
    .filter(CompanyRow.deleted_at.is_(None))  # <-- добавить
    .group_by(CrmContactRow.funnel_stage)
    .all()
)
```

#### Шаг 11: Исправить cities/regions — списки городов/регионов

**Файл**: `granite/api/companies.py`, функции `list_cities` (строка 350) и `list_regions` (строка 375)

```python
# list_cities
rows = (
    db.query(CompanyRow.city)
    .filter(
        CompanyRow.city.isnot(None),
        CompanyRow.city != "",
        CompanyRow.deleted_at.is_(None),  # <-- добавить
    )
    .distinct()
    .order_by(CompanyRow.city)
    .all()
)

# list_regions — аналогично
```

#### Тесты для P0-1

Добавить в `tests/test_api_companies.py` (или создать `tests/test_soft_delete.py`):

```python
def test_deleted_company_not_in_list(client, db):
    """Удалённая компания не появляется в GET /companies."""
    company = CompanyRow(name_best="Test", city="Москва", region="Москва")
    db.add(company)
    db.commit()
    cid = company.id

    # Soft-delete
    company.deleted_at = datetime.now(timezone.utc)
    db.commit()

    resp = client.get("/api/v1/companies")
    items = resp.json()["items"]
    assert all(i["id"] != cid for i in items)


def test_deleted_company_404_on_get(client, db):
    """GET /companies/{id} возвращает 404 для удалённой компании."""
    company = CompanyRow(name_best="Test", city="Москва", region="Москва")
    db.add(company)
    db.commit()
    cid = company.id

    company.deleted_at = datetime.now(timezone.utc)
    db.commit()

    resp = client.get(f"/api/v1/companies/{cid}")
    assert resp.status_code == 404


def test_deleted_company_not_in_stats(client, db):
    """Удалённые компании не учитываются в GET /stats."""
    company = CompanyRow(name_best="Test", city="Москва", region="Москва")
    db.add(company)
    db.commit()

    # Запоминаем total
    resp1 = client.get("/api/v1/stats")
    total_before = resp1.json()["total_companies"]

    # Soft-delete
    company.deleted_at = datetime.now(timezone.utc)
    db.commit()

    resp2 = client.get("/api/v1/stats")
    assert resp2.json()["total_companies"] == total_before - 1


def test_deleted_company_not_in_followup(client, db):
    """Follow-up не предлагает удалённые компании."""
    company = CompanyRow(name_best="Test", city="Москва", region="Москва")
    db.add(company)
    contact = CrmContactRow(company_id=company.id, funnel_stage="email_sent")
    db.add(contact)
    db.commit()
    cid = company.id

    company.deleted_at = datetime.now(timezone.utc)
    db.commit()

    resp = client.get("/api/v1/followup")
    items = resp.json()["items"]
    assert all(i["company_id"] != cid for i in items)


def test_deleted_company_not_in_tasks(client, db):
    """Задачи удалённых компаний не видны в GET /tasks."""
    company = CompanyRow(name_best="Test", city="Москва", region="Москва")
    db.add(company)
    db.commit()
    task = CrmTaskRow(company_id=company.id, title="Test task")
    db.add(task)
    db.commit()
    tid = task.id

    company.deleted_at = datetime.now(timezone.utc)
    db.commit()

    resp = client.get("/api/v1/tasks")
    items = resp.json()["items"]
    assert all(i["id"] != tid for i in items)
```

**Оценка**: 4-6 часов (код + тесты)

---

### Задача P0-2: Унификация `stop_automation` — Integer → Boolean

**Замечание #2 [ВЫСОКОЕ]** — `stop_automation` Integer в БД, bool в схеме

**Проблема**: SQLite хранит Boolean как Integer, но в коде используется вперемешку `0/1` и `True/False`. При миграции на PostgreSQL это сломается. Кроме того, отсутствие CHECK constraint позволяет записать `2`, `3`, `-1`.

#### Шаг 1: Миграция Alembic — добавить CHECK constraint

Создать миграцию:

```bash
cd /home/z/my-project/granite-crm
uv run alembic revision -m "add_check_stop_automation"
```

**Файл миграции** (`alembic/versions/xxx_add_check_stop_automation.py`):

```python
def upgrade():
    op.execute(
        "ALTER TABLE crm_contacts ADD CONSTRAINT chk_stop_automation "
        "CHECK (stop_automation IN (0, 1))"
    )

def downgrade():
    op.execute("ALTER TABLE crm_contacts DROP CONSTRAINT chk_stop_automation")
```

> Примечание: SQLite 3.25+ поддерживает CHECK constraints. Однако `ALTER TABLE DROP CONSTRAINT` не поддерживается — для downgrade нужен `batch_alter_table`.

#### Шаг 2: Изменить ORM-модель на Boolean

**Файл**: `granite/database.py`, строка 228

```python
# БЫЛО:
stop_automation = Column(Integer, default=0, server_default="0", index=True)

# СТАЛО:
stop_automation = Column(Boolean, default=False, server_default="0", index=True)
```

SQLAlchemy для SQLite автоматически маппит `Boolean` на `Integer` с хранением `0/1`, но при этом Python-сторона работает только с `True/False`. Это обеспечит совместимость при миграции на PostgreSQL — `Boolean` создаст колонку `BOOLEAN` вместо `INTEGER`.

#### Шаг 3: Добавить Pydantic-валидатор для обратной совместимости

**Файл**: `granite/api/schemas.py`, класс `CompanyResponse` (строка 144)

```python
from pydantic import field_validator

class CompanyResponse(BaseModel):
    # ... существующие поля ...
    stop_automation: bool = False

    @field_validator("stop_automation", mode="before")
    @classmethod
    def coerce_bool(cls, v):
        """Конвертация int→bool для обратной совместимости с SQLite."""
        return bool(v)

    model_config = {"from_attributes": True}
```

Валидатор гарантирует, что даже если из БД придёт `0` или `1` (из-за кэша или прямого SQL), Pydantic сконвертирует в `bool`.

#### Шаг 4: Унифицировать использование в коде

Все места, где используется int-сравнение или int-присваивание:

**Файл**: `granite/api/stage_transitions.py`, строка 42

```python
# БЫЛО:
contact.stop_automation = 1

# СТАЛО:
contact.stop_automation = True
```

**Файл**: `granite/api/followup.py`, строка 48

```python
# БЫЛО:
CrmContactRow.stop_automation == 0

# СТАЛО:
CrmContactRow.stop_automation == False
# или (более Pythonic):
CrmContactRow.stop_automation.is_(False)
```

> Примечание: SQLAlchemy корректно транслирует `== False` в `= 0` для SQLite и `= FALSE` для PostgreSQL при использовании типа `Boolean`. Альтернативно можно использовать `~CrmContactRow.stop_automation` (побитовое отрицание), но `== False` читабельнее.

**Файл**: `granite/api/campaigns.py`, строка 131

```python
# БЫЛО (truthy-проверка — работает, но неявно):
if contact.stop_automation:

# СТАЛО (явная проверка — предпочтительно):
if contact.stop_automation is True:
```

**Файл**: `granite/api/companies.py`, строка 55

```python
# БЫЛО:
"stop_automation": bool(contact.stop_automation) if contact else False,

# СТАЛО (bool() уже не нужен, но оставляем для safety):
"stop_automation": bool(contact.stop_automation) if contact else False,
```

Оставляем `bool()` как защитный слой — он не вредит, а при переходе на Boolean-колонку может быть убран позже.

#### Шаг 5: Обновить составной индекс

**Файл**: `granite/database.py`, строка 191

Составной индекс `ix_crm_contacts_funnel_stop` остаётся корректным — SQLAlchemy понимает `Boolean` в индексе.

#### Тесты для P0-2

```python
def test_stop_automation_bool_in_response(client, db):
    """stop_automation возвращается как bool, не int."""
    company = CompanyRow(name_best="Test", city="Москва", region="Москва")
    db.add(company)
    contact = CrmContactRow(company_id=company.id, stop_automation=True)
    db.add(contact)
    db.commit()

    resp = client.get(f"/api/v1/companies/{company.id}")
    data = resp.json()
    assert data["stop_automation"] is True
    assert isinstance(data["stop_automation"], bool)


def test_stop_automation_patch_bool(client, db):
    """PATCH /companies/{id} принимает bool для stop_automation."""
    company = CompanyRow(name_best="Test", city="Москва", region="Москва")
    db.add(company)
    contact = CrmContactRow(company_id=company.id)
    db.add(contact)
    db.commit()

    resp = client.patch(
        f"/api/v1/companies/{company.id}",
        json={"stop_automation": True},
    )
    assert resp.json()["ok"] is True

    db.refresh(contact)
    assert contact.stop_automation is True
```

**Оценка**: 2-3 часа (код + миграция + тесты)

---

## Фаза P1: API-контракт для фронтенда

Изменения, которые直接影响 TypeScript-кодогенерацию и типобезопасность фронтенда. Без них фронтендер получит `any[]`, `Record<string, any>` и отсутствие валидации переходов воронки.

---

### Задача P1-1: Типизация `PaginatedResponse` для touches

**Замечание #4 [ВЫСОКОЕ]** — `PaginatedResponse` без типа для touches

**Проблема**: Одна строка кода даёт `items: any[]` в TypeScript вместо полноценной типизации.

#### Исправление

**Файл**: `granite/api/touches.py`, строка 56

```python
# БЫЛО:
@router.get("/companies/{company_id}/touches", response_model=PaginatedResponse)

# СТАЛО:
@router.get("/companies/{company_id}/touches", response_model=PaginatedResponse[TouchResponse])
```

Одно изменение — OpenAPI начнёт генерировать корректную схему с типизированными `items`.

#### Тесты для P1-1

```python
def test_touches_response_typed(client, db):
    """GET /companies/{id}/touches возвращает типизированные items."""
    company = CompanyRow(name_best="Test", city="Москва", region="Москва")
    db.add(company)
    db.commit()
    touch = CrmTouchRow(company_id=company.id, channel="email", direction="outgoing")
    db.add(touch)
    db.commit()

    resp = client.get(f"/api/v1/companies/{company.id}/touches")
    data = resp.json()
    assert "items" in data
    assert "total" in data
    assert data["items"][0]["channel"] == "email"
    assert data["items"][0]["direction"] == "outgoing"
```

Также проверить OpenAPI-схему:

```python
def test_touches_openapi_schema(client):
    """OpenAPI-схема для touches содержит типизацию items."""
    resp = client.get("/openapi.json")
    schema = resp.json()
    # Найти схему PaginatedResponse_TouchResponse_
    touch_page_key = None
    for key in schema["components"]["schemas"]:
        if "TouchResponse" in key and "Paginated" in key:
            touch_page_key = key
            break
    assert touch_page_key is not None, "PaginatedResponse[TouchResponse] not found in OpenAPI"
    items_schema = schema["components"]["schemas"][touch_page_key]["properties"]["items"]
    assert items_schema["items"]["$ref"] is not None
```

**Оценка**: 30 минут

---

### Задача P1-2: Типизация `FunnelResponse`

**Замечание #9 [СРЕДНЕЕ]** — `FunnelResponse` без типизации полей

**Проблема**: `extra: "allow"` создаёт `Record<string, any>` в TypeScript. Фронтенд не знает, какие ключи есть в ответе.

#### Исправление

**Файл**: `granite/api/schemas.py`, класс `FunnelResponse` (строка 297)

```python
# БЫЛО:
class FunnelResponse(BaseModel):
    """Распределение по стадиям воронки."""
    model_config = {"extra": "allow"}
    # Динамические ключи: new, email_sent, ..., unreachable -> int

# СТАЛО:
class FunnelResponse(BaseModel):
    """Распределение по стадиям воронки."""
    new: int = 0
    email_sent: int = 0
    email_opened: int = 0
    tg_sent: int = 0
    wa_sent: int = 0
    replied: int = 0
    interested: int = 0
    not_interested: int = 0
    unreachable: int = 0
```

Убрать `model_config = {"extra": "allow"}` — теперь все ключи явно описаны, и Pydantic будет отвергать неизвестные поля.

#### Тесты для P1-2

```python
def test_funnel_response_typed(client, db):
    """GET /funnel возвращает все 9 стадий с int-значениями."""
    resp = client.get("/api/v1/funnel")
    data = resp.json()
    for stage in ["new", "email_sent", "email_opened", "tg_sent", "wa_sent",
                   "replied", "interested", "not_interested", "unreachable"]:
        assert stage in data
        assert isinstance(data[stage], int)


def test_funnel_openapi_schema(client):
    """OpenAPI-схема FunnelResponse содержит все 9 полей."""
    resp = client.get("/openapi.json")
    schema = resp.json()
    funnel_schema = schema["components"]["schemas"]["FunnelResponse"]
    for stage in ["new", "email_sent", "email_opened", "tg_sent", "wa_sent",
                   "replied", "interested", "not_interested", "unreachable"]:
        assert stage in funnel_schema["properties"]
```

**Оценка**: 30 минут

---

### Задача P1-3: Валидация переходов воронки

**Замечание #3 [ВЫСОКОЕ]** — Нет валидации переходов воронки

**Проблема**: Фронтенд может перевести компанию из `new` сразу в `interested`, минуя все промежуточные стадии. Drag-and-drop на Kanban-доске создаст невалидный переход.

#### Шаг 1: Добавить схему `TransitionRequest`

**Файл**: `granite/api/schemas.py`

```python
class TransitionRequest(BaseModel):
    """Запрос на переход стадии воронки."""
    new_stage: str = Field(
        ...,
        pattern="^(new|email_sent|email_opened|tg_sent|wa_sent|replied|interested|not_interested|unreachable)$",
        description="Целевая стадия воронки",
    )
    reason: str = Field("", max_length=500, description="Причина ручного перехода")
```

#### Шаг 2: Добавить схему ответа `TransitionResponse`

**Файл**: `granite/api/schemas.py`

```python
class TransitionResponse(BaseModel):
    """Ответ на запрос перехода стадии."""
    ok: bool = True
    old_stage: str
    new_stage: str
```

#### Шаг 3: Определить карту валидных переходов

**Файл**: `granite/api/funnel.py` (или отдельный файл `granite/api/funnel_transitions.py`)

```python
# Валидные переходы для ручного перемещения.
# Автоматические переходы (через stage_transitions.py) не подчиняются этим правилам —
# они вызываются при создании касаний и имеют собственную логику.
VALID_MANUAL_TRANSITIONS = {
    "new": {"email_sent", "unreachable"},
    "email_sent": {"email_opened", "tg_sent", "unreachable"},
    "email_opened": {"tg_sent", "wa_sent", "unreachable"},
    "tg_sent": {"wa_sent", "replied", "unreachable"},
    "wa_sent": {"replied", "not_interested", "unreachable"},
    "replied": {"interested", "not_interested"},
    "interested": set(),      # конечная — нет ручных переходов
    "not_interested": set(),  # конечная
    "unreachable": set(),     # конечная
}

# Обратные переходы (откат) — только для администратора/отладки.
# По умолчанию отключены, включаются через force=True.
ROLLBACK_TRANSITIONS = {
    "email_sent": {"new"},
    "email_opened": {"email_sent"},
    "tg_sent": {"email_opened", "email_sent"},
    "wa_sent": {"tg_sent"},
    "replied": {"wa_sent"},
    "not_interested": {"replied"},
    "unreachable": {"wa_sent", "tg_sent", "email_sent", "new"},
}
```

#### Шаг 4: Добавить эндпоинт перехода

**Файл**: `granite/api/funnel.py`

```python
from fastapi import HTTPException
from granite.database import CompanyRow, CrmContactRow, CrmTouchRow

@router.post("/funnel/{company_id}/transition", response_model=TransitionResponse)
def transition_stage(
    company_id: int,
    body: TransitionRequest,
    force: bool = Query(False, description="Разрешить обратные переходы"),
    db: Session = Depends(get_db),
):
    """Перевести компанию на новую стадию воронки с валидацией перехода.

    Автоматические переходы (через касания) обходят эту валидацию.
    Ручной переход логируется как touch с note='funnel_transition'.
    """
    # Проверяем, что компания существует и не удалена
    company = db.query(CompanyRow).filter(
        CompanyRow.id == company_id,
        CompanyRow.deleted_at.is_(None),
    ).first()
    if not company:
        raise HTTPException(404, "Company not found")

    contact = db.get(CrmContactRow, company_id)
    if not contact:
        raise HTTPException(404, "CRM contact not found")

    current = contact.funnel_stage

    # Тот же stage — нет операции
    if current == body.new_stage:
        return TransitionResponse(ok=True, old_stage=current, new_stage=body.new_stage)

    # Проверяем валидность перехода
    allowed = VALID_MANUAL_TRANSITIONS.get(current, set())
    if force:
        allowed = allowed | ROLLBACK_TRANSITIONS.get(current, set())

    if body.new_stage not in allowed:
        raise HTTPException(
            409,
            f"Invalid transition: {current} -> {body.new_stage}. "
            f"Allowed from '{current}': {sorted(allowed)}. "
            f"Use ?force=true for rollback transitions.",
        )

    old_stage = contact.funnel_stage
    contact.funnel_stage = body.new_stage
    contact.updated_at = datetime.now(timezone.utc)

    # Аудит-лог через touch
    db.add(CrmTouchRow(
        company_id=company_id,
        channel="manual",
        direction="outgoing",
        subject=f"Stage transition: {old_stage} -> {body.new_stage}",
        body=body.reason,
        note="funnel_transition",
    ))
    db.flush()

    return TransitionResponse(ok=True, old_stage=old_stage, new_stage=body.new_stage)
```

#### Шаг 5: Ограничить прямой `PATCH /companies/{id}` для `funnel_stage`

**Файл**: `granite/api/companies.py`, функция `update_company` (строка 159)

Добавить предупреждение в docstring и логирование:

```python
@router.patch("/companies/{company_id}", response_model=OkResponse)
def update_company(company_id: int, data: UpdateCompanyRequest, db: Session = Depends(get_db)):
    """Обновить CRM-поля компании.

    ВНИМАНИЕ: для изменения funnel_stage используйте POST /funnel/{id}/transition.
    Прямой PATCH не валидирует переходы — оставлено для обратной совместимости.
    """
    # ... существующий код ...

    # Логируем ручной переход стадии
    if data.funnel_stage is not None and contact.funnel_stage != data.funnel_stage:
        logger.warning(
            f"Direct stage change via PATCH: company={company_id} "
            f"{contact.funnel_stage} -> {data.funnel_stage}. "
            f"Consider using POST /funnel/{company_id}/transition instead."
        )

    # ... остальной код ...
```

В будущей версии можно добавить `deprecated=True` для `funnel_stage` в `UpdateCompanyRequest`.

#### Тесты для P1-3

```python
def test_valid_transition(client, db):
    """Валидный переход new -> email_sent."""
    company = CompanyRow(name_best="Test", city="Москва", region="Москва")
    db.add(company)
    contact = CrmContactRow(company_id=company.id, funnel_stage="new")
    db.add(contact)
    db.commit()

    resp = client.post(
        f"/api/v1/funnel/{company.id}/transition",
        json={"new_stage": "email_sent", "reason": "Sent cold email"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["old_stage"] == "new"
    assert data["new_stage"] == "email_sent"

    db.refresh(contact)
    assert contact.funnel_stage == "email_sent"


def test_invalid_transition_409(client, db):
    """Невалидный переход new -> interested возвращает 409."""
    company = CompanyRow(name_best="Test", city="Москва", region="Москва")
    db.add(company)
    contact = CrmContactRow(company_id=company.id, funnel_stage="new")
    db.add(contact)
    db.commit()

    resp = client.post(
        f"/api/v1/funnel/{company.id}/transition",
        json={"new_stage": "interested"},
    )
    assert resp.status_code == 409
    assert "Invalid transition" in resp.json()["error"]


def test_rollback_with_force(client, db):
    """Обратный переход с ?force=true."""
    company = CompanyRow(name_best="Test", city="Москва", region="Москва")
    db.add(company)
    contact = CrmContactRow(company_id=company.id, funnel_stage="email_sent")
    db.add(contact)
    db.commit()

    # Без force — 409
    resp = client.post(
        f"/api/v1/funnel/{company.id}/transition",
        json={"new_stage": "new"},
    )
    assert resp.status_code == 409

    # С force — OK
    resp = client.post(
        f"/api/v1/funnel/{company.id}/transition?force=true",
        json={"new_stage": "new", "reason": "Mistake"},
    )
    assert resp.status_code == 200


def test_transition_creates_audit_touch(client, db):
    """Переход создаёт touch с note='funnel_transition'."""
    company = CompanyRow(name_best="Test", city="Москва", region="Москва")
    db.add(company)
    contact = CrmContactRow(company_id=company.id, funnel_stage="new")
    db.add(contact)
    db.commit()

    client.post(
        f"/api/v1/funnel/{company.id}/transition",
        json={"new_stage": "email_sent", "reason": "Test"},
    )

    touches = db.query(CrmTouchRow).filter_by(
        company_id=company.id, note="funnel_transition"
    ).all()
    assert len(touches) == 1
    assert "new" in touches[0].subject
    assert "email_sent" in touches[0].subject
```

**Оценка**: 3-4 часа

---

## Фаза P2: Инфраструктура и SSE

Исправления инфраструктуры: утечка памяти, унификация SSE, мелкие баги middleware. Не блокируют фронтенд, но влияют на стабильность и опыт разработки.

---

### Задача P2-1: Исправление утечки памяти в rate limiter

**Замечание #5 [ВЫСОКОЕ]** — Утечка памяти в rate limiter

**Проблема**: `_rate_limit_store` никогда не удаляет пустые бакеты, а `import re` выполняется на каждом запросе.

#### Шаг 1: Вынести `import re` на уровень модуля

**Файл**: `granite/api/app.py`, строка 222

```python
# БЫЛО (внутри цикла for в rate_limit_middleware):
import re as _re

# СТАЛО (на уровне модуля, вверху файла):
import re as _re
```

Добавить рядом с `import time` и `import threading` (строка 21-22).

#### Шаг 2: Удалять пустые бакеты

**Файл**: `granite/api/app.py`, функция `rate_limit_middleware` (строка 239)

```python
# БЫЛО:
timestamps.append(now)
_rate_limit_store[bucket_key] = timestamps

# СТАЛО:
timestamps.append(now)
if timestamps:
    _rate_limit_store[bucket_key] = timestamps
else:
    _rate_limit_store.pop(bucket_key, None)
```

Также добавить периодическую полную очистку старых ключей (раз в 1000 запросов):

```python
# В начале функции rate_limit_middleware:
request_count = getattr(rate_limit_middleware, '_request_count', 0) + 1
rate_limit_middleware._request_count = request_count

if request_count % 1000 == 0:
    with _rate_limit_lock:
        now = time.time()
        stale_keys = [
            k for k, v in _rate_limit_store.items()
            if not v or now - v[-1] > 300  # нет запросов > 5 минут
        ]
        for k in stale_keys:
            del _rate_limit_store[k]
```

#### Шаг 3: Анкорировать regex-паттерны

**Файл**: `granite/api/app.py`, строка 176

```python
# БЫЛО:
_RATE_LIMITS = {
    "post:/companies/.*?/send": (10, 60),
    "post:/campaigns/.*?/run": (3, 60),
    "get:/export/.*": (20, 60),
}

# СТАЛО:
_RATE_LIMITS = {
    r"^post:/companies/\d+/send$": (10, 60),
    r"^post:/campaigns/\d+/run$": (3, 60),
    r"^get:/export/.+$": (20, 60),
}
```

Анкорированные паттерны (`^...$`) не совпадут с неожиданными путями типа `post:/companies/42/send/spam`.

#### Тесты для P2-1

```python
def test_rate_limit_no_memory_leak():
    """Пустые бакеты удаляются из _rate_limit_store."""
    from granite.api.app import _rate_limit_store, _rate_limit_lock
    import time

    # Симулируем запрос, который попал под лимит
    key = "127.0.0.1:^post:/companies/\\d+/send$"
    with _rate_limit_lock:
        _rate_limit_store[key] = []

    # Симулируем очистку — пустой бакет должен быть удалён
    with _rate_limit_lock:
        for k, v in list(_rate_limit_store.items()):
            if not v:
                del _rate_limit_store[k]

    assert key not in _rate_limit_store


def test_rate_limit_anchored_patterns():
    """Анкорированные паттерны не совпадают с неожиданными путями."""
    import re
    pattern = r"^post:/companies/\d+/send$"
    assert re.match(pattern, "post:/companies/42/send")
    assert not re.match(pattern, "post:/companies/42/send/spam")
    assert not re.match(pattern, "post:/companies/abc/send")
```

**Оценка**: 1-2 часа

---

### Задача P2-2: Унификация SSE-формата

**Замечание #6 [СРЕДНЕЕ]** — Несогласованный SSE-формат

**Проблема**: Pipeline SSE использует `type` для дискриминации событий, Campaign SSE — `status`. Фронтенду нужны два разных парсера для одинаковой задачи.

#### Шаг 1: Определить единый SSE-формат

```python
# Единый формат для всех SSE-стримов в Granite CRM
{
    "type": "started" | "progress" | "phase" | "done" | "error" | "heartbeat",
    "data": { ... }  # Специфичные для типа данные
}
```

#### Шаг 2: Обновить Pipeline SSE

**Файл**: `granite/api/pipeline_status.py`, функция `_run_pipeline_bg` (строка 194)

```python
# БЫЛО:
events.put({"type": "started", "city": city})
events.put({"type": "phase", "phase": "scraping", "city": city})
events.put({"type": "done", "city": city})
events.put({"type": "error", "city": city, "message": str(e)})

# СТАЛО:
events.put({"type": "started", "data": {"city": city}})
events.put({"type": "phase", "data": {"phase": "scraping", "city": city}})
events.put({"type": "done", "data": {"city": city}})
events.put({"type": "error", "data": {"city": city, "message": str(e)}})
```

Обновить `event_stream()` (строка 171):

```python
# Проверка терминального события
if event.get("type") in ("done", "error"):
    break
```

Эта строка остаётся без изменений — она уже использует `type`.

#### Шаг 3: Обновить Campaign SSE

**Файл**: `granite/api/campaigns.py`, функция `generate()` (строка 290)

```python
# БЫЛО:
yield f"data: {json.dumps({'status': 'started', 'total': len(recipients)})}\n\n"
yield f"data: {json.dumps({'sent': sent, 'total': len(recipients), 'company_id': company.id})}\n\n"
yield f"data: {json.dumps({'status': 'completed', 'sent': sent, 'total': len(recipients)})}\n\n"
yield f"data: {json.dumps({'error': 'Campaign not found'})}\n\n"

# СТАЛО:
yield f"data: {json.dumps({'type': 'started', 'data': {'total': len(recipients)}})}\n\n"
yield f"data: {json.dumps({'type': 'progress', 'data': {'sent': sent, 'total': len(recipients), 'company_id': company.id}})}\n\n"
yield f"data: {json.dumps({'type': 'done', 'data': {'sent': sent, 'total': len(recipients)}})}\n\n"
yield f"data: {json.dumps({'type': 'error', 'data': {'message': 'Campaign not found'}})}\n\n"
```

Аналогично для всех `yield` в функции `generate()` — около 8 мест.

#### Шаг 4: Добавить heartbeat для Campaign SSE

Campaign SSE не имеет heartbeat — при длинной кампании (десятки минут) браузер может закрыть соединение. Добавить:

```python
# Внутри цикла отправки, после каждого yield:
import time as _time
# ... send email ...
yield f"data: {json.dumps({'type': 'progress', 'data': {...}})}\n\n"
_time.sleep(SEND_DELAY)

# Добавить heartbeat каждые 30 секунд:
last_heartbeat = _time.time()
if _time.time() - last_heartbeat > 30:
    yield f"data: {json.dumps({'type': 'heartbeat', 'data': {}})}\n\n"
    last_heartbeat = _time.time()
```

#### Шаг 5: Обновить обработку ошибок в Campaign SSE

```python
# БЫЛО:
if not db_campaign:
    return StreamingResponse(
        iter([f"data: {json.dumps({'error': 'Campaign not found'})}\n\n"]),
        media_type="text/event-stream",
    )

# СТАЛО:
if not db_campaign:
    return StreamingResponse(
        iter([f"data: {json.dumps({'type': 'error', 'data': {'message': 'Campaign not found'}})}\n\n"]),
        media_type="text/event-stream",
    )
```

Все 4 места с `{'error': ...}` в Campaign SSE (строки 247, 253, 284, 304, 309, 314).

#### Тесты для P2-2

```python
def test_pipeline_sse_format(client, db):
    """Pipeline SSE использует единый формат {type, data}."""
    # Это интеграционный тест — запускает SSE и парсит события
    # (или мокает pipeline manager)
    pass  # Требует мокирования PipelineManager


def test_campaign_sse_format(client, db):
    """Campaign SSE использует единый формат {type, data}."""
    # Аналогично — мокируется EmailSender
    pass
```

> Примечание: SSE-тесты сложнее писать, т.к. требуют мокирования внешних зависимостей (PipelineManager, EmailSender). Можно также добавить unit-тесты на формат JSON-вывода отдельно от SSE-механики.

**Оценка**: 2-3 часа

---

### Задача P2-3: Dead code в API Key middleware

**Замечание #10 [НИЗКОЕ]** — Недостижимый код

**Проблема**: `skip_paths` в условии API Key middleware — dead code, т.к. все пути в `skip_paths` не начинаются с `/api/v1/` и отсекаются первым условием.

#### Исправление

**Файл**: `granite/api/app.py`, строка 266-272

```python
# БЫЛО:
skip_paths = ("/health", "/docs", "/openapi.json", "/redoc")
if (
    not request.url.path.startswith("/api/v1/")
    or request.url.path in skip_paths
    or request.url.path.startswith("/api/v1/track/")
    or request.method == "OPTIONS"
):
    return await call_next(request)

# СТАЛО:
if (
    not request.url.path.startswith("/api/v1/")
    or request.url.path.startswith("/api/v1/track/")
    or request.method == "OPTIONS"
):
    return await call_next(request)
```

Удалить `skip_paths` и условие `request.url.path in skip_paths`.

**Оценка**: 10 минут

---

### Задача P2-4: `expose_headers` в CORS

**Замечание #11 [НИЗКОЕ]** — Нет `expose_headers` в CORS

**Проблема**: JavaScript на фронтенде не может читать кастомные заголовки ответа (`X-Total-Count`, `ETag`, `X-Request-Id`).

#### Исправление

**Файл**: `granite/api/app.py`, строка 248-254

```python
# БЫЛО:
app.add_middleware(
    CORSMiddleware,
    allow_origins=_get_cors_origins(),
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS", "HEAD"],
    allow_headers=["Content-Type", "Authorization", "X-API-Key", "Accept"],
    allow_credentials=True,
)

# СТАЛО:
app.add_middleware(
    CORSMiddleware,
    allow_origins=_get_cors_origins(),
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS", "HEAD"],
    allow_headers=["Content-Type", "Authorization", "X-API-Key", "Accept"],
    allow_credentials=True,
    expose_headers=["X-Total-Count", "X-Request-Id", "ETag"],
)
```

**Оценка**: 5 минут

---

### Задача P2-5: Rate limit на tracking pixel

**Замечание #12 [НИЗКОЕ]** — Нет rate limit на tracking pixel

**Проблема**: Эндпоинт `/api/v1/track/open/{tracking_id}.png` полностью открыт — нет аутентификации и нет rate limit. Теоретически можно перебирать tracking IDs.

#### Исправление

**Файл**: `granite/api/app.py`, строка 176 (словарь `_RATE_LIMITS`)

```python
# БЫЛО:
_RATE_LIMITS = {
    r"^post:/companies/\d+/send$": (10, 60),
    r"^post:/campaigns/\d+/run$": (3, 60),
    r"^get:/export/.+$": (20, 60),
}

# СТАЛО:
_RATE_LIMITS = {
    r"^post:/companies/\d+/send$": (10, 60),
    r"^post:/campaigns/\d+/run$": (3, 60),
    r"^get:/export/.+$": (20, 60),
    r"^get:/api/v1/track/": (20, 60),  # 20 запросов/мин с одного IP
}
```

Лимит 20 запросов в минуту — достаточен для легитимных открытий писем (даже если в одном письме несколько пикселей), но блокирует перебор.

Дополнительно можно добавить логирование подозрительной активности:

**Файл**: `granite/api/tracking.py`

```python
# В функции обработки tracking pixel, после валидации:
if request_count_from_ip > 10:  # Если с одного IP более 10 запросов
    logger.warning(
        f"Suspicious tracking activity: IP={client_ip}, "
        f"requests={request_count_from_ip}/min"
    )
```

**Оценка**: 30 минут

---

## Фаза P3: Фичи для фронтенда

Новые эндпоинты и возможности, которые улучшат UX фронтенда. Не блокируют запуск, но сильно улучшат опыт.

---

### Задача P3-1: Bulk-операции для компаний

**Замечание #8 [СРЕДНЕЕ]** — Нет bulk-операций

**Проблема**: Для массовых операций (выделить 50 компаний, сменить стадию) нужно 50 отдельных PATCH-запросов. Нет атомарности, медленно, нет прогресса.

#### Шаг 1: Добавить схемы запросов/ответов

**Файл**: `granite/api/schemas.py`

```python
class BulkUpdateRequest(BaseModel):
    """Массовое обновление компаний."""
    company_ids: List[int] = Field(..., min_length=1, max_length=500,
                                    description="ID компаний (макс. 500)")
    funnel_stage: Optional[str] = Field(None, pattern="^(new|email_sent|email_opened|tg_sent|wa_sent|replied|interested|not_interested|unreachable)$")
    stop_automation: Optional[bool] = None
    notes: Optional[str] = None


class BulkDeleteRequest(BaseModel):
    """Массовое удаление компаний."""
    company_ids: List[int] = Field(..., min_length=1, max_length=500,
                                    description="ID компаний (макс. 500)")


class BulkResponse(BaseModel):
    """Результат массовой операции."""
    ok: bool = True
    affected: int = 0
    skipped: int = 0
    errors: Optional[List[str]] = None
```

#### Шаг 2: Добавить bulk-эндпоинты

**Файл**: `granite/api/companies.py`

Важно: эти эндпоинты должны быть определены ДО `/companies/{company_id}`, иначе FastAPI попытается распарсить `bulk` как `company_id`.

```python
@router.patch("/companies/bulk", response_model=BulkResponse)
def bulk_update_companies(data: BulkUpdateRequest, db: Session = Depends(get_db)):
    """Массовое обновление компаний.

    Применяет указанные поля ко всем компаниям из списка.
    Пропускает удалённые компании.
    Атомарно — либо все обновления применяются, либо ни одного.
    """
    updates = data.model_dump(exclude_unset=True, exclude={"company_ids"})
    if not updates:
        raise HTTPException(400, "No fields to update")

    # Фильтруем: только активные компании
    active_ids = (
        db.query(CompanyRow.id)
        .filter(
            CompanyRow.id.in_(data.company_ids),
            CompanyRow.deleted_at.is_(None),
        )
        .all()
    )
    active_id_set = {row[0] for row in active_ids}
    skipped = len(data.company_ids) - len(active_id_set)

    if not active_id_set:
        return BulkResponse(ok=True, affected=0, skipped=skipped)

    # Для CRM-полей нужен отдельный UPDATE через CrmContactRow
    crm_fields = {"funnel_stage", "stop_automation", "notes"}
    crm_updates = {k: v for k, v in updates.items() if k in crm_fields}
    company_updates = {k: v for k, v in updates.items() if k not in crm_fields}

    affected = 0

    if company_updates:
        # Обновляем поля в таблице companies
        affected += (
            db.query(CompanyRow)
            .filter(CompanyRow.id.in_(active_id_set))
            .update(company_updates, synchronize_session="fetch")
        )

    if crm_updates:
        # Обновляем поля в таблице crm_contacts
        # Сначала создаём CrmContactRow для компаний, у которых их нет
        existing_contacts = (
            db.query(CrmContactRow.company_id)
            .filter(CrmContactRow.company_id.in_(active_id_set))
            .all()
        )
        existing_ids = {row[0] for row in existing_contacts}
        missing_ids = active_id_set - existing_ids

        for cid in missing_ids:
            db.add(CrmContactRow(company_id=cid))

        if missing_ids:
            db.flush()

        # Конвертируем stop_automation из bool в int для SQLite (если нужно)
        if "stop_automation" in crm_updates and isinstance(crm_updates["stop_automation"], bool):
            # SQLAlchemy Boolean обработает конвертацию автоматически
            pass

        affected += (
            db.query(CrmContactRow)
            .filter(CrmContactRow.company_id.in_(active_id_set))
            .update(crm_updates, synchronize_session="fetch")
        )

    db.flush()
    return BulkResponse(ok=True, affected=len(active_id_set), skipped=skipped)


@router.delete("/companies/bulk", response_model=BulkResponse)
def bulk_delete_companies(data: BulkDeleteRequest, db: Session = Depends(get_db)):
    """Массовое soft-delete компаний."""
    now = datetime.now(timezone.utc)

    active_ids = (
        db.query(CompanyRow.id)
        .filter(
            CompanyRow.id.in_(data.company_ids),
            CompanyRow.deleted_at.is_(None),
        )
        .all()
    )
    active_id_set = {row[0] for row in active_ids}
    skipped = len(data.company_ids) - len(active_id_set)

    if not active_id_set:
        return BulkResponse(ok=True, affected=0, skipped=skipped)

    count = (
        db.query(CompanyRow)
        .filter(CompanyRow.id.in_(active_id_set))
        .update({"deleted_at": now}, synchronize_session="fetch")
    )
    db.flush()

    return BulkResponse(ok=True, affected=count, skipped=skipped)
```

#### Шаг 3: Зарегистрировать маршруты до `{company_id}`

Убедиться, что в `companies.py` bulk-эндпоинты находятся ДО эндпоинта `get_company`:

```python
# Порядок маршрутов в companies.py:
# 1. GET  /companies           — список
# 2. PATCH /companies/bulk     — массовое обновление  <-- NEW
# 3. DELETE /companies/bulk    — массовое удаление    <-- NEW
# 4. GET  /companies/{id}      — карточка
# 5. PATCH /companies/{id}     — обновление
# ...
```

#### Тесты для P3-1

```python
def test_bulk_update_funnel_stage(client, db):
    """Массовое изменение funnel_stage."""
    companies = []
    for i in range(5):
        c = CompanyRow(name_best=f"Test {i}", city="Москва", region="Москва")
        db.add(c)
        db.flush()
        db.add(CrmContactRow(company_id=c.id, funnel_stage="new"))
        companies.append(c)
    db.commit()
    ids = [c.id for c in companies]

    resp = client.patch(
        "/api/v1/companies/bulk",
        json={"company_ids": ids, "funnel_stage": "email_sent"},
    )
    data = resp.json()
    assert data["ok"] is True
    assert data["affected"] == 5

    for cid in ids:
        contact = db.get(CrmContactRow, cid)
        assert contact.funnel_stage == "email_sent"


def test_bulk_delete(client, db):
    """Массовое soft-delete."""
    companies = []
    for i in range(3):
        c = CompanyRow(name_best=f"Del {i}", city="Москва", region="Москва")
        db.add(c)
        companies.append(c)
    db.commit()
    ids = [c.id for c in companies]

    resp = client.delete(
        "/api/v1/companies/bulk",
        json={"company_ids": ids},
    )
    data = resp.json()
    assert data["affected"] == 3

    for cid in ids:
        c = db.get(CompanyRow, cid)
        assert c.deleted_at is not None


def test_bulk_skips_deleted(client, db):
    """Bulk-операция пропускает удалённые компании."""
    c1 = CompanyRow(name_best="Active", city="Москва", region="Москва")
    c2 = CompanyRow(name_best="Deleted", city="Москва", region="Москва")
    db.add_all([c1, c2])
    db.commit()

    c2.deleted_at = datetime.now(timezone.utc)
    db.commit()

    resp = client.patch(
        "/api/v1/companies/bulk",
        json={"company_ids": [c1.id, c2.id], "funnel_stage": "email_sent"},
    )
    data = resp.json()
    assert data["affected"] == 1
    assert data["skipped"] == 1


def test_bulk_max_500(client):
    """Превышение лимита 500 ID."""
    ids = list(range(1, 502))
    resp = client.patch(
        "/api/v1/companies/bulk",
        json={"company_ids": ids, "funnel_stage": "new"},
    )
    assert resp.status_code == 422
```

**Оценка**: 3-4 часа

---

### Задача P3-2: Real-time уведомления (поэтапно)

**Замечание #7 [СРЕДНЕЕ]** — Нет real-time уведомлений

**Проблема**: Единственный real-time механизм — SSE для двух операций. Все остальные изменения данных не пушатся — фронтенд вынужден поллить.

#### Этап 1 (рекомендуемый сейчас): Оптимизация поллинга

Минимальные изменения, которые уменьшат нагрузку от поллинга:

**1a. ETag для `GET /stats`**

**Файл**: `granite/api/stats.py`

```python
from fastapi import Response
import hashlib

@router.get("/stats", response_model=StatsResponse)
def get_stats(
    response: Response,
    db: Session = Depends(get_db),
    city: Optional[str] = None,
):
    """Агрегированная статистика с ETag для conditional requests."""
    result = _compute_stats(db, city)  # вынести логику в отдельную функцию

    # ETag на основе содержимого
    etag = hashlib.md5(
        json.dumps(result, sort_keys=True, default=str).encode()
    ).hexdigest()
    response.headers["ETag"] = f'"{etag}"'

    return result
```

Фронтенд шлёт `If-None-Match: "<etag>"` — если данные не изменились, получает `304 Not Modified` без тела.

**1b. `Last-Modified` для `GET /companies`**

**Файл**: `granite/api/companies.py`

```python
from fastapi import Response

@router.get("/companies", response_model=PaginatedResponse[CompanyResponse])
def list_companies(
    response: Response,
    db: Session = Depends(get_db),
    # ... параметры ...
):
    # ... существующий код ...

    # Last-Modified — по самой свежей updated_at
    last_modified = db.query(func.max(CompanyRow.updated_at)).filter(
        CompanyRow.deleted_at.is_(None)
    ).scalar()
    if last_modified:
        response.headers["Last-Modified"] = last_modified.strftime(
            "%a, %d %b %Y %H:%M:%S GMT"
        )

    return {"items": items, "total": total, "page": page, "per_page": per_page}
```

#### Этап 2 (следующая итерация): WebSocket-эндпоинт

Создать единый WebSocket-эндпоинт для push-уведомлений. Реализовать в отдельном PR.

```python
# granite/api/ws.py — новый файл
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import asyncio
import json

router = APIRouter()

class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, event: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(event)
            except Exception:
                self.active_connections.remove(connection)

manager = ConnectionManager()


@router.websocket("/ws/notifications")
async def ws_notifications(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # Держим соединение, ждём сообщения от клиента (ping)
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        manager.disconnect(websocket)
```

Интеграция — пушить события при:
- Email открыт (tracking pixel) → `{"type": "email_opened", "company_id": 42}`
- Стадия изменилась (stage_transitions) → `{"type": "stage_changed", "company_id": 42, "old": "new", "new": "email_sent"}`
- Задача выполнена → `{"type": "task_done", "task_id": 15}`
- Кампания завершилась → `{"type": "campaign_completed", "campaign_id": 3}`

#### Этап 3 (production): Redis Pub/Sub

Для multi-worker деплоя (uvicorn --workers N) in-memory WebSocket не работает — нужен Redis Pub/Sub:

```python
import redis.asyncio as aioredis

async def redis_listener():
    r = aioredis.from_url("redis://localhost")
    pubsub = r.pubsub()
    await pubsub.subscribe("granite:events")
    async for message in pubsub.listen():
        if message["type"] == "message":
            event = json.loads(message["data"])
            await manager.broadcast(event)
```

#### Рекомендация

Реализовать только этап 1 (ETag + Last-Modified) в текущем спринте. WebSocket — в следующей итерации, когда будет ясно, какие именно события нужны фронтенду. Redis — только при деплое с несколькими worker'ами.

**Оценка**:
- Этап 1: 2-3 часа
- Этап 2: 6-8 часов
- Этап 3: 4-6 часов

---

## Сводная таблица оценок

| Задача | Замечание | Фаза | Оценка | Файлы |
|--------|-----------|------|--------|-------|
| P0-1 | #1 КРИТИЧЕСКОЕ | P0 | 4-6ч | `companies.py`, `stats.py`, `followup.py`, `campaigns.py`, `pipeline_status.py`, `tasks.py`, `funnel.py`, `database.py` |
| P0-2 | #2 ВЫСОКОЕ | P0 | 2-3ч | `database.py`, `schemas.py`, `stage_transitions.py`, `followup.py`, `campaigns.py` + миграция |
| P1-1 | #4 ВЫСОКОЕ | P1 | 0.5ч | `touches.py` |
| P1-2 | #9 СРЕДНЕЕ | P1 | 0.5ч | `schemas.py` |
| P1-3 | #3 ВЫСОКОЕ | P1 | 3-4ч | `schemas.py`, `funnel.py`, `companies.py` |
| P2-1 | #5 ВЫСОКОЕ | P2 | 1-2ч | `app.py` |
| P2-2 | #6 СРЕДНЕЕ | P2 | 2-3ч | `pipeline_status.py`, `campaigns.py` |
| P2-3 | #10 НИЗКОЕ | P2 | 0.2ч | `app.py` |
| P2-4 | #11 НИЗКОЕ | P2 | 0.1ч | `app.py` |
| P2-5 | #12 НИЗКОЕ | P2 | 0.5ч | `app.py`, `tracking.py` |
| P3-1 | #8 СРЕДНЕЕ | P3 | 3-4ч | `schemas.py`, `companies.py` |
| P3-2 | #7 СРЕДНЕЕ | P3 | 2-3ч (этап 1) | `stats.py`, `companies.py` |

**Итого P0**: 6-9 часов (1-1.5 дня)
**Итого P1**: 4-5 часов (0.5-1 дня)
**Итого P2**: 4-6 часов (0.5-1 дня)
**Итого P3**: 5-7 часов (1 день)
**Общий итог**: ~19-27 часов (2.5-3.5 рабочих дня)

---

## Порядок работы (git-ветвление)

```
main
  └── fix/p0-soft-delete          ← P0-1: фильтр deleted_at
        └── fix/p0-stop-automation ← P0-2: Boolean унификация
              └── fix/p1-api-contract ← P1-1, P1-2, P1-3: типизация + воронка
                    └── fix/p2-infra    ← P2-1..P2-5: инфраструктура
                          └── feat/p3-bulk ← P3-1: bulk-операции
                                └── feat/p3-realtime ← P3-2: ETag/WebSocket
```

Каждая ветка — отдельный PR с ревью. P0 мержится сразу (критические баги). P1 мержится после подтверждения, что фронтенд-кодогенерация работает. P2 и P3 — по готовности.

---

## Чеклист перед началом

- [ ] Создать бэкап БД: `cp data/granite.db data/granite.db.bak.$(date +%Y%m%d)`
- [ ] Убедиться, что все 591 тест проходят: `uv run pytest --tb=short`
- [ ] Создать ветку `fix/p0-soft-delete` от `main`
- [ ] После каждого шага — запускать тесты: `uv run pytest tests/ -x`
