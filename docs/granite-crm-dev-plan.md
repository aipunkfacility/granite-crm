# Granite CRM — Полный план разработки

> **Бизнес-контекст:** Ретушь портретов для памятников (B2B, Россия). Вы во Вьетнаме. Каналы: email (массово), TG/WA (индивидуально). Никаких звонков.
>
> **Цель:** Собрать базу → загрузить в CRM → запустить рассылку → получать заказы.

---

## 1. Целевая архитектура

```
┌──────────────────────────────────────────────────────────────┐
│ granite-crm-db/ (этот репо — всё в одном)                     │
│                                                              │
│  Python (Мозг + Сбор данных)                                 │
│  ├── config.yaml + Pydantic валидация                        │
│  ├── cli.py (run / export / api)                             │
│  ├── granite/pipeline/ (скрапер: scrape→dedup→enrich→score)   │
│  ├── granite/database.py (8 таблиц: 4 скрапер + 4 CRM)       │
│  └── granite/api/ (FastAPI — CRUD, email, трекинг)           │
│                                                              │
│  Node.js (Руки — мессенджеры)                                │
│  ├── workers/wa-worker.js (whatsapp-web.js)                   │
│  └── workers/tg-worker.js (Pyrogram, опционально)            │
│                                                              │
│  Общее: data/granite.db (SQLite WAL — оба языка читают/пишут) │
└──────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│ granite-crm-web/ (отдельный репо — фронтенд, Phase 3)         │
│  Next.js + shadcn/ui → дашборд, таблица, карточка, кампании  │
└──────────────────────────────────────────────────────────────┘
```

### Почему всё в одном репо

Отдельные микросервисы — это правильно, но не для твоей ситуации:
- SQLite — файловая БД, не(net)сервис, разделение бессмысленно
- 3 дня до запуска — каждый репо = отдельный деплой/CI/CD/CORS
- Позже вынести API легко (достаточно перенести `granite/api/`)

### Python vs Node.js

| Язык | Роль | Почему |
|------|-----|--------|
| **Python** | Скрапер + CRM API + логика воронки | Уже написан, SQLAlchemy, Pydantic, LLM |
| **Node.js** | WhatsApp/TG воркеры | `whatsapp-web.js` требует Node + Puppeteer. TG можно и на Python (Pyrogram) |

Оба работают с одной SQLite через WAL — без конфликтов.

---

## 2. База данных — полная схема

### Уже есть (скрапер, не трогать)

```
raw_companies          Сырые записи от скраперов
companies              Уникальные компании (после дедупликации)
enriched_companies     Обогащённые: мессенджеры, скоринг, сегмент
pipeline_runs          Лог запусков пайплайна
```

### Добавить (CRM — из концепта v4)

```
crm_contacts           Воронка и статус контакта (1:1 с companies)
crm_email_logs         Логи email-рассылок + tracking pixel
crm_touches            Все касания (email, TG, WA, manual)
crm_tasks              Задачи (follow-up, отправить КП, etc.)
crm_email_campaigns    Кампании email-рассылок
crm_templates          Шаблоны сообщений (email, TG, WA)
crm_auto_rules         Автоматические правила (no_response → create_task)
crm_orders             Заказы на ретушь
```

### crm_contacts — главная CRM-таблица

