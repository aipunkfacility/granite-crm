# Гайд по базе данных проекта

## 1. Общая архитектура

Проект использует **SQLite** как хранилище — файл `data/granite.db`. Доступ к БД осуществляется через **SQLAlchemy ORM** (декларативные модели в `granite/database.py`). Схема управляется через **Alembic** — систему миграций, позволяющую менять структуру таблиц без потери данных.

Связь между компонентами:

```
config.yaml                 granite/database.py              alembic/
┌──────────────┐         ┌─────────────────────┐         ┌─────────────────┐
│ database:    │────────▶│ Database()          │────────▶│ env.py          │
│   path: ...  │         │  ├─ engine (SQLite)  │         │  ├─ get_url()   │
│              │         │  ├─ WAL PRAGMAs      │         │  ├─ online()    │
│              │         │  ├─ alembic upgrade  │         │  └─ offline()   │
│              │         │  └─ SessionLocal     │         │                 │
└──────────────┘         └─────────────────────┘         │ versions/       │
                                                         │  ├─ 0001_...    │
                     granite/models.py                   │  └─ ...         │
                     ┌─────────────────────┐             └─────────────────┘
                     │ RawCompany (Pydantic)│
                     │ Company (Pydantic)   │
                     │ EnrichedCompany      │
                     └─────────────────────┘
```

## 2. Таблицы и схема

### 2.1 raw_companies — сырые данные скреперов

Каждый скрепер сохраняет результаты в эту таблицу без изменений. Один и тот же реальный объект может иметь несколько записей (от разных источников).

| Колонка | Тип | Описание |
|---------|-----|----------|
| `id` | INTEGER PK | Автоинкремент |
| `source` | VARCHAR, NOT NULL | Источник: `jsprav`, `web_search`, `2gis`, `yell`, `jsprav_playwright`, `google_maps`, `avito` (индекс) |
| `source_url` | VARCHAR | URL страницы-источника |
| `name` | VARCHAR, NOT NULL | Название компании (как на сайте) |
| `phones` | JSON | Список телефонов `["79001234567", ...]` |
| `address_raw` | TEXT | Сырой адрес (default "") |
| `website` | VARCHAR | URL сайта |
| `emails` | JSON | Список email (default `[]`) |
| `geo` | VARCHAR | Координаты "lat,lon" |
| `messengers` | JSON | Мессенджеры (default `{}`) |
| `scraped_at` | DATETIME | Время скрапинга (auto) |
| `needs_review` | BOOLEAN | Флаг подозрительной записи (default False) |
| `review_reason` | VARCHAR | Причина пометки (логика A-3/A-5) |
| `city` | VARCHAR, NOT NULL | Город из config.yaml (индекс) |
| `region` | VARCHAR, NOT NULL | Регион/область (default "", индекс) |
| `merged_into` | INTEGER FK | ID компании в `companies`, куда слита запись (SET NULL, индекс) |

Индексы: `ix_raw_companies_city`, `ix_raw_companies_source`.

### 2.2 companies — после дедупликации

Уникальные компании, полученные слиянием дублей из `raw_companies`. Алгоритм кластеризации — Union-Find по общим телефонам и доменам сайтов.

| Колонка | Тип | Описание |
|---------|-----|----------|
| `id` | INTEGER PK | Автоинкремент |
| `merged_from` | JSON | Список ID из `raw_companies` `[1, 5, 12]` |
| `name_best` | VARCHAR, NOT NULL | Лучшее название (самое длинное) |
| `phones` | JSON | Объединённые уникальные телефоны |
| `address` | TEXT | Лучший адрес |
| `website` | VARCHAR | Нормализованный URL сайта |
| `emails` | JSON | Объединённые уникальные email |
| `city` | VARCHAR, NOT NULL | Город (индекс) |
| `messengers` | JSON | Мессенджеры из сырых данных |
| `sources` | JSON | Список источников данных `["jsprav", "web_search"]` (default `[]`) |
| `status` | VARCHAR | `raw` → `validated` → `enriched` → `contacted` (default `"raw"`, индекс) |
| `segment` | VARCHAR | `A` / `B` / `C` / `D` / `Не определено` |
| `needs_review` | BOOLEAN | Флаг подозрительной записи или конфликта |
| `review_reason` | VARCHAR | Причина (например, агрегатор или foreign_city) |
| `region` | VARCHAR, NOT NULL | Регион/область (индекс) |
| `merged_into` | INTEGER FK | Куда слита эта компания (SET NULL) |
| `created_at` | DATETIME | Время создания записи (UTC) |
| `updated_at` | DATETIME | Время последнего обновления (UTC) |
| `deleted_at` | DATETIME | Мягкое удаление (soft-delete) |

