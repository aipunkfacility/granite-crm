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

Все таблицы (`raw_companies`, `companies`) хранят только `city` (String, без FK). Регион вычисляется на лету через `regions.yaml`, но нигде не сохраняется. API и экспорт не имеют фильтра по региону.

### 3. Нет справочника городов в БД

Города — просто строки. Нет проверки на опечатки, нет UNIQUE constraint. Если web_search найдёт компанию из города не из списка — она сохранится с произвольным `city`.

### 4. Нет механизма переназначения города

Если при обогащении выясняется, что компания из другого города (name="Гранитная мастерская в Абакане" при scraping city=Абаза) — она остаётся привязана к Абазе.

### 5. Дублирование логики падежей

`web_search.py:_build_foreign_city_roots()` (строки 337-380) генерирует корни падежей для фильтрации. Эта же логика нужна для `detect_city()`, но сейчас нигде не переиспользуется.

---

## Архитектура решения

### Обзор изменений

```
regions.yaml ──→ cities_ref (новая таблица, INTEGER PK + UNIQUE name)
                     │
                     ▼
raw_companies ──→ companies ──→ enriched_companies
   +city            +city         +city (region через JOIN)
   +region          +region
                     │
                     ▼
            enrichment_phase:
            detect_city() → reassign city + region
                     │
                     ▼
            unmatched_cities (новая таблица, без JSON company_ids)
```

### Принципы

1. **Не удалять, переназначать.** Компания из чужого города — не мусор, просто в другом городе.
2. **Справочник — источник истины.** `cities_ref` заполняется из `regions.yaml` при старте.
3. **Неизвестные города — не терять.** Всё, что не совпало со справочником — в `unmatched_cities` для ручной проверки.
4. **Чистая БД.** Обратная совместимость не требуется — все колонки NOT NULL, чистая схема.
5. **Region только в `raw_companies` и `companies`.** `enriched_companies` получает регион через JOIN — не дублируем.

---

## Детальный план по файлам

### 1. БД: Новая таблица `cities_ref`

**Файл:** `granite/database.py`

**Новая модель:**

```python
class CityRefRow(Base):
    """Справочник городов. Заполняется из regions.yaml."""
    __tablename__ = "cities_ref"

    id = Column(Integer, primary_key=True)                  # Integer PK
    name = Column(String, nullable=False, unique=True, index=True)  # "Абаза"
    region = Column(String, nullable=False, index=True)     # "Республика Хакасия"
    is_doppelganger = Column(Boolean, default=False)        # True для 5 городов-двойников
    is_populated = Column(Boolean, default=False)           # True после скрапинга города
```

**Почему Integer PK, а не String:**

- SQLite не поддерживает `ALTER TABLE ... ADD CONSTRAINT FK` — Integer PK оставляет путь к FK в будущем
- UNIQUE constraint на `name` гарантирует отсутствие дублей
- Case-insensitive UNIQUE в SQLite через COLLATE NOCASE — дополнительная защита
- `companies.city` остаётся String (без FK) — гибкость для новых городов из `unmatched_cities`

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
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    resolved = Column(Boolean, default=False)
    resolved_to = Column(String, nullable=True)                  # Куда переназначен (если resolved)
```

**Изменения против оригинального плана:**

- ~~`company_ids = Column(JSON)`~~ — удалено. JSON не индексируется в SQLite, сложно поддерживать консистентность.
- Вместо этого при просмотре `unmatched` делается `SELECT COUNT(*) FROM companies WHERE city = unmatched_city.name` — всегда актуально.

**Когда попадает:**

- `detect_city()` не нашёл город в `cities_ref`
- `city` из `companies` отсутствует в `cities_ref`

**Зачем:**

- Не терять контакты из мелких посёлков, которых нет в `regions.yaml`
- Собрать список кандидатов для расширения `regions.yaml`
- Ручная проверка: `resolved=True` + `resolved_to="Абаза"` → массовый апдейт компаний через `UPDATE companies SET city = resolved_to WHERE city = unmatched_name`

---

### 3. БД: Добавить колонку `region` в `raw_companies` и `companies`

**Файл:** `granite/database.py` + Alembic миграция

**Изменения:**

| Таблица | Добавить | Nullable |
|---------|----------|----------|
| `raw_companies` | `region = Column(String, nullable=False, index=True, default="")` | **NOT NULL** |
| `companies` | `region = Column(String, nullable=False, index=True, default="")` | **NOT NULL** |

**`enriched_companies` НЕ получает колонку `region`.** Регион берётся через JOIN с `companies`:

```python
session.query(CompanyRow.region, EnrichedCompanyRow.cms, ...) \
    .join(EnrichedCompanyRow)