```sql
CREATE TABLE crm_contacts (
    company_id          INTEGER PRIMARY KEY,

    -- Воронка
    funnel_stage        TEXT DEFAULT 'new',
    -- new → email_sent → email_opened → follow_up_sent →
    -- second_follow_up → contacted → portfolio_sent →
    -- interested → test_order → regular_client
    -- neg: not_interested → unreachable
    not_interested_reason TEXT DEFAULT '',

    -- Email
    email_sent_count    INTEGER DEFAULT 0,
    email_opened_count  INTEGER DEFAULT 0,
    email_replied_count INTEGER DEFAULT 0,
    last_email_opened_at DATETIME,

    -- Мессенджеры
    last_contact_at     DATETIME,
    last_contact_channel TEXT DEFAULT '',
    contact_count       INTEGER DEFAULT 0,
    first_contact_at    DATETIME,
    last_tg_at          DATETIME,
    last_wa_at          DATETIME,
    tg_sent_count       INTEGER DEFAULT 0,
    wa_sent_count       INTEGER DEFAULT 0,

    -- Ручное
    notes               TEXT DEFAULT '',
    tags                TEXT DEFAULT '',
    color_label         TEXT DEFAULT '',
    archived            INTEGER DEFAULT 0,

    -- Заказы
    order_count         INTEGER DEFAULT 0,
    total_revenue       INTEGER DEFAULT 0,

    -- Метаданные
    created_at          DATETIME,
    updated_at          DATETIME,

    FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE
);
```

### crm_email_logs — логи + tracking

```sql
CREATE TABLE crm_email_logs (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id          INTEGER NOT NULL,
    campaign_id         INTEGER,

    email_to            TEXT NOT NULL,
    email_subject       TEXT DEFAULT '',
    email_template      TEXT DEFAULT '',

    status              TEXT DEFAULT 'pending',
    -- pending / sent / bounced / opened / replied / failed

    sent_at             DATETIME,
    opened_at           DATETIME,
    replied_at          DATETIME,
    bounced_at          DATETIME,
    bounce_reason       TEXT DEFAULT '',
    error_message       TEXT DEFAULT '',

    tracking_id         TEXT UNIQUE,  -- UUID для tracking pixel

    created_at          DATETIME,
    updated_at          DATETIME,

    FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE
);
```

### crm_touches — журнал касаний

```sql
CREATE TABLE crm_touches (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id          INTEGER NOT NULL,
    channel             TEXT NOT NULL,  -- email / tg / wa / manual
    direction           TEXT NOT NULL,  -- outgoing / incoming
    status              TEXT DEFAULT 'sent',
    -- sent / delivered / read / replied / failed
    subject             TEXT DEFAULT '',
    body                TEXT DEFAULT '',
    note                TEXT DEFAULT '',
    response_text       TEXT DEFAULT '',
    response_at         DATETIME,
    created_at          DATETIME,
    FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE
);
```

### crm_tasks — задачи

```sql
CREATE TABLE crm_tasks (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id          INTEGER,
    title               TEXT NOT NULL,
    description         TEXT DEFAULT '',
    due_date            DATE,
    priority            TEXT DEFAULT 'normal',
    status              TEXT DEFAULT 'pending',
    -- pending / in_progress / completed / cancelled
    task_type           TEXT DEFAULT 'follow_up',
    -- follow_up / send_portfolio / check_response / remind / custom
    created_at          DATETIME,
    completed_at        DATETIME,
    FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE SET NULL
);
```

### crm_email_campaigns — кампании

```sql
CREATE TABLE crm_email_campaigns (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    name                TEXT NOT NULL,
    template_name       TEXT DEFAULT '',
    city_filter         TEXT DEFAULT '',
    total_count         INTEGER DEFAULT 0,
    sent_count          INTEGER DEFAULT 0,
    opened_count        INTEGER DEFAULT 0,
    replied_count       INTEGER DEFAULT 0,
    bounced_count       INTEGER DEFAULT 0,
    status              TEXT DEFAULT 'draft',
    -- draft / running / completed / paused / failed
    started_at          DATETIME,
    completed_at        DATETIME,
    created_at          DATETIME,
    updated_at          DATETIME
);
```

### crm_templates — шаблоны

```sql
CREATE TABLE crm_templates (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    name                TEXT NOT NULL,
    channel             TEXT NOT NULL,  -- email / tg / wa
    subject             TEXT DEFAULT '',
    body                TEXT NOT NULL,
    variables           TEXT DEFAULT '[]',
    is_default          INTEGER DEFAULT 0,
    created_at          DATETIME,
    updated_at          DATETIME
);
```

