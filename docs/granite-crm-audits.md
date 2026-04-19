# Granite CRM — Матрица аудитов

Проект: [granite-crm](https://github.com/aipunkfacility/granite-crm)
Дата: 2026-04-19

---

## Содержание

| # | Аудит | Критичность | Файлы-мишени |
|---|-------|-------------|-------------|
| 1 | Безопасность API и аутентификация | HIGH | `granite/api/app.py`, `granite/api/*.py` |
| 2 | Защита от SSRF и инъекций в скраперах | HIGH | `granite/utils.py`, `granite/scrapers/*.py`, `granite/enrichers/*.py` |
| 3 | Целостность данных и схемы БД | HIGH | `granite/database.py`, `alembic/versions/*.py` |
| 4 | Надёжность дедупликации | MEDIUM | `granite/dedup/*.py` |
| 5 | Качество скоринга и сегментации | MEDIUM | `granite/enrichers/classifier.py`, `config.yaml` |
| 6 | Консистентность API-эндпоинтов | MEDIUM | `granite/api/*.py`, `granite/api/schemas.py` |
| 7 | Покрытие тестами и граничные случаи | MEDIUM | `tests/*.py` |
| 8 | Производительность и масштабируемость | MEDIUM | `granite/api/*.py`, `granite/pipeline/*.py` |
| 9 | Конфигурация и production readiness | LOW | `config.yaml`, `.env`, `cli.py` |
| 10 | Обработка ошибок и устойчивость пайплайна | LOW | `granite/pipeline/manager.py`, `granite/pipeline/*.py` |

---

## Аудит 1: Безопасность API и аутентификация

**Критичность:** HIGH
**Область:** API-слой (`granite/api/app.py`, все роутеры)

### Что проверять

API использует middleware `api_key_auth_middleware` в `app.py:107-132`. Ключ читается из env `GRANITE_API_KEY`. Если переменная не задана — аутентификация **полностью отключена** (dev-режим). Это потенциальная проблема при деплое без настройки env.

CORS-origins по умолчанию включают `localhost:3000` и `localhost:5173` (`app.py:69-74`). При production-деплое нужно явно задать `CORS_ORIGINS`.

Нужно проверить:
- Сравнение API-ключа (`provided_key != expected_key` в `app.py:126`) — уязвимо к timing-attack. Использовать `hmac.compare_digest`.
- Отсутствие rate limiting на всех эндпоинтах, включая `POST /companies/{id}/send` (отправка мессенджеров) и `POST /campaigns/{id}/run` (запуск рассылки).
- Endpoint `GET /export/{city}.csv` — не валидирует `city` (может содержать path traversal: `../../etc/passwd`).
- Endpoint `GET /track/open/{tracking_id}.png` — tracking_id не валидируется на формат UUID; при подстановке SQL в `tracking_id` возможна инъекция (зависит от реализации tracking.py).
- Email sender (`granite/email/sender.py:81-84`) — body_text вставляется в HTML без экранирования (`<pre>` + `<img>`). Возможна XSS через тело письма (если клиент читает HTML).
- `PATCH /companies/{id}` — `setattr(contact, key, value)` в цикле (`companies.py:177-178`). Pydantic-схема `UpdateCompanyRequest` ограничивает поля, но если схема изменится — можно записать любое поле модели.
- Шаблоны (`CrmTemplateRow.render`) используют `str.replace` — безопасно от инъекции. Но template body может содержать произвольный HTML (для email) — нет санитизации.

### Промпт

```
Проведи аудит безопасности API Granite CRM.

Контекст: FastAPI-приложение с API-key auth (X-API-Key header).
Код: granite/api/app.py (middleware), granite/api/*.py (11 роутеров).

Проверь следующее:

1. Timing-attack на API-key сравнение (app.py:126):
   provided_key != expected_key — заменить на hmac.compare_digest.
   Найти все места сравнения секретов.

2. Rate limiting:
   - POST /companies/{id}/send (messenger.py) — нет лимита на отправку.
   - POST /campaigns/{id}/run (campaigns.py) — нет лимита на запуск рассылок.
   - GET /export/{city}.csv — нет лимита на экспорт (вычислительно тяжёлый).
   Предложить стратегию rate limiting (slowapi / in-memory counter).

3. Path traversal в GET /export/{city}.csv:
   Проверить, передаётся ли city в os.path или SQL без валидации.
   Если да — предложить fix (whitelist / sanitize).

4. Tracking pixel GET /track/open/{tracking_id}.png:
   Проверить granite/api/tracking.py — валидация tracking_id на UUID.
   Проверить SQL-запрос — параметризован ли он.

5. Email XSS:
   granite/email/sender.py:81-84 — body_text вставляется в HTML <pre>.
   Проверить, экранируется ли body_text через html.escape().
   Если нет — предложить fix.

6. setattr в PATCH /companies/{id} (companies.py:177-178):
   Оценить риск: Pydantic-схема UpdateCompanyRequest ограничивает поля.
   Но setattr в цикле без explicit whitelist — антипаттерн.
   Предложить явный whitelist.

7. CORS в production:
   app.py:69-74 — дефолтные origins (localhost).
   Проверить, есть ли warning при запуске без CORS_ORIGINS env.
   Предложить log warning или reject в production.

Формат ответа:
- Для каждого пункта: статус (OK / ISSUE / CRITICAL), описание, рекомендуемый fix.
- Приоритизированный список исправлений.
```

---

## Аудит 2: Защита от SSRF и инъекций в скраперах

**Критичность:** HIGH
**Область:** Скраперы и обогатители (`granite/utils.py`, `granite/scrapers/*.py`, `granite/enrichers/*.py`)

### Что проверять

Проект активно делает HTTP-запросы к внешним сайтам. Есть функция `is_safe_url()` в `utils.py:480-558` — проверяет SSRF (localhost, private IPs, link-local, cloud-metadata). Однако нужно проверить:

- DNS rebinding: `is_safe_url` проверяет hostname, но DNS может разрешиться в private IP после проверки. Между `is_safe_url` и `requests.get` нет принудительного bind к публичному IP.
- URL из scraped-данных (website компании) передаются в `fetch_page`, `check_site_alive`, `messenger_scanner` без дополнительной валидации (поверх `is_safe_url`).
- `WebSearchScraper` парсит результаты DuckDuckGo и делает follow-up запросы к найденным URL — потенциально恶意 сайт может быть в результатах.
- `tg_finder.py` делает запросы к `t.me/+{phone}` и `t.me/{username}` — URL формируются из данных, но `is_safe_url` НЕ вызывается (только в `tg_request` опционально).
- SQL в пайплайне: `pipeline/dedup_phase.py`, `pipeline/enrichment_phase.py` — есть ли raw SQL? Если да — параметризован ли?
- `config.yaml` парсится через `yaml.safe_load` — безопасно от YAML deserialization. Но `config_validator.py` нужно проверить.

### Промпт

```
Проведи аудит SSRF и инъекционных уязвимостей в Granite CRM.

Контекст: Python-приложение, которое парсит сайты и отправляет HTTP-запросы.
Ключевой файл: granite/utils.py:480-558 — is_safe_url().

Проверь следующее:

1. SSRF защита:
   - is_safe_url() проверяет hostname на private IPs. Но между проверкой
     и фактическим запросом может пройти DNS rebinding.
   - Найти ВСЕ места, где делается requests.get / httpx.get / playwright goto.
   - Для каждого: вызывается ли is_safe_url() перед запросом?
   - Файлы: granite/utils.py (fetch_page, check_site_alive),
     granite/enrichers/messenger_scanner.py, granite/scrapers/*.py,
     granite/enrichers/tg_finder.py.

2. tg_finder.py SSRF:
   - URL формируется как f"https://t.me/+{norm_phone}" и f"https://t.me/{v}".
   - norm_phone проверяется через normalize_phone (только цифры).
   - username через generate_usernames (regex [^a-z0-9] удалён).
   - Но tg_request() не вызывает is_safe_url — нужна ли проверка?

3. DNS rebinding:
   - Предложить защиту: requests с timeout, IP pinning, или
     повторная проверка после DNS resolution.
   - Реалистично ли для данного проекта (скоринг CRM, не критичный)?

4. SQL injection:
   - Найти все raw SQL-запросы (sa_text(), text()).
   - Проверить параметризацию: все ли используют :param?
   - Особое внимание: granite/api/companies.py (json_extract),
     granite/api/export.py, granite/pipeline/dedup_phase.py,
     granite/pipeline/enrichment_phase.py.

5. YAML / config injection:
   - config.yaml загружается через yaml.safe_load — OK.
   - Проверить granite/config_validator.py — валидирует ли он
     потенциально опасные ключи (например, database.path = "/etc/passwd")?

6. Template injection:
   - CrmTemplateRow.render() использует str.replace — безопасно.
   - Но template body может содержать HTML для email.
   - Нужно ли санитизировать template body при создании/обновлении?

Формат: таблица с колонками [Файл:Строка | Тип уязвимости | Статус | Fix].
```

---

## Аудит 3: Целостность данных и схема БД

**Критичность:** HIGH
**Область:** Модели БД и миграции (`granite/database.py`, `alembic/versions/*.py`)

### Что проверять

БД SQLite с 10 таблицами и 8 миграциями Alembic. Ключевые риски:

- `Database.__init__` при `auto_migrate=True` делает stamp head вместо последовательного применения миграций (`database.py:410-447`). Это значит, что `create_all()` + stamp может создать таблицы **без** FK CASCADE и индексов, которые добавлены в миграциях. Это документированный fallback, но при первом деплое на пустой БД — таблицы создаются без правильных constraints.
- `run_alembic_upgrade` при наличии таблиц + пустого `alembic_version` делает stamp head, но **не проверяет**, соответствует ли текущая схема head-миграции. Если таблицы созданы старой версией кода — stamp head пропустит нужные ALTER TABLE.
- `VALID_STAGES` в `database.py:154-157` — набор допустимых стадий воронки, но **не используется** как CHECK constraint в SQLite. Валидация только на уровне API (Pydantic pattern). Пайплайн может записать любую строку в `funnel_stage`.
- Нет мягкого удаления: `DELETE /campaigns/{id}` — жёсткое удаление черновика с потерей истории.
- `raw_companies.merged_into` — FK с `ondelete="SET NULL"`, но нет индекса на `merged_into`.
- `crm_contacts.company_id` — PK, но при удалении компании CASCADE удаляет CRM-данные. Нет возможности «архивировать» компанию.
- В `CrmEmailCampaignRow.filters` — JSON хранится как `Text` (не `JSON` column). Нет валидации структуры filters.
- Нет constraints на `CrmTaskRow.priority` и `CrmTaskRow.status` — можно записать любое значение.
- `EnrichedCompanyRow.updated_at` — `onupdate=lambda: datetime.now(timezone.utc)` работает только через SQLAlchemy ORM, но **не** через raw SQL.

### Промпт

```
Проведи аудит схемы БД и целостности данных Granite CRM.

Контекст: SQLite (WAL), SQLAlchemy ORM, Alembic (8 миграций), 10 таблиц.
Основной файл: granite/database.py.

Проверь следующее:

1. Alembic stamp vs sequential upgrade:
   - Database.__init__ (database.py:400-520) при auto_migrate=True:
     • Если таблиц НЕТ — create_all() + stamp head.
     • Если таблицы ЕСТЬ + alembic_version пуст — stamp head (без ALTER).
   - Это значит, что если код обновлён и есть новая миграция с ALTER TABLE,
     stamp head ПРОПУСТИТ её. Проверить: это так? Как исправить?
   - Предложить: при несовпадении схемы — log warning + fallback на
     sequential upgrade.

2. CHECK constraints в SQLite:
   - VALID_STAGES (database.py:154-157) — не используется как CHECK.
   - funnel_stage, priority, status, segment — без constraint на уровне БД.
   - Можно ли добавить CHECK через Alembic migration?
   - Оценить: нужно ли, если есть Pydantic validation в API?

3. FK CASCADE и целостность:
   - enriched_companies.id → companies.id (CASCADE) — при удалении компании
     теряется enriched. Есть ли сценарий, где это проблема?
   - crm_contacts.company_id → companies.id (CASCADE) — то же самое.
   - crm_touches.company_id → companies.id (CASCADE).
   - Предложить: soft delete или архивация вместо CASCADE?

4. Индексы:
   - raw_companies.merged_into — FK без индекса. Нужен ли?
   - cities_ref.name — unique + index (избыточно?).
   - Проверить все FK без индексов (SQLite не создаёт автоматически).

5. Типы данных:
   - CrmEmailCampaignRow.filters — Text вместо JSON.
     Записывается как json.dumps() — нет валидации структуры.
   - RawCompanyRow.phones, emails — JSON (list). Нет валидации элементов.
   - EnrichedCompanyRow.tg_trust — JSON (dict). Нет валидации ключей.

6. Миграции:
   - Проверить alembic/versions/ — есть ли downgrade для каждой миграции?
   - Проверить, нет ли conflicting revision IDs (ecda7d78a38f встречается дважды
     в комментариях — это баг?).

7. updated_at:
   - onupdate=lambda работает только через ORM, не через raw SQL.
   - Найти все места, где updated_at обновляется вручную (setattr).
   - Найти raw SQL, который пропускает updated_at.

Формат: по каждому пункту — статус, детальное описание, рекомендация.
```

---

## Аудит 4: Надёжность дедупликации

**Критичность:** MEDIUM
**Область:** Алгоритмы дедупликации (`granite/dedup/*.py`)

### Что проверять

Дедупликация — критический этап, от которого зависит качество базы. Три кластеризатора:

- **Phone clustering** (`phone_cluster.py`): Union-Find по нормализованным телефонам. Надёжно, но если два разных предприятия используют один номер (переуступка, общий офис) — будут ошибочно слиты.
- **Site clustering** (`site_matcher.py`): По домену сайта. Если `granit.ru` — это агрегатор/каталог с множеством мастерских, все они сольются в одну запись.
- **Name matching** (`name_matcher.py`): rapidfuzz `token_sort_ratio` с threshold 88. Может слить «Гранит-М» и «Гранит-Мастер» (score ~95), но это разные компании. С другой стороны, «Мастерская памятников Иванова» и «Памятники Иванова» могут не слиться (score ~70-80).

Ключевые вопросы:
- Тreshold 88 — правильно ли подобран? Нет метрик (precision/recall) на реальных данных.
- `needs_review` флаг (`merger.py:152-217`) — помечает конфликты, но нет UI/CLI для их разрешения. Конфликты складываются в `data/conflicts/*.md` — это human-in-the-loop, но нет автоматического пересчёта после ручного разрешения.
- Слияние кластеров через Union-Find: если A~B (по телефону), B~C (по сайту), C~D (по имени), то все четыре сольются в одну — транзитивное замыкание. Это может создать огромные кластеры из реально разных компаний.
- Адресная нормализация (`extract_street` в `utils.py:303-321`) — примитивная: берёт первое слово после «ул.»/«пр.». Не нормализует «ул. Ленина, д. 45» vs «Ленина 45» vs «пр. Ленина, 45».

### Промпт

```
Проведи аудит алгоритмов дедупликации Granite CRM.

Контекст: pipeline для слияния дубликатов компаний из нескольких источников.
Файлы: granite/dedup/phone_cluster.py, site_matcher.py, name_matcher.py, merger.py.

Проверь следующее:

1. Threshold name_similarity_threshold=88:
   - Оценить на примерах:
     • "Гранит-М" vs "Гранит-Мастер" — rapidfuzz token_sort_ratio?
     • "Мастерская памятников Иванова" vs "Памятники Иванова"?
     • "Ритуал-Сервис" vs "Ритуал Сервис" (дефис vs пробел)?
     • "Мемориал-Гранит СПб" vs "Мемориал Гранит"?
   - Является ли threshold=88 оптимальным для ниши ритуальных услуг?
   - Предложить методику подбора threshold (annotated dataset + F1).

2. Транзитивное замыкание кластеров:
   - A~B (телефон), B~C (сайт), C~D (имя) → A+B+C+D в одном кластере.
   - Это может создать кластеры из 10+ реально разных компаний.
   - Проверить: есть ли ограничение на размер кластера?
   - Предложить: максимальный размер кластера или двухфазная дедупликация
     (сначала жесткие критерии, потом мягкие только внутри кластера).

3. Агрегаторы и каталоги:
   - Сайт типа granit.ru (агрегатор) → все мастерские с ним сольются.
   - Как отличить сайт-агрегатор от сайта конкретной мастерской?
   - Предложить эвристику (несколько телефонов, разные адреса на одной странице).

4. needs_review — human-in-the-loop:
   - Конфликты сохраняются в data/conflicts/*.md.
   - Есть ли CLI-команда для просмотра/разрешения конфликтов?
   - Есть ли механизм пересчёта дедупликации после ручного разрешения?
   - Предложить workflow для работы с конфликтами.

5. Адресная нормализация:
   - extract_street() в utils.py:303-321 — берёт первое слово после «ул.».
   - "ул. Ленина, д. 45" → "ленина", "Ленина 45" → "ленина 45".
   - Предложить более надёжную нормализацию (house number separation).

6. Оценка качества:
   - Есть ли тесты с известными дубликатами и не-дубликатами?
   - tests/test_dedup.py — что именно покрывают?
   - Предложить набор тестовых кейсов (golden dataset).

Формат: по каждому пункту — анализ, конкретные примеры, рекомендация.
```

---

## Аудит 5: Качество скоринга и сегментации

**Критичность:** MEDIUM
**Область:** Скоринг и классификация (`granite/enrichers/classifier.py`, `config.yaml`)

### Что проверять

Classifier (`classifier.py`) использует набор сигналов с весами из `config.yaml:scoring.weights`. Сегменты: A (>=50), B (>=30), C (>=15), D (<15), spam (=0).

Ключевые вопросы:
- Вес `has_telegram: +15` — самый высокий позитивный сигнал. Но Telegram может быть найден по телефону (t.me/+7XXX) — это не гарантирует, что канал принадлежит компании. Метод валидации — только проверка «contact button» на странице, без проверки description на ритуальные ключевые слова.
- Вес `cms_bitrix: +10` — почему Bitrix выше, чем WordPress/Tilda (+3)? Bitrix — платный, но не всегда означает «крупная мастерская». Тilda часто используется именно маленькими мастерскими.
- Штраф `-10` за не-российский TLD (.com, .net, .org) — но многие нормальные мастерские используют .com (например, granit.com). Это может занижать скор реальных лидов.
- `is_network: +5` — сеть филиалов может быть как плюсом (крупный клиент), так и минусом (нецелевой сегмент для производителя памятников). Нет различения.
- `tg_trust_multiplier: 2` — умножает `trust_score` из `tg_trust.py`. Нужно проверить, что `trust_score` имеет осмысленный диапазон и не даёт >30 баллов одним сигналом.
- SEO-штраф `-15` — за ключевые слова в названии. Но regex не покрывает все варианты (например, «Памятники и надгробия из гранита с доставкой» — попадёт, а «Гранитные памятники недорого» — тоже попадёт). Нужно проверить false positives.
- Нет сигнала «наличие портфолио/фотографий на сайте» — косвенный показатель реального производителя.
- Нет негативного сигнала «только мобильный телефон, без адреса» — часто признак агрегатора/посредника.

### Промпт

```
Проведи аудит системы скоринга Granite CRM.

Контекст: CRM для ритуальных мастерских РФ. Классификатор ранжирует
компании по сегментам A/B/C/D/spam для приоритизации аутрича.
Файлы: granite/enrichers/classifier.py, config.yaml (секции scoring, enrichment).

Проверь следующее:

1. Анализ весов:
   - has_telegram: +15 (самый высокий). Но TG может быть найден
     через t.me/+7XXX (проверка «contact button») без валидации
     тематики канала. Оценить: насколько этот сигнал надёжен?
   - cms_bitrix: +10 vs cms_modern (WordPress/Tilda): +3.
     Обосновать: почему Bitrix в 3.3 раза выше?
     Bitrix = крупная компания? Или просто другая CMS?
   - Штраф .com/.net/.org: -10. Сколько реальных мастерских
     используют .com? Дать оценку false positive rate.
   - is_network: +5. Филиальная сеть — плюс или минус для аутрича?
     Сценарий: производитель памятников продаёт через филиалы.
   - tg_trust_multiplier: 2 × trust_score.
     Какой диапазон trust_score? Максимальный вклад в итоговый score?

2. Пропущенные сигналы:
   - Нет сигнала «портфолио / галерея работ» на сайте.
   - Нет сигнала «только мобильный, без адреса» (признак посредника).
   - Нет сигнала «упоминание ЧПУ / лазерного станка» в тексте сайта
     (есть tech_keywords в config, но не используются в classifier).
   - Есть ли tech_keywords extraction в enrichment, но не в scoring?
     Если да — предложить добавить.

3. SEO-детектор:
   - Regex в classifier.py:19-22 и utils.py:10-16.
   - Оценить false positives: "Гранитные памятники от производителя"
     — это SEO или реальное название?
   - "Мемориал-Гранит" — НЕ SEO (нет ключевых слов).
   - "Памятники из гранита недорого с доставкой" — SEO.
   - Штраф -15 за SEO: может ли реальная компания с SEO-названием
     получить низкий score? Пример расчёта.

4. Калибровка сегментов:
   - Thresholds: A>=50, B>=30, C>=15. На основе каких данных подобраны?
   - Рассчитать примеры:
     • Сайт (5) + TG (15) + WA (10) + 2 телефона (5) + email (5) = 40 → B
     • Сайт (5) + Bitrix (10) + TG (15) + Marquiz (8) + email (5) = 43 → B
     • Сайт (5) + TG (15) + WA (10) + 2 tel (5) + email (5) + network (5) = 45 → B
   - Достижим ли segment A без .com-штрафа? Что нужно для A?
   - Есть ли дисбаланс (слишком много B, слишком мало A)?

5. Рекомендации по улучшению:
   - Предложить 3-5 дополнительных сигналов с обоснованием.
   - Предложить скорректированные веса.
   - Предложить методику валидации (annotated sample → AUC/F1).

Формат: для каждого пункта — анализ с конкретными расчётами, рекомендация.
```

---

## Аудит 6: Консистентность API-эндпоинтов

**Критичность:** MEDIUM
**Область:** Все API-роутеры (`granite/api/*.py`, `granite/api/schemas.py`)

### Что проверять

11 роутеров с разными паттернами. Нужно проверить:

- `list_companies` (companies.py:57-143) — 3-way join (Company + Enriched + CRM). `q.count()` + `q.offset().limit()` — два запроса вместо одного (potential race condition: count ≠ actual rows). `per_page` max 200 — может быть слишком большим для 3-way join.
- `GET /companies/{id}` — 3 отдельных `db.get()` вместо одного join. Если company существует, но enriched нет — возвращается incomplete response. Нет 404 на enriched missing (expected).
- `PATCH /companies/{id}` — создаёт CrmContactRow если не существует. Но если company не существует — CrmContactRow создаётся с несуществующим FK (integrity error при commit).
- Campaigns: `_get_campaign_recipients` загружает ВСЕ компании в память (`.all()`), потом фильтрует в Python. Для 10K+ компаний — OOM risk.
- `POST /campaigns/{id}/run` — SSE stream с `session = SessionFactory()` в generator. `session.close()` в finally — но если SSE disconnect произойдёт между `commit()` и `close()` — данные могут быть неконсистентны.
- Tasks: `PATCH /tasks/{id}` — нет проверки, что task принадлежит существующей компании.
- Touches: `POST /companies/{id}/touches` — нет валидации body length (можно отправить body на 10MB).
- Templates: `POST /templates` — name pattern `^[a-z0-9_]+$` запрещает кириллицу. Но template может использоваться для русского контента — name не должен быть ограничен.
- Export: CSV export — нет sanitization заголовков columns (если column name содержит `;` или `"` — сломает CSV).

### Промпт

```
Проведи аудит консистентности API Granite CRM.

Контекст: FastAPI с 11 роутерами, SQLAlchemy ORM, SQLite.
Файлы: granite/api/*.py, granite/api/schemas.py, granite/api/stage_transitions.py.

Проверь:

1. N+1 и неэффективные запросы:
   - GET /companies (companies.py:57-143): q.count() + q.offset().limit()
     — 2 запроса. Race condition: count ≠ actual rows?
     Предложить: single query с window function или subquery.
   - GET /companies/{id}: 3 db.get() вместо join. OK для SQLite?
   - GET /followup (followup.py:27-126): q.all() загружает ВСЕ строки
     в память, потом фильтрует в Python. При 10K компаний — OOM?
     Предложить: SQL-level фильтрация дней (DATEDIFF в SQLite).

2. Campaign recipients memory:
   - _get_campaign_recipients (campaigns.py:80-130): .all() загружает
     все компании + enriched + contacts в память.
   - При 50K компаний — ~500MB RAM.
   - Предложить: cursor-based iteration или SQL-level фильтрация.

3. SSE session management:
   - POST /campaigns/{id}/run (campaigns.py:210-368):
     session создан в generator, закрыт в finally.
   - Между commit() и close() — если SSE disconnect?
   - Проверить: есть ли try/except вокруг commit()?
   - Предложить: explicit session lifecycle.

4. Input validation:
   - PATCH /companies/{id}: нет проверки company existence
     перед созданием CrmContactRow (FK violation при commit).
   - PATCH /tasks/{id}: нет проверки task → company relationship.
   - POST /companies/{id}/touches: нет лимита на body length.
   - Предложить: explicit existence checks + length limits.

5. Response model consistency:
   - GET /companies возвращает dict (не CompanyResponse).
   - GET /campaigns возвращает list[dict] (не CampaignResponse).
   - А GET /companies/{id} указывает response_model=CompanyResponse.
   - Предложить: унифицировать — все через response_model.

6. Error handling:
   - Проверить все endpoints: все ли ошибки обёрнуты в HTTPException?
   - Есть ли необработанные exceptions (500 вместо 4xx)?
   - Проверить: DB integrity errors (FK violation) → какой HTTP status?

Формат: таблица [Endpoint | Проблема | Severity | Рекомендация].
```

---

## Аудит 7: Покрытие тестами и граничные случаи

**Критичность:** MEDIUM
**Область:** Тесты (`tests/*.py`)

### Что проверять

16 тестовых файлов. Нужно проверить:

- `tests/test_crm_api.py` — покрывает ли все API endpoints? Включая edge cases (empty DB, non-existent IDs, invalid input)?
- `tests/test_dedup.py` — есть ли тесты на транзитивное замыкание? На false positives (разные компании слились)?
- `tests/test_classifier.py` — есть ли тесты на граничные значения score (0, 14, 15, 16, 29, 30, 31, 49, 50, 51)?
- `tests/test_pipeline.py` и `test_refactored_pipeline.py` — интеграционные тесты? Мокают ли внешние API (DuckDuckGo, Telegram)?
- Нет тестов на: `granite/api/campaigns.py` (run campaign SSE), `granite/api/followup.py`, `granite/api/messenger.py`, `granite/email/sender.py`, `granite/messenger/` (dispatcher, tg_sender, wa_sender).
- Нет тестов на concurrent access (multiple API requests simultaneously).
- Нет тестов на миграции (downgrade + upgrade cycle).
- `tests/test_migrations.py` — проверяет ли downgrade?

### Промпт

```
Проведи аудит тестового покрытия Granite CRM.

Контекст: 16 тестовых файлов в tests/, pytest + pytest-asyncio.
Запуск: cd granite-crm && UV_CACHE_DIR=/home/z/.cache/uv uv run pytest --tb=short -q

Задания:

1. Запусти тесты и собери результаты:
   uv run pytest --tb=short -q 2>&1
   Сколько passed / failed / skipped?
   Покрытие по модулям (если доступно pytest-cov).

2. Проанализируй каждый тестовый файл:
   Для каждого файла в tests/:
   - Какие функции/классы тестирует?
   - Какие edge cases покрывает?
   - Какие критичные сценарии ПРОПУЩЕНЫ?

3. Критичные непокрытые области (приоритизировано):
   a. Campaign SSE (campaigns.py run_campaign):
      - Concurrent runs (два POST /run одновременно).
      - SSE disconnect во время отправки.
      - Campaign с 0 получателей.
   b. Messenger sending (messenger.py, messenger/):
      - stop_automation = True.
      - Нет контакта TG/WA для компании.
      - Template rendering failure.
   c. Email sender (email/sender.py):
      - SMTP permanent error.
      - SMTP temporary error + retry.
      - Invalid email address.
   d. Follow-up queue (followup.py):
      - Timezone handling (naive vs aware datetime).
      - Stage "new" с уже отправленным email (MISS-8 fix).
   e. Stage transitions (stage_transitions.py):
      - Все переходы new → email_sent → ... → replied.
      - Обратные переходы (если возможны).
      - stop_automation при incoming touch.

4. Предложить набор недостающих тестов:
   - 10 критичных тестов, которых не хватает.
   - Для каждого: название, что проверяет, какой модуль.
   - Приоритизация: HIGH (потенциальные баги) / MEDIUM (robustness).

Формат:
- Сводная таблица покрытия [Модуль | Покрыто | Пропущено | Priority].
- Список из 10 недостающих тестов с описанием.
```

---

## Аудит 8: Производительность и масштабируемость

**Критичность:** MEDIUM
**Область:** API, пайплайн, БД (`granite/api/*.py`, `granite/pipeline/*.py`, `granite/database.py`)

### Что проверять

- **SQLite limitations**: WAL mode помогает с конкурентными записями, но SQLite — однопоточный при записи. При одновременном запуске пайплайна и API — `busy_timeout=5000` может не хватить при тяжёлых write-операциях.
- **Enrichment concurrency**: `max_concurrent: 3` (default). Использует `ThreadPoolExecutor` (sync) или `asyncio.Semaphore` (async). При 1000 компаний на город — 1000 HTTP-запросов к сайтам. Даже с 3 потоками — ~6 часов (2 сек × 1000 / 3).
- **Campaign SSE**: `SEND_DELAY = 3` сек между письмами. 100 писем = 5 минут. `MAX_SENDS_PER_RUN = 100`. При 500 получателей — 5 запусков.
- **Database connection pooling**: `sessionmaker` без `pool_size`. SQLite `check_same_thread=False` — OK для FastAPI (один поток per request), но не для ThreadPoolExecutor в пайплайне.
- **JSON columns**: `json_extract` в SQLite — нет индекса. Фильтр `has_telegram = 1` делает full table scan на `enriched_companies.messengers`.
- **Export**: `GET /export/{city}.csv` — генерация CSV in-memory для всего города. При 5000 компаний — может быть медленно.
- **Follow-up queue**: `GET /followup` загружает все строки в память (`.all()`) и фильтрует в Python.

### Промпт

```
Проведи аудит производительности Granite CRM.

Контекст: FastAPI + SQLite (WAL) + async/sync пайплайн парсинга.
Файлы: granite/database.py, granite/pipeline/*.py, granite/api/*.py.

Проверь:

1. SQLite write contention:
   - Пайплайн использует ThreadPoolExecutor (max_threads=3).
   - API использует FastAPI (async).
   - Одновременная работа: пайплайн пишет в raw_companies/companies,
     API читает из тех же таблиц.
   - WAL + busy_timeout=5000 — достаточно ли?
   - Оценить: при каком количестве одновременных записей начнутся
     "database is locked"?
   - Предложить: если проблема — PostgreSQL или queue-based writes.

2. Enrichment throughput:
   - 1000 компаний/город, 3 потока, ~2 сек/запрос → ~11 минут.
   - Telegram finder: до 5 username variants × 5 retries × exponential
     backoff (5→80 сек) = до 25 минут на ОДНУ компанию в worst case.
   - Предложить: timeout на enrichment per company, skip after N failures.
   - Оценить реалистичное время обогащения 1 города (1000 компаний).

3. JSON column performance:
   - json_extract(enriched_companies.messengers, '$.telegram') — без индекса.
   - SQLite generated columns (вычисляемые столбцы) как решение?
   - Предложить: добавить generated column has_telegram BOOL с индексом.

4. Campaign sending throughput:
   - SEND_DELAY=3 сек, MAX_SENDS_PER_RUN=100.
   - 1000 получателей → 10 запусков по 100 = 50 минут.
   - Предложить: configurable delay, batch size, parallel SMTP sessions.
   - Оценить: является ли bottleneck'ом SMTP или API?

5. Follow-up queue:
   - GET /followup: q.all() → Python-level фильтрация.
   - При 10K компаний — загрузка всех в память.
   - Предложить: SQL-level фильтрация (CASE WHEN для stage rules).

6. Memory usage:
   - _get_campaign_recipients: .all() для всех компаний.
   - Enrichment: batch_flush=50 — 50 enriched records в памяти.
   - Оценить: пиковое потребление RAM при 100K компаний в БД.

Формат: [Узкое место | Текущая производительность | Предложение | Приоритет].
```

---

## Аудит 9: Конфигурация и production readiness

**Критичность:** LOW
**Область:** Конфигурация (`config.yaml`, `.env`, `cli.py`, `pyproject.toml`)

### Что проверять

- `config.yaml:1` — комментарий «No schema validation — malformed config will fail at runtime». Нет JSON Schema или Pydantic модели для конфига. Ошибка обнаружится только при запуске конкретной фазы.
- Секреты: `SMTP_PASS`, `DGIS_API_KEY`, `GRANITE_API_KEY` — в env. Нет `.env.example` с описанием всех переменных. Нет проверки наличия обязательных переменных при старте.
- `config.yaml:379` — `database.path: "data/granite.db"` — относительный путь. При запуске из другого каталога — создаст БД в неожиданном месте.
- Нет logging конфигурации для structured JSON (для production monitoring).
- Нет health check для SMTP (проверка подключения при старте).
- Нет graceful shutdown signal handling (SIGTERM для пайплайна).
- `pyproject.toml` — нужно проверить: есть ли pinned dependencies (uv.lock)? Есть ли dev dependencies отделены от prod?
- Нет Dockerfile или docker-compose.yml для production деплоя.

### Промпт

```
Проведи аудит конфигурации и production readiness Granite CRM.

Контекст: FastAPI + SQLite + Playwright + cron-подобный пайплайн.
Файлы: config.yaml, .env, cli.py, pyproject.toml.

Проверь:

1. Config validation:
   - config.yaml:1 — "No schema validation".
   - config_validator.py — что именно валидирует?
   - Предложить: Pydantic Settings model для конфига с default values.
   - Какой minimum required config для запуска? Документировать.

2. Secrets management:
   - Найти ВСЕ env variables: os.environ.get() во всех файлах.
   - Создать список: [VAR_NAME | Default | Used in | Required?].
   - Создать .env.example с описанием каждого параметра.
   - Проверить: есть ли проверка наличия обязательных переменных
     при старте API (SMTP_HOST, SMTP_USER для кампаний)?

3. Database path:
   - config.yaml: "data/granite.db" — относительный путь.
   - Что произойдёт при cd /tmp && python cli.py run moskva?
   - Предложить: absolute path или resolution relative to project root.

4. Logging:
   - loguru rotation="10 MB", retention="30 days" — OK.
   - Но нет structured JSON logging для production.
   - Предложить: JSON formatter для loguru (loguru-json или custom).
   - Проверить: есть ли sensitive data в логах (пароли, API keys, телефоны)?

5. Production deployment:
   - Нет Dockerfile. Предложить минимальный Dockerfile (multi-stage).
   - Нет health check для SMTP.
   - Нет graceful shutdown.
   - cli.py api — uvicorn без --workers. Для production — нужен gunicorn + workers.
   - Предложить: docker-compose.yml (app + sqlite volume).

6. Dependency management:
   - pyproject.toml: проверить, отделены ли dev от prod dependencies.
   - uv.lock: зафиксированы ли версии?
   - Есть лиKnown vulnerabilities в dependencies?

Формат:
- Таблица env variables.
- Список production readiness issues с приоритетом.
- Предложенный Dockerfile и docker-compose.yml.
```

---

## Аудит 10: Обработка ошибок и устойчивость пайплайна

**Критичность:** LOW
**Область:** Пайплайн (`granite/pipeline/manager.py`, `granite/pipeline/*.py`, `granite/scrapers/base.py`)

### Что проверять

- `PipelineManager._run_phase` (manager.py:158-174): критические фазы (scraping, dedup) выбрасывают `PipelineCriticalError`. Некритические (enrichment, scoring, export) — логируют ошибку и продолжают. Но enrichment failure → нет enriched данных → scoring на пустых данных → все компании получат score 0.
- `BaseScraper.run` (base.py:47-64): ловит ВСЕ исключения и возвращает пустой список. Ошибка silently swallowed. Нет механизма partial retry (если 100 компаний scraped и упал на 101-й — первые 100 потеряны при --force).
- `CheckpointManager` — сохраняет прогресс между фазами. Но нет checkpoint внутри фазы (если enrichment упало на компании 500 из 1000 — при перезапуске начнёт с начала фазы).
- Error classification (`utils.py:582-598`): категоризирует ошибки для логирования, но не используется для принятия решений (retry/skip/abort).
- Playwright failures: `JspravPlaywrightScraper` — если Playwright упал (browser crash), нет cleanup. Броузерный процесс может остаться висеть.
- `WebClient` — нет circuit breaker при массовых 429 от DuckDuckGo. После нескольких 429 — exponential backoff, но нет глобального «stop scraping this city».

### Промпт

```
Проведи аудит обработки ошибок в пайплайне Granite CRM.

Контекст: 6-фазный пайплайн (scrape→dedup→enrich→score→export).
Файлы: granite/pipeline/manager.py, pipeline/*.py, scrapers/base.py,
granite/utils.py (classify_error).

Проверь:

1. Graceful degradation:
   - Если enrichment фаза упала — scoring запустится на пустых данных.
   - Результат: все компании получат score=0, segment="spam".
   - Предложить: skip scoring если enrichment не completed.
   - Или: scoring учитывает "no enriched data" как отдельный сигнал.

2. Partial progress:
   - CheckpointManager сохраняет прогресс между фазами.
   - Но внутри фазы (enrichment 1000 компаний) — нет checkpoint.
   - Если упало на компании 500 — перезапуск начнёт с начала фазы.
   - Предложить: batch-level checkpoint (каждые 50 компаний).
   - Оценить: насколько сложно реализовать?

3. Error swallowing:
   - BaseScraper.run (base.py:47-64): ловит Exception, возвращает [].
   - Ошибка silently swallowed — только logger.error.
   - Предложить: error counter + threshold (если >20% компаний failed — abort).
   - Или: collect errors + report в конце фазы.

4. Retry strategy:
   - Scrapers: max_retries из config, но retry только на network errors.
   - TG finder: exponential backoff 5→80 сек. При 5 юзернеймов × 5 retries
     = до 25 запросов на ОДНУ компанию.
   - Предложить: per-company timeout (например, 60 сек total).
   - Предложить: circuit breaker per source (если >50% requests failed — skip).

5. Playwright cleanup:
   - JspravPlaywrightScraper использует shared browser context.
   - Если browser crash — нет cleanup процесса.
   - Предложить: try/finally с browser.close().

6. Error reporting:
   - classify_error() в utils.py: network/parsing/data.
   - Используется ли для retry/skip решений?
   - Предложить: error dashboard (количество ошибок по типу/источнику).

7. idempotency:
   - Запуск pipeline两次 для одного города — что произойдёт?
   - --force: очищает старые данные.
   - Без --force: checkpoint detected → resume.
   - Но resume enrichment — перезапишет существующие enriched данные?
   - Проверить: enrichment_phase.run() — UPSERT или INSERT?

Формат: [Компонент | Проблема | Impact | Рекомендация].
```

---

## Как пользоваться этим документом

### Запуск аудита

1. Выбрать аудит из таблицы выше.
2. Скопировать промпт и вставить в чат с LLM.
3. Добавить контекст: прикрепить соответствующие файлы или указать путь `/home/z/my-project/granite-crm/`.
4. Для аудитов с тестами (7) — сначала запустить `pytest --cov`, затем передать результат в промпт.

### Приоритет выполнения

| Порядок | Аудит | Обоснование |
|---------|-------|------------|
| 1 | Аудит 1 (Безопасность API) | Критические уязвимости перед production |
| 2 | Аудит 3 (Схема БД) | Потеря данных при миграциях |
| 3 | Аудит 2 (SSRF) | Парсинг внешних сайтов — поверхность атаки |
| 4 | Аудит 5 (Скоринг) | Неправильный скоринг = пустые лиды |
| 5 | Аудит 4 (Дедупликация) | Качество базы данных |
| 6 | Аудит 8 (Производительность) | Масштабирование на 1000+ городов |
| 7 | Аудит 7 (Тесты) | Регрессионная безопасность |
| 8 | Аудит 6 (API консистентность) | Разработка фронтенда |
| 9 | Аудит 10 (Ошибки пайплайна) | Надёжность в production |
| 10 | Аудит 9 (Конфигурация) | Production deployment |

### Комбинированный запуск

Для быстрого старта — запустить аудиты 1, 3, 5 параллельно (они независимы и покрывают самые критичные области).