```

**Почему только в двух таблицах:**

- БД чистая — не нужно мигрировать существующие данные
- `raw_companies`: регион известен сразу (из `city_config.region`), не нужно вычислять позже
- `companies`: регион обновляется при переназначении города — единственный источник истины
- ~~`enriched_companies`~~ — устраняет рассинхрон: не нужно обновлять region в двух таблицах при reassign

**Как заполняется:**

- **raw_companies**: при скрапинге — `city_config.get("region", "")` (уже доступно из base.py)
- **companies**: при dedup — `lookup_region(city)` из cities_ref / regions.yaml
- **reassign**: `detect_city()` → canonical city → `lookup_region(city)` → обновить region в CompanyRow

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

    Исключаются:
        - Стоп-слова (регионы, области, республики, края)
        - Корни короче 5 символов
    """
```

**Стоп-слова для фильтрации** (не включать в lookup):

```python
_STOP_WORDS = {
    "республика", "область", "край", "округ", "автономн",
    "ханты", "манси", "ненец", "чукот", "ямал",
    # Регионы, которые могут совпадать с названиями городов
}
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

    Приоритет совпадений (по убыванию):
        1. После предлогов/маркеров: "в Абакане", "г. Абакан", "город Абакан"
        2. После запятой: "ул. Ленина, Абакан"
        3. Просто вхождение с word boundary

    Примеры:
        "Гранитная мастерская в Абакане" → "Абакан"      # приоритет 1
        "ул. Промышленная, 7Е, Абакан" → "Абакан"         # приоритет 2
        "Гранит Хакасии" → None                            # "Хакасия" — стоп-слово
        "Памятники Абаза" exclude="Абаза" → None
        "Памятники Кировск" → None  # двойник, неоднозначно
    """
```

**Логика:**

1. `text_lower = text.lower()`
2. **ПРОХОД 1 (высокий приоритет):** Ищем паттерны `"в {root}"`, `"г. {root}"`, `"город {root}"`
   - Нашёл → return canonical name (если ≠ exclude_city)
3. **ПРОХОД 2 (средний приоритет):** Ищем после запятой/точки с запятой
   - Нашёл → return canonical name (если ≠ exclude_city)
4. **ПРОХОД 3 (низкий приоритет):** Для каждого `root` из `sorted_roots` (длинные первыми):
   - `pos = text_lower.find(root)`
   - Проверяем word boundary: `pos == 0 or not text_lower[pos-1].isalpha()`
   - Проверяем что root не часть другого слова: `pos + len(root) >= len(text_lower) or not text_lower[pos+len(root)].isalpha()`
   - Если совпал → смотрим в `city_lookup[root]`
     - canonical name ≠ exclude_city → return canonical name
     - canonical name == exclude_city → skip
     - `None` (двойник) → skip (неоднозначно)
5. Не нашли → return None

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
def lookup_region(city: str) -> str:
    """Найти регион для города.

    Returns:
        Название региона или "" если не найден.
    """
```

Обёртка над `_find_city_region()`, возвращает `""` вместо `None` (NOT NULL в БД). Top-level функция (не метод класса).

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

### 7. `scraping_phase.py`: Региональные запросы в основном потоке

**Файл:** `granite/pipeline/scraping_phase.py`

**Изменение:** Вместо отдельного `run_regional_pass()` — добавить региональные запросы к существующему скрапингу города.

Для города Абаза (регион: Республика Хакасия):

```python
# Основной запрос — по городу
queries = [f"{q} {self.city}" for q in base_queries]

# Региональные запросы — для поиска компаний из соседних городов того же региона
regional_queries = [f"{q} {region_name}" for q in base_queries]
queries.extend(regional_queries)
```

**Результат:** Компании из соседних городов того же региона будут найдены на основном скрапинге, а затем `_reassign_cities()` переназначит их в правильные города.

**Не нужно:**

- Отдельный `run_regional_pass()` в manager.py
- Отдельная CLI команда `regional`
- Дублирование scraping-логики

---

### 8. `enrichment_phase.py`: Переназначение города после обогащения

**Файл:** `granite/pipeline/enrichment_phase.py`

#### 8.1. Новый метод `_reassign_cities()`

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
    3. Если нашли другой город → обновить city + region в CompanyRow
    4. Если город не из справочника → записать в unmatched_cities

    Returns:
        Количество переназначенных компаний.
    """
```