### crm_auto_rules — автоматические правила

```sql
CREATE TABLE crm_auto_rules (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    name                TEXT NOT NULL,
    trigger_type        TEXT NOT NULL,  -- no_response / schedule
    trigger_channel     TEXT DEFAULT '',
    trigger_days        INTEGER DEFAULT 0,
    funnel_stages       TEXT DEFAULT '',
    action_type         TEXT NOT NULL,  -- create_task / change_stage
    action_params       TEXT DEFAULT '',
    enabled             INTEGER DEFAULT 1,
    created_at          DATETIME,
    updated_at          DATETIME
);
```

### crm_orders — заказы

```sql
CREATE TABLE crm_orders (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id          INTEGER NOT NULL,
    description         TEXT DEFAULT '',
    photo_count         INTEGER DEFAULT 1,
    complexity          TEXT DEFAULT 'standard',
    price               INTEGER DEFAULT 0,
    deadline            DATE,
    status              TEXT DEFAULT 'new',
    -- new → in_progress → delivered → completed / cancelled
    notes               TEXT DEFAULT '',
    revision_count      INTEGER DEFAULT 0,
    created_at          DATETIME,
    updated_at          DATETIME,
    FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE
);
```

---

## 3. Воронка касаний

### Цепочка (без звонков)

```
День 0:   Email массово (по городу, темплейт email-improved-dark.html)
День 5:   TG follow-up (если есть TG у контакта)
День 9:   WA follow-up (если не ответил в TG, или TG нет)
День 14:  Второй email (Re:, короче, "больше не буду беспокоить")
День 21:  Unreachable (4 касания, 0 ответов)
```

### Статусы воронки

```
new                → ещё не касались
email_sent         → отправлен email
email_opened       → открыли письмо (tracking pixel)
follow_up_sent     → написали в первый мессенджер
second_follow_up   → написали во второй мессенджер
contacted          → ответили в любом канале
portfolio_sent     → отправили портфолио
interested         → проявили интерес
test_order         → дали тестовый заказ
regular_client     → постоянный клиент
not_interested     → отказались
unreachable        → 4+ касаний, 0 ответов
```

### Автоматические правила

| Правило | Триггер | Действие |
|---------|---------|----------|
| follow-up TG | email_sent + 5 дней без ответа | Задача: написать в TG |
| follow-up WA | follow_up_sent + 4 дня без ответа | Задача: написать в WA |
| второй email | second_follow_up + 5 дней без ответа | Задача: отправить Re: email |
| unreachable | 4 касания + 21 день | Предложить: пометить unreachable |
| reopen warm | email_opened + не replied + 7 дней | Задача: follow-up |

---

## 4. Скоринг — обновлённый

### Что влияет (из концепта v4)

| Фактор | Балл | Почему |
|--------|------|--------|
| Есть email | +15 | Первый канал — без email начинаем с мессенджера (сложнее) |
| Есть TG | +12 | Лучший канал для follow-up |
| TG trust ≥ 2 | +10 | Живой контакт, не бот |
| Есть производство (keywords) | +10 | Делают памятники → нужны портреты |
| Есть ЧПУ/лазер (keywords) | +8 | Много заказов на гравировку → постоянная потребность |
| Есть WA | +8 | Хороший второй канал |
| Есть сайт | +5 | Серьёзная компания |
| Несколько телефонов | +5 | Крупнее → больше заказов |
| Has marquiz | +3 | Онлайн-заказы → нужны фото для портфолио |
| Сеть филиалов | +3 | Много точек → много заказов |

**Максимум: ~84 баллов.** CMS НЕ влияет на скоринг — только информационное поле.

### Пороги сегментов