Индексы: `ix_companies_city`, `ix_companies_status`, `ix_companies_needs_review`, `ix_companies_city_deleted` (составной: city + deleted_at).

### 2.3 enriched_companies — обогащённые данные

Связь **1:1** с `companies` по `id` (Primary Key + Foreign Key). Содержит результаты обогащения: мессенджеры, анализ Telegram, CMS, скоринг. При удалении компании из `companies` запись автоматически удаляется (`ON DELETE CASCADE`).

| Колонка | Тип | Описание |
|---------|-----|----------|
| `id` | INTEGER PK, FK | → `companies.id` (CASCADE) |
| `name` | VARCHAR | Копия `name_best` |
| `phones` | JSON | Телефоны (могут быть дополнены) |
| `address_raw` | TEXT | Копия адреса |
| `website` | VARCHAR | Сайт (может быть найден через web_search) |
| `emails` | JSON | Email (могут быть дополнены) |
| `city` | VARCHAR, NOT NULL | Город (индекс) |
| `messengers` | JSON | Итоговые мессенджеры `{"telegram": "t.me/...", "whatsapp": "..."}` |
| `tg_trust` | JSON | Анализ TG: `{"trust_score": 3, "has_avatar": true, "has_description": true}` |
| `cms` | VARCHAR | CMS сайта: `bitrix`, `wordpress`, `tilda`, `unknown` |
| `has_marquiz` | BOOLEAN | Наличие виджета Marquiz на сайте |
| `is_network` | BOOLEAN | Является частью филиальной сети |
| `crm_score` | INTEGER | Итоговый скор (0–100+) (индекс) |
| `segment` | VARCHAR | `A` / `B` / `C` / `D` (индекс) |
| `region` | VARCHAR, NOT NULL | Регион/область (индекс) |
| `updated_at` | DATETIME | Время обновления (UTC, auto on update) |

Индексы: `ix_enriched_companies_city`, `ix_enriched_companies_crm_score`, `ix_enriched_companies_segment`, `ix_enriched_segment_network` (составной: segment + is_network), `ix_enriched_cms` (cms), `ix_enriched_marquiz` (has_marquiz).

### 2.4 alembic_version — служебная таблица

Создаётся и управляется Alembic автоматически. Хранит текущую ревизию схемы:

| Колонка | Тип | Описание |
|---------|-----|----------|
| `version_num` | VARCHAR | ID текущей миграции (например, `025a08dcc789`) |

### 2.5 crm_contacts — CRM-воронка компании

Главная CRM-запись для компании. Создаётся SEED-скриптом для всех компаний из `companies`. Отслеживает стадию воронки и метрики касаний.

| Колонка | Тип | Описание |
|---------|-----|----------|
| `company_id` | INTEGER PK, FK | → `companies.id` (CASCADE) |
| `funnel_stage` | VARCHAR | Стадия воронки (индекс): `new`, `email_sent`, `email_opened`, `tg_sent`, `wa_sent`, `replied`, `interested`, `not_interested`, `unreachable` |
| `email_sent_count` | INTEGER | Кол-во отправленных email |
| `email_opened_count` | INTEGER | Кол-во открытых email |
| `email_replied_count` | INTEGER | Кол-во ответов на email |
| `last_email_sent_at` | DATETIME | Время последнего отправленного email |
| `last_email_opened_at` | DATETIME | Время последнего открытия |
| `tg_sent_count` | INTEGER | Кол-во отправленных TG-сообщений |
| `wa_sent_count` | INTEGER | Кол-во отправленных WA-сообщений |
| `last_tg_at` | DATETIME | Время последнего TG-касания |
| `last_wa_at` | DATETIME | Время последнего WA-касания |
| `contact_count` | INTEGER | Общее кол-во касаний |
| `last_contact_at` | DATETIME | Время последнего касания (индекс) |
| `last_contact_channel` | VARCHAR | Канал последнего касания |
| `first_contact_at` | DATETIME | Время первого касания |
| `notes` | TEXT | Ручные заметки |
| `stop_automation` | INTEGER | Флаг остановки автоматизации (индекс) |
| `unsubscribe_token` | VARCHAR, NOT NULL, UNIQUE | Токен для отписки (auto-generate, индекс) |
| `created_at` | DATETIME | Время создания |
| `updated_at` | DATETIME | Время обновления (auto on update) |