**Детали:**

- Ищет `EnrichedCompanyRow` по `record.id`
- Обновляет `crow.city = real_city`, `crow.region = lookup_region(real_city)` (CompanyRow — источник истины)
- Обновляет `erow.city = real_city` (region не хранится — берётся через JOIN)
- Если `real_city` есть в `cities_ref` — обновляет `is_populated=True`
- Если `real_city` НЕ в `cities_ref` — добавляет в `unmatched_cities`
- Логирует: `"Переназначен: {name} — {current_city} → {real_city}"`

#### 8.2. Вызов в `run()` (sync)

После `_run_deep_enrich_for()` (строка 127):

```python
# ПРОХОД 3: переназначение города по обогащённым данным
reassigned = self._reassign_cities(session, companies, city, name_attr="name_best")
if reassigned:
    print_status(
        f"Переназначено {reassigned} компаний в другие города", "info"
    )
```

#### 8.3. Вызов в `run_async()`

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

#### 8.4. Обновить `_print_enriched_status()`

Добавить индикатор переназначения:

```python
if erow.city != current_city:
    parts.append(f"→ {erow.city}")
```

---

### 9. `dedup_phase.py`: Заполнять `region` + записывать неизвестные города

**Файл:** `granite/pipeline/dedup_phase.py`

#### 9.1. При создании CompanyRow (строка 118)

```python
city_name = merged["city"]
region_name = ""
try:
    from granite.pipeline.region_resolver import lookup_region
    region_name = lookup_region(city_name)
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

#### 9.2. Запись неизвестных городов в `unmatched_cities`

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
        ))
```

~~`company_ids` больше не сохраняется~~ — при просмотре `unmatched` делается COUNT по `companies.city`.

---

### 10. `manager.py`: seed_cities + unmatched review

**Файл:** `granite/pipeline/manager.py`

#### 10.1. Вызов `seed_cities_table()` при старте

```python
def __init__(self, config, db):
    ...
    # Заполняем справочник городов при старте
    from granite.pipeline.region_resolver import seed_cities_table
    seed_cities_table(db)
```

#### 10.2. Новый метод `run_unmatched_review()`

```python
def run_unmatched_review(self) -> list[dict]:
    """Вывести список неразрешённых городов из unmatched_cities.

    Returns:
        [{"name": "...", "count": N, "context": "..."}]
    """
```

**Детали:**

- `count` вычисляется через `SELECT COUNT(*) FROM companies WHERE city = unmatched_city.name`
- Не хранит company_ids — всегда актуальные данные

~~**`run_regional_pass()` удалён** — региональные запросы интегрированы в scraping_phase (секция 7).~~

---

### 11. `models.py`: Добавить `region` в RawCompany

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

### 12. `cli.py`: Новые команды

**Файл:** `cli.py`

~~**Команда `regional` удалена** — региональные запросы интегрированы в основной скрапинг.~~

#### 12.1. Команда `seed-cities`

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

#### 12.2. Команда `unmatched`

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

#### 12.3. Команда `cities status` (новая)

```python
@app.command("cities-status")
def cities_status():
    """Показать статус городов: проскрапленные / непроскрапленные."""
    config = load_config()
    setup_logging(config)
    db = Database(config_path=_config_path)

    with db.session_scope() as session:
        all_cities = session.query(CityRefRow).order_by(CityRefRow.region, CityRefRow.name).all()

    from collections import defaultdict
    by_region = defaultdict(lambda: {"total": 0, "populated": 0, "pending": 0, "pending_cities": []})
    for c in all_cities:
        region = c.region
        by_region[region]["total"] += 1
        if c.is_populated:
            by_region[region]["populated"] += 1
        else:
            by_region[region]["pending"] += 1
            by_region[region]["pending_cities"].append(c.name)

    for region, stats in sorted(by_region.items()):
        pending_list = ", ".join(stats["pending_cities"][:5])
        if len(stats["pending_cities"]) > 5:
            pending_list += f" ... и ещё {len(stats['pending_cities']) - 5}"
        status = "✅" if stats["pending"] == 0 else f"⏳ {stats['pending']}/{stats['total']}"
        print(f"{status} {region}: {pending_list}")

    db.engine.dispose()
```

---