```
A ≥ 50  → Цифровая мастерская / производитель с мессенджером (первый приоритет)
B 30-49 → Есть сайт/мессенджер, но мало данных
C 15-29 → Минимум данных
D < 15  → Холодные
```

---

## 5. План разработки

### Phase 0: Стабилизация скрапера

Это то, что делает скрапер надёжным. Без этого — каждое касание с CRM может сломаться из-за краша пайплайна.

| Шаг | Что | Файлы | Зачем |
|:---:|---|---|---|
| 0.1 | **Pydantic ConfigSchema** | `granite/config.py` (NEW) | Ошибки конфига при старте, а не через 30 мин на проде |
| 0.2 | Подключить в cli.py + manager.py | `cli.py` | `load_config()` вместо `yaml.safe_load()` |
| 0.3 | **Rate limiting** | `granite/utils.py` | Глобальный token-bucket: не более N запросов/мин к одному домену. Без этого — бан 2ГИС/Яндекс/Jsprav |
| 0.4 | **Refactor enrichment_phase** | `granite/pipeline/enrichment_phase.py` | 400 строк → 3 модуля по <150. Легче дебажить, меньше побочных эффектов |
| 0.5 | Тесты | `tests/` | После каждого шага — `pytest tests/ -q` |
| 0.6 | Прогон на 1 городе | — | `python cli.py run --city Астрахань` — без ошибок |

**Зачем Phase 0 первая:** CRM без стабильных данных = пустая CRM. Если скрапер крашится на городе, CRM будет пустой, а рассылка уйдёт вникуда.

**Инструкции для агента Phase 0:**

```
## Правила:
1. Читай файл ПОЛНОСТЬЮ перед редактированием
2. НЕ трогай файлы, не указанные в задании
3. После изменения — запускай: pytest tests/ -q
4. Если тесты упали — фиксируй СРАЗУ
5. Используй Edit, не Write
6. Один логический шаг → один коммит
7. Не рефактори то, что не просили

## Шаг 0.1 — ConfigSchema
Создай granite/config.py:
- CityConfig, ScrapingConfig, SourceConfig, DedupConfig,
  ScoringWeights, ScoringLevels, ScoringConfig, ExportPreset,
  LoggingConfig, DatabaseConfig, ConfigSchema
- load_config(path) → validated dict
- source-поля loose (model_config = {"extra": "allow"})

## Шаг 0.3 — Rate limiting
В granite/utils.py добавь:
- class RateLimiter: token-bucket per domain
- Глобальный инстанс _rate_limiter
- Обёртку rate_limited_fetch(url) — вызывает fetch_page через лимитер
- В config.yaml: scraping.max_requests_per_minute: 30

## Шаг 0.4 — Refactor enrichment_phase
Разбить на:
- granite/enrichers/phone_handler.py (нормализация, дедуп телефонов)
- granite/enrichers/site_enricher.py (tech_extractor + messenger_scanner)
- granite/enrichers/tg_enricher.py (tg_finder + tg_trust)
enrichment_phase.py — только оркестрация (цикл по компаниям, вызовы)

После КАЖДОГО шага: pytest tests/ -q. Если упали — чини тут же.
```

---

### Phase 1: CRM backend (API + таблицы)

CRM работает, данные доступны через HTTP.

