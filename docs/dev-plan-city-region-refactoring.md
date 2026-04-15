# Дев-план: Рефакторинг привязки к городу/региону

**Дата:** 2026-04-16
**Статус:** Approved
**БД:** удалена — обратная совместимость не требуется
**Цель:** Искать по городу (не региону), переназначать компании в правильный город после обогащения, хранить регион в БД, собирать неизвестные города для проверки.

---

## Текущее состояние (проблемы)

### 1. Поиск по региону вместо города
`web_search.py:663`:
```python
search_query = f"{query} {region_name}"  # "гранитная мастерская Хакасия"
```
Для Абазы (17к населения) DuckDuckGo возвращает компании из Абакана (столица, 180к). ~20 из 21 результата — нерелевантны.

### 2. Нет колонки `region` в БД
Все таблицы (`raw_companies`, `companies`, `enriched_companies`) хранят только `city` (String, без FK). Регион вычисляется на лету через `regions.yaml`, но нигде не сохраняется. API и экспорт не имеют фильтра по региону.

### 3. Нет справочника городов в БД
Города — просто строки. Нет проверки на опечатки, нет FK на справочник. Если web_search найдёт компанию из города не из списка — она сохранится с произвольным `city`.

### 4. Нет механизма переназначения города
Если при обогащении выясняется, что компания из другого города (name="Гранитная мастерская в Абакане" при scraping city=Абаза) — она остаётся привязана к Абазе.

### 5. Дублирование логики падежей
`web_search.py:_build_foreign_city_roots()` (строки 337-380) генерирует корни падежей для фильтрации. Эта же логика нужна для `detect_city()`, но сейчас нигде не переиспользуется.

---

## Архитектура решения

### Обзор изменений

```
regions.yaml ──→ cities_ref (новая таблица)
                     │
                     ▼
raw_companies ──→ companies ──→ enriched_companies
   +city            +city         +city
   +region          +region        +region
                                   │
                                   ▼
                          enrichment_phase:
                          detect_city() → reassign city + region
                                   │
                                   ▼
                          unmatched_cities (новая таблица)
```

### Принципы

1. **Не удалять, переназначать.** Компания из чужого города — не мусор, просто в другом городе.
2. **Справочник — источник истины.** `cities_ref` заполняется из `regions.yaml` при старте.
3. **Неизвестные города — не терять.** Всё, что не совпало со справочником — в `unmatched_cities` для ручной проверки.
4. **Чистая БД.** Обратная совместимость не требуется — все колонки NOT NULL, чистая схема.

---

## Детальный план по файлам

### 1. БД: Новая таблица `cities_ref`

**Файл:** `granite/database.py`

**Новая модель:**
```python
class CityRefRow(Base):
    """Справочник городов. Заполняется из regions.yaml."""
    __tablename__ = "cities_ref"

    name = Column(String, primary_key=True)            # "Абаза"
    region = Column(String, nullable=False, index=True)  # "Республика Хакасия"
    is_doppelganger = Column(Boolean, default=False)      # True для 5 городов-двойников
    is_populated = Column(Boolean, default=False)          # True после скрапинга города
```

**Почему String PK, а не Integer id?**
- `city` в `companies`/`enriched_companies` — String
- Прямой JOIN без дополнительного lookup
- Имя города — уникально по определению (кроме 5 двойников, которые помечены)

**Заполнение:**
- При первом запуске пайплайна (или отдельной CLI-командой `seed-cities`)
- Читает `regions.yaml`, вставляет строки в `cities_ref`
- Для 5 двойников: `is_doppelganger = True`
- `INSERT OR IGNORE` — безопасен для повторного вызова

**Миграция:**
- Alembic-миграция: `add_cities_ref_and_region`

---

### 2. БД: Новая таблица `unmatched_cities`

**Файл:** `granite/database.py`