Индексы: `ix_crm_contacts_funnel_stage`, `ix_crm_contacts_last_contact_at`, `ix_crm_contacts_stop_automation`, `ix_crm_contacts_funnel_stop` (составной: funnel_stage + stop_automation).

### 2.6 crm_touches — лог касаний

Каждое отправленное или полученное сообщение (email, TG, WA, manual).

| Колонка | Тип | Описание |
|---------|-----|----------|
| `id` | INTEGER PK | Автоинкремент |
| `company_id` | INTEGER FK, NOT NULL | → `companies.id` (CASCADE) (индекс) |
| `channel` | VARCHAR, NOT NULL | Канал: `email`, `tg`, `wa`, `manual` |
| `direction` | VARCHAR, NOT NULL | Направление: `outgoing`, `incoming` |
| `subject` | VARCHAR | Тема сообщения |
| `body` | TEXT | Тело сообщения |
| `note` | TEXT | Примечание |
| `created_at` | DATETIME | Время касания (UTC) |

Индексы: `ix_crm_touches_company_id`.

### 2.7 crm_templates — шаблоны сообщений

Шаблоны с плейсхолдерами `{from_name}`, `{city}`, `{company_name}`. Подстановка через `str.replace()` (безопасная, без eval).

| Колонка | Тип | Описание |
|---------|-----|----------|
| `id` | INTEGER PK | Автоинкремент |
| `name` | VARCHAR, NOT NULL, UNIQUE | Имя шаблона (max 64 символа) |
| `channel` | VARCHAR, NOT NULL | Канал: `email`, `tg`, `wa` |
| `subject` | VARCHAR | Тема (для email) |
| `body` | TEXT, NOT NULL | Тело с плейсхолдерами |
| `body_type` | VARCHAR(10), NOT NULL | Тип: `plain` или `html` (default `"plain"`) |
| `description` | VARCHAR | Описание шаблона |
| `retired` | BOOLEAN, NOT NULL | Архивный/immutable шаблон (default False) |
| `created_at` | DATETIME | Время создания |
| `updated_at` | DATETIME | Время обновления |

Методы: `render(**kwargs)` — подставить значения в body (для html экранирует через `html.escape()`, для plain — как есть), `render_subject(**kwargs)` — в subject.

### 2.8 crm_email_logs — лог отправки email

Запись об отправленном письме с UUID для tracking pixel.

| Колонка | Тип | Описание |
|---------|-----|----------|
| `id` | INTEGER PK | Автоинкремент |
| `company_id` | INTEGER FK, NOT NULL | → `companies.id` (CASCADE) (индекс) |
| `email_to` | VARCHAR, NOT NULL | Адрес получателя |
| `email_subject` | VARCHAR | Тема письма |
| `template_name` | VARCHAR | Имя использованного шаблона |
| `campaign_id` | INTEGER FK | ID кампании → `crm_email_campaigns.id` (SET NULL, индекс) |
| `status` | VARCHAR | Статус: `pending`, `sent`, `opened`, `replied`, `bounced`, `error` (индекс) |
| `sent_at` | DATETIME | Время отправки |
| `opened_at` | DATETIME | Время открытия (через tracking pixel) |
| `replied_at` | DATETIME | Время ответа |
| `bounced_at` | DATETIME | Время bounce |
| `error_message` | TEXT | Текст ошибки |
| `tracking_id` | VARCHAR, UNIQUE | UUID для tracking pixel (индекс) |
| `ab_variant` | VARCHAR(1) | Вариант A/B теста: "A" или "B" (nullable) |
| `template_id` | INTEGER FK | ID immutable-шаблона → `crm_templates.id` (nullable) |
| `created_at` | DATETIME | Время создания |

Индексы: `ix_crm_email_logs_company_id`, `ix_crm_email_logs_campaign_id`, `ix_crm_email_logs_tracking_id`.

### 2.9 crm_tasks — задачи

Задачи: follow-up, отправка портфолио, звонок и т.д.

| Колонка | Тип | Описание |
|---------|-----|----------|
| `id` | INTEGER PK | Автоинкремент |
| `company_id` | INTEGER FK | → `companies.id` (SET NULL) (индекс) |
| `title` | VARCHAR, NOT NULL | Заголовок задачи |
| `description` | TEXT | Описание |
| `due_date` | DATETIME | Срок выполнения |
| `priority` | VARCHAR | `low`, `normal`, `high` |
| `status` | VARCHAR | `pending`, `in_progress`, `done`, `cancelled` (индекс) |
| `task_type` | VARCHAR | `follow_up`, `send_portfolio`, `send_test_offer`, `check_response`, `other` |
| `created_at` | DATETIME | Время создания |
| `completed_at` | DATETIME | Время завершения |