### 13. API: Фильтр по региону

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

### 14. Alembic миграция

**Новый файл:** `alembic/versions/YYYYMMDD_add_cities_ref_and_region.py`

```python
def upgrade():
    # 1. cities_ref — INTEGER PK + UNIQUE name
    op.create_table(
        "cities_ref",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String, nullable=False, unique=True, index=True),
        sa.Column("region", sa.String, nullable=False, index=True),
        sa.Column("is_doppelganger", sa.Boolean, default=False),
        sa.Column("is_populated", sa.Boolean, default=False),
    )

    # 2. unmatched_cities — без JSON company_ids
    op.create_table(
        "unmatched_cities",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("name", sa.String, nullable=False, unique=True, index=True),
        sa.Column("detected_from", sa.String, nullable=False, default=""),
        sa.Column("context", sa.Text, nullable=False, default=""),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("resolved", sa.Boolean, default=False),
        sa.Column("resolved_to", sa.String, nullable=True),
    )

    # 3. region column — NOT NULL с default "" (БД чистая)
    op.add_column("raw_companies", sa.Column("region", sa.String, nullable=False, server_default="", index=True))
    op.add_column("companies", sa.Column("region", sa.String, nullable=False, server_default="", index=True))
    # enriched_companies НЕ получает region — берётся через JOIN с companies
```

**Примечание:** `downgrade()` не нужен — БД удалена, откатывать нечего.

---

### 15. Тесты

**Файл:** `tests/test_region_resolver.py` (новые)

| Тест | Описание |
|------|----------|
| `test_build_city_lookup_basic` | Корректность lookup для "Абакан" |
| `test_build_city_lookup_doppelganger` | 5 двойников помечены None |
| `test_build_city_lookup_variants` | Падежи: "москв" → "Москва", "перм" → "Пермь" |
| `test_build_city_lookup_stop_words` | "Хакасия", "область" — не попадают в lookup |
| `test_build_city_lookup_min_length` | Корни < 5 символов исключены |
| `test_detect_city_basic` | "Гранитная мастерская в Абакане" → "Абакан" |
| `test_detect_city_address` | "ул. Промышленная, 7, Абакан" → "Абакан" |
| `test_detect_city_preposition_priority` | "в Абакане" имеет приоритет над простым вхождением |
| `test_detect_city_exclude_self` | "Памятники Абаза" exclude="Абаза" → None |
| `test_detect_city_doppelganger` | "Памятники Кировск" → None (неоднозначно) |
| `test_detect_city_word_boundary` | Не ловит город в середине другого слова |
| `test_detect_city_longest_match` | "Саяногорск" > "Саян" |
| `test_detect_city_stop_word` | "Гранит Хакасии" → None (Хакасия — стоп-слово) |
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
| `test_reassign_integration` | **Интеграционный:** мок DDG + мок HTTP → полный цикл scraping → dedup → enrichment → reassign → проверка city/region |

**Файл:** `tests/test_web_search_city_query.py` (обновить существующие)

| Тест | Описание |
|------|----------|
| `test_search_uses_city_not_region` | Query содержит город, не регион |
| `test_foreign_city_filter_via_shared_lookup` | Фильтр чужего города через общий lookup |
| `test_raw_company_has_region` | RawCompany содержит region |
| `test_regional_queries_in_scraping` | Региональные запросы добавляются к основным |

---

## Порядок реализации

```
Этап 1: Схема БД + модели
  ├─ 1.1. database.py: CityRefRow (INTEGER PK + UNIQUE name), UnmatchedCityRow (без JSON)
  ├─ 1.2. database.py: region column (NOT NULL) в raw_companies, companies
  ├─ 1.3. models.py: region в RawCompany
  ├─ 1.4. Alembic миграция
  └─ 1.5. uv run pytest -v — убедиться что существующие тесты проходят

Этап 2: Инфраструктура (без изменения поведения скрапинга)
  ├─ 2.1. region_resolver.py: build_city_lookup(), detect_city(), seed_cities_table(), lookup_region()
  │       (стоп-слова, min root length 5, приоритет предлогов)
  ├─ 2.2. web_search.py: _build_foreign_city_roots() через build_city_lookup()
  └─ 2.3. Тесты для detect_city(), build_city_lookup(), стоп-слов

Этап 3: Основной фикс — искать по городу
  ├─ 3.1. web_search.py: строка 663 — город вместо региона
  ├─ 3.2. scraping_phase.py: добавить региональные запросы к основным
  ├─ 3.3. base.py / скреперы: передавать region в RawCompany
  ├─ 3.4. scraping_phase.py: сохранять region в _save_raw()
  └─ 3.5. Тесты web_search + региональных запросов

Этап 4: Переназначение городов
  ├─ 4.1. enrichment_phase.py: _reassign_cities()
  ├─ 4.2. dedup_phase.py: заполнение region + unmatched_cities
  └─ 4.3. Тесты переназначения + интеграционный тест полного цикла

Этап 5: CLI и API
  ├─ 5.1. manager.py: seed_cities_table() в __init__, run_unmatched_review()
  ├─ 5.2. cli.py: команды seed-cities, unmatched, cities-status
  ├─ 5.3. api/companies.py: фильтр по region
  └─ 5.4. exporters/csv.py: столбец region

Этап 6: Финализация
  ├─ 6.1. Запустить все тесты: uv run pytest tests/ -v
  └─ 6.2. Обновить worklog
```