**Новая модель:**
```python
class UnmatchedCityRow(Base):
    """Города, не найденные в справочнике. Для ручной проверки."""
    __tablename__ = "unmatched_cities"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False, unique=True, index=True)
    detected_from = Column(String, nullable=False, default="")   # "enrichment" / "web_search" / "dedup"
    context = Column(Text, nullable=False, default="")           # Текст, откуда извлечён
    company_ids = Column(JSON, default=list)                     # [id1, id2, ...]
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    resolved = Column(Boolean, default=False)
    resolved_to = Column(String, nullable=True)                  # Куда переназначен (если resolved)
```

**Когда попадает:**
- `detect_city()` не нашёл город в `cities_ref`
- `city` из `companies`/`enriched_companies` отсутствует в `cities_ref`

**Зачем:**
- Не терять контакты из мелких посёлков, которых нет в `regions.yaml`
- Собрать список кандидатов для расширения `regions.yaml`
- Ручная проверка: `resolved=True` + `resolved_to="Абаза"` → массовый апдейт компаний

---

### 3. БД: Добавить колонку `region` во все таблицы с городами

**Файл:** `granite/database.py` + Alembic миграция

**Изменения:**

| Таблица | Добавить | Nullable |
|---------|----------|----------|
| `raw_companies` | `region = Column(String, nullable=False, index=True, default="")` | **NOT NULL** |
| `companies` | `region = Column(String, nullable=False, index=True, default="")` | **NOT NULL** |
| `enriched_companies` | `region = Column(String, nullable=False, index=True, default="")` | **NOT NULL** |

**Почему `region` во всех таблицах:**
- БД чистая — не нужно мигрировать существующие данные
- `raw_companies`: регион известен сразу (из `city_config.region`), не нужно вычислять позже
- `companies` и `enriched_companies`: регион обновляется при переназначении города
- Default `""` — на случай если город не найден в справочнике (вместе с записью в `unmatched_cities`)

**Как заполняется:**
- **raw_companies**: при скрапинге — `city_config.get("region", "")` (уже доступно из base.py)
- **companies**: при dedup — `lookup_region(city)` из cities_ref / regions.yaml
- **enriched_companies**: при обогащении — берётся из CompanyRow, обновляется при reassign
- **reassign**: `detect_city()` → canonical city → `lookup_region(city)` → обновить region

---

### 4. `base.py`: Сохранять `region` в RawCompany

**Файл:** `granite/scrapers/base.py`

**Изменение в `BaseScraper.__init__()`** (или в `run()`):

```python
# Убедиться что city_config возвращает region
# (уже работает — _get_city_config() возвращает {"region": "Республика Хакасия", "name": "Абаза"})
```

**Изменение в скреперах** (jsprav, web_search, jsprav_playwright):

При создании `RawCompany`:
```python
RawCompany(
    source=Source.WEB_SEARCH,
    source_url=url,
    name=title,
    phones=[],
    address_raw="",
    website=url,
    emails=[],
    city=self.city,
    region=self.city_config.get("region", ""),   # <-- новое поле
)
```

**Изменение в `scraping_phase.py:_save_raw()`** (строка 222):

```python
row = RawCompanyRow(
    source=r.source.value,
    ...
    city=r.city,
    region=r.region,   # <-- новое поле
    ...
)
```

---

### 5. `region_resolver.py`: Общая утилита падежей + `detect_city()`

**Файл:** `granite/pipeline/region_resolver.py`

#### 5.1. Новая функция `build_city_lookup()`

Вынести из `web_search.py:_build_foreign_city_roots()` в общую утилиту:

```python
def build_city_lookup() -> tuple[dict[str, str | None], list[str]]:
    """Построить lookup-структуру для поиска городов в тексте.

    Returns:
        (city_lookup, sorted_roots)
        - city_lookup: {variant_lower: canonical_name | None}
          {"абакан": "Абакан", "абаканск": "Абакан", ...}
          None = двойник (неоднозначно)
        - sorted_roots: список корней, отсортированных по длине (длинные первыми)

    Корни для каждого города:
        - Полное имя lowercase: "москва"
        - Префикс len-1 (для падежей): "москв" ловит "Москве"
        - Корень без "ь": "пермь" → "перм" ловит "в Перми"
    """
```