Индексы: `ix_crm_tasks_company_id`, `ix_crm_tasks_status`.

### 2.10 crm_email_campaigns — email-кампании

Набор получателей + шаблон + статистика.

| Колонка | Тип | Описание |
|---------|-----|----------|
| `id` | INTEGER PK | Автоинкремент |
| `name` | VARCHAR, NOT NULL | Название кампании |
| `template_name` | VARCHAR, NOT NULL | Имя шаблона |
| `status` | VARCHAR | `draft`, `running`, `completed`, `paused`, `paused_daily_limit`, `error` (индекс) |
| `filters` | JSON | JSON-фильтр для выборки получателей |
| `total_sent` | INTEGER | Кол-во отправленных |
| `total_opened` | INTEGER | Кол-во открытых |
| `total_replied` | INTEGER | Кол-во ответов |
| `subject_a` | VARCHAR | Тема варианта A для A/B теста (nullable) |
| `subject_b` | VARCHAR | Тема варианта B для A/B теста (nullable) |
| `total_errors` | INTEGER | Кол-во ошибок отправки (default 0) |
| `total_recipients` | INTEGER | Общее число получателей (default 0) |
| `started_at` | DATETIME | Время запуска |
| `completed_at` | DATETIME | Время завершения |
| `created_at` | DATETIME | Время создания |
| `updated_at` | DATETIME | Время последнего обновления |

Индексы: `ix_crm_email_campaigns_status`.

### 2.11 Диаграмма связей (ER)

```
┌─────────────────┐       ┌──────────────────────┐
│  raw_companies  │       │     companies        │
├─────────────────┤       ├──────────────────────┤
│ id (PK)         │──┐    │ id (PK)              │
│ source          │  │    │ merged_from (JSON)   │
│ source_url      │  │    │ name_best            │
│ name            │  └──▶│ phones (JSON)        │
│ phones (JSON)   │       │ address              │
│ address_raw     │       │ website              │
│ website         │       │ emails (JSON)        │
│ emails (JSON)   │       │ city                 │
│ geo             │       │ messengers (JSON)    │
│ messengers      │       │ status               │
│ scraped_at      │       │ segment              │
│ city            │       │ needs_review         │
│ merged_into(FK) │       │ review_reason        │
└─────────────────┘       │ created_at           │
                           │ updated_at           │
                           └──────────┬───────────┘
                                      │ 1:1 (PK = FK, CASCADE)
                           ┌──────────▼───────────┐
                           │ enriched_companies   │
                           ├──────────────────────┤
                           │ id (PK, FK→companies)│
                           │ name                 │
                           │ phones, emails       │
                           │ messengers (JSON)    │
                           │ tg_trust (JSON)      │
                           │ cms                  │
                           │ has_marquiz          │
                           │ is_network           │
                           │ crm_score            │
                           │ segment              │
                           │ updated_at           │
                           └──────────┬───────────┘
                                      │
                                      │ (через companies.id)
          ┌───────────────────────────┼───────────────────────────┐
          │                           │                           │
          ▼                           ▼                           ▼
┌─────────────────┐         ┌─────────────────┐         ┌─────────────────┐
│ crm_contacts    │         │ crm_touches     │         │ crm_email_logs  │
├─────────────────┤         ├─────────────────┤         ├─────────────────┤
│ company_id(PK,FK)         │ id (PK)         │         │ id (PK)         │
│ funnel_stage    │         │ company_id (FK) │         │ company_id (FK) │
│ email_*_count   │         │ channel         │         │ email_to        │
│ tg_sent_count   │         │ direction       │         │ email_subject   │
│ wa_sent_count   │         │ subject, body   │         │ template_name   │
│ contact_count   │         │ note            │         │ campaign_id     │
│ last_contact_at │         │ created_at      │         │ status          │
│ notes           │         └─────────────────┘         │ tracking_id     │
│ stop_automation │                                     │ sent_at, opened │
└─────────────────┘                                     │ error_message   │
                                                        └─────────────────┘
          │
          ▼
┌─────────────────┐         ┌─────────────────┐
│ crm_tasks       │         │ crm_templates   │
├─────────────────┤         ├─────────────────┤
│ id (PK)         │         │ id (PK)         │
│ company_id (FK) │         │ name (UNIQUE)   │
│ title           │         │ channel         │
│ description     │         │ subject, body   │
│ due_date        │         │ description     │
│ priority,status │         └─────────────────┘
│ task_type       │
│ completed_at    │         ┌─────────────────┐
└─────────────────┘         │crm_email_campaigns│
                            ├─────────────────┤
                            │ id (PK)         │
                            │ name            │
                            │ template_name   │
                            │ status          │
                            │ filters (JSON)  │
                            │ total_sent/open │
                            │ total_replied   │
                            └─────────────────┘
```

