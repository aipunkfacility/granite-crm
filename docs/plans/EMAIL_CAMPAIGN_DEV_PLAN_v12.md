# RetouchGrav — Email Campaign Dev Plan v12

> Александр · @ganjavagen  
> База: ~6 000 компаний → **434 приоритетных цели** (A+B, не-сеть, валидный email)  
> SMTP: ai.punk.facility@gmail.com (личный аккаунт, App Password)  
> v12 · 2026-04-27 · v11 + верификация аудита (audits.md + scraper-audit.md) + 4 новых задачи + 6 уточнений

---

## Содержание

1. [Что изменилось относительно v11](#1-что-изменилось-относительно-v11)
2. [Верификация аудита — что реально, что нет](#2-верификация-аудита--что-реально-что-нет)
3. [Стратегия и волны](#3-стратегия-и-волны)
4. [Прогрев домена](#4-прогрев-домена)
5. [Шаблоны писем](#5-шаблоны-писем)
6. [Технический план — этапы реализации](#6-технический-план--этапы-реализации)
7. [Roadmap по дням](#7-roadmap-по-дням)
8. [Открытые вопросы](#8-открытые-вопросы)

---

## 1. Что изменилось относительно v11

### Новые задачи (из аудита, верифицированные против кода)

| # | Задача | Откуда | Этап | Почему |
|---|--------|--------|------|--------|
| 15 | Template name pattern: `^[a-z0-9_]+$` → разрешить кириллицу | Аудит #6, верифицировано | 2 | `schemas.py:88` запрещает кириллицу в имени шаблона — неприемлемо для русского рынка |
| 16 | Создать `.env.example` с описанием всех переменных | Аудит #9, верифицировано | 1 | Нет `.env.example`, нет проверки обязательных переменных при старте |
| 17 | Рефакторинг f-string в raw SQL → параметризованные `:param` | Аудит #2, верифицировано | 4 | `companies.py` интерполирует значения в SQL через f-string — антипаттерн, даже если сейчас безопасно через Pydantic |
| 18 | `_get_campaign_recipients`: заменить `.all()` на курсор/батч | Аудит #6 + #8, верифицировано | 2 | `campaigns.py:134` загружает ВСЕ компании в память — при 50K+ OOM risk |

### Уточнения к существующим задачам

| Задача | Уточнение | Источник |
|--------|-----------|----------|
| 1 (Unsubscribe) | Auth bypass для `/api/v1/track/` **уже частично реализован** в коде (строки 280–309 `app.py`) — нужно проверить полноту | Верификация |
| 6 (Bounce parser) | `process_bounces.py` **уже использует** `get_engine()` из app (аудит утверждал обратное — но это было в v8, уже пофикшено) | Верификация |
| 8 (SMTP_SSL) | Подтверждено: `sender.py:136-138` использует `SMTP+starttls()` с портом 587 по умолчанию — не работает с 465 | Верификация |
| 12 (Immutable шаблоны) | Подтверждено: `CrmEmailLogRow.template_name` (String, строка 351), `CrmTemplateRow` не имеет `retired` — всё как запланировано в v11 | Верификация |
| 4 (Валидатор) | Агрегаторы из scraper-audit (A-1: SKIP_DOMAINS) — **предпосылка** для валидатора. Без чистой базы валидатор фильтрует меньше | Scraper-audit |
| 7 (SEO-regex) | Scraper-audit A-7: расширение `is_seo_title()` + `is_aggregator_name()` — **дополнительные паттерны** к задаче 7 | Scraper-audit |

### Открытые вопросы, перенесённые из аудита

| Вопрос | Приоритет | Когда решать |
|--------|-----------|-------------|
| Rate limiting на API-эндпоинты (slowapi / in-memory) | LOW | После запуска Волны 1 — внутренний инструмент, не публичный API |
| DNS rebinding защита в `is_safe_url()` | DEFER | Внутренний инструмент, риск минимальный |
| SMTP health check при старте приложения | MEDIUM | Этап 1 (задача 16 — вместе с `.env.example`) |
| CORS origins: warning при использовании дефолтов | ALREADY DONE | В коде уже есть `logger.warning` при использовании дефолтных origins (строки 100–103 `app.py`) |
| `q.count()` + `q.offset().limit()` race condition в `list_companies` | LOW | SQLite под WAL — практически не проявляется при текущих объёмах |

<details>
<summary>Разница v10 → v11 (для справки)</summary>

| # | В v10 (баг) | В v11 (фикс) | Почему |
|---|-------------|--------------|--------|
| 1 | `total_opened` / `total_replied` никогда не обновляются — SSE всегда показывает 0 | ✅ Инкремент в tracking.py и process_replies.py | Оператор не видит метрик без этих счётчиков |
| 2 | Отписка не вызывает `cancel_followup_tasks()` — follow-up приходит после отписки | ✅ Вызов `cancel_followup_tasks()` в `unsubscribe_confirm()` | Отписка = никаких писем, включая запланированные follow-up |
| 3 | Follow-up задача создаётся (5.1), отменяется (5.2), но **никогда не отправляется** — нет механизма исполнения | ✅ Добавлен `scripts/process_followups.py` (задача 11) | Архитектурная дыра: без исполнителя follow-up мёртвый код |
| 4 | `_get_campaign_recipients()` вызывается, но не определена | ✅ Добавлена реализация (задача 2.4) | Без неё непонятно: кому отправлять, как избежать дублей при resume |
| 5 | `CrmTouchRow`: отписка пишет `note=`, reply пишет `body=` — два разных поля | ✅ Унифицировано: везде `body=` | Один и тот же ORM-объект, несовместимые поля = runtime error |
| 6 | Auth bypass только для `/unsubscribe/`, но `/track/open/` тоже вызывается без API-ключа | ✅ Добавлен bypass для `/api/v1/track/` | Почтовые клиенты не отправляют заголовки авторизации |

</details>

---

## 2. Верификация аудита — что реально, что нет

Аудит (`docs/archive/audits.md`, 10 областей) был написан Claude **без доступа к коду**, только по документации. Верификация проведена путём чтения исходного кода в `/home/z/my-project/granite-crm/`.

### 2.1 Уже исправлено (аудит опоздал)

| Утверждение аудита | Реальность в коде | Вердикт |
|--------------------|-------------------|---------|
| `app.py:126`: `!=` уязвим к timing-attack | `app.py:300`: `hmac.compare_digest(provided_key, expected_key)` | ❌ Ложное — уже пофикшено |
| `sender.py:81-84`: body_text без экранирования → XSS | `sender.py:90`: `html.escape(body_text)` | ❌ Ложное — уже пофикшено |
| `tg_finder.py` не вызывает `is_safe_url()` | `tg_finder.py:5,26`: импортирует и вызывает `is_safe_url` | ❌ Ложное — уже пофикшено |
| `CrmEmailCampaignRow.filters` — `Text` вместо `JSON` | `database.py:414`: `Column(JSON, default=dict)` | ❌ Ложное — миграция `i3j4k5l6m7n8` конвертировала |
| `PATCH /companies/{id}` создаёт CrmContactRow без проверки компании | `companies.py:329-331`: `db.get(CompanyRow, company_id)` → 404 если нет | ❌ Ложное — проверка есть |
| `tracking_id` не валидируется → SQL injection | `tracking.py:21,34`: `_TRACKING_ID_PATTERN = re.compile(r"^[a-zA-Z0-9\-_]{8,64}$")` | ❌ Ложное — валидация есть |
| `GET /export/{city}.csv` — path traversal через `city` | `export.py:64`: ORM filter, `sanitize_filename()` на строке 81 | ❌ Ложное — path traversal невозможен |
| Alembic: `stamp head` вместо последовательных миграций | `database.py:472-543`: 3-уровневая стратегия, stamp только для fresh install | ❌ Ложное — уже пофикшено |
| `VALID_STAGES` нет CHECK constraint | CHECK constraint добавлен через миграцию (комментарий в `database.py:221-222`) | ❌ Ложное — добавлено |

### 2.2 Подтверждённые проблемы (действительны)

| Утверждение аудита | Реальность в коде | Действие в v12 |
|--------------------|-------------------|---------------|
| Template name `^[a-z0-9_]+$` запрещает кириллицу | `schemas.py:88`: `pattern=r"^[a-z0-9_]+$"` — точно так | Задача 15 (этап 2) |
| `_get_campaign_recipients` загружает `.all()` в память | `campaigns.py:134`: `rows = q.all()` — точно так | Задача 18 (этап 2, внутри задачи 2) |
| `list_companies`: 2 запроса `count()` + `offset().limit()` | `companies.py:308-309` — точно так | Отложено (низкий приоритет) |
| Raw SQL через f-string в `companies.py` | `companies.py:126-131,148-158` — f-string с Pydantic-валидацией | Задача 17 (этап 4) |
| Нет `.env.example` | Проверено: файл не существует | Задача 16 (этап 1) |
| `config_validator.py` не проверяет SMTP/API ключи | `config_validator.py` — только scoring, database, scraping | Задача 16 (этап 1) |
| Нет SMTP health check при старте | Проверено: нет проверки подключения | Задача 16 (этап 1) |
| `setattr(contact, key, value)` в цикле | `companies.py:417` — да, но Pydantic ограничивает до 3 полей | Приемлемо, добавить комментарий |

### 2.3 Неверные номера строк (аудит без кода)

| Утверждение | Указано | Реально |
|-------------|---------|---------|
| `api_key_auth_middleware` | app.py:107-132 | app.py:280-309 |
| CORS defaults | app.py:69-74 | app.py:79-84 |
| `is_safe_url()` | utils.py:480-558 | utils.py:699-777 |
| `VALID_STAGES` | database.py:154-157 | database.py:197-200 |
| `setattr` в PATCH | companies.py:177-178 | companies.py:417 |
| `needs_review` в merger | merger.py:152-217 | merger.py:168-246 |

### 2.4 Scraper-audit (качество данных)

Scraper-audit (`docs/archive/scraper-audit.md`) анализирует качество базы и НЕ зависит от кода — это анализ данных. Его выводы **достоверны** и напрямую влияют на email-кампанию:

| Проблема | Влияние на рассылку | Действие |
|----------|---------------------|----------|
| 56% web_search — агрегаторы (660 из 1174) | Письма уходят колл-центрам, а не мастерским | Предпосылка: scraper-audit A-1 перед запуском |
| 51% jsprav — нецелевые категории (ритуальные услуги) | Нецелевая аудитория не ответит | Предпосылка: scraper-audit A-2 перед запуском |
| 58% enriched — SEO-имена вместо реальных | Обращение «Уважаемая компания Памятники из гранита» | Задача 7 + scraper-audit A-4/A-7 |
| Нет фильтра по городу контактов | Московский телефон в записи города Абаза | Scraper-audit A-5, не блокирует рассылку |

**Важно:** Scraper-audit A-1 (SKIP_DOMAINS) и A-2 (jsprav категории) — это **предпосылки** для запуска рассылки. Без них в базе ~40% мусора, который валидатор (задача 4) не сможет отфильтровать полностью. Однако рассылку можно начинать **до** их реализации, если вручную проверить список из 434 приоритетных целей.

---

## 3. Стратегия и волны

### 3.1 Реальное состояние базы

```
Всего в базе:                           ~6 000 компаний
Обработанные города:                    29 из 46
Сегмент A, не-сеть, валидный email:     175
Сегмент B, не-сеть, валидный email:     259
────────────────────────────────────────────────────────
Приоритетная база:                      434 компании
Крупные сети (ручная работа):           8 компаний
```

### 3.2 Волны

Принцип: **тестируем только одну переменную за раз**.

| Фаза | Волна | Аудитория | Размер | Шаблон | Цель |
|------|-------|-----------|--------|--------|------|
| **0** | Калибровка | Сегмент A, email, случайные 50 | 50 | `cold_email_v1`, тема A vs B | Найти лучшую тему |
| **1** | Marquiz | Marquiz=1, tg_trust≥2, A+B | ~22 | `cold_email_marquiz` | Тёплая аудитория |
| **1** | Bitrix | CMS=bitrix, A+B | ~41 | `cold_email_v1` (победитель) или `cold_email_bitrix` | Деловой тон |
| **2** | Остаток A | Tilda+WP, A | ~60–80 | `cold_email_v1` (победитель) | Основной сегмент |
| **2** | Остаток B | B | ~259 | `cold_email_v1` (победитель) | Масштаб |

> **Важно по волне 1 / Marquiz:** После фикса SEO-regex (задача 7) «Гранитные мастерские» и «Гранит-Мастер» больше не флагаются как SEO. Но остаются другие SEO-паттерны (купить/цены/изготовление + город). Перед запуском проверить список — 22 компании, 10 минут.

---

## 4. Прогрев домена

### 4.1 Обязательный чеклист до первой отправки

Поскольку отправка через Gmail — SPF/DKIM/DMARC настраивать не нужно (Google управляет ими). Но нужно другое:

```
[ ] Gmail: включить 2FA на ai.punk.facility@gmail.com
[ ] Gmail: создать App Password (https://myaccount.google.com/apppasswords)
[ ] .env: SMTP_HOST=smtp.gmail.com, SMTP_PORT=465, SMTP_PASS=<app-password>
[ ] .env: IMAP_HOST=imap.gmail.com (для bounce + reply)
[ ] Проверка: отправить тестовое письмо себе через sender.py
[ ] Проверить заголовки полученного письма (Show Original в Gmail):
    - SPF: pass (google.com)
    - DKIM: pass (google.com) — подпись Google, не ваша
[ ] mail-tester.com: оценка ≥ 8/10 (проверка содержимого письма, не только заголовков)
    Тест: отправить письмо на адрес теста → проверить отчёт
[ ] Публичный URL для tracking/unsubscribe настроен (см. открытые вопросы)
    Проверка: curl {BASE_URL}/health → {"status": "ok"}
[ ] Unsubscribe-эндпоинт работает:
    GET {BASE_URL}/api/v1/unsubscribe/{token} → страница подтверждения
[ ] Tracking pixel работает:
    открыть {BASE_URL}/api/v1/track/open/test1234.png → 200, прозрачный PNG
[ ] Перед каждым запуском кампании: curl {BASE_URL}/health → ok
    (публичный URL может упасть; проверка занимает 5 секунд)
```

### 4.2 График прогрева (первые 10 дней)

| День | Лимит писем | Статус |
|------|-------------|--------|
| 1 | 0 — только чеклист и инфра | Подготовка |
| 2 | 10 | Старт Фазы 0 |
| 3 | 20 | Фаза 0 продолжение |
| 4 | 20 | Фаза 0 окончание |
| 5–6 | 0 — мониторинг ответов | Пауза |
| 7 | 30 | Старт Волны 1 |
| 8 | 30 | |
| 9 | 50 | |
| 10+ | 50 (global daily limit) | Рабочий режим |

> Итого Фаза 0: 50 писем за 3 дня (10+20+20). Паузы — наблюдение за bounce rate. Если bounce > 5% → стоп, разбираемся с базой.

### 4.3 Метрики здоровья

| Метрика | Норма | Стоп-сигнал |
|---------|-------|-------------|
| Bounce rate (hard) | < 2% | ≥ 5% → стоп |
| Spam complaints | < 0.1% | ≥ 0.5% → стоп |
| Open rate (mail.ru/Яндекс) | 10–20% | < 5% → проверить что Gmail не в спаме |
| Reply rate | цель ≥ 3% | < 1% → пересмотреть шаблон |

### 4.4 Признаки блокировки Gmail

| Симптом | Что делать |
|---------|-----------|
| Письма уходят в «Промоакции» | Норма — не блокировка |
| SMTP ошибка 421 / 550 | Снизить объём на 50% на 3 дня |
| Письма вообще не уходят | Проверить App Password, SMTP-настройки |
| Bounce rate ≥ 5% | Стоп кампании, разбор базы |

---

## 5. Шаблоны писем

### 5.1 `cold_email_v1` — основной (Фаза 0, Волны 2–4)

```
Имя в БД: cold_email_v1
Канал: email
body_type: plain

─── ТЕМА A ───
Подготовка фото под гравировку — пришлите самый сложный случай

─── ТЕМА B ───
Ретушь под памятник: старые и плохие фото — в день заказа

─── ТЕЛО ───
Здравствуйте.

Ищу контакты мастерских в {city} и области, которым нужна
качественная ретушь портретов для гравировки на памятниках.

Беру сложные случаи: старые фото, низкое разрешение,
повреждённые снимки. Нейросети + ручная доработка.
Срок — 12–24 часа, срочно — 3–6 часов. Цена — от 700 ₽.

Готов сделать 1–2 пробных бесплатно — на ваших реальных
исходниках, без обязательств.

Примеры работ: https://retouchgrav.netlify.app

Александр
Telegram: @ganjavagen

---
Если не актуально — ответьте «нет», больше не напишу.
Отписаться: {unsubscribe_url}
```

### 5.2 `cold_email_marquiz` — для Marquiz + TG (Волна 1)

```
Имя в БД: cold_email_marquiz
Канал: email
body_type: plain

─── ТЕМА A ───
Подготовка фото под гравировку — могу разгрузить вас на ретуши

─── ТЕМА B ───
Ретушь портретов для вашей мастерской — оплата после результата

─── ТЕЛО ───
Здравствуйте.

Ищу контакты мастерских в {city} и области, которым нужна
качественная ретушь портретных фото для гравировки на памятниках.

Беру всё что сложно: старые снимки 80-х, фото на документах,
групповые — когда нужно вырезать одного человека, низкое разрешение.

Нейросети + ручная доработка. 12–24 часа, срочно 3–6 часов.
Цена — от 700 ₽, оплата после результата для новых клиентов.

Начнём с бесплатной пробы: пришлите 1–2 ваших текущих исходника —
покажу результат.

Примеры работ: https://retouchgrav.netlify.app

Александр
Telegram: @ganjavagen

---
Отписаться: {unsubscribe_url}
```

### 5.3 `follow_up_email_v1` — follow-up (только email, через 7 дней)

```
Имя в БД: follow_up_email_v1
Канал: email
body_type: plain

─── ТЕМА ───
Re: {original_subject}

─── ТЕЛО ───
Добрый день.

Писал на прошлой неделе про ретушь портретов.

Не хочу надоедать — просто оставлю ссылку на примеры:
https://retouchgrav.netlify.app

Первый портрет бесплатно — пришлите в ответ любой сложный исходник.

Александр · @ganjavagen
---
Отписаться: {unsubscribe_url}
```

> **v11: Тема follow-up** — `{original_subject}` — плейсхолдер, который заменяется на тему исходного письма при отправке. `process_followups.py` (задача 11) извлекает оригинальную тему из `CrmTouchRow` и подставляет её. Если исходное письмо было отправлено с темой B (`Ретушь под памятник...`), follow-up будет `Re: Ретушь под памятник...`, а не `Re: подготовка фото под гравировку`.

### 5.4 Критерий выбора победителя A/B

**Реальность:** при 25/25 писем на каждую тему статистическая значимость минимальна. 1 ответ = 4% — это шум.

**Практический критерий:**

- Если одна тема набрала **≥ 2 ответа**, а другая **0** — используем первую
- Если обе темы дали **0 ответов** за 5 дней — проблема в теле письма или домене, не в теме. Пересматриваем письмо, не запускаем волны
- Если обе дали **1 ответ** — **ничья**, используем тему A (по умолчанию)

Никаких процентов и «превышение на 50%» на выборке из 25 — это иллюзия точности.

### 5.5 `cold_email_bitrix` — для Bitrix CMS (Волна 1, опционально)

> **Опциональный шаблон.** Если Bitrix-кампании (41 компания) хочется выделить отдельным более формальным письмом — используйте этот шаблон. Если нет — используется `cold_email_v1` с темой-победителем, как в таблице волн выше.

```
Имя в БД: cold_email_bitrix
Канал: email
body_type: plain

─── ТЕМА A ───
Аутсорс ретуши под гравировку — в день заказа

─── ТЕМА B ───
Подготовка фото для гравировки на памятниках — без предоплаты

─── ТЕЛО ───
Здравствуйте.

Предлагаю сотрудничество по ретуши портретов
для гравировки на памятниках.

Что делаю:
— восстановление сложных исходников (старые, размытые, повреждённые)
— ретушь под конкретный станок и технологию (лазер / ударный)
— замена фона, одежды, монтаж, сборка в полный рост
— срок в день обращения, оплата после одобрения результата

Для партнёрских мастерских с постоянным потоком — индивидуальные
условия и выделенный приоритет.

Начнём с бесплатной пробы: пришлите 1–2 реальных исходника —
покажу результат на вашем материале.

Примеры работ: https://retouchgrav.netlify.app

Александр
Telegram: @ganjavagen

---
Отписаться: {unsubscribe_url}
```

> **Почему формальный тон:** Bitrix-мастерские — часто с менеджером или офис-менеджером. Письмо может читать не владелец. Чёткая структура и буллеты работают лучше, чем разговорный стиль.

---

## 6. Технический план

### Текущее состояние кода (что уже есть)

| Компонент | Статус |
|-----------|--------|
| `CrmEmailCampaignRow.subject_a` / `subject_b` | ✅ В ORM + миграция |
| `CrmTemplateRow.render()` + `render_subject()` | ✅ Полная реализация |
| Campaign lock (Python `threading.Lock()`) | ✅ Потокобезопасный |
| Атомарный `UPDATE ... WHERE status NOT IN (...)` | ✅ |
| Tracking pixel + bot-фильтрация | ✅ |
| SMTP retry на `SMTPTemporaryError` | ✅ |
| Stale campaign watchdog (`POST /campaigns/stale`) | ✅ Ручной |
| `EmailSender._smtp_send` | ⚠️ Использует `SMTP+starttls()` — не работает с портом 465 |
| `hmac.compare_digest` для API-ключа | ✅ (подтверждено аудитом) |
| `html.escape()` в email sender | ✅ (подтверждено аудитом) |
| `is_safe_url()` в tg_finder | ✅ (подтверждено аудитом) |
| `CrmEmailCampaignRow.filters` → JSON | ✅ (подтверждено аудитом) |
| CHECK constraint на funnel_stage | ✅ Через миграцию (подтверждено аудитом) |

### Что нужно реализовать

---

## 6.0 Этапы реализации + TDD

Все 18 задач (14 из v11 + 4 новых из аудита) разбиты на 4 этапа. Каждый этап — законченный кусок работы, который можно протестировать и задеплоить независимо. TDD: сначала тест, потом код.

### Этап 1: Фундамент — критические фиксы + инфраструктура (0 писем)

**Цель:** починить то, что сломано, и подготовить инфраструктуру для первой отправки. После этого этапа CRM способна отправить тестовое письмо и обработать отписку.

**Принцип TDD:** для каждого фикса сначала пишем тест, который воспроизводит баг, потом фиксим.

| Задача | Что делаем | Тесты (сначала!) |
|--------|-----------|-----------------|
| **8. SMTP_SSL** | `sender.py`: порт 465 → `SMTP_SSL`, 587 → `SMTP+STARTTLS` | `test_sender_port_465_uses_smtp_ssl()` — мок `smtplib.SMTP_SSL`, проверяем что вызывается с портом 465. `test_sender_port_587_uses_starttls()` — мок `smtplib.SMTP`, проверяем `starttls()` вызван |
| **7. SEO-regex** | Убрать 4×«гранит» из `_SEO_TITLE_PATTERN`, починить `памятник[аиы]?` негативным lookahead. Добавить паттерны из scraper-audit A-7: `памятники в/из/на`, `изготовление памятников`, `памятники и надгробия`, `гранитн* мастерск*` | `test_granit_not_seo()` — «Гранит-Мастер», «Гранитные мастерские» → `needs_review=False`. `test_pamiatniki_in_company_name_not_seo()` — «Гранит-Мастер ООО Памятники» → `needs_review=False`. `test_real_seo_still_detected()` — «памятники из гранита купить москва» → `needs_review=True`. `test_seo_pamiatniki_v_gorod()` — «Памятники в Абакане» → `needs_review=True`. `test_seo_izgotovlenie()` — «Изготовление памятников недорого» → `needs_review=True` |
| **14. SEO-regex** (дублирует 7) | То же что 7 — вынести в одну задачу | Объединить с задачей 7 |
| **1. Unsubscribe** | `unsubscribe_token` в `CrmContactRow` + эндпоинт + `cancel_followup_tasks()` | `test_unsubscribe_token_unique()` — 100 контактов, все токены уникальны. `test_unsubscribe_sets_stop_automation()` — GET `/unsubscribe?token=X` → `stop_automation=1`. `test_unsubscribe_cancels_followup()` — если есть pending follow-up задача → `status="cancelled"`. `test_unsubscribe_twice_idempotent()` — повторный клик не падает |
| **6. Auth bypass** | `/track/open/` + `/api/v1/track/` в whitelist middleware. **Проверить:** в текущем коде (app.py:280-309) частично реализовано — расширить | `test_tracking_pixel_no_auth()` — GET `/api/v1/track/open/XXX.png` без API-ключа → 200, не 401 |
| **16. .env.example + стартовые проверки** (НОВОЕ) | Создать `.env.example` с описанием всех переменных. Добавить SMTP health check при старте (опционально, с `--check-smtp` флагом). Добавить предупреждение о missing обязательных env vars | `test_env_example_exists()` — файл `.env.example` существует. `test_smtp_health_check_on_flag()` — `--check-smtp` → проверка подключения. `test_missing_smtp_env_warns()` — нет `SMTP_HOST` → `logger.warning` |

**Порядок реализации (этап 1):**
1. Задача 16: `.env.example` + стартовые проверки (15 мин)
2. Написать все тесты для задач 7/14, 8, 1, 6 (красные)
3. Задача 8: SMTP_SSL фикс → тесты зелёные
4. Задача 7/14: SEO-regex (включая паттерны из scraper-audit A-7) → тесты зелёные
5. Задача 1: Unsubscribe (миграция + API + cancel_followup) → тесты зелёные
6. Задача 6: Auth bypass → проверить текущее состояние, расширить → тесты зелёные
7. `uv run pytest tests/ -v` — всё зелёное
8. Ручной тест: отправить 1 письмо себе → проверить отписку → проверить tracking pixel

**Зависимости:** нет — можно начинать сразу

---

### Этап 2: Отправка + валидация + A/B (первые 10 тестовых писем)

**Цель:** CRM может создавать кампанию с A/B тестом, валидировать получатели, отправлять и восстанавливаться после краша. После этого этапа можно запустить первую тестовую кампанию на 5-10 своих адресов.

**Принцип TDD:** для каждого эндпоинта и каждой функции — тест с моками SMTP/IMAP.

| Задача | Что делаем | Тесты (сначала!) |
|--------|-----------|-----------------|
| **2. Recovery + отправка** | `lifespan()`: running→paused. `_get_campaign_recipients()`: фильтр + дедуп. `sender.py`: commit после каждого письма (не batch) | `test_recovery_running_to_paused()` — создать кампанию status=running, запустить lifespan → status=paused. `test_campaign_recipients_dedup()` — два письма одному contact → только 1 получатель. `test_campaign_recipients_filter_stop_automation()` — contact с `stop_automation=1` не в списке. `test_commit_per_email()` — мок БД, после каждого `send()` → `commit()` вызван |
| **18. Campaign recipients: батч вместо .all()** (НОВОЕ) | Заменить `campaigns.py:134` `q.all()` на `q.yield_per(100)` или cursor-based итерацию. Групповая обработка по 100 записей. В рамках задачи 2 | `test_campaign_recipients_no_oom()` — мок с 5000 компаний → итерация по батчам, не всё в памяти сразу. `test_yield_per_100_processes_all()` — все 5000 компаний обработаны |
| **4. Валидатор** | `validate_recipients()`: агрегаторы (SKIP_DOMAINS из scraper-audit A-1), невалидные email, дедуп, `EMAIL_SESSION_GAP_HRS`, признаки блокировки Gmail | `test_aggregator_filtered()` — `tsargranit.ru` → отфильтрован. `test_invalid_email_filtered()` — `test@` → отфильтрован. `test_duplicate_email_deduped()` — две компании с одним email → 1 получатель. `test_session_gap()` — письмо 30 мин назад → отфильтрован. `test_gmail_block_signs()` — 5 bounced @gmail.com → домен помечен |
| **3. A/B + счётчики** | `determine_ab_variant()`: детерминированное распределение по company_id. `total_errors`, `ab_variant` в логах. A/B stats endpoint | `test_ab_deterministic()` — `determine_ab_variant(company_id=42)` всегда одинаковый результат. `test_ab_50_50_split()` — 100 компаний → ~50/50. `test_total_errors_increment()` — ошибка отправки → `total_errors+1`. `test_ab_variant_in_log()` — письмо → `CrmEmailLogRow.ab_variant` = "A" или "B". `test_ab_stats_endpoint()` — GET `/campaigns/1/ab-stats` → `{A: {...}, B: {...}}` |
| **12 (impl). Immutable шаблоны** | `data/email_templates.json` с ID. `seed-templates`: INSERT-only. `CrmEmailLogRow.template_id`. `CrmTemplateRow.retired`. Миграция | `test_seed_inserts_new()` — пустая БД → 10 шаблонов. `test_seed_skips_existing()` — повторный seed → 0 новых. `test_template_id_in_log()` — отправка → `template_id=1`. `test_retired_not_in_campaign_list()` — GET `/templates` → `retired=true` не показывается. `test_immutable_no_update()` — изменить JSON, seed → существующий шаблон НЕ обновился |
| **15. Template name: разрешить кириллицу** (НОВОЕ) | `schemas.py:88`: изменить `pattern=r"^[a-z0-9_]+$"` на `pattern=r"^[a-z0-9_\u0430-\u044f]+$"` или убрать pattern вообще (имя — не ключ). Рассмотреть: добавить `description` поле для человекочитаемого имени | `test_template_name_cyrillic()` — `name="холодное_письмо_v1"` → accepted. `test_template_name_still_rejects_spaces()` — `name="cold email"` → rejected (если сохраняем pattern). `test_template_description_field()` — `description="Холодное письмо v1"` → сохраняется |

**Порядок реализации (этап 2):**
1. Написать все тесты (красные)
2. Задача 2 + 18: Recovery + отправка + батч-итерация → тесты зелёные
3. Задача 4: Валидатор → тесты зелёные
4. Задача 3: A/B + счётчики → тесты зелёные
5. Задача 12 impl: Immutable шаблоны → тесты зелёные
6. Задача 15: Template name кириллица → тесты зелёные (10 мин)
7. Интеграционный тест: создать кампанию → A/B → валидация → отправка 5 писем себе → проверить логи
8. `uv run pytest tests/ -v` — всё зелёное

**Зависимости:** этап 1 завершён (SMTP работает, отписка работает, auth bypass для tracking)

---

### Этап 3: Обратная связь — follow-up, bounce, reply (10-20 реальных писем)

**Цель:** CRM автоматически обрабатывает bounce, распознаёт ответы, отправляет follow-up. После этого этапа можно запустить первую реальную кампанию на 20-30 мастерских.

**Принцип TDD:** мокаем IMAP, подставляем тестовые письма, проверяем что CRM правильно меняет статусы.

| Задача | Что делаем | Тесты (сначала!) |
|--------|-----------|-----------------|
| **6. Bounce parser** | `process_bounces.py`: IMAP → распознать bounce → `CrmEmailLogRow.status="bounced"`, `CrmContactRow.funnel_stage="unreachable"` | `test_bounce_511_user_unknown()` — мок IMAP с DSN 5.1.1 → статус bounced, funnel unreachable. `test_bounce_522_mailbox_full()` — DSN 5.2.2 → статус bounced, funnel НЕ меняется. `test_bounce_571_blocked()` — DSN 5.7.1 → `stop_automation=1`. `test_bounce_imap_connection_error()` — IMAP недоступен → graceful, не крашится |
| **9. Reply parser** | `process_replies.py`: IMAP → распознать ответ → `funnel_stage="replied"`, `cancel_followup_tasks()`, `total_replied++`, `body=` унификация | `test_reply_detected()` — мок IMAP с ответом → `funnel_stage="replied"`. `test_reply_cancels_followup()` — ответ → pending follow-up = cancelled. `test_reply_increments_total_replied()` — ответ → `campaign.total_replied+1`. `test_reply_touch_body_unified()` — `CrmTouchRow.body=` заполнен. `test_ooo_ignored()` — автоответчик → без изменений. `test_spam_complaint()` — «это спам» → `stop_automation=1` |
| **5. Follow-up + счётчики** | `_maybe_create_followup_task()`: создать задачу +7д. `cancel_followup_tasks()`: отменить при терминальной стадии. `total_opened++` при tracking pixel | `test_followup_created_on_open()` — tracking pixel → `CrmTaskRow(task_type="follow_up", due_date=+7d)`. `test_followup_cancelled_on_reply()` — ответ → задача cancelled. `test_followup_cancelled_on_unsubscribe()` — отписка → задача cancelled. `test_total_opened_increment()` — tracking pixel → `campaign.total_opened+1` |
| **11. Follow-up executor** | `process_followups.py`: созревшие задачи → отправить письмо → completed | `test_followup_sent_when_due()` — задача с `due_date < now` → письмо отправлено, статус done. `test_followup_not_sent_when_future()` — `due_date > now` → ничего. `test_followup_not_sent_when_cancelled()` — статус cancelled → ничего. `test_followup_uses_reply_subject()` — тема `Re: {original_subject}` |

**Порядок реализации (этап 3):**
1. Написать все тесты (красные)
2. Задача 5: Follow-up создание + отмена + счётчики → тесты зелёные
3. Задача 11: Follow-up executor → тесты зелёные
4. Задача 6: Bounce parser → тесты зелёные
5. Задача 9: Reply parser → тесты зелёные
6. Интеграционный тест: отправка → bounce → проверка unreachable; отправка → ответ → проверка replied + follow-up отменён
7. `uv run pytest tests/ -v` — всё зелёное

**Зависимости:** этапы 1+2 завершены (отправка работает, A/B работает, логи пишутся)

---

### Этап 4: UI + финализация + hardening (запуск Волны 1)

**Цель:** фронтенд для управления кампаниями, post-reply UI, Bitrix-решение, hardening из аудита. После этого этапа — полноценный запуск первой волны на 50 компаний.

**Принцип TDD:** для UI — e2e тесты через Playwright. Для API-изменений — обычные юнит-тесты.

| Задача | Что делаем | Тесты (сначала!) |
|--------|-----------|-----------------|
| **10. Фронтенд** | Wizard создания кампании (шаблон + A/B + фильтры). Карточка компании с post-reply кнопками. Dashboard со статистикой | E2E: `test_campaign_wizard_creates_campaign()` — заполнить форму → кампания в БД. `test_ab_subject_b_optional()` — без темы B → кампания без A/B. `test_post_reply_buttons()` — карточка компании → кнопка «Цена» → письмо отправлено. Юнит: `test_template_dropdown_excludes_retired()` — API `/templates` не возвращает retired |
| **12 (доки)** | `docs/POST_REPLY_PLAYBOOK.md` + `docs/EMAIL_TEMPLATES.md` — уже созданы, Александр редактирует | — (документация, не код) |
| **13. Bitrix-шаблон** | Решение: отдельный шаблон `cold_email_bitrix` или общий. Зависит от результатов этапа 2 | Если создаём: `test_bitrix_template_in_json()` — шаблон #4 в `email_templates.json` |
| **17. Raw SQL: f-string → параметризованные** (НОВОЕ) | `companies.py:126-131,148-158`: заменить f-string интерполяцию на `:param` с `text(...).bindparams()`. Pydantic-валидация защищает сейчас, но антипаттерн на будущее | `test_raw_sql_parameterized()` — все `sa_text()` вызовы используют `:param`, а не f-string. `test_tg_trust_filter_parameterized()` — `tg_trust_min`/`tg_trust_max` через bindparam. `test_source_filter_parameterized()` — `source` через bindparam |
| **5 (открытые вопросы)** | mail-tester.com оценка, DKIM/SPF/DMARC, Cloudflare Tunnel, признаки блокировки Gmail | — (инфраструктура, не код) |

**Порядок реализации (этап 4):**
1. Задача 10: Фронтенд — wizard + карточка + dashboard
2. Задача 13: Bitrix-решение
3. Задача 17: Raw SQL рефакторинг
4. Александр редактирует шаблоны в `email_templates.json`
5. `seed-templates` → шаблоны в БД
6. Прогрев домена (3 дня по 5 писем на свои адреса)
7. mail-tester.com → оценка ≥ 8/10
8. Запуск Волны 1: 50 компаний, A/B тест тем

**Зависимости:** этапы 1+2+3 завершены

---

### Сводка по этапам

| Этап | Задачи | Результат | Когда можно тестировать |
|------|--------|-----------|------------------------|
| 1 | 1, 6, 7/14, 8, **16** | CRM может отправить 1 письмо + отписка + tracking + `.env.example` | Сразу после завершения |
| 2 | 2, 3, 4, 12(impl), **15, 18** | CRM может создать кампанию с A/B + валидация + кириллица в шаблонах + батч-итерация | 1-2 дня после этапа 1 |
| 3 | 5, 6, 9, 11 | CRM обрабатывает bounce/reply/follow-up автоматически | 2-3 дня после этапа 2 |
| 4 | 10, 12(доки), 13, **17** | Полный цикл: UI → кампания → статистика → post-reply → hardening | 3-5 дней после этапа 3 |

---

### Задача 1: Unsubscribe — токен + эндпоинт

**Проблема v6:** отписка через `tracking_id` письма — хрупко при нескольких письмах.  
**Решение:** постоянный `unsubscribe_token` в `CrmContactRow`.

#### 1.1 Миграция Alembic

```python
# alembic/versions/xxxx_add_unsubscribe_token.py

def upgrade():
    op.add_column(
        "crm_contacts",
        sa.Column("unsubscribe_token", sa.String, nullable=True, unique=True)
    )
    op.execute("""
        UPDATE crm_contacts
        SET unsubscribe_token = lower(hex(randomblob(16)))
        WHERE unsubscribe_token IS NULL
    """)
    op.alter_column("crm_contacts", "unsubscribe_token", nullable=False)
    op.create_index("ix_crm_contacts_unsubscribe_token", "crm_contacts", ["unsubscribe_token"])

def downgrade():
    op.drop_index("ix_crm_contacts_unsubscribe_token")
    op.drop_column("crm_contacts", "unsubscribe_token")
```

#### 1.2 ORM

```python
# granite/database.py — CrmContactRow
import secrets

class CrmContactRow(Base):
    # ... существующие поля ...
    unsubscribe_token = Column(
        String,
        nullable=False,
        default=lambda: secrets.token_hex(16),
        unique=True,
    )
```

#### 1.3 Эндпоинт отписки

Файл `granite/api/unsubscribe.py`:

```python
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from granite.api.deps import get_db
from granite.database import CrmContactRow, CrmTouchRow
from granite.api.helpers import cancel_followup_tasks  # v11: публичная функция
from datetime import datetime, timezone

router = APIRouter()

_UNSUBSCRIBE_PAGE = """<!DOCTYPE html>
<html><body style="font-family:sans-serif;max-width:500px;margin:60px auto;text-align:center">
<h2>RetouchGrav</h2>
<p>{msg}</p>
{extra}
</body></html>"""

@router.get("/unsubscribe/{token}", response_class=HTMLResponse)
def unsubscribe_page(token: str, db: Session = Depends(get_db)):
    """Страница подтверждения отписки. НЕ отписывает при GET —
    защита от префетча почтовыми клиентами."""
    contact = db.query(CrmContactRow).filter_by(unsubscribe_token=token).first()
    if not contact:
        raise HTTPException(404, "Ссылка недействительна")

    if contact.stop_automation:
        return _UNSUBSCRIBE_PAGE.format(
            msg="Вы уже отписаны. Писем больше не будет.",
            extra="",
        )

    return _UNSUBSCRIBE_PAGE.format(
        msg="Подтвердите отписку от рассылки RetouchGrav.",
        extra=f'''
        <form method="POST" action="/api/v1/unsubscribe/{token}">
          <button type="submit" style="padding:10px 24px;font-size:16px;cursor:pointer">
            Отписаться
          </button>
        </form>''',
    )


@router.post("/unsubscribe/{token}", response_class=HTMLResponse)
def unsubscribe_confirm(token: str, db: Session = Depends(get_db)):
    """Собственно отписка — только POST."""
    contact = db.query(CrmContactRow).filter_by(unsubscribe_token=token).first()
    if not contact:
        raise HTTPException(404, "Ссылка недействительна")

    if contact.stop_automation:
        return _UNSUBSCRIBE_PAGE.format(msg="Вы уже отписаны.", extra="")

    contact.stop_automation = True
    contact.funnel_stage = "not_interested"
    contact.updated_at = datetime.now(timezone.utc)

    # v11: отменить pending follow-up задачи
    cancel_followup_tasks(contact.company_id, "not_interested", db)

    db.add(CrmTouchRow(
        company_id=contact.company_id,
        channel="email",
        direction="incoming",
        subject="Отписка",
        body="unsubscribe_link",  # v11: унифицировано — везде body
    ))
    db.commit()

    return _UNSUBSCRIBE_PAGE.format(
        msg="Вы успешно отписаны. Больше писем не будет.",
        extra="",
    )
```

**Регистрация маршрута** — в `app.py` добавить:
```python
from granite.api import unsubscribe
app.include_router(unsubscribe.router, prefix="/api/v1", tags=["unsubscribe"])
```

**Auth bypass** — в `api_key_auth_middleware` (app.py:280-309) добавить:
```python
# Отписка и tracking доступны без API-ключа (клики из email / пиксели)
or request.url.path.startswith("/api/v1/unsubscribe/")
or request.url.path.startswith("/api/v1/track/")
```

> **v12 заметка:** Текущий код (app.py:280-309) уже имеет auth bypass для некоторых путей. Перед реализацией — проверить что именно уже обойдено и расширить при необходимости.

#### 1.4 Плейсхолдер `{unsubscribe_url}` в sender.py

```python
# В методе send() — перед рендером шаблона:
if contact:
    unsubscribe_url = f"{self.base_url}/api/v1/unsubscribe/{contact.unsubscribe_token}"
else:
    unsubscribe_url = ""
render_kwargs["unsubscribe_url"] = unsubscribe_url
```

`CrmTemplateRow.render()` уже поддерживает произвольные плейсхолдеры — достаточно передать `unsubscribe_url` в `render_kwargs`.

---

### Задача 2: Recovery + отправка + батч-итерация

#### 2.1 Recovery при старте — `lifespan()`

```python
# granite/api/app.py — lifespan()
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app):
    # При старте: все running кампании → paused
    db = SessionFactory()
    try:
        running = db.query(CrmEmailCampaignRow).filter(
            CrmEmailCampaignRow.status == "running"
        ).all()
        for c in running:
            c.status = "paused"
        db.commit()
        if running:
            logger.warning(f"Recovery: {len(running)} running campaigns → paused")
    finally:
        db.close()
    yield
    # Shutdown: cleanup
```

#### 2.2 `_get_campaign_recipients()` — фильтр + дедуп

```python
# granite/api/campaigns.py

def _get_campaign_recipients(campaign: CrmEmailCampaignRow, db: Session) -> list[dict]:
    """Получить список получателей кампании с фильтрацией и дедупликацией."""
    filters = campaign.filters or {}

    # v12: батч-итерация вместо .all() (задача 18)
    q = (
        db.query(CompanyRow, EnrichedCompanyRow, CrmContactRow)
        .outerjoin(EnrichedCompanyRow, EnrichedCompanyRow.id == CompanyRow.id)
        .outerjoin(CrmContactRow, CrmContactRow.company_id == CompanyRow.id)
        .filter(CompanyRow.deleted_at.is_(None))
    )

    # Применяем фильтры из campaign.filters
    if filters.get("segment"):
        q = q.filter(EnrichedCompanyRow.segment.in_(filters["segment"]))
    if filters.get("city"):
        q = q.filter(CompanyRow.city.in_(filters["city"]))

    # Исключаем: stop_automation, нет email, уже отправлено в этой кампании
    q = q.filter(
        CrmContactRow.stop_automation == False,
        CrmContactRow.email.isnot(None),
        CrmContactRow.email != "",
    )

    # Дедуп: уже отправленные в этой кампании
    sent_emails = set(
        row.recipient_email
        for row in db.query(CrmEmailLogRow.recipient_email)
        .filter(CrmEmailLogRow.campaign_id == campaign.id)
        .all()
    )

    # v12: yield_per вместо all() (задача 18)
    recipients = []
    seen_emails = set()
    for company, enriched, contact in q.yield_per(100):
        if not contact or not contact.email:
            continue
        if contact.email in sent_emails:
            continue
        if contact.email in seen_emails:
            continue  # дедуп email
        seen_emails.add(contact.email)
        recipients.append({
            "company_id": company.id,
            "company_name": company.name,
            "city": company.city,
            "email": contact.email,
            "contact": contact,
            "enriched": enriched,
        })

    return recipients
```

#### 2.3 `sender.py`: commit после каждого письма

```python
# В методе send_campaign() — после каждого send():
try:
    result = self.send(template, contact, subject, ...)
    log = CrmEmailLogRow(
        campaign_id=campaign.id,
        company_id=contact.company_id,
        recipient_email=contact.email,
        status="sent",
        ab_variant=variant,
        template_id=template.id,  # v11: template_id вместо template_name
        tracking_id=tracking_id,
        sent_at=datetime.now(timezone.utc),
    )
    db.add(log)
    campaign.total_sent += 1
    db.commit()  # commit после КАЖДОГО письма
except Exception as e:
    campaign.total_errors += 1
    db.commit()  # фиксируем ошибку
    logger.error(f"Send failed: {e}")
```

---

### Задача 3: A/B тест + счётчики

#### 3.1 Детерминированное распределение A/B

```python
# granite/api/campaigns.py

def determine_ab_variant(company_id: int, campaign_id: int) -> str:
    """Детерминированное распределение: одна компания всегда
    получает один и тот же вариант для данной кампании."""
    return "A" if (company_id + campaign_id) % 2 == 0 else "B"
```

#### 3.2 Счётчики в ORM

```python
# granite/database.py — CrmEmailCampaignRow
class CrmEmailCampaignRow(Base):
    # ... существующие поля ...
    total_sent = Column(Integer, default=0)
    total_opened = Column(Integer, default=0)      # v11: добавлено
    total_replied = Column(Integer, default=0)     # v11: добавлено
    total_errors = Column(Integer, default=0)
```

Миграция для `total_opened` и `total_replied` (если ещё не создана):

```python
# alembic/versions/xxxx_add_total_opened_replied.py
def upgrade():
    op.add_column("crm_email_campaigns", sa.Column("total_opened", sa.Integer, default=0))
    op.add_column("crm_email_campaigns", sa.Column("total_replied", sa.Integer, default=0))

def downgrade():
    op.drop_column("crm_email_campaigns", "total_replied")
    op.drop_column("crm_email_campaigns", "total_opened")
```

#### 3.3 A/B stats endpoint

```python
# granite/api/campaigns.py

@router.get("/campaigns/{campaign_id}/ab-stats")
def ab_stats(campaign_id: int, db: Session = Depends(get_db)):
    """Статистика A/B теста по вариантам."""
    campaign = db.get(CrmEmailCampaignRow, campaign_id)
    if not campaign:
        raise HTTPException(404)

    logs = db.query(CrmEmailLogRow).filter(
        CrmEmailLogRow.campaign_id == campaign_id
    ).all()

    stats = {}
    for variant in ("A", "B"):
        variant_logs = [l for l in logs if l.ab_variant == variant]
        stats[variant] = {
            "sent": len(variant_logs),
            "opened": sum(1 for l in variant_logs if l.opened_at),
            "replied": sum(1 for l in variant_logs if l.status == "replied"),
            "bounced": sum(1 for l in variant_logs if l.status == "bounced"),
            "errors": sum(1 for l in variant_logs if l.status == "error"),
        }
    return stats
```

---

### Задача 4: Валидатор получателей

```python
# granite/api/campaigns.py или granite/api/validator.py

# Агрегаторы из scraper-audit A-1
SKIP_DOMAINS = {
    "tsargranit.ru", "alshei.ru", "mipomnim.ru", "uznm.ru",
    "monuments.su", "masterskay-granit.ru", "gr-anit.ru",
    "v-granit.ru", "nbs-granit.ru", "granit-pamiatnik.ru",
    "postament.ru", "uslugio.com", "pqd.ru", "spravker.ru",
    "orgpage.ru", "totadres.ru", "mapage.ru", "zoon.ru",
}

EMAIL_SESSION_GAP_HRS = 4  # минимальный интервал между письмами одной компании

def validate_recipients(recipients: list[dict], campaign_id: int, db: Session) -> dict:
    """Валидация списка получателей перед отправкой.
    
    Returns:
        {"valid": [...], "filtered": [...], "stats": {...}}
    """
    valid = []
    filtered = []

    for r in recipients:
        reasons = []

        # 1. Агрегатор по домену
        website = r.get("enriched", {}).website if r.get("enriched") else None
        if website:
            domain = extract_domain(website)
            if domain in SKIP_DOMAINS:
                reasons.append(f"aggregator_domain:{domain}")

        # 2. Невалидный email
        email = r.get("email", "")
        if not email or not _is_valid_email(email):
            reasons.append("invalid_email")

        # 3. Session gap — не отправлять слишком часто
        last_sent = _last_email_sent(r["company_id"], db)
        if last_sent and (datetime.now(timezone.utc) - last_sent).total_seconds() < EMAIL_SESSION_GAP_HRS * 3600:
            reasons.append("session_gap")

        # 4. Дедуп email — уже в списке
        # (обрабатывается в _get_campaign_recipients)

        if reasons:
            filtered.append({"recipient": r, "reasons": reasons})
        else:
            valid.append(r)

    return {
        "valid": valid,
        "filtered": filtered,
        "stats": {
            "total": len(valid) + len(filtered),
            "valid": len(valid),
            "filtered": len(filtered),
            "by_reason": Counter(
                reason for f in filtered for reason in f["reasons"]
            ),
        },
    }

def _is_valid_email(email: str) -> bool:
    """Минимальная валидация: есть @, домен, нет пробелов."""
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email))
```

---

### Задача 5: Follow-up + счётчики

#### 5.1 Создание follow-up задачи при tracking pixel

```python
# granite/api/tracking.py — после инкремента open

def _maybe_create_followup_task(contact: CrmContactRow, campaign_id: int, db: Session):
    """Создать follow-up задачу +7 дней, если ещё нет."""
    existing = db.query(CrmTaskRow).filter(
        CrmTaskRow.company_id == contact.company_id,
        CrmTaskRow.task_type == "follow_up",
        CrmTaskRow.status == "pending",
    ).first()
    if existing:
        return  # уже есть

    task = CrmTaskRow(
        company_id=contact.company_id,
        task_type="follow_up",
        status="pending",
        due_date=datetime.now(timezone.utc) + timedelta(days=7),
        description=f"follow_up:campaign_{campaign_id}",
    )
    db.add(task)
```

#### 5.2 `cancel_followup_tasks()` — публичная функция

```python
# granite/api/helpers.py

def cancel_followup_tasks(company_id: int, reason: str, db: Session):
    """Отменить все pending follow-up задачи для компании.
    
    Вызывается при: reply, unsubscribe, stop_automation.
    """
    tasks = db.query(CrmTaskRow).filter(
        CrmTaskRow.company_id == company_id,
        CrmTaskRow.task_type == "follow_up",
        CrmTaskRow.status == "pending",
    ).all()
    for t in tasks:
        t.status = "cancelled"
    if tasks:
        logger.info(f"Cancelled {len(tasks)} follow-up tasks for company {company_id} (reason: {reason})")
```

---

### Задача 6: Auth bypass + Bounce parser

#### 6.1 Auth bypass — расширение middleware

Текущий код (app.py:280-309) использует `hmac.compare_digest` (подтверждено верификацией). Нужно добавить bypass для `/api/v1/track/`:

```python
# В api_key_auth_middleware:
if (
    request.url.path.startswith("/api/v1/unsubscribe/")
    or request.url.path.startswith("/api/v1/track/")
    or request.url.path == "/health"
):
    response = await call_next(request)
    return response
```

#### 6.2 Bounce parser

```python
# scripts/process_bounces.py

"""Обработка bounce-писем через IMAP.

Запуск: uv run python scripts/process_bounces.py
Расписание: каждые 30 минут (cron или systemd timer)
"""

import imaplib
import email
from email.header import decode_header
from granite.api.app import get_engine
from granite.database import CrmEmailLogRow, CrmContactRow
from sqlalchemy.orm import Session

# SMTP bounce DSN-коды
_PERMANENT_BOUNCE = re.compile(r"5\.[1-3]\.\d")   # user unknown, mailbox full, etc.
_BLOCKED = re.compile(r"5\.7\.[1-9]")               # blocked / spam reported

def process_bounces():
    engine = get_engine()  # v9: используем общий engine, не Database()
    with Session(engine) as db:
        mail = imaplib.IMAP4_SSL(os.environ["IMAP_HOST"])
        mail.login(os.environ["SMTP_USER"], os.environ["SMTP_PASS"])
        mail.select("INBOX")

        _, msg_ids = mail.search(None, '(UNSEEN SUBJECT "Undelivered" OR SUBJECT "bounce" OR SUBJECT "failure")')
        for msg_id in msg_ids[0].split():
            _, msg_data = mail.fetch(msg_id, "(RFC822)")
            msg = email.message_from_bytes(msg_data[0][1])

            # Извлечь DSN-код и tracking_id
            dsn_code = _extract_dsn(msg)
            tracking_id = _extract_tracking_id(msg)

            if not tracking_id or not dsn_code:
                continue

            log = db.query(CrmEmailLogRow).filter_by(tracking_id=tracking_id).first()
            if not log:
                continue

            log.status = "bounced"

            contact = db.query(CrmContactRow).filter_by(company_id=log.company_id).first()
            if contact:
                if _PERMANENT_BOUNCE.match(dsn_code):
                    contact.funnel_stage = "unreachable"
                if _BLOCKED.match(dsn_code):
                    contact.stop_automation = True

            db.commit()
            mail.store(msg_id, "+FLAGS", "\\Seen")

        mail.logout()
```

---

### Задача 7: SEO-regex

#### Текущий паттерн (utils.py)

```python
_SEO_TITLE_PATTERN = re.compile(
    r"(?:купить|цен[аыуе]|недорог|заказать|от производитель|"
    r"с установк|на могил|доставк|скидк|каталог|"
    r"памятник[аиы]?\s+(?:из|в|на|от))",
    re.IGNORECASE,
)
```

#### Паттерн после фикса (задача 7 + scraper-audit A-7)

```python
_SEO_TITLE_PATTERN = re.compile(
    r"(?:купить|цен[аыуе]|недорог|заказать|от производитель|"
    r"с установк|на могил|доставк|скидк|каталог|"
    r"памятник[аиы]?\s+(?=из|в|на|от|и)\s*"   # негативный lookahead: "ООО Памятники" не флагается
    r"(?:из|в|на|от|и)\s+|"                     # только если после памятник идёт предлог
    r"памятники\s+(?:в|из|на|и)\s+|"            # "Памятники в Абакане", "Памятники из гранита"
    r"памятники\s+(?:на\s+кладбищ)|"            # "Памятники на кладбище"
    r"изготовление\s+памятников|"                # "Изготовление памятников"
    r"памятники\s+и\s+надгробия|"               # "Памятники и надгробия"
    r"гранитн[ые]+\s+мастерск)",                 # "Гранитные мастерские" — SEO-формулировка
    re.IGNORECASE,
)
```

> **Ключевой фикс:** Убрано 4×«гранит» (из v7). Добавлен негативный lookahead перед «памятник[аиы]? + предлог»: «Гранит-Мастер ООО Памятники» больше не флагается — после «памятники» нет предлога «из/в/на/от/и».

---

### Задача 8: SMTP_SSL

```python
# granite/email/sender.py — _smtp_send()

def _smtp_send(self, to: str, subject: str, body_text: str, body_html: str | None):
    """Отправка письма. Порт 465 → SMTP_SSL, порт 587 → SMTP+STARTTLS."""
    port = self.smtp_port

    if port == 465:
        # Implicit TLS — Gmail стандарт
        with smtplib.SMTP_SSL(self.smtp_host, port) as server:
            server.login(self.smtp_user, self.smtp_pass)
            msg = self._build_message(to, subject, body_text, body_html)
            server.send_message(msg)
    else:
        # STARTTLS — для портов 587 и других
        with smtplib.SMTP(self.smtp_host, port) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(self.smtp_user, self.smtp_pass)
            msg = self._build_message(to, subject, body_text, body_html)
            server.send_message(msg)
```

---

### Задача 9: Reply parser

```python
# scripts/process_replies.py

"""Обработка ответов на email через IMAP.

Запуск: uv run python scripts/process_replies.py
Расписание: каждые 15 минут
"""

# OOO / автоответчик — не считать за ответ
_OOO_PATTERNS = re.compile(
    r"(?:автоответ|out of office|автоматическ|я в отпуске|vacation|auto.?reply)",
    re.IGNORECASE,
)

# Жалоба на спам
_SPAM_COMPLAINT = re.compile(r"это\s+спам|spam|unsolicited", re.IGNORECASE)

def process_replies():
    engine = get_engine()
    with Session(engine) as db:
        mail = imaplib.IMAP4_SSL(os.environ["IMAP_HOST"])
        mail.login(os.environ["SMTP_USER"], os.environ["SMTP_PASS"])
        mail.select("INBOX")

        # Ищем непрочитанные письма, которые НЕ bounce
        _, msg_ids = mail.search(None, "(UNSEEN)")

        for msg_id in msg_ids[0].split():
            _, msg_data = mail.fetch(msg_id, "(RFC822)")
            msg = email.message_from_bytes(msg_data[0][1])

            # Пропускаем bounce (обрабатываются в process_bounces.py)
            if _is_bounce(msg):
                continue

            from_addr = _extract_sender(msg)
            subject = _extract_subject(msg)
            body = _extract_body(msg)

            if not from_addr:
                continue

            # Найти контакт по email
            contact = db.query(CrmContactRow).filter_by(email=from_addr).first()
            if not contact:
                continue

            # Проверить OOO
            if _OOO_PATTERNS.search(body or ""):
                mail.store(msg_id, "+FLAGS", "\\Seen")
                continue

            # Проверить спам-жалобу
            if _SPAM_COMPLAINT.search(body or ""):
                contact.stop_automation = True
                contact.funnel_stage = "not_interested"
                cancel_followup_tasks(contact.company_id, "spam_complaint", db)
                db.commit()
                mail.store(msg_id, "+FLAGS", "\\Seen")
                continue

            # Реальный ответ
            contact.funnel_stage = "replied"
            cancel_followup_tasks(contact.company_id, "replied", db)

            # Инкремент total_replied для кампании
            last_log = db.query(CrmEmailLogRow).filter(
                CrmEmailLogRow.company_id == contact.company_id,
                CrmEmailLogRow.status == "sent",
            ).order_by(CrmEmailLogRow.sent_at.desc()).first()

            if last_log:
                campaign = db.get(CrmEmailCampaignRow, last_log.campaign_id)
                if campaign:
                    campaign.total_replied += 1

            # Touch record
            db.add(CrmTouchRow(
                company_id=contact.company_id,
                channel="email",
                direction="incoming",
                subject=subject or "Reply",
                body=body[:2000] if body else "",  # v11: унифицировано body
            ))

            db.commit()
            mail.store(msg_id, "+FLAGS", "\\Seen")

        mail.logout()
```

---

### Задача 11: Follow-up executor

```python
# scripts/process_followups.py

"""Исполнение созревших follow-up задач.

Запуск: uv run python scripts/process_followups.py
Расписание: каждый час
"""

def process_followups():
    engine = get_engine()
    with Session(engine) as db:
        now = datetime.now(timezone.utc)

        # Найти созревшие pending задачи
        tasks = db.query(CrmTaskRow).filter(
            CrmTaskRow.task_type == "follow_up",
            CrmTaskRow.status == "pending",
            CrmTaskRow.due_date <= now,
        ).all()

        if not tasks:
            return

        sender = EmailSender()

        for task in tasks:
            contact = db.query(CrmContactRow).filter_by(
                company_id=task.company_id
            ).first()
            if not contact or not contact.email:
                task.status = "cancelled"
                continue

            if contact.stop_automation:
                task.status = "cancelled"
                continue

            # Получить оригинальную тему из touch
            last_touch = db.query(CrmTouchRow).filter(
                CrmTouchRow.company_id == contact.company_id,
                CrmTouchRow.direction == "outgoing",
                CrmTouchRow.channel == "email",
            ).order_by(CrmTouchRow.created_at.desc()).first()

            original_subject = last_touch.subject if last_touch else "ретушь портретов"

            # Найти follow-up шаблон
            template = db.query(CrmTemplateRow).filter(
                CrmTemplateRow.name == "follow_up_email_v1",
                CrmTemplateRow.retired != True,
            ).first()

            if not template:
                logger.error("Follow-up template not found")
                continue

            try:
                # Рендерим тему: Re: {original_subject}
                subject = f"Re: {original_subject}"
                rendered = template.render(city=contact.company.city or "")

                sender.send(template, contact, subject)
                task.status = "done"
            except Exception as e:
                logger.error(f"Follow-up send failed: {e}")
                task.status = "error"

            db.commit()
```

---

### Задача 12: Immutable шаблоны — реализация

#### 12.1 `data/email_templates.json`

```json
[
  {
    "id": 1,
    "name": "cold_email_v1",
    "channel": "email",
    "subject_a": "Подготовка фото под гравировку — пришлите самый сложный случай",
    "subject_b": "Ретушь под памятник: старые и плохие фото — в день заказа",
    "body": "Здравствуйте.\n\nИщу контакты мастерских в {city} и области...",
    "body_type": "plain",
    "description": "Холодное письмо — основной шаблон",
    "retired": false
  },
  {
    "id": 2,
    "name": "cold_email_marquiz",
    ...
  },
  {
    "id": 3,
    "name": "follow_up_email_v1",
    ...
  },
  {
    "id": 4,
    "name": "cold_email_bitrix",
    ...
  }
]
```

#### 12.2 Seed script — INSERT-only

```python
# scripts/seed_crm_templates.py

def seed_templates(db: Session, json_path: str = "data/email_templates.json"):
    """Загрузить шаблоны из JSON. INSERT-only: существующие НЕ обновляются."""
    with open(json_path, encoding="utf-8") as f:
        templates = json.load(f)

    added = 0
    for t in templates:
        exists = db.query(CrmTemplateRow).filter_by(name=t["name"]).first()
        if exists:
            logger.debug(f"Template '{t['name']}' already exists — skip (immutable)")
            continue
        row = CrmTemplateRow(
            name=t["name"],
            channel=t.get("channel", "email"),
            subject=t.get("subject_a", ""),
            body=t["body"],
            body_type=t.get("body_type", "plain"),
            description=t.get("description", ""),
        )
        db.add(row)
        added += 1

    db.commit()
    logger.info(f"Templates seeded: {added} new, {len(templates) - added} existing (skipped)")
```

#### 12.3 ORM изменения

```python
# Миграция: template_name → template_id + retired
class CrmEmailLogRow(Base):
    # ... существующие поля ...
    template_id = Column(Integer, ForeignKey("crm_templates.id"), nullable=True)
    # template_name оставляем для обратной совместимости, deprecated

class CrmTemplateRow(Base):
    # ... существующие поля ...
    retired = Column(Boolean, default=False)
```

---

### Задача 15: Template name — разрешить кириллицу (НОВОЕ)

**Проблема:** `schemas.py:88` — `pattern=r"^[a-z0-9_]+$"` запрещает кириллицу в имени шаблона. Для русского рынка неприемлемо: шаблон `холодное_письмо_v1` не может быть создан через API.

**Решение:** Изменить pattern на разрешающий кириллицу, или убрать pattern вообще (имя шаблона — не ключ безопасности).

```python
# granite/api/schemas.py

# До (schemas.py:88):
name: str = Field(..., min_length=1, pattern=r"^[a-z0-9_]+$")

# После:
name: str = Field(..., min_length=1, max_length=64, pattern=r"^[a-z0-9_\u0430-\u044f\u0410-\u042f]+$")
# Разрешены: строчные латиница, цифры, подчёркивание, кириллица (строчные + заглавные)
```

**Альтернатива:** убрать `pattern` совсем и добавить `description` поле для человекочитаемого имени. `name` тогда — только идентификатор для кода, может быть `^[a-z0-9_]+$`. Человеческое имя — в `description`.

---

### Задача 16: `.env.example` + стартовые проверки (НОВОЕ)

**Проблема:** Нет `.env.example`, нет проверки обязательных переменных при старте, нет SMTP health check.

**Решение:**

#### 16.1 `.env.example`

```bash
# .env.example — Granite CRM Email Campaign

# ── SMTP (обязательно для рассылки) ──
SMTP_HOST=smtp.gmail.com
SMTP_PORT=465
SMTP_USER=your-email@gmail.com
SMTP_PASS=your-app-password    # Gmail App Password, НЕ обычный пароль

# ── IMAP (обязательно для bounce + reply) ──
IMAP_HOST=imap.gmail.com
IMAP_PORT=993
# SMTP_USER и SMTP_PASS используются для IMAP тоже

# ── API ──
GRANITE_API_KEY=change-me-to-random-string    # Оставить пустым для dev-mode (auth отключён)
CORS_ORIGINS=http://localhost:3000,http://localhost:5173    # Разделить запятыми

# ── Публичный URL (для tracking + unsubscribe) ──
BASE_URL=https://your-tunnel-url.example.com    # Cloudflare Tunnel или аналогичный

# ── Опционально ──
# DGIS_API_KEY=your-2gis-api-key
```

#### 16.2 Стартовые предупреждения

```python
# granite/api/app.py — в lifespan()

required_smtp_vars = ["SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASS"]
missing = [v for v in required_smtp_vars if not os.environ.get(v)]
if missing:
    logger.warning(f"Missing SMTP env vars: {missing}. Email sending will NOT work.")

if not os.environ.get("GRANITE_API_KEY"):
    logger.warning("GRANITE_API_KEY not set — API authentication DISABLED (dev mode)")
```

#### 16.3 SMTP health check (опционально)

```python
# granite/api/app.py — /health endpoint

@app.get("/health")
def health():
    checks = {"status": "ok", "db": "ok"}
    # SMTP check — только если запрошен явно
    # (не при каждом health check — может быть медленно)
    return checks

@app.get("/health/smtp")
def health_smtp():
    """Проверка подключения к SMTP. Использовать перед запуском кампании."""
    try:
        with smtplib.SMTP_SSL(os.environ["SMTP_HOST"], int(os.environ["SMTP_PORT"])) as s:
            s.login(os.environ["SMTP_USER"], os.environ["SMTP_PASS"])
        return {"status": "ok", "smtp": "connected"}
    except Exception as e:
        return {"status": "error", "smtp": str(e)}
```

---

### Задача 17: Raw SQL — f-string → параметризованные (НОВОЕ)

**Проблема:** `companies.py:126-131` и `companies.py:148-158` интерполируют значения в SQL через f-string. Pydantic-валидация ограничивает значения, но это антипаттерн — при рефакторинге можно случайно пропустить валидацию.

**Пример (текущий):**
```python
# companies.py:126-131
query = sa_text(f"""
    SELECT ... FROM enriched_companies
    WHERE json_extract(messengers, '$.telegram.trust_score') BETWEEN {tg_trust_min} AND {tg_trust_max}
""")
```

**Пример (после фикса):**
```python
query = sa_text("""
    SELECT ... FROM enriched_companies
    WHERE json_extract(messengers, '$.telegram.trust_score') BETWEEN :tg_trust_min AND :tg_trust_max
""")
result = session.execute(query, {"tg_trust_min": tg_trust_min, "tg_trust_max": tg_trust_max})
```

---

### Задача 18: Campaign recipients — батч-итерация (НОВОЕ)

**Проблема:** `campaigns.py:134` — `rows = q.all()` загружает все компании в память. При 50K+ компаний — потенциальный OOM.

**Решение:** Заменить `.all()` на `.yield_per(100)` (SQLAlchemy батч-итерация).

```python
# До:
rows = q.all()

# После:
for company, enriched, contact in q.yield_per(100):
    # обработка записи
```

> **Заметка:** Для текущих объёмов (~6000 компаний) `.all()` работает нормально. Этот рефакторинг — профилактика на будущее. Интегрируется в задачу 2.

---

## 7. Roadmap по дням

| День | Этап | Задачи | Результат |
|------|------|--------|-----------|
| 1 | 1 | 16 (.env.example) | `.env.example` создан, предупреждения при старте |
| 2–3 | 1 | 8 (SMTP_SSL), 7/14 (SEO-regex) | SMTP работает, SEO-regex пофикшен |
| 4–5 | 1 | 1 (Unsubscribe), 6 (Auth bypass) | Отписка + tracking работают без auth |
| 6–7 | 2 | 2+18 (Recovery + отправка + батч) | CRM отправляет письмо |
| 8 | 2 | 4 (Валидатор), 15 (Template name) | Валидация + кириллица в шаблонах |
| 9–10 | 2 | 3 (A/B), 12 impl (Шаблоны) | A/B тест + immutable шаблоны |
| 11–13 | 3 | 5, 11, 6, 9 (Follow-up + bounce + reply) | Полный цикл обратной связи |
| 14–18 | 4 | 10 (Фронтенд), 13 (Bitrix), 17 (SQL) | UI + hardening |
| 19–21 | — | Прогрев домена, mail-tester | Готовность к запуску |
| 22+ | — | Запуск Волны 1 | 50 компаний, A/B тест |

---

## 8. Открытые вопросы

| # | Вопрос | Статус | Комментарий |
|---|--------|--------|-------------|
| 1 | Публичный URL для tracking/unsubscribe | ⬜ Открыт | Cloudflare Tunnel — самое простое решение. Альтернатива: ngrok, serveo |
| 2 | Проверка базы на агрегаторы перед запуском | ⬜ Открыт | Ручная проверка 434 компаний (~30 мин) или реализация scraper-audit A-1 |
| 3 | Rate limiting на API-эндпоинты | ⬜ Отложено | Внутренний инструмент, не публичный API. После Волны 1 |
| 4 | DNS rebinding защита | ⬜ Отложено | Риск минимальный для внутреннего CRM |
| 5 | PostgreSQL миграция | ⬜ Отложено | SQLite достаточен для текущих объёмов. Если потребуется конкурентная запись — мигрировать |
| 6 | `.env.example` | ✅ Задача 16 | Создаётся в этапе 1 |
| 7 | SMTP health check | ✅ Задача 16 | Эндпоинт `/health/smtp` |

---

## Changelog

| Версия | Дата | Изменения |
|--------|------|-----------|
| v1–v10 | 2026-04-22..26 | См. предыдущие версии |
| v11 | 2026-04-26 | +6 фиксов +4 дополнения (post-reply, immutable templates, TDD, этапы) |
| v12 | 2026-04-27 | Верификация аудита (audits.md + scraper-audit.md) против реального кода. 9 из 10 «уязвимостей» аудита уже исправлены в коде. 4 новые задачи из подтверждённых находок (#15–18). 6 уточнений к существующим задачам. Scraper-audit A-1/A-2 отмечены как предпосылки |