**Кэширование:** Результат кэшируется на уровне модуля (как `_REGIONS_CACHE`).

#### 5.2. Новая функция `detect_city()`

```python
def detect_city(
    text: str,
    exclude_city: str | None = None,
) -> str | None:
    """Найти упоминание города из regions.yaml в тексте.

    Args:
        text: enriched name + address для анализа
        exclude_city: текущий город (не переназначать в себя)

    Returns:
        Canonical city name или None.

    Примеры:
        "Гранитная мастерская в Абакане" → "Абакан"
        "ул. Промышленная, 7Е, Абакан" → "Абакан"
        "Памятники Абаза" exclude="Абаза" → None
        "Памятники Кировск" → None  # двойник, неоднозначно
    """
```

**Логика:**
1. `text_lower = text.lower()`
2. Для каждого `root` из `sorted_roots` (длинные первыми):
   - `pos = text_lower.find(root)`
   - Проверяем word boundary: `pos == 0 or not text_lower[pos-1].isalpha()`
   - Если совпал → смотрим в `city_lookup[root]`
     - canonical name ≠ exclude_city → return canonical name
     - canonical name == exclude_city → skip
     - `None` (двойник) → skip (неоднозначно)
3. Не нашли → return None

#### 5.3. Новая функция `seed_cities_table()`

```python
def seed_cities_table(db: Database) -> int:
    """Заполнить cities_ref из regions.yaml.

    INSERT OR IGNORE — безопасен для повторного вызова.
    Returns: количество вставленных строк.
    """
```

Вызывается в `PipelineManager.__init__()` и в CLI-команде `seed-cities`.

#### 5.4. Новый метод `lookup_region()`

```python
def lookup_region(self, city: str) -> str:
    """Найти регион для города.

    Returns:
        Название региона или "" если не найден.
    """
```

Обёртка над `_find_city_region()`, возвращает `""` вместо `None` (NOT NULL в БД).

---

### 6. `web_search.py`: Искать по ГОРОДУ + упростить через общую утилиту

**Файл:** `granite/scrapers/web_search.py`

#### 6.1. Строка 663: изменить запрос

```python
# Было:
region_name = self.city_config.get("region", self.city)
search_query = f"{query} {region_name}"

# Стало:
search_query = f"{query} {self.city}"
```

`region_name` больше не нужен для поиска. Переменную можно удалить.

#### 6.2. `_build_foreign_city_roots()` → через общую утилиту

```python
def _build_foreign_city_roots(self) -> list[str]:
    """Строит список корней городов из ДРУГИХ регионов.

    Использует build_city_lookup() из region_resolver
    вместо дублирования логики падежей.
    """
    from granite.pipeline.region_resolver import build_city_lookup, _load_regions
    target_region = self.city_config.get("region", "")
    if not target_region:
        return []

    regions = _load_regions()
    target_cities = set(regions.get(target_region, []) or [])

    city_lookup, sorted_roots = build_city_lookup()
    # Фильтруем: оставляем корни только городов НЕ из текущего региона
    return [
        root for root in sorted_roots
        if city_lookup.get(root) and city_lookup[root] not in target_cities
    ]
```

~45 строк → ~15 строк.

#### 6.3. `_title_mentions_foreign_city()` — без изменений

Логика фильтрации остаётся. Меняется только источник данных.

#### 6.4. RawCompany — добавить region

Строка ~680:
```python
companies.append(
    RawCompany(
        source=Source.WEB_SEARCH,
        ...
        city=self.city,
        region=self.city_config.get("region", ""),   # <-- новое
    )
)
```

---