## 3. SQLite: WAL-режим и оптимизации

БД работает в **WAL (Write-Ahead Logging)** режиме. Это позволяет одновременно читать и писать без блокировок — критично для параллельного парсинга через `ThreadPoolExecutor`.

PRAGMA, устанавливаемые при каждом подключении:

| PRAGMA | Значение | Зачем |
|--------|----------|-------|
| `journal_mode=WAL` | Позволяет параллельные чтения во время записи | Без "database is locked" при ThreadPoolExecutor |
| `foreign_keys=ON` | Включает проверку внешних ключей | CASCADE при удалении компании |
| `busy_timeout=5000` | 5 сек ожидания блокировки | Если другой поток пишет — ждать, а не падать |

Настройки заданы в двух местах для полноты:

- `granite/database.py` — событие `@event.listens_for(engine, "connect")` для класса `Database`
- `alembic/env.py` — для миграций

## 4. Система миграций Alembic

### 4.1 Как это работает

Alembic отслеживает текущую версию схемы в таблице `alembic_version`. При каждом изменении ORM-моделей создаётся файл миграции с функциями `upgrade()` и `downgrade()`. Команда `upgrade head` применяет все незаписанные миграции по порядку.

```
История миграций:
  base ──▶ ecda7d78a38f (initial_schema) ──▶ a3f1b2c4d5e6 ──▶ 025a08dcc789 (add_crm_tables)
              │                                  │                │
              ▼                                  ▼                ▼
         Создание всех      Удаление мёртвой    Добавление 6 CRM-
         таблиц pipeline    таблицы pipeline    таблиц: crm_contacts,
                           _runs                crm_touches, crm_templates,
                                                crm_email_logs, crm_tasks,
                                                crm_email_campaigns

  alembic_version.version_num = "025a08dcc789"
```

Список миграций:

| Ревизия | Дата | Описание |
|---------|------|----------|
| `ecda7d78a38f` | 2026-04-06 | `initial_schema` — создание raw_companies, companies, enriched_companies |
| `a3f1b2c4d5e6` | 2026-04-10 | `drop_pipeline_runs` — удаление таблицы pipeline_runs |
| `025a08dcc789` | 2026-04-11 | `add_crm_tables` — 6 CRM таблиц |
| `b9fa3d4c7894` | 2026-04-17 | `cities_ref` и `unmatched_cities` |
| `a1b2c3d4e5f6` | 2026-04-18 | `updated_at` для кампаний и чистка типов задач |
| `e2f3a4b5c6d7` | 2026-04-18 | Поля `region` и составной индекс CRM |
| `f1a2b3c4d5e6` | 2026-04-19 | Исправление FK CASCADE/SET NULL и campaign_id |
| `g1h2i3j4k5l6` | 2026-04-19 | `updated_at` для `crm_contacts` |
| `h2i3j4k5l6m7` | 2026-04-19 | Индекс на `merged_into` (performance) |
| `i3j4k5l6m7n8` | 2026-04-19 | Конвертация `filters` в JSON и оставшиеся правки |
| `j4k5l6m7n8o9` | 2026-04-19 | Добавление `merged_into` в `companies` |
| `32d3781c3b04` | 2026-04-21 | Поля `needs_review`/`review_reason` в `raw_companies` |

### 4.2 Источники URL БД

`alembic/env.py` определяет URL базы данных по приоритету:

1. **`sqlalchemy.url` из Alembic config** — когда URL установлен программно (`set_main_option`), например в CLI-командах или тестах
2. **`DATABASE_URL` из окружения** — для CI/Docker (только валидные SQLAlchemy URL: `sqlite://`, `postgresql://`, ...)
3. **`config.yaml` → `database.path`** — для локальной разработки (по умолчанию `data/granite.db`)
4. **Фоллбэк** — `sqlite:///data/granite.db`

### 4.3 Автоматические миграции при запуске

Класс `Database()` автоматически применяет `alembic upgrade head` при инициализации (параметр `auto_migrate=True` по умолчанию). Если Alembic не настроен — фоллбэк на `Base.metadata.create_all()`.

