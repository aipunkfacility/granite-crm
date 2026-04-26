# RetouchGrav — Email Campaign Dev Plan v13

> Александр · @ganjavagen  
> База: ~6 000 компаний → **434 приоритетных целей** (A+B, не-сеть, валидный email)  
> SMTP: ai.punk.facility@gmail.com (личный аккаунт, App Password)  
> v13 · 2026-04-27 · v12 + 4 баг-фикса + возврат кода из v11 + новая задача 19 + структурные улучшения

---

## Содержание

1. [Что изменилось относительно v12](#1-что-изменилось-относительно-v12)
2. [Принятые решения](#2-принятые-решения)
3. [Верификация аудита — что реально, что нет](#3-верификация-аудита--что-реально-что-нет)
4. [Стратегия и волны](#4-стратегия-и-волны)
5. [Прогрев домена](#5-прогрев-домена)
6. [Шаблоны писем](#6-шаблоны-писем)
7. [Технический план — этапы реализации](#7-технический-план--этапы-реализации)
8. [Roadmap по дням](#8-roadmap-по-дням)
9. [Открытые вопросы](#9-открытые-вопросы)
10. [Changelog](#10-changelog)

---

## 1. Что изменилось относительно v12

### Критические баг-фиксы

| # | Баг в v12 | Фикс в v13 | Почему |
|---|-----------|-----------|--------|
| 1 | `гранитн[ые]+\s+мастерск` в SEO-regex флагает «Гранитные мастерские» как SEO, но `test_granit_not_seo()` ожидает `needs_review=False` | ✅ Убрать `гранитн[ые]+\s+мастерск` из паттерна полностью. «Гранитные мастерские» — реальное название в нише, как и «Гранит-Мастер» (решено в v7/v11) | Тест-кейс и бизнес-логика противоречат паттерну |
| 2 | `памятник[аиы]?\s+(?=из\|в\|на\|от\|и)\s*` (lookahead) + `(?:из\|в\|на\|от\|и)\s+\|` — двойная работа и баг: lookahead без `\s+` работает некорректно | ✅ Вернуть v11-версию: `памятник[аиы]?\s*(?:из\|в\|на\|от\|и)\s+\S\|` — предлог обязателен + слово после | Lookahead — избыточность и баг одновременно |
| 3 | Template name regex `^[a-z0-9_\u0430-\u044f]+$` — нет заглавной кириллицы, `Холодное_письмо_v1` будет отвергнуто | ✅ Добавить `\u0410-\u042f`: `^[a-z0-9_\u0410-\u042f\u0430-\u044f]+$`. Также добавить миграцию `description` для CrmTemplateRow | Заглавная кириллица — обычное дело в именах шаблонов |
| 4 | `yield_per(100)` без `stream_results=True` — для SQLite может не работать | ✅ Добавить: для SQLite использовать `execution_options(stream_results=True)` или fall back на `offset/limit` батч-итерацию | SQLite — основная БД для dev, не должна ломаться |

### Восстановлено из v11

| # | Что восстановлено | Почему |
|---|------------------|--------|
| 5 | Полный код `_run_campaign_background` (~140 строк) — v12 имел только скелет | Полный код с A/B, дневным лимитом, touch record, render, delay нужен для реализации |
| 6 | SSE-прогресс эндпоинт `campaign_progress()` — полностью отсутствовал в v12 | Фронтенд не может показывать прогресс без SSE-потока |
| 7 | Исторические `<details>` блоки (v6→v7, v7→v8, v8→v9, v9→v10) | v12 имел только v10→v11, потеря контекста при откате решений |
| 8 | Полный код `process_bounces.py` и `process_replies.py` — v12 имел сокращённые версии с неопределёнными хелперами | Вынести общие IMAP-функции в `granite/email/imap_helpers.py` (задача 19) |

### Структурные улучшения

| # | Улучшение | Описание |
|---|-----------|----------|
| 9 | Новый раздел «Принятые решения» | Сводная таблица ключевых решений + почему — контекст не теряется |
| 10 | Новая задача 19: IMAP helpers module | `granite/email/imap_helpers.py` — общие IMAP-функции для задач 6 и 9. Помещена в Этап 3 |
| 11 | Задача 17 (f-string → параметризованный SQL) перенесена из Этапа 4 в Этап 2 | Быстрый рефакторинг (30 мин), затрагивает `companies.py` — лучше сделать вместе с задачей 4 (валидатор), чтобы не иметь merge-конфликтов |
| 12 | Миграция `description` для CrmTemplateRow | Задача 15 упоминала `description`, но миграция не была указана. Добавлена явно |
| 13 | Обновлены SEO-regex тест-кейсы | «Гранитные мастерские» → `needs_review=False` (согласовано с `test_granit_not_seo()`) |

---

## 2. Принятые решения

Сводная таблица ключевых архитектурных и бизнес-решений, чтобы контекст не терялся между версиями.

| Решение | Почему | Версия |
|---------|--------|--------|
| Географический фильтр убран | `.by`/`.kz` OK, нет причины блокировать | v11 |
| MAX_PER_DOMAIN не нужен | 50/день, разнообразие адресов | v11 |
| Follow-up только при открытии | Не дублируем тем, кто проигнорировал | v11 |
| Commit после каждого письма | Не теряем данные при краше | v9 |
| «Гранит» убран из SEO-regex | Нормальное название в нише | v7 |
| Gmail App Password, не свой домен | Простота, SPF/DKIM от Google | v7 |
| Шаблоны immutable (ID-based) | Честная статистика навсегда | v11 |
| `гранитн[ые]+\s+мастерск` убран из SEO-regex | «Гранитные мастерские» — реальное название, не SEO-формулировка | v13 |
| `памятник[аиы]?` — предлог обязателен + слово после | Без предлога «ООО Памятники» не SEO; lookahead избыточен | v13 |
| Template name: заглавная кириллица разрешена | `Холодное_письмо_v1` — нормальное имя | v13 |
| `yield_per` + SQLite: fallback на offset/limit | SQLite не поддерживает `stream_results` нативно | v13 |
| IMAP helpers — отдельный модуль | Дедупликация кода между process_bounces и process_replies | v13 |
| Задача 17 перенесена в Этап 2 | Тот же файл `companies.py`, что и задача 4 — избегаем конфликтов | v13 |

---

## 3. Верификация аудита — что реально, что нет

Аудит (`docs/archive/audits.md`, 10 областей) был написан Claude **без доступа к коду**, только по документации. Верификация проведена путём чтения исходного кода в `/home/z/my-project/granite-crm/`.

### 3.1 Уже исправлено (аудит опоздал)

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

### 3.2 Подтверждённые проблемы (действительны)

| Утверждение аудита | Реальность в коде | Действие в v13 |
|--------------------|-------------------|---------------|
| Template name `^[a-z0-9_]+$` запрещает кириллицу | `schemas.py:88`: `pattern=r"^[a-z0-9_]+$"` — точно так | Задача 15 (этап 2) |
| `_get_campaign_recipients` загружает `.all()` в память | `campaigns.py:134`: `rows = q.all()` — точно так | Задача 18 (этап 2, внутри задачи 2) |
| `list_companies`: 2 запроса `count()` + `offset().limit()` | `companies.py:308-309` — точно так | Отложено (низкий приоритет) |
| Raw SQL через f-string в `companies.py` | `companies.py:126-131,148-158` — f-string с Pydantic-валидацией | Задача 17 (этап 2 — **перенесено из этапа 4**) |
| Нет `.env.example` | Проверено: файл не существует | Задача 16 (этап 1) |
| `config_validator.py` не проверяет SMTP/API ключи | `config_validator.py` — только scoring, database, scraping | Задача 16 (этап 1) |
| Нет SMTP health check при старте | Проверено: нет проверки подключения | Задача 16 (этап 1) |
| `setattr(contact, key, value)` в цикле | `companies.py:417` — да, но Pydantic ограничивает до 3 полей | Приемлемо, добавить комментарий |

### 3.3 Неверные номера строк (аудит без кода)

| Утверждение | Указано | Реально |
|-------------|---------|---------|
| `api_key_auth_middleware` | app.py:107-132 | app.py:280-309 |
| CORS defaults | app.py:69-74 | app.py:79-84 |
| `is_safe_url()` | utils.py:480-558 | utils.py:699-777 |
| `VALID_STAGES` | database.py:154-157 | database.py:197-200 |
| `setattr` в PATCH | companies.py:177-178 | companies.py:417 |
| `needs_review` в merger | merger.py:152-217 | merger.py:168-246 |

### 3.4 Scraper-audit (качество данных)

Scraper-audit (`docs/archive/scraper-audit.md`) анализирует качество базы и НЕ зависит от кода — это анализ данных. Его выводы **достоверны** и напрямую влияют на email-кампанию:

| Проблема | Влияние на рассылку | Действие |
|----------|---------------------|----------|
| 56% web_search — агрегаторы (660 из 1174) | Письма уходят колл-центрам, а не мастерским | Предпосылка: scraper-audit A-1 перед запуском |
| 51% jsprav — нецелевые категории (ритуальные услуги) | Нецелевая аудитория не ответит | Предпосылка: scraper-audit A-2 перед запуском |
| 58% enriched — SEO-имена вместо реальных | Обращение «Уважаемая компания Памятники из гранита» | Задача 7 + scraper-audit A-4/A-7 |
| Нет фильтра по городу контактов | Московский телефон в записи города Абаза | Scraper-audit A-5, не блокирует рассылку |

**Важно:** Scraper-audit A-1 (SKIP_DOMAINS) и A-2 (jsprav категории) — это **предпосылки** для запуска рассылки. Без них в базе ~40% мусора, который валидатор (задача 4) не сможет отфильтровать полностью. Однако рассылку можно начинать **до** их реализации, если вручную проверить список из 434 приоритетных целей.

---

## 4. Стратегия и волны

### 4.1 Реальное состояние базы

```
Всего в базе:                           ~6 000 компаний
Обработанные города:                    29 из 46
Сегмент A, не-сеть, валидный email:     175
Сегмент B, не-сеть, валидный email:     259
────────────────────────────────────────────────────────
Приоритетная база:                      434 компании
Крупные сети (ручная работа):           8 компаний
```

### 4.2 Волны

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

## 5. Прогрев домена

### 5.1 Обязательный чеклист до первой отправки

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

### 5.2 График прогрева (первые 10 дней)

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

### 5.3 Метрики здоровья

| Метрика | Норма | Стоп-сигнал |
|---------|-------|-------------|
| Bounce rate (hard) | < 2% | ≥ 5% → стоп |
| Spam complaints | < 0.1% | ≥ 0.5% → стоп |
| Open rate (mail.ru/Яндекс) | 10–20% | < 5% → проверить что Gmail не в спаме |
| Reply rate | цель ≥ 3% | < 1% → пересмотреть шаблон |

### 5.4 Признаки блокировки Gmail

| Симптом | Что делать |
|---------|-----------|
| Письма уходят в «Промоакции» | Норма — не блокировка |
| SMTP ошибка 421 / 550 | Снизить объём на 50% на 3 дня |
| Письма вообще не уходят | Проверить App Password, SMTP-настройки |
| Bounce rate ≥ 5% | Стоп кампании, разбор базы |

---

## 6. Шаблоны писем

### 6.1 `cold_email_v1` — основной (Фаза 0, Волны 2–4)

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

### 6.2 `cold_email_marquiz` — для Marquiz + TG (Волна 1)

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

### 6.3 `follow_up_email_v1` — follow-up (только email, через 7 дней)

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

> **Тема follow-up** — `{original_subject}` — плейсхолдер, который заменяется на тему исходного письма при отправке. `process_followups.py` (задача 11) извлекает оригинальную тему из `CrmTouchRow` и подставляет её. Если исходное письмо было отправлено с темой B (`Ретушь под памятник...`), follow-up будет `Re: Ретушь под памятник...`, а не `Re: подготовка фото под гравировку`.

### 6.4 Критерий выбора победителя A/B

**Реальность:** при 25/25 писем на каждую тему статистическая значимость минимальна. 1 ответ = 4% — это шум.

**Практический критерий:**

- Если одна тема набрала **≥ 2 ответа**, а другая **0** — используем первую
- Если обе темы дали **0 ответов** за 5 дней — проблема в теле письма или домене, не в теме. Пересматриваем письмо, не запускаем волны
- Если обе дали **1 ответ** — **ничья**, используем тему A (по умолчанию)

Никаких процентов и «превышение на 50%» на выборке из 25 — это иллюзия точности.

### 6.5 `cold_email_bitrix` — для Bitrix CMS (Волна 1, опционально)

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

## 7. Технический план

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

### 7.0 Этапы реализации + TDD

Все 19 задач (14 из v11 + 4 из аудита v12 + 1 новая v13) разбиты на 4 этапа. Каждый этап — законченный кусок работы, который можно протестировать и задеплоить независимо. TDD: сначала тест, потом код.

### Этап 1: Фундамент — критические фиксы + инфраструктура (0 писем) ✅ ВЫПОЛНЕН

**Цель:** починить то, что сломано, и подготовить инфраструктуру для первой отправки. После этого этапа CRM способна отправить тестовое письмо и обработать отписку.

**Принцип TDD:** для каждого фикса сначала пишем тест, который воспроизводит баг, потом фиксим.

| Задача | Что делаем | Статус |
|--------|-----------|--------|
| **8. SMTP_SSL** | `sender.py`: порт 465 → `SMTP_SSL`, 587 → `SMTP+STARTTLS` | ✅ Порт по умолчанию 465, SMTP_SSL/STARTTLS по порту |
| **7/14. SEO-regex** | Убрать `гранитн[ые]+\s+мастерск`, починить `памятник[аиы]?` (предлог обязателен + слово после). Убрать `гранитнаямастерская` из слипшихся | ✅ 11 тест-кейсов из v13 проходят |
| **1. Unsubscribe** | `unsubscribe_token` в `CrmContactRow` (nullable=False, auto-generate) + миграция (идемпотентная) + эндпоинт + `cancel_followup_tasks()` | ✅ ORM + миграция + API + helpers |
| **6. Auth bypass** | `/track/open/` + `/api/v1/unsubscribe/` в whitelist middleware | ✅ Оба пути в bypass |
| **16. .env.example + стартовые проверки** | `.env.example` с SMTP/IMAP/API/BASE_URL/отправка. Warning при старте. `/health/smtp` endpoint | ✅ Файл + warnings + health check |

**Порядок реализации (этап 1):**
1. ~~Задача 16: `.env.example` + стартовые проверки (15 мин)~~ ✅
2. ~~Написать все тесты для задач 7/14, 8, 1, 6 (красные)~~ — тесты SEO-regex обновлены
3. ~~Задача 8: SMTP_SSL фикс~~ ✅
4. ~~Задача 7/14: SEO-regex~~ ✅
5. ~~Задача 1: Unsubscribe (миграция + API + cancel_followup)~~ ✅ + фикс nullable=False
6. ~~Задача 6: Auth bypass~~ ✅
7. `uv run pytest tests/ -v` — всё зелёное — ✅ 118/118 тестов пройдено
8. Ручной тест: отправить 1 письмо себе → проверить отписку → проверить tracking pixel — ⚠️ не проводился

**Коммиты:** `b01fe5a` (Этап 1), `d201ca0` (fix unsubscribe_token nullable)

**Зависимости:** нет — можно начинать сразу

---

### Этап 2: Отправка + валидация + A/B + рефакторинг (первые 10 тестовых писем)

**Цель:** CRM может создавать кампанию с A/B тестом, валидировать получатели, отправлять и восстанавливаться после краша. После этого этапа можно запустить первую тестовую кампанию на 5-10 своих адресов.

**Принцип TDD:** для каждого эндпоинта и каждой функции — тест с моками SMTP/IMAP.

| Задача | Что делаем | Тесты (сначала!) |
|--------|-----------|-----------------|
| **2. Recovery + отправка** | `lifespan()`: running→paused. `_get_campaign_recipients()`: фильтр + дедуп. `sender.py`: commit после каждого письма (не batch). Полный `_run_campaign_background` | `test_recovery_running_to_paused()` — создать кампанию status=running, запустить lifespan → status=paused. `test_campaign_recipients_dedup()` — два письма одному contact → только 1 получатель. `test_campaign_recipients_filter_stop_automation()` — contact с `stop_automation=1` не в списке. `test_commit_per_email()` — мок БД, после каждого `send()` → `commit()` вызван |
| **18. Campaign recipients: батч вместо .all()** (из аудита) | Заменить `campaigns.py:134` `q.all()` на батч-итерацию с учётом SQLite. В рамках задачи 2 | `test_campaign_recipients_no_oom()` — мок с 5000 компаний → итерация по батчам, не всё в памяти сразу. `test_yield_per_100_processes_all()` — все 5000 компаний обработаны |
| **4. Валидатор** | `validate_recipients()`: агрегаторы (SKIP_DOMAINS из scraper-audit A-1), невалидные email, дедуп, `EMAIL_SESSION_GAP_HRS`, признаки блокировки Gmail | `test_aggregator_filtered()` — `tsargranit.ru` → отфильтрован. `test_invalid_email_filtered()` — `test@` → отфильтрован. `test_duplicate_email_deduped()` — две компании с одним email → 1 получатель. `test_session_gap()` — письмо 30 мин назад → отфильтрован. `test_gmail_block_signs()` — 5 bounced @gmail.com → домен помечен |
| **3. A/B + счётчики** | `determine_ab_variant()`: детерминированное распределение по company_id. `total_errors`, `ab_variant` в логах. A/B stats endpoint | `test_ab_deterministic()` — `determine_ab_variant(company_id=42)` всегда одинаковый результат. `test_ab_50_50_split()` — 100 компаний → ~50/50. `test_total_errors_increment()` — ошибка отправки → `total_errors+1`. `test_ab_variant_in_log()` — письмо → `CrmEmailLogRow.ab_variant` = "A" или "B". `test_ab_stats_endpoint()` — GET `/campaigns/1/ab-stats` → `{A: {...}, B: {...}}` |
| **12 (impl). Immutable шаблоны** | `data/email_templates.json` с ID. `seed-templates`: INSERT-only. `CrmEmailLogRow.template_id`. `CrmTemplateRow.retired`. Миграция | `test_seed_inserts_new()` — пустая БД → 10 шаблонов. `test_seed_skips_existing()` — повторный seed → 0 новых. `test_template_id_in_log()` — отправка → `template_id=1`. `test_retired_not_in_campaign_list()` — GET `/templates` → `retired=true` не показывается. `test_immutable_no_update()` — изменить JSON, seed → существующий шаблон НЕ обновился |
| **15. Template name: разрешить кириллицу** (из аудита) | `schemas.py:88`: изменить pattern на `^[a-z0-9_\u0410-\u042f\u0430-\u044f]+$` (включая заглавную кириллицу). Добавить `description` поле + миграция | `test_template_name_cyrillic()` — `name="Холодное_письмо_v1"` → accepted. `test_template_name_still_rejects_spaces()` — `name="cold email"` → rejected. `test_template_description_field()` — `description="Холодное письмо v1"` → сохраняется |
| **17. Raw SQL: f-string → параметризованные** (из аудита, **перенесено из этапа 4**) | `companies.py:126-131,148-158`: заменить f-string интерполяцию на `:param` с `text(...).bindparams()`. Быстрый рефакторинг (30 мин), тот же файл что задача 4 | `test_raw_sql_parameterized()` — все `sa_text()` вызовы используют `:param`, а не f-string. `test_tg_trust_filter_parameterized()` — `tg_trust_min`/`tg_trust_max` через bindparam. `test_source_filter_parameterized()` — `source` через bindparam |

**Порядок реализации (этап 2):**
1. Написать все тесты (красные)
2. Задача 2 + 18: Recovery + отправка + батч-итерация → тесты зелёные
3. Задача 4: Валидатор → тесты зелёные
4. Задача 17: Raw SQL рефакторинг (30 мин, пока `companies.py` открыт) → тесты зелёные
5. Задача 3: A/B + счётчики → тесты зелёные
6. Задача 12 impl: Immutable шаблоны → тесты зелёные
7. Задача 15: Template name кириллица + description миграция → тесты зелёные (15 мин)
8. Интеграционный тест: создать кампанию → A/B → валидация → отправка 5 писем себе → проверить логи
9. `uv run pytest tests/ -v` — всё зелёное

**Зависимости:** этап 1 завершён (SMTP работает, отписка работает, auth bypass для tracking)

---

### Этап 3: Обратная связь — follow-up, bounce, reply, IMAP helpers (10-20 реальных писем)

**Цель:** CRM автоматически обрабатывает bounce, распознаёт ответы, отправляет follow-up. После этого этапа можно запустить первую реальную кампанию на 20-30 мастерских.

**Принцип TDD:** мокаем IMAP, подставляем тестовые письма, проверяем что CRM правильно меняет статусы.

| Задача | Что делаем | Тесты (сначала!) |
|--------|-----------|-----------------|
| **19. IMAP helpers module** (НОВОЕ v13) | `granite/email/imap_helpers.py`: общие IMAP-функции для задач 6 и 9. `extract_email()`, `extract_body()`, `is_bounce()`, `is_ooo()`, `extract_bounced_email()`, `extract_dsn()` | `test_extract_email_brackets()` — `"Иван <ivan@mail.ru>"` → `"ivan@mail.ru"`. `test_extract_email_plain()` — `"ivan@mail.ru"` → `"ivan@mail.ru"`. `test_extract_body_plain()` — text/plain часть извлечена. `test_is_bounce_dsn()` — DSN 5.1.1 → True. `test_is_bounce_normal()` — обычное письмо → False. `test_is_ooo_russian()` — «автоответ» → True. `test_is_ooo_english()` — «Out of Office» → True. `test_extract_bounced_email()` — Final-Recipient извлечён. `test_extract_dsn()` — DSN-код извлечён из delivery-status |
| **6. Bounce parser** | `process_bounces.py`: IMAP → распознать bounce → `CrmEmailLogRow.status="bounced"`, `CrmContactRow.funnel_stage="unreachable"`. Использует `imap_helpers` | `test_bounce_511_user_unknown()` — мок IMAP с DSN 5.1.1 → статус bounced, funnel unreachable. `test_bounce_522_mailbox_full()` — DSN 5.2.2 → статус bounced, funnel НЕ меняется. `test_bounce_571_blocked()` — DSN 5.7.1 → `stop_automation=1`. `test_bounce_imap_connection_error()` — IMAP недоступен → graceful, не крашится |
| **9. Reply parser** | `process_replies.py`: IMAP → распознать ответ → `funnel_stage="replied"`, `cancel_followup_tasks()`, `total_replied++`, `body=` унификация. Использует `imap_helpers` | `test_reply_detected()` — мок IMAP с ответом → `funnel_stage="replied"`. `test_reply_cancels_followup()` — ответ → pending follow-up = cancelled. `test_reply_increments_total_replied()` — ответ → `campaign.total_replied+1`. `test_reply_touch_body_unified()` — `CrmTouchRow.body=` заполнен. `test_ooo_ignored()` — автоответчик → без изменений. `test_spam_complaint()` — «это спам» → `stop_automation=1` |
| **5. Follow-up + счётчики** | `_maybe_create_followup_task()`: создать задачу +7д. `cancel_followup_tasks()`: отменить при терминальной стадии. `total_opened++` при tracking pixel | `test_followup_created_on_open()` — tracking pixel → `CrmTaskRow(task_type="follow_up", due_date=+7d)`. `test_followup_cancelled_on_reply()` — ответ → задача cancelled. `test_followup_cancelled_on_unsubscribe()` — отписка → задача cancelled. `test_total_opened_increment()` — tracking pixel → `campaign.total_opened+1` |
| **11. Follow-up executor** | `process_followups.py`: созревшие задачи → отправить письмо → completed | `test_followup_sent_when_due()` — задача с `due_date < now` → письмо отправлено, статус done. `test_followup_not_sent_when_future()` — `due_date > now` → ничего. `test_followup_not_sent_when_cancelled()` — статус cancelled → ничего. `test_followup_uses_reply_subject()` — тема `Re: {original_subject}` |

**Порядок реализации (этап 3):**
1. Написать все тесты (красные)
2. Задача 19: IMAP helpers module → тесты зелёные
3. Задача 5: Follow-up создание + отмена + счётчики → тесты зелёные
4. Задача 11: Follow-up executor → тесты зелёные
5. Задача 6: Bounce parser (использует imap_helpers) → тесты зелёные
6. Задача 9: Reply parser (использует imap_helpers) → тесты зелёные
7. Интеграционный тест: отправка → bounce → проверка unreachable; отправка → ответ → проверка replied + follow-up отменён
8. `uv run pytest tests/ -v` — всё зелёное

**Зависимости:** этапы 1+2 завершены (отправка работает, A/B работает, логи пишутся)

---

### Этап 4: UI + финализация (запуск Волны 1)

**Цель:** фронтенд для управления кампаниями, post-reply UI, Bitrix-решение. После этого этапа — полноценный запуск первой волны на 50 компаний.

**Принцип TDD:** для UI — e2e тесты через Playwright. Для API-изменений — обычные юнит-тесты.

| Задача | Что делаем | Тесты (сначала!) |
|--------|-----------|-----------------|
| **10. Фронтенд** | Wizard создания кампании (шаблон + A/B + фильтры). Карточка компании с post-reply кнопками. Dashboard со статистикой | E2E: `test_campaign_wizard_creates_campaign()` — заполнить форму → кампания в БД. `test_ab_subject_b_optional()` — без темы B → кампания без A/B. `test_post_reply_buttons()` — карточка компании → кнопка «Цена» → письмо отправлено. Юнит: `test_template_dropdown_excludes_retired()` — API `/templates` не возвращает retired |
| **12 (доки)** | `docs/POST_REPLY_PLAYBOOK.md` + `docs/EMAIL_TEMPLATES.md` — уже созданы, Александр редактирует | — (документация, не код) |
| **13. Bitrix-шаблон** | Решение: отдельный шаблон `cold_email_bitrix` или общий. Зависит от результатов этапа 2 | Если создаём: `test_bitrix_template_in_json()` — шаблон #4 в `email_templates.json` |
| **5 (открытые вопросы)** | mail-tester.com оценка, DKIM/SPF/DMARC, Cloudflare Tunnel, признаки блокировки Gmail | — (инфраструктура, не код) |

**Порядок реализации (этап 4):**
1. Задача 10: Фронтенд — wizard + карточка + dashboard
2. Задача 13: Bitrix-решение
3. Александр редактирует шаблоны в `email_templates.json`
4. `seed-templates` → шаблоны в БД
5. Прогрев домена (3 дня по 5 писем на свои адреса)
6. mail-tester.com → оценка ≥ 8/10
7. Запуск Волны 1: 50 компаний, A/B тест тем

**Зависимости:** этапы 1+2+3 завершены

---

### Сводка по этапам

| Этап | Задачи | Результат | Когда можно тестировать |
|------|--------|-----------|------------------------|
| 1 | 1, 6, 7/14, 8, **16** | CRM может отправить 1 письмо + отписка + tracking + `.env.example` | Сразу после завершения |
| 2 | 2, 3, 4, 12(impl), **15, 17, 18** | CRM может создать кампанию с A/B + валидация + кириллица + батч-итерация + параметризованный SQL | 1-2 дня после этапа 1 |
| 3 | **19**, 5, 6, 9, 11 | CRM обрабатывает bounce/reply/follow-up автоматически + IMAP helpers | 2-3 дня после этапа 2 |
| 4 | 10, 12(доки), 13 | Полный цикл: UI → кампания → статистика → post-reply | 3-5 дней после этапа 3 |

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
from granite.api.helpers import cancel_followup_tasks
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

    # Отменить pending follow-up задачи
    cancel_followup_tasks(contact.company_id, "not_interested", db)

    db.add(CrmTouchRow(
        company_id=contact.company_id,
        channel="email",
        direction="incoming",
        subject="Отписка",
        body="unsubscribe_link",
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

> **Заметка:** Текущий код (app.py:280-309) уже имеет auth bypass для некоторых путей. Перед реализацией — проверить что именно уже обойдено и расширить при необходимости.

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

### Задача 2: Recovery + отправка + батч-итерация + SSE-прогресс

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

> **Заметка для оператора:** BackgroundTask живёт в памяти процесса. При любом перезапуске сервера (ошибка, `--reload`, ручной рестарт) задача теряется, кампания переходит в `paused`. Это ожидаемое поведение — нужно вручную нажать «Продолжить» в UI.

#### 2.2 Эндпоинт запуска кампании

```python
@router.post("/campaigns/{campaign_id}/run")
async def run_campaign(campaign_id: int, background_tasks: BackgroundTasks, request: Request):
    """Запустить кампанию. Отправка — в BackgroundTask, прогресс — через SSE."""
    SessionFactory = request.app.state.Session

    # 1. Проверить что нет уже запущенной кампании
    check_session = SessionFactory()
    try:
        running = check_session.query(CrmEmailCampaignRow).filter_by(status="running").first()
        if running and running.id != campaign_id:
            raise HTTPException(409, f"Уже запущена кампания #{running.id} '{running.name}'")
    finally:
        check_session.close()

    # 2. Атомарно сменить статус
    pre_session = SessionFactory()
    try:
        result = pre_session.execute(
            sa_text(
                "UPDATE crm_email_campaigns SET status='running', "
                "started_at=COALESCE(started_at, :now), updated_at=:now "
                "WHERE id=:id AND status NOT IN ('running', 'completed')"
            ),
            {"id": campaign_id, "now": datetime.now(timezone.utc)},
        )
        pre_session.commit()
        if result.rowcount == 0:
            raise HTTPException(400, "Кампания не может быть запущена")
    finally:
        pre_session.close()

    # 3. Запустить фоновую задачу
    background_tasks.add_task(_run_campaign_background, campaign_id, SessionFactory)
    return {"status": "started", "campaign_id": campaign_id}
```

#### 2.3 Фоновая задача отправки — `_run_campaign_background`

```python
def _run_campaign_background(campaign_id: int, SessionFactory) -> None:
    """Фоновая отправка писем. Создаёт свою сессию БД."""
    import time, random
    from granite.email.sender import EmailSender
    from granite.email.validator import validate_recipients

    EMAIL_DELAY_MIN = int(os.environ.get("EMAIL_DELAY_MIN", "45"))
    EMAIL_DELAY_MAX = int(os.environ.get("EMAIL_DELAY_MAX", "120"))
    EMAIL_DAILY_LIMIT = int(os.environ.get("EMAIL_DAILY_LIMIT", "50"))

    session = SessionFactory()
    sender = EmailSender()

    try:
        campaign = session.get(CrmEmailCampaignRow, campaign_id)
        if not campaign or campaign.status != "running":
            return

        # v13: ищем шаблон по template_id, а не по template_name
        template = None
        if campaign.template_id:
            template = session.query(CrmTemplateRow).filter_by(id=campaign.template_id).first()
        if not template and campaign.template_name:
            # Фоллбэк для обратной совместимости
            template = session.query(CrmTemplateRow).filter_by(name=campaign.template_name).first()
        if not template:
            campaign.status = "error"
            session.commit()
            return

        recipients = _get_campaign_recipients(campaign, session)

        # Валидация получателей
        valid, warnings = validate_recipients(recipients)
        if warnings:
            logger.warning(
                f"Кампания {campaign_id}: пропущено {len(warnings)} получателей — "
                + ", ".join(w["reason"] for w in warnings[:5])
            )

        from_name = os.environ.get("FROM_NAME", "")
        sent = campaign.total_sent or 0

        for company, enriched, contact, email_to in valid:
            # Проверить паузу/отмену
            session.refresh(campaign)
            if campaign.status != "running":
                logger.info(f"Кампания {campaign_id}: статус '{campaign.status}', выход")
                return

            # Глобальный дневной лимит
            last_24h = datetime.now(timezone.utc) - timedelta(hours=24)
            sent_today = (
                session.query(func.count(CrmEmailLogRow.id))
                .filter(CrmEmailLogRow.sent_at >= last_24h)
                .scalar()
            )
            if sent_today >= EMAIL_DAILY_LIMIT:
                campaign.status = "paused_daily_limit"
                campaign.updated_at = datetime.now(timezone.utc)
                session.commit()
                logger.info(f"Кампания {campaign_id}: дневной лимит ({EMAIL_DAILY_LIMIT})")
                return

            # Рендер шаблона
            city = company.city or ""
            render_kwargs = {
                "from_name": from_name,
                "city": city,
                "company_name": company.name_best or "",
                "website": company.website or "",
                "unsubscribe_url": f"{sender.base_url}/api/v1/unsubscribe/{contact.unsubscribe_token}" if contact else "",
            }

            # A/B тема
            subject = get_ab_subject(company.id, campaign.subject_a, campaign.subject_b, template, render_kwargs)

            # Track A/B variant
            ab_variant = "A" if subject == (campaign.subject_a or template.render_subject(**render_kwargs)) else "B"

            rendered = template.render(**render_kwargs)

            # Отправка
            try:
                if template.body_type == "html":
                    from granite.utils import html_to_plain_text
                    body_text = html_to_plain_text(rendered)
                    tracking_id = sender.send(
                        company_id=company.id, email_to=email_to,
                        subject=subject, body_text=body_text, body_html=rendered,
                        template_id=template.id, db_session=session,  # v13: template_id
                        campaign_id=campaign.id,
                        ab_variant=ab_variant,
                    )
                else:
                    tracking_id = sender.send(
                        company_id=company.id, email_to=email_to,
                        subject=subject, body_text=rendered,
                        template_id=template.id, db_session=session,  # v13: template_id
                        campaign_id=campaign.id,
                        ab_variant=ab_variant,
                    )

                if tracking_id:
                    sent += 1
                    campaign.total_sent = sent
                    session.add(CrmTouchRow(
                        company_id=company.id, channel="email",
                        direction="outgoing", subject=subject,
                        body=f"[tracking_id={tracking_id}] [subject={subject}] [ab={ab_variant}]",
                    ))
                    if contact:
                        from granite.api.stage_transitions import apply_outgoing_touch
                        apply_outgoing_touch(contact, "email")
                    # commit после КАЖДОГО письма — не теряем данные при краше
                    campaign.updated_at = datetime.now(timezone.utc)
                    session.commit()
                else:
                    campaign.total_errors = (campaign.total_errors or 0) + 1
                    session.commit()

            except Exception as e:
                logger.error(f"Ошибка отправки company_id={company.id}: {e}")
                campaign.total_errors = (campaign.total_errors or 0) + 1
                session.commit()

            # Задержка
            delay = random.randint(EMAIL_DELAY_MIN, EMAIL_DELAY_MAX)
            time.sleep(delay)

        # Цикл завершён
        campaign.status = "completed"
        campaign.completed_at = datetime.now(timezone.utc)
        session.commit()

    except Exception as e:
        logger.exception(f"Критическая ошибка в кампании {campaign_id}: {e}")
        try:
            campaign = session.get(CrmEmailCampaignRow, campaign_id)
            if campaign:
                campaign.status = "error"
                session.commit()
        except Exception:
            pass
    finally:
        session.close()
```

#### 2.4 SSE-прогресс эндпоинт

```python
@router.get("/campaigns/{campaign_id}/progress")
async def campaign_progress(campaign_id: int, request: Request):
    """SSE: прогресс из БД каждые 3 секунды."""
    SessionFactory = request.app.state.Session

    async def generate():
        while True:
            session = SessionFactory()
            try:
                campaign = session.get(CrmEmailCampaignRow, campaign_id)
                if not campaign:
                    yield f"data: {json.dumps({'error': 'not_found'})}\n\n"
                    return

                yield f"data: {json.dumps({
                    'status': campaign.status,
                    'sent': campaign.total_sent or 0,
                    'errors': campaign.total_errors or 0,
                    'opened': campaign.total_opened or 0,
                    'replied': campaign.total_replied or 0,
                })}\n\n"

                if campaign.status in ("completed", "error", "paused", "paused_daily_limit"):
                    return
            finally:
                session.close()

            await asyncio.sleep(3)

    return StreamingResponse(generate(), media_type="text/event-stream")
```

#### 2.5 Статус `paused_daily_limit`

Кампания переходит в `paused_daily_limit` при достижении дневного лимита. Ручной перезапуск на следующий день — достаточно. В UI: показать причину паузы и кнопку «Продолжить».

Статус `paused_daily_limit` входит в группу `paused`-подобных — разрешён перезапуск:

```python
if campaign.status not in ("draft", "paused", "paused_daily_limit"):
    raise HTTPException(400, "Кампания не может быть запущена")
```

#### 2.6 `_get_campaign_recipients()` — батч-итерация (задача 18)

```python
# granite/api/campaigns.py

def _get_campaign_recipients(campaign: CrmEmailCampaignRow, db: Session) -> list[tuple]:
    """Получить список получателей кампании с фильтрацией и дедупликацией.
    
    v13: батч-итерация вместо .all() с учётом SQLite.
    """
    filters = campaign.filters or {}

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

    # Исключаем: stop_automation, нет email
    q = q.filter(
        CrmContactRow.stop_automation == False,
        CrmContactRow.email.isnot(None),
        CrmContactRow.email != "",
    )

    # Дедуп: уже отправленные в этой кампании
    sent_emails = set(
        row[0] for row in db.query(CrmEmailLogRow.email_to)
        .filter(CrmEmailLogRow.campaign_id == campaign.id)
        .all()
    )

    recipients = []
    seen_emails = set()

    # v13: батч-итерация с учётом SQLite
    # Для PostgreSQL: q.yield_per(100).execution_options(stream_results=True)
    # Для SQLite: yield_per работает, но stream_results не поддерживается
    # Используем try/except для автоматического выбора подхода
    try:
        rows = q.yield_per(100).execution_options(stream_results=True)
    except Exception:
        # SQLite fallback — просто итерируем
        rows = q.yield_per(100) if hasattr(q, 'yield_per') else q.all()

    for company, enriched, contact in rows:
        if not contact or not contact.email:
            continue
        if contact.email in sent_emails:
            continue
        if contact.email in seen_emails:
            continue  # дедуп email
        seen_emails.add(contact.email)
        recipients.append((company, enriched, contact, contact.email))

    return recipients
```

> **Заметка по SQLite:** Для текущих объёмов (~6000 компаний) `.all()` работает нормально. Батч-итерация — профилактика на будущее. При переходе на PostgreSQL `stream_results=True` обеспечит эффективную потоковую обработку.

---

### Задача 3: A/B — детерминированное распределение + счётчики

#### 3.1 Колонка `total_errors`

```python
# granite/database.py — CrmEmailCampaignRow
total_errors = Column(Integer, default=0)
```

Миграция:
```bash
uv run cli.py db migrate "add total_errors to campaigns"
uv run cli.py db upgrade head
```

#### 3.2 Функция A/B-распределения

```python
# granite/api/campaigns.py

def get_ab_subject(
    company_id: int,
    subject_a: str | None,
    subject_b: str | None,
    template: CrmTemplateRow,
    render_kwargs: dict,
) -> str:
    """Детерминированное A/B распределение по company_id.

    Если у кампании задан subject_b — делим 50/50 через MD5-хеш.
    Если subject_b нет — используем тему из шаблона.
    """
    a = subject_a or template.render_subject(**render_kwargs)

    if not subject_b:
        return a

    import hashlib
    hash_val = int(hashlib.md5(str(company_id).encode()).hexdigest(), 16)
    return a if hash_val % 2 == 0 else subject_b
```

#### 3.3 Колонки `total_opened` / `total_replied`

```python
# granite/database.py — CrmEmailCampaignRow
total_opened = Column(Integer, default=0)
total_replied = Column(Integer, default=0)
```

Миграция:
```bash
uv run cli.py db migrate "add total_opened total_replied to campaigns"
uv run cli.py db upgrade head
```

> **Почему это критично:** SSE-поллинг (задача 2.4) возвращает `campaign.total_opened` и `campaign.total_replied`. Без инкремента в tracking.py и process_replies.py эти значения всегда 0.

#### 3.4 A/B stats endpoint

```python
@router.get("/campaigns/{campaign_id}/ab-stats")
def get_ab_stats(campaign_id: int, db: Session = Depends(get_db)):
    """Статистика A/B теста по вариантам."""
    campaign = db.get(CrmEmailCampaignRow, campaign_id)
    if not campaign:
        raise HTTPException(404, "Кампания не найдена")

    if not campaign.subject_b:
        return {"variants": {}, "winner": None, "note": "Не A/B тест"}

    from sqlalchemy import text
    rows = db.execute(text("""
        SELECT ab_variant,
               COUNT(*) as sent,
               SUM(CASE WHEN opened_at IS NOT NULL THEN 1 ELSE 0 END) as opened,
               SUM(CASE WHEN status = 'replied' THEN 1 ELSE 0 END) as replied
        FROM crm_email_logs
        WHERE campaign_id = :cid AND ab_variant IS NOT NULL
        GROUP BY ab_variant
    """), {"cid": campaign_id}).fetchall()

    result = {}
    for row in rows:
        v = row[0]
        sent = row[1]
        result[v] = {
            "subject": campaign.subject_a if v == "A" else campaign.subject_b,
            "sent": sent,
            "opened": row[2],
            "replied": row[3],
            "reply_rate": round(row[3] / sent * 100, 1) if sent else 0,
        }

    return {
        "variants": result,
        "winner": None,  # Определяется вручную по критерию из раздела 6.4
        "note": "Победитель — по количеству ответов (см. раздел 6.4)",
    }
```

**ORM-миграция для `ab_variant`:**

```python
# granite/database.py — CrmEmailLogRow
ab_variant = Column(String(1), nullable=True)  # "A" or "B"
```

---

### Задача 4: Валидатор получателей

```python
# granite/email/validator.py

"""Валидация получателей перед отправкой."""
import re

# Домены агрегаторов — не мастерские (из scraper-audit A-1)
AGGREGATOR_DOMAINS = frozenset({
    "tsargranit.ru", "alshei.ru", "mipomnim.ru", "uznm.ru",
    "monuments.su", "masterskay-granit.ru", "gr-anit.ru",
    "v-granit.ru", "nbs-granit.ru", "granit-pamiatnik.ru",
    "postament.ru", "uslugio.com", "pqd.ru", "spravker.ru",
    "orgpage.ru", "totadres.ru", "mapage.ru", "zoon.ru",
    "memorial.ru", "vsepamyatniki.ru", "obeliski.ru",
})

# Географический фильтр НЕ нужен — Беларусь (.by) и Казахстан (.kz) OK

_EMAIL_RE = re.compile(r"^[\w.+-]+@[\w.-]+\.\w{2,}$")

EMAIL_SESSION_GAP_HRS = 4  # минимальный интервал между письмами одной компании


def validate_recipients(
    recipients: list[tuple],
) -> tuple[list[tuple], list[dict]]:
    """Возвращает (valid, warnings)."""
    valid = []
    warnings = []
    seen_emails: set[str] = set()

    for company, enriched, contact, email_to in recipients:
        # Дедупликация email
        email_lower = email_to.lower().strip()
        if email_lower in seen_emails:
            warnings.append({
                "company_id": company.id,
                "name": company.name_best,
                "reason": f"дубль email ({email_lower})",
            })
            continue
        seen_emails.add(email_lower)

        reason = _check_recipient(company, contact, email_to)
        if reason:
            warnings.append({
                "company_id": company.id,
                "name": company.name_best,
                "reason": reason,
            })
        else:
            valid.append((company, enriched, contact, email_to))

    return valid, warnings


def _check_recipient(company, contact, email_to: str) -> str | None:
    """None = валиден, строка = причина пропуска."""

    # Формат email
    if not email_to or not _EMAIL_RE.match(email_to):
        return f"невалидный email ({email_to})"

    # Агрегатор
    domain = email_to.split("@")[-1].lower()
    if domain in AGGREGATOR_DOMAINS:
        return f"агрегатор ({domain})"

    # Отписан
    if contact and contact.stop_automation:
        return "отписан"

    # Пустое или слишком длинное название
    name = (company.name_best or "").strip()
    if not name:
        return "пустое название"
    if len(name) > 80:
        return "название слишком длинное (SEO?)"

    return None
```

---

### Задача 5: Follow-up + счётчики

#### 5.1 Создание follow-up задачи при открытии письма

```python
# granite/api/tracking.py — после инкремента open

# Инкремент счётчика открытий
campaign = session.query(CrmEmailCampaignRow).filter_by(id=log.campaign_id).first()
if campaign:
    campaign.total_opened = (campaign.total_opened or 0) + 1

_maybe_create_followup_task(contact.company_id, db)


def _maybe_create_followup_task(company_id: int, db: Session) -> None:
    """Создать follow-up задачу через 7 дней после открытия письма."""
    from granite.database import CrmTaskRow

    contact = db.get(CrmContactRow, company_id)
    if not contact:
        return

    # Не создавать если уже есть активная follow-up задача
    existing = db.query(CrmTaskRow).filter(
        CrmTaskRow.company_id == company_id,
        CrmTaskRow.task_type == "follow_up",
        CrmTaskRow.status == "pending",
    ).first()
    if existing:
        return

    # Не создавать если уже ответил
    if contact.funnel_stage in ("replied", "interested", "not_interested"):
        return

    # Получить оригинальную тему из последнего touch
    last_touch = (
        db.query(CrmTouchRow)
        .filter(CrmTouchRow.company_id == company_id, CrmTouchRow.direction == "outgoing")
        .order_by(CrmTouchRow.created_at.desc())
        .first()
    )
    original_subject = last_touch.subject if last_touch else "подготовка фото под гравировку"

    db.add(CrmTaskRow(
        company_id=company_id,
        title=f"Follow-up (открыл письмо): {original_subject}",
        task_type="follow_up",
        priority="normal",
        status="pending",
        due_date=datetime.now(timezone.utc) + timedelta(days=7),
        description=original_subject,  # сохраняем тему для Re: {subject}
    ))
    db.flush()
```

> Follow-up создаётся только при открытии. Получатели, которые не открыли письмо, follow-up не получают — осознанное решение, не дублируем тем, кто проигнорировал.

#### 5.2 `cancel_followup_tasks()` — публичная функция

```python
# granite/api/helpers.py

"""Общие хелперы для API."""
from loguru import logger
from datetime import datetime, timezone


CANCEL_FOLLOWUP_ON_STAGES = {"replied", "interested", "not_interested", "unreachable"}


def cancel_followup_tasks(company_id: int, new_stage: str, db) -> None:
    """Отменить все pending follow-up задачи при переходе в терминальную стадию.

    Вызывается из:
    - stage_transitions.py (apply_incoming_touch)
    - process_replies.py (обнаружение ответа)
    - unsubscribe.py (отписка)
    """
    from granite.database import CrmTaskRow

    if new_stage not in CANCEL_FOLLOWUP_ON_STAGES:
        return
    cancelled = (
        db.query(CrmTaskRow)
        .filter(
            CrmTaskRow.company_id == company_id,
            CrmTaskRow.status == "pending",
            CrmTaskRow.task_type == "follow_up",
        )
        .update({"status": "cancelled", "completed_at": datetime.now(timezone.utc)})
    )
    if cancelled:
        logger.info(f"company_id={company_id}: отменено {cancelled} follow-up (→ {new_stage})")
```

#### 5.3 Воронка после ответа

```
replied → interested  (обсуждаем условия)
replied → not_interested  (отказ)
interested → [ручная работа вне CRM]
```

Никаких автоматических действий при `interested`.

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

#### 6.2 Bounce parser (полная реализация)

```python
# scripts/process_bounces.py

"""
Читает IMAP-ящик (Gmail), ищет bounce-уведомления,
помечает компании как unreachable.

Запуск:
  uv run python -m scripts.process_bounces
"""
import imaplib
import os
from datetime import datetime, timezone
from loguru import logger

from granite.email.imap_helpers import is_bounce, extract_bounced_email, extract_dsn  # v13: общий модуль


IMAP_HOST = os.getenv("IMAP_HOST", "imap.gmail.com")
IMAP_USER = os.getenv("SMTP_USER")
IMAP_PASS = os.getenv("SMTP_PASS")


def process_bounces() -> int:
    if not all([IMAP_HOST, IMAP_USER, IMAP_PASS]):
        logger.error("IMAP_HOST / SMTP_USER / SMTP_PASS не заданы")
        return 0

    from granite.database import get_engine, CrmEmailLogRow, CrmContactRow
    from sqlalchemy.orm import Session

    engine = get_engine()
    processed = 0

    with imaplib.IMAP4_SSL(IMAP_HOST) as imap:
        imap.login(IMAP_USER, IMAP_PASS)
        imap.select("INBOX")

        # Искать bounce: MAILER-DAEMON + Delivery Status + Gmail NDR
        uid_list = []
        for criteria in [
            '(FROM "MAILER-DAEMON" UNSEEN)',
            '(SUBJECT "Delivery Status Notification" UNSEEN)',
            '(FROM "mailer-daemon@googlemail.com" UNSEEN)',
            '(SUBJECT "Undelivered" UNSEEN)',
        ]:
            _, uids = imap.search(None, criteria)
            if uids[0]:
                uid_list.extend(uids[0].split())

        # Дедупликация UID
        seen_uids = set()
        for uid in uid_list:
            if uid in seen_uids:
                continue
            seen_uids.add(uid)

            _, data = imap.fetch(uid, "(RFC822)")
            if not data or not data[0]:
                continue
            raw = data[0][1]
            msg = email.message_from_bytes(raw)

            # v13: используем общие хелперы
            if not is_bounce(msg):
                continue

            bounce_email = extract_bounced_email(msg)
            if not bounce_email:
                continue

            dsn_code = extract_dsn(msg)

            with Session(engine) as session:
                log = (
                    session.query(CrmEmailLogRow)
                    .filter_by(email_to=bounce_email)
                    .order_by(CrmEmailLogRow.sent_at.desc())
                    .first()
                )
                if log and log.status != "bounced":
                    log.status = "bounced"
                    log.bounced_at = datetime.now(timezone.utc)

                    contact = session.query(CrmContactRow).filter_by(
                        company_id=log.company_id
                    ).first()
                    if contact:
                        # Hard bounce (5.1.x, 5.3.x) → unreachable
                        if dsn_code and dsn_code.startswith(("5.1", "5.3")):
                            contact.funnel_stage = "unreachable"
                        # Blocked (5.7.x) → stop automation
                        if dsn_code and dsn_code.startswith("5.7"):
                            contact.stop_automation = True

                    session.commit()
                    processed += 1
                    logger.info(f"Bounce: {bounce_email} → company #{log.company_id}")

            imap.store(uid, "+FLAGS", "\\Seen")

    engine.dispose()
    logger.info(f"Обработано bounce: {processed}")
    return processed


if __name__ == "__main__":
    import email
    process_bounces()
```

---

### Задача 7: SEO-regex — финальная версия (v13)

**Проблемы v12:**
1. `гранитн[ые]+\s+мастерск` — флагает «Гранитные мастерские» как SEO, но `test_granit_not_seo()` ожидает `needs_review=False`
2. `памятник[аиы]?\s+(?=из|в|на|от|и)\s*` + `(?:из|в|на|от|и)\s+|` — двойная работа, lookahead баг

**v13 фикс:**

1. **Убрать `гранитн[ые]+\s+мастерск` полностью** — «Гранитные мастерские» — реальное название в нише, как «Гранит-Мастер». Решено в v7/v11, паттерн ошибочно добавлен обратно в v12.

2. **Вернуть v11-версию `памятник[аиы]?`** — предлог обязателен + слово после него, без lookahead.

**Итоговый regex (v13):**

```python
_SEO_TITLE_PATTERN = re.compile(
    r"(?:купить|цен[аыуе]|недорог|заказать|от производитель|"
    r"с установк|на могил|доставк|скидк|каталог|"
    r"памятник[аиы]?\s*(?:из|в|на|от|и)\s+\S|"   # предлог обязателен + слово после
    r"изготовлен.*(?:памятник|надгробие)|"         # без «гранит»
    r"памятники\s*(?:в|из|на|и)\s+\S|"            # scraper-audit A-7
    r"памятники\s*(?:на\s*кладбищ)|"
    r"изготовление\s*памятников|"                  # scraper-audit A-7
    r"памятники\s*и\s*надгробия|"                  # scraper-audit A-7
    r"производство\s*памятников|"
    r"изготовлениепамятников|установкапамятников|"  # слипшиеся
    r"памятникинамогилу|купитьпамятник|заказатьпамятник)",
    re.IGNORECASE,
)
```

**Что изменилось относительно v12:**
- ❌ Убрано: `гранитн[ые]+\s+мастерск` — «Гранитные мастерские» НЕ SEO
- ❌ Убрано: lookahead `(?=из|в|на|от|и)` — избыточность и баг
- ✅ Восстановлено: `памятник[аиы]?\s*(?:из|в|на|от|и)\s+\S|` — из v11

**Тесты для обновления:**

| Входное | Было (v12) | Стало (v13) | Ожидаем |
|---------|-----------|-------------|---------|
| `"Гранитные мастерские России"` | `True` (SEO) | `False` (не SEO) | ✅ Реальное название |
| `"Гранит-Мастер"` | `False` | `False` | ✅ Не изменилось |
| `"Гранит-Мастер ООО Памятники"` | `True` | `False` | ✅ Не SEO — «Памятники» без предлога |
| `"Памятники в Екатеринбурге"` | `True` | `True` | ✅ SEO сохранено |
| `"Памятники из гранита дёшево"` | `True` | `True` | ✅ SEO сохранено |
| `"Изготовление памятников недорого"` | `True` | `True` | ✅ SEO сохранено |

Обновить тесты: `test_seo_name_extraction.py`, `test_merger.py`.

---

### Задача 8: SMTP_SSL — порт 465

```python
# granite/email/sender.py — _smtp_send()

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(min=2, max=30),
    retry=retry_if_exception(_is_temporary_smtp_error),
    reraise=True,
)
def _smtp_send(self, email_to: str, msg: MIMEMultipart) -> None:
    """SMTP-отправка с retry на временные ошибки.

    Поддерживает два режима:
    - Порт 465: SMTP_SSL (implicit TLS) — Gmail по умолчанию
    - Порт 587: SMTP + STARTTLS (explicit TLS)
    """
    if self.smtp_port == 465:
        with smtplib.SMTP_SSL(self.smtp_host, self.smtp_port) as server:
            server.login(self.smtp_user, self.smtp_pass)
            server.sendmail(self.smtp_user, [email_to], msg.as_bytes())
    else:
        with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(self.smtp_user, self.smtp_pass)
            server.sendmail(self.smtp_user, [email_to], msg.as_bytes())
```

**Также обновить дефолтный порт:**

```python
# Было:
self.smtp_port = int(os.environ.get("SMTP_PORT", "587"))
# Стало:
self.smtp_port = int(os.environ.get("SMTP_PORT", "465"))
```

---

### Задача 9: Reply parser (полная реализация с imap_helpers)

```python
# scripts/process_replies.py

"""
Читает IMAP-ящик (Gmail), ищет ответы на отправленные письма,
переводит контакты в replied.

Запуск:
  uv run python -m scripts.process_replies
"""
import email
import imaplib
import os
import re
from datetime import datetime, timezone
from loguru import logger

from granite.email.imap_helpers import extract_email, extract_body, is_bounce, is_ooo  # v13: общий модуль


IMAP_HOST = os.getenv("IMAP_HOST", "imap.gmail.com")
IMAP_USER = os.getenv("SMTP_USER")
IMAP_PASS = os.getenv("SMTP_PASS")

# Жалоба на спам
_SPAM_COMPLAINT = re.compile(r"это\s+спам|spam|unsolicited", re.IGNORECASE)


def process_replies() -> int:
    if not all([IMAP_HOST, IMAP_USER, IMAP_PASS]):
        logger.error("IMAP_HOST / SMTP_USER / SMTP_PASS не заданы")
        return 0

    from granite.database import get_engine, CrmEmailLogRow, CrmContactRow, CrmTouchRow, CrmEmailCampaignRow
    from granite.api.helpers import cancel_followup_tasks
    from sqlalchemy.orm import Session

    engine = get_engine()
    processed = 0

    with imaplib.IMAP4_SSL(IMAP_HOST) as imap:
        imap.login(IMAP_USER, IMAP_PASS)
        imap.select("INBOX")

        _, uids = imap.search(
            None,
            '(UNSEEN NOT FROM "mailer-daemon" NOT FROM "mailer-daemon@googlemail.com")',
        )
        if not uids[0]:
            logger.info("Нет новых входящих писем")
            engine.dispose()
            return 0

        for uid in uids[0].split():
            _, data = imap.fetch(uid, "(RFC822)")
            if not data or not data[0]:
                continue
            raw = data[0][1]
            msg = email.message_from_bytes(raw)

            # Пропускаем bounce (обрабатываются в process_bounces.py)
            if is_bounce(msg):
                continue

            # Извлечь email отправителя
            from_header = msg.get("From", "")
            reply_email = extract_email(from_header)
            if not reply_email:
                continue

            # Извлечь тему и тело
            subject = msg.get("Subject", "")
            body_text = extract_body(msg)

            # Проверить OOO (автоответчик)
            if is_ooo(body_text or ""):
                imap.store(uid, "+FLAGS", "\\Seen")
                continue

            # Найти контакт по email
            with Session(engine) as session:
                log = (
                    session.query(CrmEmailLogRow)
                    .filter_by(email_to=reply_email)
                    .order_by(CrmEmailLogRow.sent_at.desc())
                    .first()
                )
                if not log:
                    continue

                contact = session.query(CrmContactRow).filter_by(
                    company_id=log.company_id
                ).first()
                if not contact:
                    continue

                if contact.funnel_stage in ("replied", "interested", "not_interested", "unreachable"):
                    continue

                # Проверить спам-жалобу
                if _SPAM_COMPLAINT.search(body_text or ""):
                    contact.stop_automation = True
                    contact.funnel_stage = "not_interested"
                    cancel_followup_tasks(contact.company_id, "not_interested", session)
                    session.commit()
                    imap.store(uid, "+FLAGS", "\\Seen")
                    continue

                # Реальный ответ
                contact.funnel_stage = "replied"
                contact.updated_at = datetime.now(timezone.utc)

                # Отменить pending follow-up задачи
                cancel_followup_tasks(contact.company_id, "replied", session)

                # Обновить статус лога
                log.status = "replied"
                log.replied_at = datetime.now(timezone.utc)

                # Инкремент счётчика ответов кампании
                if log.campaign_id:
                    campaign = session.query(CrmEmailCampaignRow).filter_by(id=log.campaign_id).first()
                    if campaign:
                        campaign.total_replied = (campaign.total_replied or 0) + 1

                session.add(CrmTouchRow(
                    company_id=contact.company_id,
                    channel="email",
                    direction="incoming",
                    subject=subject[:200] if subject else "(без темы)",
                    body=body_text[:2000] if body_text else "Ответ на email",  # унифицировано — body
                ))
                session.commit()

                processed += 1
                logger.info(f"Reply: {reply_email} → company #{contact.company_id} → replied")

            imap.store(uid, "+FLAGS", "\\Seen")

    engine.dispose()
    logger.info(f"Обработано reply: {processed}")
    return processed


if __name__ == "__main__":
    process_replies()
```

**Cron-запуск (опционально):** запускать каждые 15–30 минут в рабочее время, или вручную при проверке почты.

**Ограничения:**
- Не отличает «нет, не интересно» от «да, давайте обсудим» — оба переводят в `replied`. Дальнейшая квалификация — вручную
- Если человек пишет с другого email — не найдём. Это нормально для cold outreach
- Не парсит цепочки (thread) — только первое письмо в inbox

---

### Задача 10: Фронтенд — обновления

#### 10.1 Wizard создания кампании

```tsx
// Шаг — Шаблон + A/B
<FormField name="subject_a" label="Тема письма" required />

<Collapsible>
  <CollapsibleTrigger>
    + Добавить вариант темы B (A/B тест)
  </CollapsibleTrigger>
  <CollapsibleContent>
    <FormField name="subject_b" label="Тема B" />
    <p className="text-xs text-muted">
      Компании делятся 50/50 между A и B. Победитель — по количеству ответов.
    </p>
  </CollapsibleContent>
</Collapsible>
```

#### 10.2 Карточка кампании

```tsx
// Прогресс — поллинг SSE
<ProgressBar value={campaign.total_sent} max={campaign.total_recipients} />

// Причина паузы
{campaign.status === "paused_daily_limit" && (
  <Alert>Достигнут дневной лимит. Продолжите завтра.</Alert>
)}

// Уведомление о recovery после рестарта
{campaign.status === "paused" && campaign.was_running && (
  <Alert variant="warning">
    Кампания была остановлена (рестарт сервера). Нажмите «Продолжить» когда будете готовы.
  </Alert>
)}

// Предупреждения валидатора
{campaign.warnings?.length > 0 && (
  <Collapsible>
    <CollapsibleTrigger>
      Пропущено {campaign.warnings.length} получателей
    </CollapsibleTrigger>
    <CollapsibleContent>
      {campaign.warnings.map(w => (
        <div key={w.company_id}>{w.name}: {w.reason}</div>
      ))}
    </CollapsibleContent>
  </Collapsible>
)}
```

---

### Задача 11: Follow-up executor

```python
# scripts/process_followups.py

"""
Ищет созревшие follow-up задачи, отправляет follow-up письмо,
переводит задачу в completed.

Запуск:
  uv run python -m scripts.process_followups
  # или по cron каждые 30–60 минут
"""
import os
from datetime import datetime, timezone
from loguru import logger


def process_followups() -> int:
    from granite.database import (
        get_engine, CrmTaskRow, CrmContactRow,
        CrmCompanyRow, CrmTouchRow, CrmEmailLogRow,
    )
    from granite.email.sender import EmailSender
    from sqlalchemy.orm import Session

    engine = get_engine()
    sender = EmailSender()
    processed = 0

    with Session(engine) as session:
        # Найти все созревшие follow-up задачи
        tasks = (
            session.query(CrmTaskRow)
            .filter(
                CrmTaskRow.task_type == "follow_up",
                CrmTaskRow.status == "pending",
                CrmTaskRow.due_date <= datetime.now(timezone.utc),
            )
            .all()
        )

        for task in tasks:
            contact = session.query(CrmContactRow).filter_by(
                company_id=task.company_id
            ).first()

            # Пропустить если уже отписан или ответил
            if not contact or contact.stop_automation:
                task.status = "cancelled"
                task.completed_at = datetime.now(timezone.utc)
                continue

            if contact.funnel_stage in ("replied", "interested", "not_interested", "unreachable"):
                task.status = "cancelled"
                task.completed_at = datetime.now(timezone.utc)
                continue

            company = session.get(CrmCompanyRow, task.company_id)
            if not company or not contact.email:
                task.status = "cancelled"
                task.completed_at = datetime.now(timezone.utc)
                continue

            # Получить оригинальную тему из description
            original_subject = task.description or "подготовка фото под гравировку"
            followup_subject = f"Re: {original_subject}"

            # Рендер follow-up шаблона
            from granite.database import CrmTemplateRow
            template = session.query(CrmTemplateRow).filter_by(
                name="follow_up_email_v1"
            ).first()

            if not template:
                logger.error("Шаблон follow_up_email_v1 не найден в БД")
                engine.dispose()
                return processed

            city = company.city or ""
            render_kwargs = {
                "city": city,
                "original_subject": original_subject,
                "unsubscribe_url": f"{sender.base_url}/api/v1/unsubscribe/{contact.unsubscribe_token}",
            }

            rendered = template.render(**render_kwargs)

            # Отправка
            try:
                tracking_id = sender.send(
                    company_id=company.id,
                    email_to=contact.email,
                    subject=followup_subject,
                    body_text=rendered,
                    template_id=template.id,  # v13: template_id
                    db_session=session,
                )

                if tracking_id:
                    task.status = "completed"
                    task.completed_at = datetime.now(timezone.utc)

                    session.add(CrmTouchRow(
                        company_id=company.id,
                        channel="email",
                        direction="outgoing",
                        subject=followup_subject,
                        body=f"[follow-up] [tracking_id={tracking_id}]",
                    ))

                    if contact.funnel_stage == "email_opened":
                        contact.funnel_stage = "follow_up_sent"

                    processed += 1
                    logger.info(
                        f"Follow-up: {contact.email} → company #{company.id}"
                    )
                else:
                    task.status = "error"
                    logger.warning(f"Follow-up не отправлен: company #{company.id}")

            except Exception as e:
                logger.error(f"Ошибка follow-up company #{company.id}: {e}")
                task.status = "error"

            session.commit()

    engine.dispose()
    logger.info(f"Обработано follow-up: {processed}")
    return processed


if __name__ == "__main__":
    process_followups()
```

**Cron-запуск:** каждые 30–60 минут в рабочее время (МСК 09:00–19:00), или вручную.

**Зависимости:**
- Задача 1 (unsubscribe_token) — для `{unsubscribe_url}` в шаблоне
- Задача 5.1 (создание CrmTaskRow с `description=original_subject`)
- Задача 8 (SMTP_SSL) — для корректной отправки
- Шаблон `follow_up_email_v1` должен быть в БД

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
    "body": "Здравствуйте.\n\nИщу контакты мастерских в {city} и области, которым нужна\nкачественная ретушь портретов для гравировки на памятниках.\n\nБеру сложные случаи: старые фото, низкое разрешение,\nповреждённые снимки. Нейросети + ручная доработка.\nСрок — 12–24 часа, срочно — 3–6 часов. Цена — от 700 ₽.\n\nГотов сделать 1–2 пробных бесплатно — на ваших реальных\nисходниках, без обязательств.\n\nПримеры работ: https://retouchgrav.netlify.app\n\nАлександр\nTelegram: @ganjavagen\n\n---\nЕсли не актуально — ответьте «нет», больше не напишу.\nОтписаться: {unsubscribe_url}",
    "body_type": "plain",
    "description": "Холодное письмо — основной шаблон",
    "retired": false
  },
  {
    "id": 2,
    "name": "cold_email_marquiz",
    "channel": "email",
    "subject_a": "Подготовка фото под гравировку — могу разгрузить вас на ретуши",
    "subject_b": "Ретушь портретов для вашей мастерской — оплата после результата",
    "body": "Здравствуйте.\n\nИщу контакты мастерских в {city} и области, которым нужна\nкачественная ретушь портретных фото для гравировки на памятниках.\n\nБеру всё что сложно: старые снимки 80-х, фото на документах,\nгрупповые — когда нужно вырезать одного человека, низкое разрешение.\n\nНейросети + ручная доработка. 12–24 часа, срочно 3–6 часов.\nЦена — от 700 ₽, оплата после результата для новых клиентов.\n\nНачнём с бесплатной пробы: пришлите 1–2 ваших текущих исходника —\nпокажу результат.\n\nПримеры работ: https://retouchgrav.netlify.app\n\nАлександр\nTelegram: @ganjavagen\n\n---\nОтписаться: {unsubscribe_url}",
    "body_type": "plain",
    "description": "Холодное письмо — тёплая аудитория (Marquiz + TG)",
    "retired": false
  },
  {
    "id": 3,
    "name": "follow_up_email_v1",
    "channel": "email",
    "subject": "Re: {original_subject}",
    "body": "Добрый день.\n\nПисал на прошлой неделе про ретушь портретов.\n\nНе хочу надоедать — просто оставлю ссылку на примеры:\nhttps://retouchgrav.netlify.app\n\nПервый портрет бесплатно — пришлите в ответ любой сложный исходник.\n\nАлександр · @ganjavagen\n---\nОтписаться: {unsubscribe_url}",
    "body_type": "plain",
    "description": "Follow-up через 7 дней после открытия",
    "retired": false
  },
  {
    "id": 4,
    "name": "cold_email_bitrix",
    "channel": "email",
    "subject_a": "Аутсорс ретуши под гравировку — в день заказа",
    "subject_b": "Подготовка фото для гравировки на памятниках — без предоплаты",
    "body": "Здравствуйте.\n\nПредлагаю сотрудничество по ретуши портретов\nдля гравировки на памятниках.\n\nЧто делаю:\n— восстановление сложных исходников (старые, размытые, повреждённые)\n— ретушь под конкретный станок и технологию (лазер / ударный)\n— замена фона, одежды, монтаж, сборка в полный рост\n— срок в день обращения, оплата после одобрения результата\n\nДля партнёрских мастерских с постоянным потоком — индивидуальные\nусловия и выделенный приоритет.\n\nНачнём с бесплатной пробы: пришлите 1–2 реальных исходника —\nпокажу результат на вашем материале.\n\nПримеры работ: https://retouchgrav.netlify.app\n\nАлександр\nTelegram: @ganjavagen\n\n---\nОтписаться: {unsubscribe_url}",
    "body_type": "plain",
    "description": "Холодное письмо — формальный тон (Bitrix)",
    "retired": false
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
        exists = db.query(CrmTemplateRow).filter_by(id=t["id"]).first()
        if exists:
            logger.debug(f"Template #{t['id']} '{t['name']}' already exists — skip (immutable)")
            continue
        row = CrmTemplateRow(
            id=t["id"],
            name=t["name"],
            channel=t.get("channel", "email"),
            subject=t.get("subject_a", ""),
            body=t["body"],
            body_type=t.get("body_type", "plain"),
            description=t.get("description", ""),  # v13: description из JSON
        )
        db.add(row)
        added += 1

    db.commit()
    logger.info(f"Templates seeded: {added} new, {len(templates) - added} existing (skipped)")
```

#### 12.3 ORM изменения

```python
# Миграция: template_name → template_id + retired + description
class CrmEmailLogRow(Base):
    # ... существующие поля ...
    template_id = Column(Integer, ForeignKey("crm_templates.id"), nullable=True)
    # template_name оставляем для обратной совместимости, deprecated

class CrmTemplateRow(Base):
    # ... существующие поля ...
    retired = Column(Boolean, default=False)
    description = Column(String, nullable=True)  # v13: человекочитаемое описание
```

**Миграция для `description` и `retired`:**

```python
# alembic/versions/xxxx_add_description_retired_to_crm_templates.py

def upgrade():
    op.add_column("crm_templates", sa.Column("description", sa.String, nullable=True))
    op.add_column("crm_templates", sa.Column("retired", sa.Boolean, default=False))

def downgrade():
    op.drop_column("crm_templates", "retired")
    op.drop_column("crm_templates", "description")
```

---

### Задача 13: Bitrix-шаблон (опционально)

Если Волна 1 (Bitrix, 41 компания) будет идти отдельным шаблоном — создать `cold_email_bitrix` (см. 6.5). Если нет — используется `cold_email_v1` с темой-победителем.

Решение принимается после Фазы 0, когда станет ясен tone победившего шаблона.

---

### Задача 14: SEO-regex фиксы

Объединено с задачей 7. См. задачу 7 для деталей.

---

### Задача 15: Template name — разрешить кириллицу (включая заглавную)

**Проблема:** `schemas.py:88` — `pattern=r"^[a-z0-9_]+$"` запрещает кириллицу в имени шаблона. v12 добавил `\u0430-\u044f` (строчная), но забыл `\u0410-\u042f` (заглавная). Для русского рынка неприемлемо: шаблон `Холодное_письмо_v1` не может быть создан через API.

**Решение:**

```python
# granite/api/schemas.py

# До (v12):
name: str = Field(..., min_length=1, pattern=r"^[a-z0-9_\u0430-\u044f]+$")

# После (v13):
name: str = Field(..., min_length=1, max_length=64, pattern=r"^[a-z0-9_\u0410-\u042f\u0430-\u044f]+$")
# Разрешены: строчные латиница, цифры, подчёркивание, кириллица (строчные + ЗАГЛАВНЫЕ)
```

**Миграция `description` для CrmTemplateRow** — см. задачу 12.3.

---

### Задача 16: `.env.example` + стартовые проверки

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

# ── Отправка ──
FROM_NAME=Александр
EMAIL_DELAY_MIN=45
EMAIL_DELAY_MAX=120
EMAIL_DAILY_LIMIT=50

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

#### 16.3 SMTP health check

```python
# granite/api/app.py — /health endpoint

@app.get("/health")
def health():
    return {"status": "ok", "db": "ok"}

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

### Задача 17: Raw SQL — f-string → параметризованные (перенесено в Этап 2)

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

**Почему перенесено в Этап 2:** Быстрый рефакторинг (30 мин), затрагивает тот же файл `companies.py`, что и задача 4 (валидатор). Лучше сделать вместе, чем потом иметь merge-конфликты.

---

### Задача 18: Campaign recipients — батч-итерация с учётом SQLite

**Проблема:** `campaigns.py:134` — `rows = q.all()` загружает все компании в память. При 50K+ компаний — потенциальный OOM.

**Решение:** Заменить `.all()` на батч-итерацию.

```python
# Для PostgreSQL:
for company, enriched, contact in q.yield_per(100).execution_options(stream_results=True):
    # обработка записи

# Для SQLite (stream_results не поддерживается):
for company, enriched, contact in q.yield_per(100):
    # обработка записи

# Универсальный подход (try/except):
try:
    rows = q.yield_per(100).execution_options(stream_results=True)
except Exception:
    rows = q.yield_per(100)
```

> **Заметка:** Для текущих объёмов (~6000 компаний) `.all()` работает нормально. Этот рефакторинг — профилактика на будущее. Интегрируется в задачу 2.6.

---

### Задача 19: IMAP helpers module (НОВОЕ v13)

**Проблема:** `process_bounces.py` и `process_replies.py` содержат дублирующийся код для работы с IMAP: извлечение email из заголовка, тела письма, определение bounce/OOO. В v12 хелперы были сокращены с неопределёнными функциями (`_is_bounce()`, `_extract_sender()`, `_extract_body()`).

**Решение:** Вынести общие IMAP-функции в отдельный модуль `granite/email/imap_helpers.py`.

```python
# granite/email/imap_helpers.py

"""Общие IMAP-хелперы для process_bounces.py и process_replies.py."""

import email
import re
from email.header import decode_header


# ── Извлечение email из заголовков ──

def extract_email(header: str) -> str | None:
    """Извлечь email из заголовка From/To/Cc.
    
    Поддерживает форматы:
      "Иван Иванов <ivan@mail.ru>"
      "ivan@mail.ru"
    """
    if not header:
        return None
    # Сначала пробуем извлечь из угловых скобок
    match = re.search(r'<([\w._%+-]+@[\w.-]+\.\w+)>', header)
    if match:
        return match.group(1).lower()
    # Иначе ищем email напрямую
    match = re.search(r'([\w._%+-]+@[\w.-]+\.\w+)', header)
    if match:
        return match.group(1).lower()
    return None


# ── Извлечение тела письма ──

def extract_body(msg) -> str:
    """Извлечь текстовое тело письма (text/plain)."""
    for part in msg.walk():
        content_type = part.get_content_type()
        if content_type == "text/plain":
            payload = part.get_payload(decode=True)
            if payload:
                return payload.decode("utf-8", errors="ignore")
    # Если нет text/plain — попробовать text/html
    for part in msg.walk():
        content_type = part.get_content_type()
        if content_type == "text/html":
            payload = part.get_payload(decode=True)
            if payload:
                return payload.decode("utf-8", errors="ignore")
    return ""


# ── Определение bounce ──

# SMTP-коды hard bounce
_HARD_BOUNCE_CODES = re.compile(
    r"\b5[05][013]\b"  # 500, 501, 503, 550, 551, 553
)
_HARD_BOUNCE_PHRASES = [
    "user unknown",
    "no such user",
    "unknown user",
    "mailbox not found",
    "address rejected",
    "recipient invalid",
    "recipient not found",
    "no such recipient",
    "delivery status notification",
    "undelivered mail",
]

_BOUNCE_FROM_PATTERNS = re.compile(
    r"mailer-daemon|postmaster|mail delivery subsystem",
    re.IGNORECASE,
)


def is_bounce(msg) -> bool:
    """Определить, является ли письмо bounce-уведомлением."""
    from_header = msg.get("From", "").lower()
    subject = msg.get("Subject", "").lower()
    
    # Проверяем From
    if _BOUNCE_FROM_PATTERNS.search(from_header):
        return True
    
    # Проверяем Subject
    if any(phrase in subject for phrase in ("delivery status", "undelivered", "returned mail", "failure notice")):
        return True
    
    # Проверяем тело на DSN-коды
    text = msg.as_string().lower()
    if _HARD_BOUNCE_CODES.search(text):
        return True
    if any(phrase in text for phrase in _HARD_BOUNCE_PHRASES):
        return True
    
    return False


# ── Определение OOO (автоответчик) ──

_OOO_PATTERNS = re.compile(
    r"(?:автоответ|out of office|автоматическ|я в отпуске|vacation|"
    r"auto.?reply|автоматическое ответ|не могу ответить|буду отсутствовать|"
    r"я на больничном|временно недоступен)",
    re.IGNORECASE,
)


def is_ooo(body: str) -> bool:
    """Определить, является ли тело письма автоответчиком (Out of Office)."""
    if not body:
        return False
    return bool(_OOO_PATTERNS.search(body))


# ── Извлечение bounced email ──

def extract_bounced_email(msg) -> str | None:
    """Извлечь email получателя из bounce-уведомления.
    
    Ищет в:
    1. message/delivery-status части (Final-Recipient)
    2. text/plain части (regex fallback)
    """
    for part in msg.walk():
        if part.get_content_type() in ("message/delivery-status", "text/plain"):
            content = part.get_payload(decode=True)
            if content:
                text = content.decode("utf-8", errors="ignore")
                match = re.search(
                    r"Final-Recipient:.*?<?([\w._%+-]+@[\w.-]+\.\w+)>?", text
                )
                if match:
                    return match.group(1).lower()
    return None


# ── Извлечение DSN-кода ──

_DSN_PATTERN = re.compile(r"[45]\.\d+\.\d+")


def extract_dsn(msg) -> str | None:
    """Извлечь DSN (Delivery Status Notification) код из bounce-письма.
    
    Ищет в:
    1. message/delivery-status части (Diagnostic-Code)
    2. text/plain части (regex fallback)
    """
    for part in msg.walk():
        if part.get_content_type() in ("message/delivery-status", "text/plain"):
            content = part.get_payload(decode=True)
            if content:
                text = content.decode("utf-8", errors="ignore")
                # Ищем Diagnostic-Code
                match = re.search(r"Diagnostic-Code:\s*smtp;\s*([45]\.\d+\.\d+)", text)
                if match:
                    return match.group(1)
                # Fallback: ищем DSN-код напрямую
                match = _DSN_PATTERN.search(text)
                if match:
                    return match.group(0)
    return None
```

---

## 8. Roadmap по дням

### День 1 — Инфраструктура + критические фиксы (0 писем)

```
[ ] Задача 16: .env.example + стартовые проверки (15 мин)
[ ] Задача 8: фикс SMTP_SSL в sender.py (порт 465 + SMTP_SSL)
[ ] Задача 7/14: фикс SEO-regex (убрать «гранит» + убрать гранитн* мастерск* + починить памятник[аиы]?)
[ ] Обновить тесты: test_seo_name_extraction.py, test_merger.py
    (таблица тестовых пар — в задаче 7)
[ ] Запустить полный набор тестов
[ ] Gmail: 2FA + App Password
[ ] .env: SMTP + IMAP + BASE_URL
[ ] Тест: отправить письмо себе через sender.py (с портом 465)
[ ] Проверить заголовки: SPF pass, DKIM pass (google.com)
[ ] mail-tester.com: оценка ≥ 8/10
[ ] Задача 1: миграция unsubscribe_token, эндпоинт /unsubscribe/{token}
[ ] Задача 2.1: recovery в lifespan()
[ ] Задача 3.3: миграция total_opened, total_replied, total_errors
[ ] Задача 3.4: миграция ab_variant в crm_email_logs
[ ] granite/api/helpers.py: cancel_followup_tasks() (задача 5.2)
[ ] Настроить публичный URL (см. открытые вопросы)
[ ] Сквозной тест: отправить → открыть → tracking → отписаться
[ ] Перед запуском кампании всегда: curl {BASE_URL}/health → ok
```

### День 2 — Рефакторинг отправки + SQL + Фаза 0 старт (10 писем)

```
[ ] Задача 2.2–2.6: BackgroundTask + SSE-поллинг + батч-итерация + _run_campaign_background
[ ] Задача 18: yield_per вместо .all() (в рамках задачи 2)
[ ] Задача 4: validator.py (с дедупликацией email)
[ ] Задача 17: Raw SQL рефакторинг (30 мин, пока companies.py открыт)
[ ] Задача 3: total_errors + A/B-распределение + ab_variant tracking
[ ] Задача 3.4: A/B stats endpoint
[ ] Задача 15: Template name кириллица + description миграция
[ ] Создать кампанию: 10 получателей, сегмент A, тема A vs B
[ ] Запустить, проверить логи
[ ] Проверить что total_opened инкрементируется при открытии (tracking pixel)
```

### День 3–4 — Фаза 0, ещё 40 писем + IMAP helpers

```
[ ] 20 писем / день
[ ] Задача 19: IMAP helpers module (granite/email/imap_helpers.py)
[ ] Задача 5: follow-up при открытии + авто-отмена + счётчики
[ ] Задача 6: process_bounces.py (использует imap_helpers)
[ ] Задача 9: process_replies.py (использует imap_helpers)
[ ] Задача 11: process_followups.py
[ ] Мониторинг bounce rate
[ ] Проверить что total_replied инкрементируется при ответе
[ ] Проверить A/B stats endpoint: /campaigns/{id}/ab-stats
```

### День 5–6 — Пауза, мониторинг

```
[ ] 0 писем
[ ] Ответить всем кто написал
[ ] process_replies.py — обработать ответы
[ ] process_followups.py — проверить созревшие follow-up
[ ] Оценить тему A vs B (практический критерий из 6.4)
[ ] Задача 10: обновления фронтенда
[ ] Задача 12: ✅ Созданы docs/POST_REPLY_PLAYBOOK.md + docs/EMAIL_TEMPLATES.md
[ ] Задача 13: принять решение — нужен ли cold_email_bitrix для Волны 1
```

### День 7–9 — Волна 1: Marquiz + Bitrix

```
[ ] Проверить список Marquiz (22 компании) — убрать SEO-имена
[ ] Кампания Marquiz: cold_email_marquiz, 22 получателя
[ ] 30 писем / день
[ ] Кампания Bitrix: cold_email_v1 (победитель) или cold_email_bitrix (задача 13)
[ ] process_followups.py — запускать каждые 30–60 минут
```

### День 10+ — Волны 2–4, масштаб

```
[ ] 50 писем / день (рабочий режим)
[ ] Волна 2: остаток A (60–80 компаний)
[ ] Волна 3: сегмент B (259 компаний)
[ ] Follow-up через 7 дней (process_followups.py)
[ ] process_bounces.py — запускать каждые 2–3 дня
[ ] process_replies.py — запускать каждый день
```

---

## 9. Открытые вопросы

| Вопрос | Статус |
|--------|--------|
| **Публичный URL для tracking pixel и отписки** — Cloudflare Tunnel или альтернатива | ⬜ Решается отдельно. До решения tracking не работает, но отправлять можно — просто без метрик открытий и без рабочей ссылки отписки |
| **Тексты писем** | ⬜ Отдельная задача |
| **Телефон в подписи** — где нужен, заменить на российский номер | ⬜ Отдельно по мере необходимости |
| **`_get_campaign_recipients()` — точная структура фильтрации** | ✅ Уточнено по текущей ORM. См. задачу 2.6 |
| Rate limiting на API-эндпоинты (slowapi / in-memory) | LOW — после запуска Волны 1 |
| DNS rebinding защита в `is_safe_url()` | DEFER — внутренний инструмент |
| `q.count()` + `q.offset().limit()` race condition в `list_companies` | LOW — SQLite WAL |
| `company_ids` колонка в `CrmEmailCampaignRow` | ⬜ Рекомендация: добавить `Column(JSON, default=list)` — явный список удобнее динамической фильтрации |

### MAX_PER_DOMAIN

v2/v3 имели `MAX_PER_DOMAIN=2` — максимум 2 письма на один домен-получатель за сутки (не на адрес, а на домен: @yandex.ru, @mail.ru). Идея: не бомбить один почтовый провайдер. При текущих объёмах (50/день, 434 получателя с разными доменами) это избыточно. Если в будущем объёмы вырастут — можно вернуть через env-переменную.

---

## 10. Changelog

| Версия | Дата | Изменения |
|--------|------|-----------|
| v13 | 2026-04-27 | 4 баг-фикса (SEO-regex ×2, template name, yield_per/SQLite), возврат кода из v11 (background sender, SSE, full process_bounces/replies, historical blocks), задача 19 (IMAP helpers), раздел «Принятые решения», задача 17 → Этап 2, миграция description |
| v12 | 2026-04-27 | Верификация аудита + 4 новых задачи (15–18) + 6 уточнений |
| v11 | 2026-04-26 | 6 фиксов + 4 дополнения (post-reply playbook, географический фильтр убран, immutable шаблоны) |
| v10 | — | Убран телефон, cancel_followup при reply, BackgroundTask заметка |
| v9 | — | SMTP_SSL, SEO-regex негативный lookahead, IMAP reply parser, commit после каждого письма |
| v8 | — | «Гранит» убран из SEO-regex |
| v7 | — | Gmail App Password вместо своего домена, SQLite-совместимость |
| v6 | — | Базовая архитектура |

---

<details>
<summary>Разница v11 → v12 (для справки)</summary>

### Новые задачи (из аудита, верифицированные против кода)

| # | Задача | Откуда | Этап | Почему |
|---|--------|--------|------|--------|
| 15 | Template name pattern: `^[a-z0-9_]+$` → разрешить кириллицу | Аудит #6, верифицировано | 2 | `schemas.py:88` запрещает кириллицу в имени шаблона — неприемлемо для русского рынка |
| 16 | Создать `.env.example` с описанием всех переменных | Аудит #9, верифицировано | 1 | Нет `.env.example`, нет проверки обязательных переменных при старте |
| 17 | Рефакторинг f-string в raw SQL → параметризованные `:param` | Аудит #2, верифицировано | 4 | `companies.py` интерполирует значения в SQL через f-string — антипаттерн |
| 18 | `_get_campaign_recipients`: заменить `.all()` на курсор/батч | Аудит #6 + #8, верифицировано | 2 | `campaigns.py:134` загружает ВСЕ компании в память — при 50K+ OOM risk |

### Уточнения к существующим задачам

| Задача | Уточнение | Источник |
|--------|-----------|----------|
| 1 (Unsubscribe) | Auth bypass для `/api/v1/track/` **уже частично реализован** в коде (строки 280–309 `app.py`) | Верификация |
| 6 (Bounce parser) | `process_bounces.py` **уже использует** `get_engine()` из app | Верификация |
| 8 (SMTP_SSL) | Подтверждено: `sender.py:136-138` использует `SMTP+starttls()` с портом 587 | Верификация |
| 12 (Immutable шаблоны) | Подтверждено: `CrmEmailLogRow.template_name` (String), `CrmTemplateRow` не имеет `retired` | Верификация |
| 4 (Валидатор) | Агрегаторы из scraper-audit (A-1: SKIP_DOMAINS) — предпосылка для валидатора | Scraper-audit |
| 7 (SEO-regex) | Scraper-audit A-7: расширение `is_seo_title()` + `is_aggregator_name()` | Scraper-audit |

### SEO-regex баг в v12

v12 добавил `гранитн[ые]+\s+мастерск` в SEO-regex, что противоречит тесту `test_granit_not_seo()` и решению из v7/v11 что «Гранит» в названиях — норма для ниши. Исправлено в v13.

v12 также добавил избыточный lookahead `(?=из|в|на|от|и)` в паттерн `памятник[аиы]?`, который дублировал следующий за ним `(?:из|в|на|от|и)`. Исправлено в v13 возвратом к v11-версии.

</details>

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

### Дополнения v11

| # | Добавление | Описание |
|---|-----------|----------|
| 7 | Post-reply playbook + Email-шаблоны | Задача 12: два документа |
| 8 | Географический фильтр убран | `.by`/`.kz` — нет причины блокировать |
| 9 | Возврат мелочей из v2–v4 | `EMAIL_SESSION_GAP_HRS`, дедуп email, A/B stats, Bitrix-шаблон |
| 10 | MAX_PER_DOMAIN не нужен | 50/день, разнообразие адресов |
| 11 | Шаблоны: immutable ID + JSON source of truth | `CrmEmailLogRow.template_id`, `CrmTemplateRow.retired` |

</details>

<details>
<summary>Разница v9 → v10 (для справки)</summary>

| В v9 | В v10 | Почему |
|------|-------|--------|
| Телефон в подписи писем: `WhatsApp: +84 946 943 543` | ✅ Убран из всех шаблонов | Телефон светить минимально |
| `process_replies.py` напрямую меняет `funnel_stage`, не вызывая логику отмены follow-up | ✅ Добавлен вызов `cancel_followup_tasks()` после перевода в `replied` | Без этого авто-отмена follow-up задач не срабатывает |
| BackgroundTask теряется при перезапуске сервера | ✅ Добавлена явная заметка для оператора | После рестарта кампания → `paused` |
| Cloudflare Tunnel — единственный вариант | ⬜ Вынесено в открытые вопросы | Решается отдельно |

</details>

<details>
<summary>Разница v8 → v9 (для справки)</summary>

| В v8 | В v9 | Почему |
|------|-------|--------|
| `smtplib.SMTP` + `starttls()` для порта 465 | ✅ `smtplib.SMTP_SSL` для 465 | Порту 465 нужен implicit TLS |
| `памятник[аиы]?\s*(?:из\|в\|на\|от\|и)?\s*` флагает «Гранит-Мастер ООО Памятники» | ✅ Паттерн переписан | Предлог обязателен + слово после |
| Нет механизма обнаружения ответов | ✅ Добавлен IMAP reply parser | Воронка упоминает `replied`, но некому перевести |
| `process_bounces.py` создаёт `Database()` напрямую | ✅ Использует `get_engine()` из app | Разные пути к БД — риск |
| Background task: commit каждые 10 писем | ✅ Commit после каждого письма | При краше теряются данные |

</details>

<details>
<summary>Разница v7 → v8 (для справки)</summary>

| В v7 | В v8 | Почему |
|------|-------|--------|
| SEO-regex содержит «гранит» в 4 паттернах | ✅ Убрано | «Гранит» в названии — норма для ниши |

</details>

<details>
<summary>Разница v6 → v7 (для справки)</summary>

| В v6 | В v7 | Почему |
|------|-------|--------|
| SPF/DKIM/DMARC настраиваются на своём домене | ❌ Убрано — отправка через Gmail | Google управляет SPF/DKIM/DMARC для gmail.com |
| DKIM-подпись в sender.py | ❌ Убрано | Невозможно через Gmail SMTP |
| Заголовки List-Unsubscribe | ❌ Убрано | Gmail фильтрует произвольные заголовки |
| `SELECT FOR UPDATE` | ❌ Исправлено | SQLite не поддерживает |
| Recovery через `on_event` | ❌ Исправлено | Депрекейтнут, используем `lifespan()` |
| A/B тест: «≥ 3% + 50%» | ⚠️ Упрощено | На 25/25 — шум, не статистика |
| Авто-resume при `paused_daily_limit` | ❌ Не нужен | Ручной перезапуск — нормально |
| `{company_name}` убрано | ✅ Добавлен `{city}` | Персонализация без SEO-мусора |
| Bounce: паттерн `"550"` | ❌ Исправлено | Ложные срабатывания, теперь regex по SMTP-кодам |
| Валидатор email | ✅ Добавлено | Минимальная проверка формата |
| GET /unsubscribe отписывает | ⚠️ Добавлена защита | Префетч почтовых клиентов |

</details>

---

## Приложение: переменные окружения

```bash
# .env

# SMTP (Gmail)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=465                        # SMTP_SSL (implicit TLS)
SMTP_USER=ai.punk.facility@gmail.com
SMTP_PASS=xxxx xxxx xxxx xxxx    # App Password (16 символов)

# Отправка
FROM_NAME=Александр
BASE_URL=https://crm.yourdomain.com   # публичный URL (решается отдельно)
EMAIL_DELAY_MIN=45
EMAIL_DELAY_MAX=120
EMAIL_DAILY_LIMIT=50
EMAIL_SESSION_GAP_HRS=2              # минимальный интервал между сессиями отправки (часы)

# IMAP (для bounce + reply, Gmail)
IMAP_HOST=imap.gmail.com

# CRM
GRANITE_API_KEY=             # опционально
```

---

## Приложение: сводка фиксов v12 → v13

| # | Баг v12 | Фикс v13 | Где |
|---|---------|----------|-----|
| 1 | `гранитн[ые]+\s+мастерск` флагает «Гранитные мастерские» как SEO | Убран из паттерна полностью | Задача 7 |
| 2 | `памятник[аиы]?` lookahead + дублирование предлогов | Возвращена v11-версия: предлог обязателен + `\S` после | Задача 7 |
| 3 | Template name regex не разрешает заглавную кириллицу | Добавлен `\u0410-\u042f` | Задача 15 |
| 4 | `yield_per(100)` без `stream_results=True` для SQLite | try/except с fallback | Задача 18 |
| 5 | `_run_campaign_background` — только скелет | Полный код из v11 с `template_id` | Задача 2.3 |
| 6 | SSE-прогресс эндпоинт отсутствует | Восстановлен из v11 | Задача 2.4 |
| 7 | Исторические `<details>` блоки урезаны | Восстановлены v6→v7, v7→v8, v8→v9, v9→v10 | Конец документа |
| 8 | `process_bounces.py` / `process_replies.py` — неопределённые хелперы | Полный код + `imap_helpers.py` (задача 19) | Задачи 6, 9, 19 |
| 9 | Нет раздела «Принятые решения» | Новый раздел 2 | Раздел 2 |
| 10 | Нет задачи 19 (IMAP helpers) | Новая задача в Этапе 3 | Задача 19 |
| 11 | Задача 17 в Этапе 4 → merge-конфликты с задачей 4 | Перенесена в Этап 2 | Этапы |
| 12 | Нет миграции `description` для CrmTemplateRow | Явная миграция добавлена | Задача 12.3 |
| 13 | SEO-regex тест-кейсы не согласованы | «Гранитные мастерские» → `needs_review=False` | Задача 7 |