### 7. `enrichment_phase.py`: Переназначение города после обогащения

**Файл:** `granite/pipeline/enrichment_phase.py`

#### 7.1. Новый метод `_reassign_cities()`

```python
def _reassign_cities(
    self,
    session,
    records: list,
    current_city: str,
    name_attr: str = "name_best",
) -> int:
    """Проверить enriched данные и переназначить город при необходимости.

    Для каждой записи:
    1. Берёт name + address_raw
    2. detect_city(text, exclude_city=current_city)
    3. Если нашли другой город → обновить city + region в CompanyRow и EnrichedCompanyRow
    4. Если город не из справочника → записать в unmatched_cities

    Returns:
        Количество переназначенных компаний.
    """
```

**Детали:**
- Ищет `EnrichedCompanyRow` по `record.id`
- Обновляет `erow.city = real_city`, `erow.region = lookup_region(real_city)`
- Обновляет `CompanyRow.city = real_city`, `CompanyRow.region = lookup_region(real_city)`
- Если `real_city` есть в `cities_ref` — обновляет `is_populated=True`
- Если `real_city` НЕ в `cities_ref` — добавляет в `unmatched_cities` с `company_ids=[record.id]`
- Логирует: `"Переназначен: {name} — {current_city} → {real_city}"`

#### 7.2. Вызов в `run()` (sync)

После `_run_deep_enrich_for()` (строка 127):

```python
# ПРОХОД 3: переназначение города по обогащённым данным
reassigned = self._reassign_cities(session, companies, city, name_attr="name_best")
if reassigned:
    print_status(
        f"Переназначено {reassigned} компаний в другие города", "info"
    )
```

#### 7.3. Вызов в `run_async()`

Аналогично после строки 228:

```python
# ПРОХОД 3: переназначение города по обогащённым данным
with self.db.session_scope() as session:
    enriched_companies = session.query(EnrichedCompanyRow).filter_by(city=city).all()
    reassigned = self._reassign_cities(session, enriched_companies, city, name_attr="name")
    if reassigned:
        print_status(
            f"Переназначено {reassigned} компаний в другие города", "info"
        )
```

#### 7.4. Обновить `_print_enriched_status()`

Добавить индикатор переназначения:

```python
if erow.city != current_city:
    parts.append(f"→ {erow.city}")
```

---

### 8. `dedup_phase.py`: Заполнять `region` + записывать неизвестные города

**Файл:** `granite/pipeline/dedup_phase.py`

#### 8.1. При создании CompanyRow (строка 118)

```python
city_name = merged["city"]
region_name = ""
try:
    from granite.pipeline.region_resolver import RegionResolver
    resolver = RegionResolver(self.config or {})
    region_name = resolver.lookup_region(city_name)
except Exception:
    pass

row = CompanyRow(
    name_best=merged["name_best"],
    ...
    city=city_name,
    region=region_name,
    ...
)
```

#### 8.2. Запись неизвестных городов в `unmatched_cities`

После создания `CompanyRow`, если `region_name == ""`:

```python
if not region_name:
    from granite.database import UnmatchedCityRow
    existing = session.query(UnmatchedCityRow).filter_by(name=city_name).first()
    if not existing:
        session.add(UnmatchedCityRow(
            name=city_name,
            detected_from="dedup",
            context=merged["name_best"],
            company_ids=[row.id],
        ))
    else:
        # Добавить id компании в существующую запись
        ids = existing.company_ids or []
        if row.id not in ids:
            ids.append(row.id)
            existing.company_ids = ids
```

---

### 9. `manager.py`: seed_cities + региональный проход + unmatched review

**Файл:** `granite/pipeline/manager.py`

#### 9.1. Вызов `seed_cities_table()` при старте

```python
def __init__(self, config, db):
    ...
    # Заполняем справочник городов при старте
    from granite.pipeline.region_resolver import seed_cities_table
    seed_cities_table(db)
```