```python
# Стандартное использование — миграции применяются автоматически
db = Database()                  # auto_migrate=True
db = Database(auto_migrate=True) # то же самое

# Без миграций — только create_all (для быстрых скриптов/тестов)
db = Database(auto_migrate=False)
```

### 4.4 Имена файлов миграций

Шаблон из `alembic.ini`:

```
%(year)d%(month).2d%(day).2d_%(hour).2d%(minute).2d%(second).2d_%(rev)s_%(slug)s
```

Пример: `20260406_191015_ecda7d78a38f_initial_schema.py`

## 5. Типовые операции

### 5.1 Добавление новой колонки

Пример: нужно добавить колонку `last_contacted_at` в `companies`.

**Шаг 1.** Изменить ORM-модель в `granite/database.py`:

```python
class CompanyRow(Base):
    # ... существующие колонки ...
    last_contacted_at = Column(DateTime, nullable=True)  # НОВАЯ
```

**Шаг 2.** Сгенерировать миграцию:

```bash
uv run cli.py db migrate "add last_contacted_at to companies"
```

Alembic создаст файл в `alembic/versions/` с `op.add_column("companies", ...)`.

**Шаг 3.** Проверить сгенерированный файл:

```bash
uv run cli.py db check
```

**Шаг 4.** Применить:

```bash
uv run cli.py db upgrade head
```

Все существующие данные сохранятся. Новая колонка будет `NULL` для старых записей.

### 5.2 Добавление новой таблицы

Пример: нужна таблица `email_templates` для хранения шаблонов писем.

**Шаг 1.** Создать ORM-модель в `granite/database.py`:

```python
class EmailTemplateRow(Base):
    __tablename__ = "email_templates"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False, unique=True)
    subject = Column(String, default="")
    body = Column(Text, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(tz=timezone.utc))
```

**Шаг 2.** Сгенерировать и применить миграцию:

```bash
uv run cli.py db migrate "add email_templates table"
uv run cli.py db upgrade head
```

### 5.3 Добавление индекса

```python
# В ORM-модели:
name = Column(String, nullable=False, index=True)  # автоматически создаст ix_companies_name

# Или через миграцию вручную:
op.create_index("ix_raw_companies_source", "raw_companies", ["source"])
```

### 5.4 Откат изменения

```bash
# На одну миграцию назад
uv run cli.py db downgrade -1

# До конкретной ревизии
uv run cli.py db downgrade ecda7d78a38f

# Полный откат (удаление всех таблиц, кроме alembic_version)
uv run cli.py db downgrade base
```

### 5.5 Удаление колонки

**Шаг 1.** Убрать из ORM-модели:

```python
class CompanyRow(Base):
    # review_reason удалена
    ...
```

**Шаг 2.** Сгенерировать миграцию (Alembic увидит, что колонки больше нет в модели):

```bash
uv run cli.py db migrate "remove review_reason from companies"
```

**Шаг 3.** Проверить и применить:

```bash
# Проверить, что detected правильно
uv run cli.py db check

# Применить (колонка и её данные будут удалены!)
uv run cli.py db upgrade head
```

## 6. CLI-команды для управления БД

Все команды доступны через `python cli.py db ...`:

| Команда | Описание | Пример |
|---------|----------|--------|
| `db upgrade` | Применить миграции | `python cli.py db upgrade head` |
| `db downgrade` | Откатить миграции | `python cli.py db downgrade -1` |
| `db history` | История миграций | `python cli.py db history -v` |
| `db current` | Текущая версия | `python cli.py db current` |
| `db migrate` | Создать миграцию | `python cli.py db migrate "add column"` |
| `db stamp` | Пометить версию | `python cli.py db stamp head` |
| `db check` | Проверить различия ORM ↔ БД | `python cli.py db check` |

### Примеры использования

```bash
# Посмотреть текущую версию
uv run cli.py db current

# История всех миграций (подробно)
uv run cli.py db history --verbose

# Проверить, нужны ли миграции
uv run cli.py db check

# Создать миграцию для изменений в моделях
uv run cli.py db migrate "add yandex_maps_rating to enriched_companies"

# Применить
uv run cli.py db upgrade head

# Что-то пошло не так — откатить
uv run cli.py db downgrade -1

# Несколько шагов назад
uv run cli.py db downgrade -3
```

## 7. Перенос существующей БД на Alembic

Если у вас есть БД, созданная до внедрения Alembic (без таблицы `alembic_version`):