| Шаг | Что | Файлы | Результат |
|:---:|---|---|---|
| 1.1 | CRM таблицы + Alembic миграция | `granite/database.py`, миграция | 9 новых таблиц |
| 1.2 | Pydantic схемы для CRM | `granite/api/schemas.py` (NEW) | CompanyCRM, ContactCRM, TouchCRM, TaskCRM |
| 1.3 | FastAPI app + deps | `granite/api/app.py`, `deps.py` | `uvicorn granite.api.app:app` запускается |
| 1.4 | GET /api/v1/companies | `granite/api/companies.py` | Фильтры: city, segment, funnel_stage, has_telegram, min_score, search |
| 1.5 | GET /api/v1/companies/{id} | `granite/api/companies.py` | Карточка + activities |
| 1.6 | PATCH /api/v1/companies/{id} | `granite/api/crm.py` | Обновить funnel_stage, notes, tags |
| 1.7 | POST /api/v1/companies/{id}/touches | `granite/api/crm.py` | Логировать касание (email, TG, WA, manual) |
| 1.8 | POST /api/v1/companies/{id}/tasks | `granite/api/tasks.py` | Создать задачу |
| 1.9 | GET /api/v1/tasks | `granite/api/tasks.py` | Список задач: pending, today, overdue |
| 1.10 | PATCH /api/v1/tasks/{id} | `granite/api/tasks.py` | Завершить задачу |
| 1.11 | GET /api/v1/funnel | `granite/api/funnel.py` | Воронка: количества по stages |
| 1.12 | GET /api/v1/export/{preset} | `granite/api/export.py` | Скачать CSV |
| 1.13 | Seed: стартовые шаблоны + правила | скрипт или migration | 3 email, 3 TG, 2 WA шаблона + 5 auto_rules |
| 1.14 | cli.py: команда `api` | `cli.py` | `python cli.py api` |
| 1.15 | Docker | `Dockerfile`, `docker-compose.yml` | `docker compose up` |

**Инструкции для агента Phase 1:**

```
## Шаг 1.1 — CRM таблицы
В granite/database.py добавить ORM-модели:
CrmContactRow, CrmEmailLogRow, CrmTouchRow, CrmTaskRow,
CrmCampaignRow, CrmTemplateRow, CrmAutoRuleRow, CrmOrderRow

Все с ForeignKey на companies.id (CASCADE enriched_companies → через companies).
CrmContactRow.company_id = PRIMARY KEY (1:1 с company).

Создать Alembic миграцию: alembic revision --autogenerate -m "add_crm_tables"

## Шаг 1.3 — FastAPI
Создать granite/api/:
- app.py: FastAPI, CORS middleware, lifespan, include routers
- deps.py: get_db() (lru_cache), get_config()

## Шаг 1.4-1.12 — Endpoints
Каждый endpoint в отдельном файле-роутере.
Query параметры для /companies:
  ?city=&segment=&funnel_stage=&has_telegram=1&has_website=1
  &min_score=&max_score=&search=&page=1&per_page=50
  &order_by=crm_score&order_dir=desc

Пагинация: {"items": [...], "total": 100, "page": 1, "per_page": 50}

После КАЖДОГО шага: pytest tests/ -q
```

---

### Phase 2: Email-кампании

Массовая рассылка + трекинг открытий.

| Шаг | Что | Файлы | Результат |
|:---:|---|---|---|
| 2.1 | Email sender (smtplib / Resend) | `granite/email/sender.py` (NEW) | Отправка HTML email через Gmail SMTP |
| 2.2 | Tracking pixel endpoint | `granite/api/tracking.py` | GET /api/v1/track/open/{id}.png → 1×1 PNG + лог |
| 2.3 | Создание кампании | `granite/api/campaigns.py` | POST /api/v1/campaigns (city, template, filter) |
| 2.4 | Запуск кампании | `granite/api/campaigns.py` | POST /api/v1/campaigns/{id}/run (SSE progress) |
| 2.5 | Статистика кампании | `granite/api/campaigns.py` | GET /api/v1/campaigns/{id}/stats |
| 2.6 | Авто-правила: запуск | `granite/api/rules.py` | POST /api/v1/rules/process — проверяет все правила, создаёт задачи |
| 2.7 | Follow-up очередь | `granite/api/followup.py` | GET /api/v1/followup — контакты которым нужно написать |
| 2.8 | Второй email шаблон | seed | "Re: ..." с "больше не буду беспокоить" |

**Инструкции для агента Phase 2:**