#### 9.2. Новый метод `run_regional_pass()`

```python
def run_regional_pass(self) -> dict[str, int]:
    """Региональный поиск: для каждого региона — поиск по региону.

    1. Берёт queries из config.yaml
    2. Для каждой пары (query, region): DDG поиск
    3. Для каждого результата: парсит сайт
    4. detect_city(enriched_name + address) → определяет город
    5. Сохраняет под правильным городом с правильным регионом

    Returns:
        {region: count} — сколько новых компаний добавлено по каждому региону.
    """
```

**Детали:**
- Пропускает регионы, где все города уже имеют enriched-записи
- DDG query: `f"{query} {region_name}"`
- Для каждого URL → scrape → enriched name/address
- `detect_city()` → canonical city
- Если city в этом регионе → создать CompanyRow + EnrichedCompanyRow
- Если city в другом регионе → пропускает
- Если city не определён → `unmatched_cities`
- Дедуп: проверяет по phone/website перед вставкой
- **Важно:** для каждой созданной CompanyRow сразу заполняется `region` из cities_ref

#### 9.3. Новый метод `run_unmatched_review()`

```python
def run_unmatched_review(self) -> list[dict]:
    """Вывести список неразрешённых городов из unmatched_cities.

    Returns:
        [{"name": "...", "count": N, "context": "..."}]
    """
```

---

### 10. `models.py`: Добавить `region` в RawCompany

**Файл:** `granite/models.py`

```python
@dataclass
class RawCompany:
    source: Source
    source_url: str = ""
    name: str = ""
    phones: list[str] = field(default_factory=list)
    address_raw: str = ""
    website: str = ""
    emails: list[str] = field(default_factory=list)
    city: str = ""
    region: str = ""          # <-- новое поле
    geo: list[float] | None = None
    messengers: dict = field(default_factory=dict)
    scraped_at: datetime | None = None
```

---

### 11. `cli.py`: Новые команды

**Файл:** `cli.py`

#### 11.1. Команда `regional`

```python
@app.command()
def regional():
    """Региональный поиск по всем регионам (после основного скрапинга).

    Для каждого региона запускает web_search с региональным запросом.
    Результаты автоматически привязываются к правильному городу.
    """
    config = load_config()
    setup_logging(config)
    db = Database(config_path=_config_path)
    manager = PipelineManager(config, db)
    results = manager.run_regional_pass()

    total = sum(results.values())
    print_status(f"Региональный поиск: {total} новых компаний", "success")
    for region, count in sorted(results.items()):
        if count > 0:
            print(f"  {region}: +{count}")
    db.engine.dispose()
```

#### 11.2. Команда `seed-cities`

```python
@app.command()
def seed_cities():
    """Заполнить справочник городов из regions.yaml."""
    config = load_config()
    setup_logging(config)
    db = Database(config_path=_config_path)

    from granite.pipeline.region_resolver import seed_cities_table
    count = seed_cities_table(db)
    print_status(f"Заполнено {count} городов в справочник", "success")
    db.engine.dispose()
```

#### 11.3. Команда `unmatched`

```python
@app.command()
def unmatched():
    """Показать неразрешённые города (не из regions.yaml)."""
    config = load_config()
    setup_logging(config)
    db = Database(config_path=_config_path)
    manager = PipelineManager(config, db)

    results = manager.run_unmatched_review()
    if not results:
        print_status("Нет неразрешённых городов", "success")
        return

    print_status(f"Неразрешённых городов: {len(results)}", "warning")
    for r in results:
        print(f"  [{r['count']} компаний] {r['name']} — {r['context']}")
    db.engine.dispose()
```

---

### 12. API: Фильтр по региону

**Файл:** `granite/api/companies.py`

Добавить параметр `region`:

```python
@router.get("/companies")
def list_companies(
    city: Optional[str] = None,
    region: Optional[str] = None,   # <-- новый
    ...
):
    q = session.query(CompanyRow)
    if city:
        q = q.filter(CompanyRow.city == city)
    if region:
        q = q.filter(CompanyRow.region == region)
```