```bash
# 1. Проверить, что ORM и БД совпадают
uv run cli.py db check

# 2. Пометить текущую схему как head (без выполнения SQL)
uv run cli.py db stamp head

# 3. Убедиться, что версия установлена
uv run cli.py db current
# → Rev: 025a08dcc789 (head)
```

После этого все последующие миграции будут применяться инкрементально.

## 8. Поток данных через таблицы

```
Скреперы (jsprav, web_search, dgis, yell)
        │
        ▼
┌─────────────────┐     ┌───────────────────┐
│ raw_companies   │────▶│ companies         │  Фаза 2: Дедупликация
│ (сырые данные)  │     │ (уникальные)      │  Union-Find по телефонам/сайтам
└─────────────────┘     └─────────┬─────────┘
                                  │
                    ┌─────────────┼─────────────┐
                    │             │             │
                    ▼             ▼             ▼
          ┌──────────────┐ ┌───────────┐ ┌──────────────┐
          │enriched_     │ │crm_       │ │crm_          │
          │companies     │ │contacts   │ │tasks         │
          │(мессенджеры, │ │(воронка,  │ │(follow-up,   │
          │ CMS, скор)   │ │ метрики)  │ │ звонок)      │
          └──────┬───────┘ └─────┬─────┘ └──────────────┘
                 │               │
                 │               │ ◄── касания ── crm_touches
                 │               │               (лог email/tg/wa)
                 ▼               ▼
          ┌──────────────────────────────┐
          │ crm_email_logs               │  Отправка email
          │ (tracking pixel, open rate)  │  через crm_templates
          └──────────────────────────────┘
                 │
                 ▼
          ┌──────────────────────────────┐
          │ crm_email_campaigns          │  Массовые рассылки
          │ (статистика кампании)        │  filters + template
          └──────────────┬───────────────┘
                         │
                         ▼
          ┌──────────────────────────────┐
          │ data/export/                 │  Экспорт
          │ {city}_enriched.csv          │  CSV + Markdown + пресеты
          └──────────────────────────────┘
```

Ключевые моменты потока:

1. **raw_companies → companies**: кластеризация по телефонам/сайтам (Union-Find). После слияния ID исходных строк сохраняются в поле `merged_from` (JSON-массив).
2. **companies → enriched_companies**: связь 1:1 по `id` (PK = FK). При обновлении обогащения используется `session.merge()` — это позволяет перезаписывать данные без дублирования.
3. **companies → crm_contacts**: связь 1:1 по `company_id` (PK = FK, CASCADE DELETE). Создаётся SEED-скриптом для всех компаний.
4. **crm_contacts → crm_touches**: связь 1:N. Каждое касание (email, TG, WA, manual) логируется отдельно.
5. **ON DELETE CASCADE**: при удалении компании из `companies` автоматически удаляются записи из `enriched_companies`, `crm_contacts`, `crm_touches`, `crm_email_logs`. Для `crm_tasks` — `ON DELETE SET NULL` (задача остаётся без компании).
6. **VALID_STAGES**: допустимые стадии воронки определены в `database.py`:

   ```python
   VALID_STAGES = {
       "new", "email_sent", "email_opened", "tg_sent", "wa_sent",
       "replied", "interested", "not_interested", "unreachable",
   }
   ```

   Валидация применяется в API schemas (`UpdateCompanyRequest.funnel_stage`).

## 9. Работа с БД в коде

### 9.1 Создание подключения

```python
from granite.database import Database

# Стандартный способ — читает путь из config.yaml
db = Database()

# Явный путь
db = Database(db_path="data/granite.db")

# С другим config
db = Database(config_path="config.prod.yaml")

# Без авто-миграций (для тестов/скриптов)
db = Database(auto_migrate=False)
```

### 9.2 Чтение данных

```python
from granite.database import Database, EnrichedCompanyRow

session = db.get_session()

# Все обогащённые компании города
companies = session.query(EnrichedCompanyRow).filter_by(city="Волгоград").all()

# Сегмент A с Telegram
hot_leads = session.query(EnrichedCompanyRow).filter(
    EnrichedCompanyRow.city == "Волгоград",
    EnrichedCompanyRow.segment == "A",
    EnrichedCompanyRow.messengers["telegram"].isnot(None)
).all()

# Сортировка по скору
top = session.query(EnrichedCompanyRow)\
    .filter_by(city="Волгоград")\
    .order_by(EnrichedCompanyRow.crm_score.desc())\
    .limit(20)\
    .all()

session.close()
```

### 9.3 Запись данных