```
## Шаг 2.1 — Email sender
granite/email/sender.py:
- send_email(to, subject, html_body, reply_to=None)
- Использует smtplib + Gmail SMTP (настройки из .env)
- Каждый email → запись в crm_email_logs с tracking_id (UUID)
- В HTML внедряется tracking pixel:
  <img src="{BASE_URL}/api/v1/track/open/{tracking_id}.png" ...>

## Шаг 2.2 — Tracking pixel
GET /api/v1/track/open/{id}.png:
1. Находим crm_email_logs по tracking_id
2. Обновляем: opened_at = now(), status = 'opened'
3. Обновляем crm_contacts: email_opened_count++, last_email_opened_at
4. Если funnel_stage == 'email_sent' → 'email_opened'
5. Возвращаем 1×1 transparent PNG (43 байта, cache-control: no-store)

## Шаг 2.4 — Запуск кампании
POST /api/v1/campaigns/{id}/run:
1. Фильтр: companies WHERE emails NOT NULL AND emails != '[]'
   AND city = campaign.city_filter
   AND company_id NOT IN (SELECT company_id FROM crm_email_logs)
2. Для каждого: send_email() + crm_touches (channel='email')
3. Обновить crm_contacts: email_sent_count++, funnel_stage = 'email_sent'
4. SSE (Server-Sent Events) для прогресс-бара
```

---

### Phase 3: WA/TG воркеры + фронтенд

Автоматизация мессенджеров и веб-интерфейс.

| Шаг | Что | Файлы | Результат |
|:---:|---|---|---|
| 3.1 | WA воркер (whatsapp-web.js) | `workers/wa-worker.js` (NEW) | Node.js скрипт: берёт задачи из crm_tasks, отправляет |
| 3.2 | TG воркер (Pyrogram) | `workers/tg-worker.py` (NEW) | Python: поиск по номеру, отправка сообщений |
| 3.3 | Kill-switch | воркеры | Проверка: если входящее за 24ч → стоп автоматика |
| 3.4 | Next.js проект | `granite-crm-web/` (NEW repo) | Dashboard, таблица, карточка |
| 3.5 | Dashboard | `/app/page.tsx` | Метрики: всего, email отправлено, конверсия, выручка |
| 3.6 | Таблица компаний | `/app/companies/page.tsx` | Фильтры, сортировка, пагинация, bulk actions |
| 3.7 | Company card | `/app/companies/[id]/page.tsx` | Все данные + touches timeline + задачи + заказы |
| 3.8 | Кампании | `/app/campaigns/page.tsx` | Создать, запустить, статистика, SSE прогресс |
| 3.9 | Follow-up очередь | `/app/followup/page.tsx` | Кого касаться, кнопки [TG] [WA] [Email] |
| 3.10 | Запуск скрапера на все города | — | Реальные данные |

**Инструкции для агента Phase 3:**

```
## Шаг 3.1 — WA воркер
workers/wa-worker.js:
- Подключение к SQLite: better-sqlite3 (синхронный, быстрый)
- whatsapp-web.js с LocalAuth + headless Puppeteer
- Каждый 5 минут: SELECT FROM crm_tasks WHERE status='pending' AND channel='wa'
- Отправка с эмуляцией печати (typing simulation)
- Рандомная задержка: random(120, 300) секунд между сообщениями
- После отправки: crm_touches + update crm_contacts (wa_sent_count++, last_wa_at)
- Kill-switch: если crm_touches direction='incoming' за 24ч → skip
- Только в рабочие часы МСК (9:00-18:00)

## Шаг 3.2 — TG воркер
workers/tg-worker.py:
- Pyrogram (MTProto API)
- Аналогично WA: опрашивает crm_tasks, отправляет
- Поиск по номеру: ImportContacts → GetContacts
- В первом сообщении — НЕТ ссылок (бан за спам)
- Kill-switch аналогично

## Шаг 3.4-3.9 — Фронтенд
Используй fullstack-dev skill для Next.js.
Минимальный функционал:
- Таблица с серверной пагинацией и фильтрами
- Карточка с timeline касаний
- Кнопки логирования касаний
- Кампании: создать → превью → запустить → прогресс
```