---

### 13. Alembic миграция

**Новый файл:** `alembic/versions/YYYYMMDD_add_cities_ref_and_region.py`

```python
def upgrade():
    # 1. cities_ref
    op.create_table(
        "cities_ref",
        sa.Column("name", sa.String, primary_key=True),
        sa.Column("region", sa.String, nullable=False, index=True),
        sa.Column("is_doppelganger", sa.Boolean, default=False),
        sa.Column("is_populated", sa.Boolean, default=False),
    )

    # 2. unmatched_cities
    op.create_table(
        "unmatched_cities",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("name", sa.String, nullable=False, unique=True, index=True),
        sa.Column("detected_from", sa.String, nullable=False, default=""),
        sa.Column("context", sa.Text, nullable=False, default=""),
        sa.Column("company_ids", sa.JSON, default=list),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("resolved", sa.Boolean, default=False),
        sa.Column("resolved_to", sa.String, nullable=True),
    )

    # 3. region column — NOT NULL с default "" (БД чистая)
    op.add_column("raw_companies", sa.Column("region", sa.String, nullable=False, server_default="", index=True))
    op.add_column("companies", sa.Column("region", sa.String, nullable=False, server_default="", index=True))
    op.add_column("enriched_companies", sa.Column("region", sa.String, nullable=False, server_default="", index=True))
```

**Примечание:** `downgrade()` не нужен — БД удалена, откатывать нечего.

---

### 14. Тесты

**Файл:** `tests/test_region_resolver.py` (новые)

| Тест | Описание |
|------|----------|
| `test_build_city_lookup_basic` | Корректность lookup для "Абакан" |
| `test_build_city_lookup_doppelganger` | 5 двойников помечены None |
| `test_build_city_lookup_variants` | Падежи: "москв" → "Москва", "перм" → "Пермь" |
| `test_detect_city_basic` | "Гранитная мастерская в Абакане" → "Абакан" |
| `test_detect_city_address` | "ул. Промышленная, 7, Абакан" → "Абакан" |
| `test_detect_city_exclude_self` | "Памятники Абаза" exclude="Абаза" → None |
| `test_detect_city_doppelganger` | "Памятники Кировск" → None (неоднозначно) |
| `test_detect_city_word_boundary` | Не ловит город в середине другого слова |
| `test_detect_city_longest_match` | "Саяногорск" > "Саян" |
| `test_seed_cities_table` | Заполнение cities_ref из regions.yaml |
| `test_lookup_region` | "Абаза" → "Республика Хакасия" |
| `test_lookup_region_unknown` | "НесуществующийГород" → "" |

**Файл:** `tests/test_enrichment_reassign.py` (новые)

| Тест | Описание |
|------|----------|
| `test_reassign_city_basic` | "в Абакане" при city=Абаза → city="Абакан", region="Хакасия" |
| `test_reassign_city_same` | Компания из Абазы → не переназначается |
| `test_reassign_city_unmatched` | Неизвестный город → unmatched_cities |
| `test_reassign_city_preserves_data` | Переназначение не трогает phones/emails/website |
| `test_reassign_city_doppelganger` | Двойник → не переназначается (неоднозначно) |

**Файл:** `tests/test_web_search_city_query.py` (обновить существующие)

| Тест | Описание |
|------|----------|
| `test_search_uses_city_not_region` | Query содержит город, не регион |
| `test_foreign_city_filter_via_shared_lookup` | Фильтр чужого города через общий lookup |
| `test_raw_company_has_region` | RawCompany содержит region |

---

## Порядок реализации