```python
from granite.database import RawCompanyRow, EnrichedCompanyRow, CrmContactRow

with db.session_scope() as session:
    # Новая сырая запись
    raw = RawCompanyRow(
        source="web_search",
        name="ГранитМастер",
        phones=["79001234567"],
        city="Волгоград",
    )
    session.add(raw)

    # Обновление обогащённых данных (merge = insert or update)
    enriched = EnrichedCompanyRow(
        id=company_id,  # должен существовать в companies
        name="ГранитМастер",
        messengers={"telegram": "t.me/granitmaster"},
        crm_score=45,
        segment="B",
    )
    session.merge(enriched)

    # Работа с CRM-контактом
    contact = CrmContactRow(
        company_id=company_id,
        funnel_stage="new",
        notes="Первый контакт через email",
    )
    session.merge(contact)
# commit() вызывается автоматически при выходе из with
# при исключении — автоматически rollback()
```

### 9.4 CRM-воронка: типовые запросы

```python
from granite.database import CrmContactRow, CrmTouchRow, VALID_STAGES

with db.session_scope() as session:
    # Все компании на стадии "new"
    new_companies = session.query(CrmContactRow).filter_by(
        funnel_stage="new"
    ).all()

    # Компании, которые ответили (replied) и имеют высокий скор
    from sqlalchemy.orm import joinedload
    interested = (
        session.query(CrmContactRow)
        .join(EnrichedCompanyRow, CrmContactRow.company_id == EnrichedCompanyRow.id)
        .filter(CrmContactRow.funnel_stage == "replied")
        .filter(EnrichedCompanyRow.crm_score >= 50)
        .all()
    )

    # История касаний компании
    touches = session.query(CrmTouchRow).filter_by(
        company_id=company_id
    ).order_by(CrmTouchRow.created_at.desc()).all()

    # Перевести компанию на новую стадию
    contact = session.query(CrmContactRow).filter_by(company_id=company_id).first()
    if contact:
        contact.funnel_stage = "email_sent"
        contact.email_sent_count += 1
        contact.last_contact_at = datetime.now(timezone.utc)
        contact.last_contact_channel = "email"
```

## 10. Бэкап и восстановление

### Полный бэкап

```bash
# Копирование файла БД (WAL-режим — можно копировать без остановки)
cp data/granite.db data/backups/granite_20260406.db
cp data/granite.db-wal data/backups/granite_20260406.db-wal  # если есть
cp data/granite.db-shm data/backups/granite_20260406.db-shm  # если есть
```

### Восстановление

```bash
# Заменить файл БД
cp data/backups/granite_20260406.db data/granite.db

# Проверить, что версия схемы совпадает
uv run cli.py db current

# Если версии не совпадают — применить недостающие миграции
uv run cli.py db upgrade head
```

### Экспорт данных в SQL

```bash
# Через sqlite3 CLI
sqlite3 data/granite.db .dump > data/backups/granite_dump.sql

# Восстановление из дампа
sqlite3 data/granite.db < data/backups/granite_dump.sql
```

## 11. JSON-колонки

Несколько колонок хранят данные в формате JSON (SQLite 3.38+ поддерживает нативный JSON). Работа с ними через SQLAlchemy:

```python
# Запись
company.phones = ["79001234567", "79160000000"]
company.messengers = {"telegram": "t.me/firm", "vk": "vk.com/firm"}

# Чтение
phones = company.phones or []         # list[str]
messengers = company.messengers or {} # dict[str, str]

# Фильтрация (SQLite JSON1)
from sqlalchemy import func
# Компании, у которых есть telegram в messengers
result = session.query(EnrichedCompanyRow).filter(
    func.json_extract(EnrichedCompanyRow.messengers, '$.telegram').isnot(None)
).all()
```

Колонки с JSON-данными: `phones`, `emails`, `messengers`, `merged_from`, `tg_trust`.

## 12. Тестирование

Все тесты миграций находятся в `tests/test_migrations.py` (9 тестов). Они используют временные БД и проверяют:

- Создание всех таблиц при `upgrade head`
- Полное удаление при `downgrade base`
- Идемпотентность: `upgrade → downgrade → upgrade` даёт ту же схему
- Корректную запись версии в `alembic_version`
- Автоматическую миграцию через `Database()`
- Фоллбэк на `create_all()` при `auto_migrate=False`
- Отсутствие различий между ORM и БД после `upgrade`
- Наличие внешних ключей с правильными `referred_table`

Запуск:

```bash
# Все тесты
uv run pytest tests/ -v

# Только тесты миграций
uv run pytest tests/test_migrations.py -v
```