---

### Phase 4: Автоматизация и аналитика

| Шаг | Что | Результат |
|:---:|---|---|
| 4.1 | Cron-задача: авто-правила каждый час | След-up очередь обновляется автоматически |
| 4.2 | Воронка по городам | Графики конверсии |
| 4.3 | А/Б тестирование шаблонов | Два шаблона → сравнение open rate |
| 4.4 | Персонализация через LLM | Каждое сообщение уникальное (Spintax или AI) |
| 4.5 | Экспорт отчётов | Excel/CSV с конверсией по городам |

---

## 6. Приоритеты

### Сначала (Phase 0)

**Rate limiting** — без него бан источников при массовом скрапинге. 10-20 сообщений в день по WA — это тихо, но скрапер делает тысячи запросов к 2ГИС/Яндекс/Jsprav. Rate limiting на уровне HTTP-клиента, не на уровне мессенджеров.

**Refactor enrichment_phase** — 400 строк оркестратор + обогащение + нормализация в одном файле. Любой баг = сложно локализовать. Разбить на модули = каждый модуль тестируется отдельно.

**ConfigSchema** — malformed YAML = runtime KeyError через 30 минут работы.

### Потом (Phase 1-2)

CRM API + email-кампании. Без этого можно только смотреть на базу руками.

### Потом (Phase 3-4)

Воркеры + фронтенд. Автоматизация мессенджеров — это риск бана, нужно аккуратно.

---

## 7. Правила работы с AI-агентами

### Формат промпта — ВСЕГДА

```
## Правила:
1. Читай файл ПОЛНОСТЬЮ перед редактированием
2. НЕ трогай файлы, не указанные в задании
3. После изменения — запускай: pytest tests/ -q
4. Если тесты упали — фиксируй СРАЗУ, не продолжай
5. Используй Edit, не Write (не перезаписывай файлы)
6. Один логический шаг → один коммит
7. Не рефактори то, что не просили
8. Добавляй __all__ в новые модули
9. Добавляй docstring к новым функциям/классам
10. Не добавляй зависимости без необходимости
```

### Одна задача = один агент = один коммит

```
✅ ПРАВИЛЬНО:
  Агент: "Создай granite/config.py с Pydantic ConfigSchema" → коммит → тест → ок
  Агент: "Подключи ConfigSchema в cli.py" → коммит → тест → ок

❌ НЕПРАВИЛЬНО:
  Агент: "Переделай весь проект под CRM" → 50 файлов → 200 багов
```

### Запускать последовательно, никогда параллельно

```
Step 0.1 → test → commit → Step 0.2 → test → commit → …
```

### Файлы-границы

Агент НЕ трогает файлы из других шагов. Если нужно что-то из другого файла — указать явно.

---

## 8. Запуск — шпаргалка

### Скрапер

```bash
python cli.py run --city Астрахань
python cli.py run --city Астрахань --re-enrich
python cli.py run --all --max-threads 2
python cli.py run --city Москва --force    # очистить и заново
```

### API