---

## Риски и митигация

| Риск | Митигация |
|------|-----------|
| `detect_city()` ложно срабатывает (общие слова типа "Белый" в "Белая Калитва") | Word boundary + минимальная длина 5 + стоп-слова + 3-проходный приоритет (предлоги > запятая > вхождение) |
| `detect_city()` ловит названия компаний ("Гранит Хакасии" → "Хакасия") | Стоп-слова исключают регионы/области/республики из lookup |
| 5 городов-двойников невозможно разрешить без контекста | `city_lookup[root] = None` → `detect_city()` возвращает None |
| Региональные запросы находят дубли | Дедуп по phone/website в dedup_phase |
| DDG rate-limit (дополнительные региональные запросы) | Existing `_search_lock`, `adaptive_delay()` — кол-во запросов удваивается, но лимиты те же |
| `build_city_lookup()` медленный (1098 городов) | Кэширование на уровне модуля, вызывается один раз за процесс |
| Integer PK усложняет lookup по имени | UNIQUE index на `name` — `WHERE name = ?` работает так же быстро как PK lookup |

---

## Пример: Жизненный цикл компании

```
1. Скрапинг Абазы
   DDG: "гранитная мастерская памятники Абаза"       ← по городу
   DDG: "гранитная мастерская памятники Хакасия"     ← региональный (соседние города)
   → RawCompany(name="Гранит Хакасии", city="Абаза", region="Республика Хакасия")

2. Дедуп
   → CompanyRow(city="Абаза", region="Республика Хакасия")

3. Обогащение
   Парсим сайт → title="Гранит Хакасии — Абакан"
   _reassign_cities():
     detect_city("Гранит Хакасии — Абакан", exclude="Абаза")
     → "Абакан" (есть в cities_ref, не exclude, приоритет — после дефиса/запятой)
     → CompanyRow.city = "Абакан", region = "Республика Хакасия"
     → EnrichedCompanyRow.city = "Абакан"  (region через JOIN)

4. Неизвестный город
   DDG: "памятники из гранита Абаза"
   → Находит сайт с адресом "пос. Вершина Тёи"
   → detect_city("пос. Вершина Тёи") → None (нет в cities_ref)
   → UnmatchedCityRow(name="Вершина Тёи", detected_from="enrichment")
   → Позже: ручная проверка → resolved_to="Абаза"
   → Массовый апдейт: UPDATE companies SET city = 'Абаза' WHERE city = 'Вершина Тёи'
```

---

## Изменения против оригинального плана (рецензия)

| # | Изменение | Причина |
|---|-----------|---------|
| 1 | **Integer PK** в `cities_ref`, не String PK | SQLite FK, CASCADE, защита от дублей |
| 2 | **Стоп-слова + приоритет предлогов** в `detect_city()` | "Гранит Хакасии" не должен детектиться как Хакасия |
| 3 | **Убран `region` из `enriched_companies`** | Рассинхрон, JOIN достаточно |
| 4 | **Региональные запросы в scraping_phase**, не отдельный проход | Не дублировать scraping-логику, удалить `run_regional_pass()` |
| 5 | **Упрощён `unmatched_cities`** — без JSON company_ids | JSON не индексируется, COUNT всегда актуален |
| 6 | **Добавлена `cities status` CLI** | Видеть какие города ещё не проскраплены |
| 7 | **Интеграционный тест полного цикла** | Проверка scraping → dedup → enrichment → reassign |