```
Этап 1: Схема БД + модели
  ├─ 1.1. database.py: CityRefRow, UnmatchedCityRow
  ├─ 1.2. database.py: region column (NOT NULL) в raw_companies, companies, enriched_companies
  ├─ 1.3. models.py: region в RawCompany
  └─ 1.4. Alembic миграция

Этап 2: Инфраструктура (без изменения поведения скрапинга)
  ├─ 2.1. region_resolver.py: build_city_lookup(), detect_city(), seed_cities_table(), lookup_region()
  ├─ 2.2. web_search.py: _build_foreign_city_roots() через build_city_lookup()
  └─ 2.3. Тесты для detect_city() и build_city_lookup()

Этап 3: Основной фикс — искать по городу
  ├─ 3.1. web_search.py: строка 663 — город вместо региона
  ├─ 3.2. base.py / скреперы: передавать region в RawCompany
  ├─ 3.3. scraping_phase.py: сохранять region в _save_raw()
  └─ 3.4. Тесты web_search

Этап 4: Переназначение городов
  ├─ 4.1. enrichment_phase.py: _reassign_cities()
  ├─ 4.2. dedup_phase.py: заполнение region + unmatched_cities
  └─ 4.3. Тесты переназначения

Этап 5: Региональный проход
  ├─ 5.1. manager.py: seed_cities_table() в __init__
  ├─ 5.2. manager.py: run_regional_pass(), run_unmatched_review()
  └─ 5.3. cli.py: команды regional, seed-cities, unmatched

Этап 6: API и экспорт
  ├─ 6.1. api/companies.py: фильтр по region
  └─ 6.2. exporters/csv.py: столбец region

Этап 7: Финализация
  ├─ 7.1. Запустить все тесты
  └─ 7.2. Обновить worklog
```

---

## Риски и митигация

| Риск | Митигация |
|------|-----------|
| `detect_city()` ложно срабатывает (общие слова типа "Белый" в "Белая Калитва") | Word boundary + минимальная длина 5 символов для корней + ручная проверка через unmatched_cities |
| 5 городов-двойников невозможно разрешить без контекста | `city_lookup[root] = None` → `detect_city()` возвращает None |
| Региональный проход находит дубли | Дедуп по phone/website перед вставкой |
| DDG rate-limit при региональном проходе (82 региона × 5 queries) | Existing `_search_lock`, `adaptive_delay()` |
| `build_city_lookup()` медленный (1098 городов) | Кэширование на уровне модуля, вызывается один раз |

---

## Пример: Жизненный цикл компании

```
1. Скрапинг Абазы
   DDG: "гранитная мастерская памятники Абаза"
   → RawCompany(name="Гранит Хакасии", city="Абаза", region="Республика Хакасия")

2. Дедуп
   → CompanyRow(city="Абаза", region="Республика Хакасия")

3. Обогащение
   Парсим сайт → title="Гранит Хакасии — Абакан"
   _reassign_cities():
     detect_city("Гранит Хакасии — Абакан", exclude="Абаза")
     → "Абакан" (есть в cities_ref, не exclude)
     → CompanyRow.city = "Абакан", region = "Республика Хакасия"
     → EnrichedCompanyRow.city = "Абакан", region = "Республика Хакасия"

4. Региональный проход (run all → regional)
   DDG: "гранитная мастерская памятники Республика Хакасия"
   → Находит сайт "ritualstoun.ru"
   → detect_city("Ритуал Стоун, Саяногорск") → "Саяногорск"
   → lookup_region("Саяногорск") → "Республика Хакасия"
   → CompanyRow(city="Саяногорск", region="Республика Хакасия")

5. Неизвестный город
   DDG: "памятники из гранита Абаза"
   → Находит сайт с адресом "пос. Вершина Тёи"
   → detect_city("пос. Вершина Тёи") → None (нет в cities_ref)
   → UnmatchedCityRow(name="Вершина Тёи", detected_from="enrichment")
   → Позже: ручная проверка → resolved_to="Абаза"
   → Массовый апдейт: CompanyRow.city = "Абаза" для всех company_ids
```