```bash
python cli.py api --port 8000

# Компании
curl "http://localhost:8000/api/v1/companies?segment=A&per_page=10"
curl "http://localhost:8000/api/v1/companies/42"

# CRM
curl -X PATCH http://localhost:8000/api/v1/companies/42 \
  -H "Content-Type: application/json" \
  -d '{"funnel_stage": "contacted"}'

curl -X POST http://localhost:8000/api/v1/companies/42/touches \
  -H "Content-Type: application/json" \
  -d '{"channel": "tg", "direction": "outgoing", "body": "Добрый день!..."}'

# Задачи
curl http://localhost:8000/api/v1/tasks?status=pending
curl -X POST http://localhost:8000/api/v1/companies/42/tasks \
  -d '{"title": "Follow-up WA", "due_date": "2026-04-15"}'

# Follow-up очередь
curl http://localhost:8000/api/v1/followup

# Воронка
curl http://localhost:8000/api/v1/funnel

# Кампании
curl -X POST http://localhost:8000/api/v1/campaigns \
  -d '{"name": "Волгоград #1", "city_filter": "Волгоград", "template_name": "cold_email_1"}'
curl -X POST http://localhost:8000/api/v1/campaigns/1/run
curl http://localhost:8000/api/v1/campaigns/1/stats

# Экспорт
curl http://localhost:8000/api/v1/export/hot_leads -o hot_leads.csv

# Auto-rules
curl -X POST http://localhost:8000/api/v1/rules/process
```

### Docker

```bash
docker compose up --build    # API на :8000
docker compose logs -f        # логи
```

### WA/TG воркеры

```bash
# WA (Node.js)
cd workers && npm install
node wa-worker.js

# TG (Python)
python workers/tg-worker.py

# Kill-switch: оба воркера проверяют crm_touches перед отправкой
```

### Мониторинг

```bash
# Сколько компаний собрано
python -c "
from granite.database import Database, CompanyRow, EnrichedCompanyRow
db = Database()
with db.session_scope() as s:
    total = s.query(CompanyRow).count()
    with_email = s.query(CompanyRow).join(EnrichedCompanyRow).filter(...).count()
    seg_a = s.query(CompanyRow).filter(CompanyRow.segment == 'A').count()
    print(f'Total: {total}, Segment A: {seg_a}')
"

# Pipeline runs
python -c "
from granite.database import Database, PipelineRunRow
db = Database()
with db.session_scope() as s:
    for r in s.query(PipelineRunRow).order_by(PipelineRunRow.id.desc()).limit(10):
        print(f'{r.city:20s} {r.stage:10s} {r.records_found or 0:>5d} found')
"

# CRM воронка
python -c "
from granite.database import Database, CrmContactRow
db = Database()
with db.session_scope() as s:
    from sqlalchemy import func
    rows = s.query(CrmContactRow.funnel_stage, func.count()).group_by(CrmContactRow.funnel_stage).all()
    for stage, cnt in rows:
        print(f'{stage:25s} {cnt:>5d}')
"
```

---

## 9. Контрольный чеклист

### Phase 0

- [ ] `load_config()` валидирует config.yaml (ошибки при старте, не runtime)
- [ ] `pytest tests/` — все тесты проходят
- [ ] `python cli.py run --city Астрахань` — completed без ошибок
- [ ] Rate limiter работает (логи показают throttled requests)
- [ ] enrichment_phase.py < 150 строк (логика вынесена)

### Phase 1

- [ ] `alembic upgrade head` — 9 новых CRM-таблиц созданы
- [ ] `python cli.py api` — сервер запускается
- [ ] `curl /api/v1/companies?per_page=5` — возвращает JSON
- [ ] `curl -X POST /api/v1/companies/1/touches` — логирует касание
- [ ] `curl /api/v1/funnel` — возвращает воронку
- [ ] `docker compose up` — работает

### Phase 2

- [ ] Email отправляется (проверить на себе)
- [ ] Tracking pixel: открыть письмо → crm_contacts обновился
- [ ] Кампания: создать → превью → запустить → SSE прогресс
- [ ] `POST /rules/process` — создаёт задачи по правилам

### Phase 3

- [ ] WA воркер: подключается к WhatsApp, берёт задачи, отправляет
- [ ] TG воркер: ищет по номеру, отправляет
- [ ] Kill-switch: входящее сообщение → автоматика стоп
- [ ] Фронтенд: таблица, карточка, кампании, follow-up очередь
- [ ] Скрапер прогонен на все города — база populated
