# RetouchGrav — Email Campaign Dev Plan v11

> Александр · @ganjavagen  
> База: ~6 000 компаний → **434 приоритетных цели** (A+B, не-сеть, валидный email)  
> SMTP: ai.punk.facility@gmail.com (личный аккаунт, App Password)  
> v11 · 2026-04-26 · v10 + 6 фиксов + 4 дополнения: post-reply playbook, возврат мелочей из ранних версий, географический фильтр убран, MAX_PER_DOMAIN объяснён и не нужен

---

## Содержание

1. [Что изменилось относительно v10](#1-что-изменилось-относительно-v10)
2. [Стратегия и волны](#2-стратегия-и-волны)
3. [Прогрев домена](#3-прогрев-домена)
4. [Шаблоны писем](#4-шаблоны-писем)
5. [Технический план — этапы реализации](#5-технический-план--этапы-реализации)
6. [Roadmap по дням](#6-roadmap-по-дням)
7. [Открытые вопросы](#7-открытые-вопросы)

---

## 1. Что изменилось относительно v10

| # | В v10 (баг) | В v11 (фикс) | Почему |
|---|-------------|--------------|--------|
| 1 | `total_opened` / `total_replied` никогда не обновляются — SSE всегда показывает 0 | ✅ Инкремент в tracking.py и process_replies.py | Оператор не видит метрик без этих счётчиков |
| 2 | Отписка не вызывает `cancel_followup_tasks()` — follow-up приходит после отписки | ✅ Вызов `cancel_followup_tasks()` в `unsubscribe_confirm()` | Отписка = никаких писем, включая запланированные follow-up |
| 3 | Follow-up задача создаётся (5.1), отменяется (5.2), но **никогда не отправляется** — нет механизма исполнения | ✅ Добавлен `scripts/process_followups.py` (задача 11) | Архитектурная дыра: без исполнителя follow-up мёртвый код |
| 4 | `_get_campaign_recipients()` вызывается, но не определена | ✅ Добавлена реализация (задача 2.4) | Без неё непонятно: кому отправлять, как избежать дублей при resume |
| 5 | `CrmTouchRow`: отписка пишет `note=`, reply пишет `body=` — два разных поля | ✅ Унифицировано: везде `body=` | Один и тот же ORM-объект, несовместимые поля = runtime error |
| 6 | Auth bypass только для `/unsubscribe/`, но `/track/open/` тоже вызывается без API-ключа | ✅ Добавлен bypass для `/api/v1/track/` | Почтовые клиенты не отправляют заголовки авторизации |

### Дополнения v11 (по итогам ревью)

| # | Добавление | Описание |
|---|-----------|----------|
| 7 | Post-reply playbook + Email-шаблоны (2 документа) | Задача 12: `docs/POST_REPLY_PLAYBOOK.md` (сценарии, фильтрация, статистика, инструкции) + `docs/EMAIL_TEMPLATES.md` (тексты 10 шаблонов: cold/follow-up/post-reply + A/B темы). ИИ-агент заполняет, Александр редактирует. Интеграция: `seed-templates` → `crm_templates` → кампании/post-reply |
| 8 | Географический фильтр убран | v2–v4 фильтровали `.by` / `.kz` — писем в Беларусь и Казахстан нет причин блокировать. В валидаторе добавлен явный комментарий |
| 9 | Возврат мелочей из v2–v4 | `EMAIL_SESSION_GAP_HRS`, дедупликация email, A/B stats endpoint, Bitrix-шаблон, mail-tester.com, признаки блокировки Gmail |
| 10 | MAX_PER_DOMAIN объяснён и не нужен | v2/v3 имели `MAX_PER_DOMAIN=2` (макс писем на один домен-получатель/сутки). При 50/день и разнообразии адресов — избыточно. Не возвращаем |
| 11 | Шаблоны: immutable ID + JSON source of truth | Шаблоны хранятся в `data/email_templates.json` с уникальными ID. Правило: **никогда не редактировать существующий шаблон** — только создавать новый с новым ID. Старые шаблоны помечаются `retired: true`. Это даёт честную статистику: каждый `template_id` в логах привязан к конкретному тексту. ORM: `CrmEmailLogRow.template_id` (Integer) вместо `template_name` (String). `crm_templates` — operational cache, seed из JSON при старте |

<details>
<summary>Дополнительные фиксы v11 (мелкие)</summary>

| Мелкий фикс | Описание |
|-------------|----------|
| `cancel_followup_tasks` → публичная функция | `_`-префикс убран, функция нужна в 3 модулях — вынесена в `granite/api/helpers.py` |
| Follow-up тема привязана к A/B победителю | `CrmTaskRow.description` сохраняет оригинальную тему; `process_followups.py` использует `Re: {subject}` |
| `total_opened` / `total_replied` колонки | Добавлены в ORM + миграция (задача 3.3) |

</details>

<details>
<summary>Разница v9 → v10 (для справки)</summary>

| В v9 | В v10 | Почему |
|------|-------|--------|
| Телефон в подписи писем: `WhatsApp: +84 946 943 543` | ✅ Убран из всех шаблонов | Телефон светить минимально; где нужен — заменить на российский номер отдельно |
| `process_replies.py` напрямую меняет `funnel_stage`, не вызывая логику отмены follow-up | ✅ Добавлен вызов `cancel_followup_tasks()` после перевода в `replied` | Без этого авто-отмена follow-up задач из задачи 5.2 не срабатывает при обнаружении ответа |
| BackgroundTask теряется при перезапуске сервера (поведение не задокументировано) | ✅ Добавлена явная заметка для оператора | После каждого рестарта сервера кампания переходит в `paused` — нужно вручную нажать «Продолжить» |
| Cloudflare Tunnel — единственный вариант для публичного URL | ⬜ Вынесено в открытые вопросы | Решается отдельно |

</details>

<details>
<summary>Разница v8 → v9 (для справки)</summary>

| В v8 | В v9 | Почему |
|------|-------|--------|
| `smtplib.SMTP` + `starttls()` для порта 465 | ✅ `smtplib.SMTP_SSL` для 465 | Порту 465 нужен implicit TLS (`SMTP_SSL`), а не STARTTLS |
| `памятник[аиы]?\s*(?:из\|в\|на\|от\|и)?\s*` флагает «Гранит-Мастер ООО Памятники» | ✅ Паттерн переписан | Добавлен негативный lookahead: совпадение только если после «памятник[аиы]?» идёт SEO-слово |
| Нет механизма обнаружения ответов | ✅ Добавлен IMAP reply parser | Воронка упоминает `replied`, но некому перевести в этот статус |
| `process_bounces.py` создаёт `Database()` напрямую | ✅ Использует `get_engine()` из app | Разные пути к БД — риск записать не в ту базу |
| Background task: commit каждые 10 писем | ✅ Commit после каждого письма | При краше между 10-ками теряются данные об отправке |

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
| Bounce: паттерн `"550"` | ❌ Исправлено | Ложные срабатывания, теперь regex по SMTP-кодов |
| Валидатор email | ✅ Добавлено | Минимальная проверка формата |
| GET /unsubscribe отписывает | ⚠️ Добавлена защита | Префетч почтовых клиентов |

</details>

---

## 2. Стратегия и волны

### 2.1 Реальное состояние базы

```
Всего в базе:                           ~6 000 компаний
Обработанные города:                    29 из 46
Сегмент A, не-сеть, валидный email:     175
Сегмент B, не-сеть, валидный email:     259
────────────────────────────────────────────────────────
Приоритетная база:                      434 компании
Крупные сети (ручная работа):           8 компаний
```

### 2.2 Волны

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

## 3. Прогрев домена

### 3.1 Обязательный чеклист до первой отправки

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

### 3.2 График прогрева (первые 10 дней)

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

### 3.3 Метрики здоровья

| Метрика | Норма | Стоп-сигнал |
|---------|-------|-------------|
| Bounce rate (hard) | < 2% | ≥ 5% → стоп |
| Spam complaints | < 0.1% | ≥ 0.5% → стоп |
| Open rate (mail.ru/Яндекс) | 10–20% | < 5% → проверить что Gmail не в спаме |
| Reply rate | цель ≥ 3% | < 1% → пересмотреть шаблон |

### 3.4 Признаки блокировки Gmail

| Симптом | Что делать |
|---------|-----------|
| Письма уходят в «Промоакции» | Норма — не блокировка |
| SMTP ошибка 421 / 550 | Снизить объём на 50% на 3 дня |
| Письма вообще не уходят | Проверить App Password, SMTP-настройки |
| Bounce rate ≥ 5% | Стоп кампании, разбор базы |

---

## 4. Шаблоны писем

### 4.1 `cold_email_v1` — основной (Фаза 0, Волны 2–4)

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

### 4.2 `cold_email_marquiz` — для Marquiz + TG (Волна 1)

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

### 4.3 `follow_up_email_v1` — follow-up (только email, через 7 дней)

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

### 4.4 Критерий выбора победителя A/B

**Реальность:** при 25/25 писем на каждую тему статистическая значимость минимальна. 1 ответ = 4% — это шум.

**Практический критерий:**

- Если одна тема набрала **≥ 2 ответа**, а другая **0** — используем первую
- Если обе темы дали **0 ответов** за 5 дней — проблема в теле письма или домене, не в теме. Пересматриваем письмо, не запускаем волны
- Если обе дали **1 ответ** — **ничья**, используем тему A (по умолчанию)

Никаких процентов и «превышение на 50%» на выборке из 25 — это иллюзия точности.

### 4.5 `cold_email_bitrix` — для Bitrix CMS (Волна 1, опционально)

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

## 5. Технический план

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

### Что нужно реализовать

---

## 5.0 Этапы реализации + TDD

Все 14 задач разбиты на 4 этапа. Каждый этап — законченный кусок работы, который можно протестировать и задеплоить независимо. TDD: сначала тест, потом код.

### Этап 1: Фундамент — критические фиксы + инфраструктура (0 писем)

**Цель:** починить то, что сломано, и подготовить инфраструктуру для первой отправки. После этого этапа CRM способна отправить тестовое письмо и обработать отписку.

**Принцип TDD:** для каждого фикса сначала пишем тест, который воспроизводит баг, потом фиксим.

| Задача | Что делаем | Тесты (сначала!) |
|--------|-----------|-----------------|
| **8. SMTP_SSL** | `sender.py`: порт 465 → `SMTP_SSL`, 587 → `SMTP+STARTTLS` | `test_sender_port_465_uses_smtp_ssl()` — мок `smtplib.SMTP_SSL`, проверяем что вызывается с портом 465. `test_sender_port_587_uses_starttls()` — мок `smtplib.SMTP`, проверяем `starttls()` вызван |
| **7. SEO-regex** | Убрать 4×«гранит» из `_SEO_TITLE_PATTERN`, починить `памятник[аиы]?` негативным lookahead | `test_granit_not_seo()` — «Гранит-Мастер», «Гранитные мастерские» → `needs_review=False`. `test_pamiatniki_in_company_name_not_seo()` — «Гранит-Мастер ООО Памятники» → `needs_review=False`. `test_real_seo_still_detected()` — «памятники из гранита купить москва» → `needs_review=True` |
| **14. SEO-regex** (дублирует 7) | То же что 7 — вынести в одну задачу | Объединить с задачей 7 |
| **1. Unsubscribe** | `unsubscribe_token` в `CrmContactRow` + эндпоинт + `cancel_followup_tasks()` | `test_unsubscribe_token_unique()` — 100 контактов, все токены уникальны. `test_unsubscribe_sets_stop_automation()` — GET `/unsubscribe?token=X` → `stop_automation=1`. `test_unsubscribe_cancels_followup()` — если есть pending follow-up задача → `status="cancelled"`. `test_unsubscribe_twice_idempotent()` — повторный клик не падает |
| **6. Auth bypass** | `/track/open/` + `/api/v1/track/` в whitelist middleware | `test_tracking_pixel_no_auth()` — GET `/api/v1/track/open/XXX.png` без API-ключа → 200, не 401 |

**Порядок реализации (этап 1):**
1. Написать все тесты для задач 7/14, 8, 1, 6 (красные)
2. Задача 8: SMTP_SSL фикс → тесты зелёные
3. Задача 7/14: SEO-regex → тесты зелёные
4. Задача 1: Unsubscribe (миграция + API + cancel_followup) → тесты зелёные
5. Задача 6: Auth bypass → тесты зелёные
6. `uv run pytest tests/ -v` — всё зелёное
7. Ручной тест: отправить 1 письмо себе → проверить отписку → проверить tracking pixel

**Зависимости:** нет — можно начинать сразу

---

### Этап 2: Отправка + валидация + A/B (первые 10 тестовых писем)

**Цель:** CRM может создавать кампанию с A/B тестом, валидировать получателей, отправлять и восстанавливаться после краша. После этого этапа можно запустить первую тестовую кампанию на 5-10 своих адресов.

**Принцип TDD:** для каждого эндпоинта и каждой функции — тест с моками SMTP/IMAP.

| Задача | Что делаем | Тесты (сначала!) |
|--------|-----------|-----------------|
| **2. Recovery + отправка** | `lifespan()`: running→paused. `_get_campaign_recipients()`: фильтр + дедуп. `sender.py`: commit после каждого письма (не batch) | `test_recovery_running_to_paused()` — создать кампанию status=running, запустить lifespan → status=paused. `test_campaign_recipients_dedup()` — два письма одному contact → только 1 получатель. `test_campaign_recipients_filter_stop_automation()` — contact с `stop_automation=1` не в списке. `test_commit_per_email()` — мок БД, после каждого `send()` → `commit()` вызван |
| **4. Валидатор** | `validate_recipients()`: агрегаторы, невалидные email, дедуп, `EMAIL_SESSION_GAP_HRS`, признаки блокировки Gmail | `test_aggregator_filtered()` — `memorial.ru` → отфильтрован. `test_invalid_email_filtered()` — `test@` → отфильтрован. `test_duplicate_email_deduped()` — две компании с одним email → 1 получатель. `test_session_gap()` — письмо 30 мин назад → отфильтрован. `test_gmail_block_signs()` — 5 bounced @gmail.com → домен помечен |
| **3. A/B + счётчики** | `determine_ab_variant()`: детерминированное распределение по company_id. `total_errors`, `ab_variant` в логах. A/B stats endpoint | `test_ab_deterministic()` — `determine_ab_variant(company_id=42)` всегда одинаковый результат. `test_ab_50_50_split()` — 100 компаний → ~50/50. `test_total_errors_increment()` — ошибка отправки → `total_errors+1`. `test_ab_variant_in_log()` — письмо → `CrmEmailLogRow.ab_variant` = "A" или "B". `test_ab_stats_endpoint()` — GET `/campaigns/1/ab-stats` → `{A: {...}, B: {...}}` |
| **12 (impl). Immutable шаблоны** | `data/email_templates.json` с ID. `seed-templates`: INSERT-only. `CrmEmailLogRow.template_id`. `CrmTemplateRow.retired`. Миграция | `test_seed_inserts_new()` — пустая БД → 10 шаблонов. `test_seed_skips_existing()` — повторный seed → 0 новых. `test_template_id_in_log()` — отправка → `template_id=1`. `test_retired_not_in_campaign_list()` — GET `/templates` → `retired=true` не показывается. `test_immutable_no_update()` — изменить JSON, seed → существующий шаблон НЕ обновился |

**Порядок реализации (этап 2):**
1. Написать все тесты (красные)
2. Задача 2: Recovery + отправка → тесты зелёные
3. Задача 4: Валидатор → тесты зелёные
4. Задача 3: A/B + счётчики → тесты зелёные
5. Задача 12 impl: Immutable шаблоны → тесты зелёные
6. Интеграционный тест: создать кампанию → A/B → валидация → отправка 5 писем себе → проверить логи
7. `uv run pytest tests/ -v` — всё зелёное

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
| 1 | 1, 6, 7/14, 8 | CRM может отправить 1 письмо + отписка + tracking | Сразу после завершения |
| 2 | 2, 3, 4, 12(impl) | CRM может создать кампанию с A/B + валидация | 1-2 дня после этапа 1 |
| 3 | 5, 6, 9, 11 | CRM обрабатывает bounce/reply/follow-up автоматически | 2-3 дня после этапа 2 |
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

**Auth bypass** — в `api_key_auth_middleware` добавить:
```python
# Отписка и tracking доступны без API-ключа (клики из email / пиксели)
or request.url.path.startswith("/api/v1/unsubscribe/")
or request.url.path.startswith("/api/v1/track/")
```

#### 1.4 Плейсхолдер `{unsubscribe_url}` в sender.py

```python
# В методе send() — перед рендером шаблона:
if contact:
    unsubscribe_url = f"{self.base_url}/api/v1/unsubscribe/{contact.unsubscribe_token}"
else:
    unsubscribe_url = ""
render_kwargs["unsubscribe_url"] = unsubscribe_url
```

`CrmTemplateRow.render()` уже поддерживает произвольные плейсхолдеры — достаточно передать `unsubscribe_url` в kwargs.

---

### Задача 2: Recovery + архитектура отправки

#### 2.1 Recovery при старте сервера

Добавить в `lifespan()` в `app.py` — **не** через `on_event` (депрекейтнут):

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # ... существующая инициализация ...

    # RECOVERY: при рестарте вернуть running → paused
    with db.session_scope() as session:
        stuck = session.query(CrmEmailCampaignRow).filter_by(status="running").all()
        for campaign in stuck:
            campaign.status = "paused"
            logger.warning(
                f"RECOVERY: кампания {campaign.id} '{campaign.name}' "
                f"переведена из running → paused (рестарт сервера)"
            )
        if stuck:
            logger.info(f"RECOVERY: восстановлено {len(stuck)} кампаний")

    yield
    # ... существующая очистка ...
```

> **Заметка для оператора:** BackgroundTask живёт в памяти процесса. При любом перезапуске сервера (ошибка, `--reload`, ручной рестарт) задача теряется, кампания переходит в `paused`. Это ожидаемое поведение — нужно вручную нажать «Продолжить» в UI.

#### 2.2 Рефакторинг: BackgroundTask + SSE-поллинг

**Проблема текущей архитектуры:** отправка происходит внутри SSE-генератора. Если клиент закрывает вкладку — SSE-соединение рвётся, отправка останавливается через `GeneratorExit`. Это работает, но хрупко: при проблемах с сетью на клиенте кампания зависает.

**Решение:** отделить отправку (BackgroundTask) от прогресса (SSE-поллинг БД).

**Новый endpoint запуска:**

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

**Фоновая задача отправки:**

```python
def _run_campaign_background(campaign_id: int, SessionFactory) -> None:
    """Фоновая отправка писем. Создаёт свою сессию БД."""
    import time, random
    from granite.email.sender import EmailSender
    from granite.email.validator import validate_recipients

    EMAIL_DELAY_MIN = int(os.environ.get("EMAIL_DELAY_MIN", "45"))
    EMAIL_DELAY_MAX = int(os.environ.get("EMAIL_DELAY_MAX", "120"))
    EMAIL_DAILY_LIMIT = int(os.environ.get("EMAIL_DAILY_LIMIT", "50"))
    EMAIL_SESSION_GAP_HRS = int(os.environ.get("EMAIL_SESSION_GAP_HRS", "2"))

    session = SessionFactory()
    sender = EmailSender()

    try:
        campaign = session.get(CrmEmailCampaignRow, campaign_id)
        if not campaign or campaign.status != "running":
            return

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
                        template_name=template.name, db_session=session,
                        campaign_id=campaign.id,
                        ab_variant=ab_variant,
                    )
                else:
                    tracking_id = sender.send(
                        company_id=company.id, email_to=email_to,
                        subject=subject, body_text=rendered,
                        template_name=template.name, db_session=session,
                        campaign_id=campaign.id,
                        ab_variant=ab_variant,
                    )

                if tracking_id:
                    sent += 1
                    campaign.total_sent = sent
                    session.add(CrmTouchRow(
                        company_id=company.id, channel="email",
                        direction="outgoing", subject=subject,
                        body=f"[tracking_id={tracking_id}] [subject={subject}] [ab={ab_variant}]",  # v11: сохраняем тему и вариант для follow-up
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

**SSE-поллинг прогресса (читает только БД):**

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

#### 2.3 Статус `paused_daily_limit`

Кампания переходит в `paused_daily_limit` при достижении дневного лимита. Ручной перезапуск на следующий день — достаточно. В UI: показать причину паузы и кнопку «Продолжить».

Статус `paused_daily_limit` входит в группу `paused`-подобных — разрешён перезапуск:

```python
if campaign.status not in ("draft", "paused", "paused_daily_limit"):
    raise HTTPException(400, "Кампания не может быть запущена")
```

#### 2.4 `_get_campaign_recipients()` — v11: реализация добавлена

Функция определяет список получателей для кампании и **фильтрует уже отправленных** (чтобы при resume не было дублей).

```python
# granite/api/campaigns.py (или отдельный модуль)

from sqlalchemy.orm import Session
from granite.database import (
    CrmEmailCampaignRow, CrmCompanyRow, CrmContactRow,
    CrmEnrichedDataRow, CrmEmailLogRow,
)


def _get_campaign_recipients(
    campaign: CrmEmailCampaignRow,
    session: Session,
) -> list[tuple]:
    """Возвращает [(company, enriched, contact, email_to), ...].

    Фильтрует:
    - Уже отправленных в этой кампании (по CrmEmailLogRow)
    - Компании без валидного email
    """
    # Получить все компании-получатели кампании
    # (фильтрация по сегменту/аудитории зависит от того,
    #  как кампания хранит свою аудиторию)
    #
    # Если кампания хранит список company_id:
    if campaign.company_ids:
        target_ids = campaign.company_ids
    else:
        # Фоллбэк: все с email, не-сеть, подходящий сегмент
        query = session.query(CrmCompanyRow).filter(
            CrmCompanyRow.email.isnot(None),
            CrmCompanyRow.email != "",
        )
        if campaign.segment == "A":
            query = query.filter(CrmCompanyRow.segment == "A")
        elif campaign.segment == "B":
            query = query.filter(CrmCompanyRow.segment == "B")
        target_ids = [c.id for c in query.all()]

    # Исключить уже отправленных в этой кампании
    already_sent = set(
        row[0] for row in session.query(CrmEmailLogRow.company_id)
        .filter(CrmEmailLogRow.campaign_id == campaign.id)
        .all()
    )

    recipients = []
    for company_id in target_ids:
        if company_id in already_sent:
            continue

        company = session.get(CrmCompanyRow, company_id)
        if not company:
            continue

        enriched = session.query(CrmEnrichedDataRow).filter_by(
            company_id=company_id
        ).first()

        contact = session.query(CrmContactRow).filter_by(
            company_id=company_id
        ).first()

        email_to = contact.email if contact and contact.email else company.email
        if not email_to:
            continue

        recipients.append((company, enriched, contact, email_to))

    return recipients
```

> **Примечание:** точная структура `CrmEmailCampaignRow` (как хранится аудитория — `company_ids`, `segment`, и т.д.) уточняется по текущей ORM. Выше — каркас, который адаптируется под реальную схему.

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

`subject_a` и `subject_b` уже есть в ORM. Если `subject_b` задан — кампания A/B-тест.

```python
# granite/api/campaigns.py (или granite/email/sender.py)

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

#### 3.3 Колонки `total_opened` / `total_replied` — v11: добавлены

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

> **Почему это критично:** SSE-поллинг (задача 2.2) возвращает `campaign.total_opened` и `campaign.total_replied`. Без инкремента в tracking.py и process_replies.py эти значения всегда 0. Оператор видит нули и не может оценить эффективность.

#### 3.4 A/B stats endpoint

Отдельный endpoint для детальной статистики по вариантам A/B:

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
               SUM(CASE WHEN status = 'opened' THEN 1 ELSE 0 END) as opened,
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
        "winner": None,  # Определяется вручную по критерию из 4.4
        "note": "Победитель — по количеству ответов (см. раздел 4.4)",
    }
```

> Требует колонку `ab_variant` в `CrmEmailLogRow` — добавляется при отправке в `_run_campaign_background`.

**ORM-миграция для `ab_variant`:**

```python
# granite/database.py — CrmEmailLogRow
ab_variant = Column(String(1), nullable=True)  # "A" or "B"
```

Миграция:
```bash
uv run cli.py db migrate "add ab_variant to crm_email_logs"
uv run cli.py db upgrade head
```

---

### Задача 4: Валидатор получателей

Файл `granite/email/validator.py`:

```python
"""Валидация получателей перед отправкой."""
import re

# Домены агрегаторов — не мастерские
AGGREGATOR_DOMAINS = frozenset({
    "memorial.ru", "vsepamyatniki.ru", "obeliski.ru",
    "mipomnim.ru", "uznm.ru", "monuments.su",
    "tsargranit.ru", "alshei.ru",
})

# Географический фильтр НЕ нужен — Беларусь (.by) и Казахстан (.kz) OK

_EMAIL_RE = re.compile(r"^[\w.+-]+@[\w.-]+\.\w{2,}$")


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

### Задача 5: Воронка — follow-up + авто-отмена + счётчики

#### 5.1 Создание follow-up задачи при открытии письма

Добавить в `granite/api/tracking.py` — после обновления `contact.funnel_stage`:

```python
# После: if contact.funnel_stage == "email_sent": contact.funnel_stage = "email_opened"

# v11: инкремент счётчика открытий
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

    # v11: получить оригинальную тему из последнего touch
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
        description=original_subject,  # v11: сохраняем тему для Re: {subject}
    ))
    db.flush()
```

> Follow-up создаётся только при открытии. Получатели, которые не открыли письмо, follow-up не получают — осознанное решение, не дублируем тем, кто проигнорировал.

#### 5.2 Авто-отмена follow-up при смене стадии

v11: вынесена в **публичную** функцию `cancel_followup_tasks()` (без `_`), потому что нужна в 3 модулях: `stage_transitions.py`, `process_replies.py`, `unsubscribe.py`.

Файл `granite/api/helpers.py`:

```python
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

Вызывать в `apply_incoming_touch()` после установки `funnel_stage`:
```python
from granite.api.helpers import cancel_followup_tasks
cancel_followup_tasks(company_id, new_stage, db)
```

#### 5.3 Воронка после ответа

```
replied → interested  (обсуждаем условия)
replied → not_interested  (отказ)
interested → [ручная работа вне CRM]
```

Никаких автоматических действий при `interested`.

---

### Задача 6: Парсинг bounce-уведомлений

Файл `scripts/process_bounces.py`:

```python
"""
Читает IMAP-ящик (Gmail), ищет bounce-уведомления,
помечает компании как unreachable.

Запуск:
  uv run python -m scripts.process_bounces
"""
import email
import imaplib
import os
import re
from datetime import datetime, timezone
from loguru import logger


IMAP_HOST = os.getenv("IMAP_HOST", "imap.gmail.com")
IMAP_USER = os.getenv("SMTP_USER")
IMAP_PASS = os.getenv("SMTP_PASS")

# SMTP-коды hard bounce — ищем как отдельные числа, не подстроки
_HARD_BOUNCE_CODES = re.compile(
    r"\b550\b|\b551\b|\b553\b",
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
]


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

            bounce_email = _extract_bounced_email(msg)
            if not bounce_email:
                continue

            if not _is_hard_bounce(msg):
                continue

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
                        contact.funnel_stage = "unreachable"
                        contact.stop_automation = True

                    session.commit()
                    processed += 1
                    logger.info(f"Bounce: {bounce_email} → company #{log.company_id}")

            imap.store(uid, "+FLAGS", "\\Seen")

    engine.dispose()
    logger.info(f"Обработано bounce: {processed}")
    return processed


def _extract_bounced_email(msg) -> str | None:
    """Извлечь email получателя из bounce-уведомления."""
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


def _is_hard_bounce(msg) -> bool:
    """Определить hard bounce по SMTP-коду или фразе."""
    text = msg.as_string().lower()
    # Коды — regex с границами слов, чтобы «550» не совпадало с IP
    if _HARD_BOUNCE_CODES.search(text):
        return True
    return any(phrase in text for phrase in _HARD_BOUNCE_PHRASES)


if __name__ == "__main__":
    process_bounces()
```

---

### Задача 7: Фикс SEO-regex — убрать «гранит» + починить `памятник[аиы]?`

**Проблема v8:** две проблемы в `_SEO_TITLE_PATTERN`:

1. «Гранит» в 4 паттернах — нормальная часть названия в нише
2. `памятник[аиы]?\s*(?:из|в|на|от|и)?\s*` флагает «Гранит-Мастер ООО Памятники» — слово «Памятники» в конце названия компании не SEO

**7.1 Убираем «гранит» из 4 паттернов:**

| # | Паттерн | Почему убрать | Покрытие сохранено |
|---|---------|---------------|-------------------|
| 1 | `изготовлен.*(?:памятник\|надгробие\|гранит)` | «гранит» как альтернатива избыточна | `изготовлен.*памятник` остаётся |
| 2 | `гранитн[ые]+\s*мастерск` | «Гранитные мастерские» — реальное название в нише | Мн.ч. без «гранит» не покрывается, но допустимо |
| 3 | `памятниковизгранита\|памятникиизгранита` | Слипшиеся слова с «гранит» | Детектор длинных слов (>15 символов) ловит |
| 4 | `гранитнаямастерская` | Слипшееся «гранитнаямастерская» | Аналогично |

**7.2 Фикс `памятник[аиы]?` — добавляем негативный lookahead:**

```python
# Было (v8):
r"памятник[аиы]?\s*(?:из|в|на|от|и)?\s*|"

# Стало (v11):
r"памятник[аиы]?\s*(?:из|в|на|от|и)\s+\S|"   # предлог обязателен + слово после
```

**Итоговый regex после фикса (v11):**

```python
_SEO_TITLE_PATTERN = re.compile(
    r"(?:купить|цен[аыуе]|недорог|заказать|от производитель|"
    r"с установк|на могил|доставк|скидк|каталог|"
    r"памятник[аиы]?\s*(?:из|в|на|от|и)\s+\S|"   # предлог обязателен + слово после
    r"изготовлен.*(?:памятник|надгробие)|"         # без «гранит»
    r"памятники\s*(?:в|из|на|и)\s+\S|"            # + слово после предлога
    r"памятники\s*(?:на\s*кладбищ)|"
    r"изготовление\s*памятников|"
    r"памятники\s*и\s*надгробия|"
    r"производство\s*памятников|"
    # Слипшиеся слова — «гранит» убрано, ловится детектором >15 символов
    r"изготовлениепамятников|установкапамятников|"
    r"памятникинамогилу|купитьпамятник|"
    r"заказатьпамятник)",
    re.IGNORECASE,
)
```

**Тесты для обновления:**

| Входное | Было | Стало | Ожидаем |
|---------|------|-------|---------|
| `"Гранитные мастерские России"` | `True` | `False` | ✅ Не SEO |
| `"Гранит-Мастер"` | `False` | `False` | ✅ Не изменилось |
| `"Гранит-Мастер ООО Памятники"` | `True` | `False` | ✅ Не SEO — «Памятники» без предлога |
| `"Памятники в Екатеринбурге"` | `True` | `True` | ✅ SEO сохранено |
| `"Памятники из гранита дёшево"` | `True` | `True` | ✅ SEO сохранено |

Обновить тесты: `test_seo_name_extraction.py`, `test_merger.py`.

---

### Задача 8: Фикс SMTP_SSL — порт 465

**Проблема v8:** sender.py использует `smtplib.SMTP(port=587) + starttls()`, а .env задаёт `SMTP_PORT=465`. Порт 465 — implicit TLS, для него нужен `smtplib.SMTP_SSL`.

```python
# granite/email/sender.py — метод _smtp_send

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

### Задача 9: Обнаружение ответов — IMAP reply parser

**Проблема v8:** воронка упоминает стадии `replied` → `interested`/`not_interested`, но нет кода, который переводит контакт в `replied`. Следующие follow-up'ы не отменяются автоматически.

**v11: вызов `cancel_followup_tasks()` + инкремент `total_replied` + унификация `body=`.**

Файл `scripts/process_replies.py`:

```python
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


IMAP_HOST = os.getenv("IMAP_HOST", "imap.gmail.com")
IMAP_USER = os.getenv("SMTP_USER")
IMAP_PASS = os.getenv("SMTP_PASS")

# Предметы, которые точно не ответы от людей
_SKIP_SUBJECTS = re.compile(
    r"delivery status|undelivered|mailer-daemon|out of office|"
    r"автоответ|автоматическ|уведомлен",
    re.IGNORECASE,
)


def process_replies() -> int:
    if not all([IMAP_HOST, IMAP_USER, IMAP_PASS]):
        logger.error("IMAP_HOST / SMTP_USER / SMTP_PASS не заданы")
        return 0

    from granite.database import get_engine, CrmEmailLogRow, CrmContactRow, CrmTouchRow, CrmEmailCampaignRow
    from granite.api.helpers import cancel_followup_tasks  # v11: публичная функция
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

            # Проверяем что это ответ, а не bounce/OOO
            subject = msg.get("Subject", "")
            if _SKIP_SUBJECTS.search(subject):
                continue

            # Извлечь email отправителя
            from_header = msg.get("From", "")
            reply_email = _extract_email(from_header)
            if not reply_email:
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

                body_text = _get_text_body(msg)[:200] if _get_text_body(msg) else ""

                contact.funnel_stage = "replied"
                contact.updated_at = datetime.now(timezone.utc)

                # v11: отменить pending follow-up задачи
                cancel_followup_tasks(contact.company_id, "replied", session)

                # Обновить статус лога
                log.status = "replied"
                log.replied_at = datetime.now(timezone.utc)

                # v11: инкремент счётчика ответов кампании
                if log.campaign_id:
                    campaign = session.query(CrmEmailCampaignRow).filter_by(id=log.campaign_id).first()
                    if campaign:
                        campaign.total_replied = (campaign.total_replied or 0) + 1

                session.add(CrmTouchRow(
                    company_id=contact.company_id,
                    channel="email",
                    direction="incoming",
                    subject=subject[:200] if subject else "(без темы)",
                    body=body_text or "Ответ на email",  # v11: унифицировано — везде body
                ))
                session.commit()

                processed += 1
                logger.info(f"Reply: {reply_email} → company #{contact.company_id} → replied")

            imap.store(uid, "+FLAGS", "\\Seen")

    engine.dispose()
    logger.info(f"Обработано reply: {processed}")
    return processed


def _extract_email(header: str) -> str | None:
    """Извлечь email из заголовка From."""
    match = re.search(r'<([\w._%+-]+@[\w.-]+\.\w+)>', header)
    if match:
        return match.group(1).lower()
    match = re.search(r'([\w._%+-]+@[\w.-]+\.\w+)', header)
    if match:
        return match.group(1).lower()
    return None


def _get_text_body(msg) -> str | None:
    """Извлечь текстовое тело письма."""
    for part in msg.walk():
        if part.get_content_type() == "text/plain":
            payload = part.get_payload(decode=True)
            if payload:
                return payload.decode("utf-8", errors="ignore")
    return None


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

### Задача 11: Отправка follow-up — v11: новая задача

**Проблема v10:** задача 5.1 создаёт `CrmTaskRow(task_type="follow_up", status="pending", due_date=+7d)`. Задача 5.2 отменяет follow-up при переходе в терминальную стадию. Но **нет кода, который отправляет follow-up письмо** — задача 5.1 и 5.2 мёртвый код без исполнителя.

Файл `scripts/process_followups.py`:

```python
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

            # Получить оригинальную тему из description (задача 5.1 сохраняет её туда)
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
                    template_name="follow_up_email_v1",
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

### Задача 12: Post-reply playbook + Email-шаблоны — два документа

**Что:** ИИ-агент заполняет два документа на основе документации проекта. Александр анализирует и правит.

1. **`docs/POST_REPLY_PLAYBOOK.md`** — сценарии post-reply, инструкции, структура фильтрации, статистика, интеграция шаблонов
2. **`docs/EMAIL_TEMPLATES.md`** — каталог всех email-шаблонов с текстами, из которого шаблоны загружаются в CRM

Оба документа **уже созданы** (итерация v11). Александр редактирует тексты → запускает `seed-templates` → шаблоны в БД.

#### 12.1 Сценарии post-reply (13 сценариев)

Все типы реакций после отправки писем. Подробности — в `docs/POST_REPLY_PLAYBOOK.md`, раздел 2.

| # | Реакция | Тип | Действие | Шаблон | CRM-статус |
|---|---------|-----|----------|--------|-----------|
| 1 | «Интересно, расскажите подробнее» | manual | Детали + предложить тест | `reply_interested` | `interested` |
| 2 | «Сколько стоит?» | manual | Прайс + оплата после результата | `reply_price_question` | `interested` |
| 3 | «Пришлите примеры» | manual | Портфолио + «пришлите свой случай» | `reply_send_examples` | `interested` |
| 4 | «Подскажите по срокам» | manual | 12–24ч, срочно 3–6ч | `reply_timing` | `interested` |
| 5 | «Нам уже кто-то делает» | manual | Мягкий ответ, дверь открыта | `reply_has_vendor` | `replied` |
| 6 | «Нет, не актуально» | auto | not_interested, без действий | — | `not_interested` |
| 7 | «Отпишите» / «Удалите данные» | auto | stop_automation=1 | — | `not_interested` + `stop_automation=1` |
| 8 | Жалоба на спам | auto | stop_automation=1 | — | `not_interested` + `stop_automation=1` |
| 9 | Автоответчик (OOO) | auto | Игнорировать, не менять стадию | — | без изменений |
| 10 | Bounce (email не существует) | auto | Отметить bounced | — | `unreachable` |
| 11 | Молчание после открытия | auto | follow-up через 7 дней | `follow_up_email_v1` | `email_opened` |
| 12 | Молчание без открытия | auto | Напоминание через 14 дней | `follow_up_email_v1` | `email_sent` |
| 13 | Молчание после 2 писем | auto | Стоп, unreachable | — | `unreachable` |

#### 12.2 Email-шаблоны — immutable ID, JSON source of truth

**Архитектурное решение:** шаблоны — immutable записи. Каждый шаблон получает уникальный ID и **никогда не редактируется**. Нужен другой текст → создаётся новый шаблон с новым ID, старый помечается `retired: true`.

**Почему:** при изменяемых шаблонах статистика по `template_name` бессмысленна — невозможно узнать какой текст реально отправлялся. Immutable ID = честная статистика навсегда.

**Source of truth:** `data/email_templates.json` — редактирует Александр, хранится в git.

**Operational cache:** `crm_templates` (БД) — seed из JSON при старте. Таблица живёт в БД для быстрого доступа при отправке.

| Категория | Шаблоны | Кол-во |
|-----------|---------|--------|
| Холодные письма | `cold_email_1` (#1), `cold_email_2` (#2), `cold_email_3` (#3), `cold_email_bitrix` (#4) | 4 |
| Follow-up | `follow_up_email_v1` (#5) | 1 |
| Post-reply | `reply_interested` (#6), `reply_price_question` (#7), `reply_send_examples` (#8), `reply_timing` (#9), `reply_has_vendor` (#10) | 5 |
| **Итого** | | **10** |

**Структура JSON-записи:**

```json
{
  "id": 1,
  "name": "cold_email_1",
  "channel": "email",
  "body_type": "plain",
  "subject": "Помощь с подготовкой фото для гравировки, {city}",
  "body": "Здравствуйте, {company_name}!...",
  "description": "Первый холодный — основной оффер",
  "created_at": "2026-04-26",
  "retired": false
}
```

**Жизненный цикл шаблона:**
1. Александр пишет новый шаблон → добавляет в JSON с новым ID
2. `seed-templates` → INSERT в `crm_templates` (новый) или пропустить (существующий)
3. Кампания ссылается на `template_id`
4. Лог отправки хранит `template_id` — навсегда привязан к конкретному тексту
5. Если шаблон не нужен → `retired: true`, но никогда не удаляется (статистика)

#### 12.3 Интеграция шаблонов в CRM

```
data/email_templates.json  (source of truth, immutable ID)
         │
         ▼  cli.py db seed-templates (INSERT новых, пропуск существующих)
crm_templates (CrmTemplateRow в БД — operational cache)
         │
         ├──▶ Кампания: template_id → body + subject
         │
         └──▶ Post-reply: кнопка сценария → шаблон → render() → отправка
         │
         ▼  при отправке
CrmEmailLogRow.template_id = 3  (навсегда привязан к конкретному тексту)
```

**seed-templates логика (UPSERT по id):**
```python
for t in json.load(open("data/email_templates.json"))["templates"]:
    existing = session.query(CrmTemplateRow).filter_by(id=t["id"]).first()
    if not existing:
        session.add(CrmTemplateRow(**t))  # INSERT — только новые
    # Существующие НЕ обновляются — immutable!
```

**Шаги интеграции:**
1. Александр создаёт новый шаблон в `data/email_templates.json` с новым ID
2. `uv run cli.py db seed-templates` — новые шаблоны добавляются в `crm_templates`
3. При создании кампании — выбрать шаблон по ID, задать A/B темы
4. При post-reply — кнопка сценария → шаблон из БД → `render(**kwargs)` → отправка
5. `CrmEmailLogRow.template_id` записывается при отправке → честная статистика

**A/B тестирование:**
- A/B по темам: `subject_a` / `subject_b` в `CrmEmailCampaignRow` — тело одно (`template_id`), темы разные
- A/B по телу: просто создать два шаблона с разными ID и запускать две кампании. Никаких `template_b_name` не нужно — immutable ID решает это элегантнее

**Запрос статистики по шаблонам:**
```sql
SELECT template_id,
       COUNT(*) as sent,
       SUM(CASE WHEN opened_at IS NOT NULL THEN 1 ELSE 0 END) as opened,
       SUM(CASE WHEN replied_at THEN 1 ELSE 0 END) as replied,
       ROUND(100.0 * SUM(CASE WHEN opened_at IS NOT NULL THEN 1 ELSE 0 END) / COUNT(*), 1) as open_rate,
       ROUND(100.0 * SUM(CASE WHEN replied_at THEN 1 ELSE 0 END) / COUNT(*), 1) as reply_rate
FROM crm_email_logs
GROUP BY template_id
ORDER BY reply_rate DESC
```
Результат: шаблон #3 — open 32%, reply 8%. Шаблон #1 — open 15%, reply 2%. Вывод: #3 работает, #1 можно `retired: true`

#### 12.4 Точная структура фильтрации (на основе текущей ORM)

Фильтры кампании — JSON в `CrmEmailCampaignRow.filters`. Полный реестр полей:

| Поле | Тип | ORM-источник | Индекс |
|------|-----|-------------|--------|
| `cities` | `list[str]` | `CompanyRow.city` | `ix_companies_city` |
| `regions` | `list[str]` | `CompanyRow.region` | индекс на `region` |
| `segments` | `list[str]` | `EnrichedCompanyRow.segment` | `ix_enriched_companies_segment` |
| `min_score` | `int` | `EnrichedCompanyRow.crm_score` | `ix_enriched_companies_crm_score` |
| `max_score` | `int` | `EnrichedCompanyRow.crm_score` | |
| `has_email` | `bool` | `CompanyRow.emails` (JSON) | |
| `has_website` | `bool` | `CompanyRow.website` | |
| `cms` | `list[str]` | `EnrichedCompanyRow.cms` | `ix_enriched_cms` |
| `has_telegram` | `bool` | `json_extract(messengers, '$.telegram')` | |
| `has_whatsapp` | `bool` | `json_extract(messengers, '$.whatsapp')` | |
| `has_marquiz` | `bool` | `EnrichedCompanyRow.has_marquiz` | `ix_enriched_marquiz` |
| `is_network` | `bool` | `EnrichedCompanyRow.is_network` | `ix_enriched_segment_network` |
| `funnel_stages` | `list[str]` | `CrmContactRow.funnel_stage` | `ix_crm_contacts_funnel_stage` |
| `exclude_companies` | `list[int]` | `CompanyRow.id` | |
| `max_per_domain` | `int` | Дедупликация по `website` домену | |
| `min_email_sent_count` | `int` | `CrmContactRow.email_sent_count` | |
| `max_email_sent_count` | `int` | `CrmContactRow.email_sent_count` | |

**Автоматические фильтры (всегда):** `stop_automation=0`, `deleted_at IS NULL`, `emails != []`

**Логика:** Все фильтры — AND. Внутри списков — OR. Пример: `cities: ["Волгоград", "Саратов"], segments: ["A"]` → (Волгоград OR Саратов) AND A

Подробный SQL-запрос и описание `max_per_domain` — в `docs/POST_REPLY_PLAYBOOK.md`, раздел 3.

#### 12.5 Хранение статистики (3 уровня в текущей ORM)

**Уровень 1:** `CrmEmailCampaignRow` — агрегат кампании (`total_sent`, `total_opened`, `total_replied`)

**Уровень 2:** `CrmEmailLogRow` — каждое письмо (`status`, `sent_at`, `opened_at`, `replied_at`, `bounced_at`, `tracking_id`, `ab_variant`)

**Уровень 3:** `CrmContactRow` — каждый контакт (`funnel_stage`, `email_sent_count`, `email_opened_count`, `email_replied_count`, `stop_automation`)

**A/B stats:** `GET /api/v1/campaigns/{id}/ab-stats` — SQL GROUP BY `ab_variant` (задача 3.4)

**Чего нет (и когда добавлять):**

| Что | Зачем | Когда |
|-----|-------|-------|
| `ab_variant` в `CrmEmailLogRow` | Разрезать статистику A/B | Миграция задачи 3.4 |
| `total_errors` в `CrmEmailCampaignRow` | Считать ошибки | Миграция задачи 3.3 |
| Исторические снапшоты по дням | Графики | Когда данных достаточно |
| ~~`template_b_name` для A/B по телу~~ | ~~A/B тело письма~~ | **Не нужно** — immutable ID: два шаблона = две кампании |

Полная детализация — в `docs/POST_REPLY_PLAYBOOK.md`, раздел 4.

#### 12.6 Сводка по файлам

| Файл | Назначение | Статус |
|------|-----------|--------|
| `docs/POST_REPLY_PLAYBOOK.md` | Сценарии, фильтрация, статистика, инструкции | Создан |
| `docs/EMAIL_TEMPLATES.md` | Человекочитаемый каталог шаблонов (документация) | Создан |
| `data/email_templates.json` | Source of truth — все шаблоны с immutable ID | Создать (задача 12 impl) |
| `granite/database.py` → `CrmTemplateRow` | ORM шаблонов (id, name, body, subject, body_type, retired) | Существует, +`retired` колонка |
| `granite/database.py` → `CrmEmailLogRow` | ORM логов — `template_id` (Integer) вместо `template_name` (String) | Миграция |
| `granite/database.py` → `CrmEmailCampaignRow` | ORM кампаний (filters, stats, subject_a/b) | Существует |
| `granite/database.py` → `CrmContactRow` | ORM контактов (funnel_stage, counters) | Существует |
| `granite/api/campaigns.py` | API кампаний + A/B stats | Существует |
| `granite/email/sender.py` | Отправка писем | Существует |
| `granite/email/validator.py` | Валидация + дедупликация | Существует |

---

### Задача 13: Bitrix-шаблон (опционально)

Если Волна 1 (Bitrix, 41 компания) будет идти отдельным шаблоном — создать `cold_email_bitrix` (см. 4.5). Если нет — используется `cold_email_v1` с темой-победителем.

Решение принимается после Фазы 0, когда станет ясен tone победившего шаблона.

---

### Задача 14: SEO-regex фиксы

4 удаления «гранит» из `_SEO_TITLE_PATTERN` в `granite/utils.py`:

1. `изготовлен.*(?:памятник|надгробие|гранит)` → убрать `|гранит`
2. `гранитн[ые]+\s*мастерск` → убрать весь паттерн
3. `памятниковизгранита|памятникиизгранита` → убрать (long-word detector >15 chars)
4. `гранитнаямастерская` → убрать (long-word detector)

**Важно:** `_RU_KEYWORDS` в `granite/web_search.py` содержит «гранит» для релевантности — НЕ трогать.

**Побочные эффекты:**
- Компании с «Гранит» в названии (Гранит-Мастер, Гранитные мастерские) больше не флагаются как SEO → попадают в рассылку
- Общее количество SEO-флагов в базе снизится → больше валидных получателей

**Когда:** До запуска Волны 1, после проверки что миграция не сломала существующие данные.

---

## 6. Roadmap по дням

### День 1 — Инфраструктура + критические фиксы (0 писем)

```
[ ] Задача 8: фикс SMTP_SSL в sender.py (порт 465 + SMTP_SSL)
[ ] Задача 7 / Задача 14: фикс SEO-regex (убрать «гранит» + починить памятник[аиы]?)
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

### День 2 — Рефакторинг отправки + Фаза 0 старт (10 писем)

```
[ ] Задача 2.2: BackgroundTask + SSE-поллинг
[ ] Задача 2.4: _get_campaign_recipients() (v11)
[ ] Задача 3: total_errors + A/B-распределение + ab_variant tracking
[ ] Задача 3.4: A/B stats endpoint
[ ] Задача 4: validator.py (с дедупликацией email)
[ ] Создать кампанию: 10 получателей, сегмент A, тема A vs B
[ ] Запустить, проверить логи
[ ] Проверить что total_opened инкрементируется при открытии (tracking pixel)
```

### День 3–4 — Фаза 0, ещё 40 писем

```
[ ] 20 писем / день
[ ] Задача 5: follow-up при открытии + авто-отмена + счётчики
[ ] Задача 6: process_bounces.py
[ ] Задача 9: process_replies.py
[ ] Задача 11: process_followups.py (v11)
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
[ ] Оценить тему A vs B (практический критерий из 4.4)
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
[ ] Задача 14: SEO-regex фиксы — если ещё не выполнены, до Волны 1
```

---

## 7. Открытые вопросы

| Вопрос | Статус |
|--------|--------|
| **Публичный URL для tracking pixel и отписки** — Cloudflare Tunnel или альтернатива | ⬜ Решается отдельно. До решения tracking не работает, но отправлять можно — просто без метрик открытий и без рабочей ссылки отписки |
| **Тексты писем** | ⬜ Отдельная задача |
| **Телефон в подписи** — где нужен, заменить на российский номер | ⬜ Отдельно по мере необходимости |
| **`_get_campaign_recipients()` — точная структура фильтрации** | ✅ Уточнено по текущей ORM. См. Приложение: структура фильтрации |

### MAX_PER_DOMAIN

v2/v3 имели `MAX_PER_DOMAIN=2` — максимум 2 письма на один домен-получатель за сутки (не на адрес, а на домен: @yandex.ru, @mail.ru). Идея: не бомбить один почтовый провайдер. При текущих объёмах (50/день, 434 получателя с разными доменами) это избыточно. Если в будущем объёмы вырастут — можно вернуть через env-переменную.

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
                                      # для будущего использования при автоматизации сессий

# IMAP (для bounce + reply, Gmail)
IMAP_HOST=imap.gmail.com

# CRM
GRANITE_API_KEY=             # опционально
```

---

## Приложение: сводка фиксов v10 → v11

| # | Баг v10 | Фикс v11 | Где |
|---|---------|----------|-----|
| 1 | `total_opened` / `total_replied` = всегда 0 | Инкремент в tracking.py и process_replies.py | Задачи 5.1, 9 |
| 2 | Отписка не отменяет follow-up | `cancel_followup_tasks()` в `unsubscribe_confirm()` | Задача 1.3 |
| 3 | Follow-up никогда не отправляется | Новый `scripts/process_followups.py` | Задача 11 |
| 4 | `_get_campaign_recipients()` не определена | Реализация с фильтром дублей | Задача 2.4 |
| 5 | `CrmTouchRow`: `note=` vs `body=` | Унифицировано: везде `body=` | Задачи 1.3, 9 |
| 6 | Auth bypass нет для `/track/` | Добавлен в middleware | Задача 1.3 |
| 7 | Нет post-reply playbook | Два документа: `docs/POST_REPLY_PLAYBOOK.md` (сценарии, фильтрация, статистика) + `docs/EMAIL_TEMPLATES.md` (10 шаблонов) | Задача 12 ✅ |
| 8 | Географический фильтр .by/.kz без причины | Убран, добавлен комментарий в валидаторе | Задача 4 |
| 9 | Мелочи из v2–v4 не возвращены | `EMAIL_SESSION_GAP_HRS`, дедупликация email, A/B stats, Bitrix-шаблон, mail-tester.com, признаки блокировки Gmail | Задачи 3.4, 4, 4.5, 13 |
| 10 | `MAX_PER_DOMAIN` из v2/v3 — нужен ли? | Не нужен при текущих объёмах, объяснено в открытых вопросах | Раздел 7 |
| — | `_cancel_followup_tasks` приватная | `cancel_followup_tasks` в `helpers.py` | Задача 5.2 |
| — | Follow-up тема не совпадает с A/B | `description=original_subject` в CrmTaskRow | Задачи 5.1, 11 |
| — | `total_opened` / `total_replied` нет в ORM | Колонки + миграция | Задача 3.3 |
| — | Нет `ab_variant` в логах | Колонка `ab_variant` в `CrmEmailLogRow` + передача в sender.send() | Задачи 3.4, 2.2 |

---

## Приложение: структура фильтрации `_get_campaign_recipients()` (по текущей ORM)

> Уточнено по `granite/database.py` на момент v11. Ранее стояло ⬜ — теперь закрыто.

### `CrmEmailCampaignRow.filters` — JSON-колонка (схема)

```json
{
    "segment": "A",              // EnrichedCompanyRow.segment (есть индекс)
    "cms": "bitrix",             // EnrichedCompanyRow.cms (есть индекс)
    "has_marquiz": true,         // EnrichedCompanyRow.has_marquiz (есть индекс)
    "is_network": false,         // EnrichedCompanyRow.is_network
    "tg_trust_min": 2,           // EnrichedCompanyRow.tg_trust (JSON dict — фильтрация через json_extract)
    "cities": ["Москва"],        // CompanyRow.city (есть индекс)
    "regions": [],               // CompanyRow.region (есть индекс)
    "funnel_stage": "new",       // CrmContactRow.funnel_stage (есть индекс)
    "stop_automation": false,    // CrmContactRow.stop_automation (есть индекс)
    "has_email": true            // CompanyRow.emails (JSON — проверка на непустой список)
}
```

### Важные замечания по ORM

1. **`company_ids` НЕТ в `CrmEmailCampaignRow`** — в текущей ORM такой колонки не существует. Код в задаче 2.4 ссылается на `campaign.company_ids` — это **ошибка**. Варианты решения:
   - **(A)** Добавить колонку `company_ids = Column(JSON, default=list)` в `CrmEmailCampaignRow` + миграция — тогда кампания может хранить конкретный список получателей
   - **(B)** Использовать только `filters` JSON для динамической фильтрации — без явного списка `company_ids`
   - **Рекомендация:** вариант (A) — явный список company_id при создании кампании проще и надёжнее, чем динамическая фильтрация. `_get_campaign_recipients()` сначала проверяет `company_ids`, затем фоллбэчит на `filters`

2. **`CrmCompanyRow.email` vs `CrmCompanyRow.emails`** — в ORM поле `emails` (JSON, list[str]), а не `email` (String). Код в задаче 2.4 использует `CrmCompanyRow.email.isnot(None)` — это **ошибка**, правильно:
   ```python
   # emails — JSON-массив, фильтрация через json_extract или Python-side
   query = session.query(CrmCompanyRow).filter(
       CrmCompanyRow.emails.isnot(None),
       func.json_array_length(CrmCompanyRow.emails) > 0,
   )
   ```

3. **`CrmCompanyRow.segment` vs `EnrichedCompanyRow.segment`** — сегмент хранится в `enriched_companies`, а не в `companies`. Код в задаче 2.4 фильтрует по `CrmCompanyRow.segment == "A"` — это **ошибка**, нужно JOIN с `EnrichedCompanyRow`:
   ```python
   query = session.query(CompanyRow).join(
       EnrichedCompanyRow, EnrichedCompanyRow.id == CompanyRow.id
   ).filter(
       EnrichedCompanyRow.segment == "A",
       EnrichedCompanyRow.is_network == False,
   )
   ```

4. **`tg_trust`** — это JSON-словарь (`{"trust_score": 3, "has_avatar": True, ...}`). Фильтрация по `tg_trust_min`:
   ```python
   # SQLite: json_extract(tg_trust, '$.trust_score') >= 2
   query = query.filter(
       func.json_extract(EnrichedCompanyRow.tg_trust, '$.trust_score') >= filters.get('tg_trust_min', 0)
   )
   ```

5. **Дедупликация email** — компания может иметь несколько email в `emails` (JSON list). Нужно выбирать первый валидный и не отправлять на один адрес дважды в рамках кампании — `seen_emails` set в валидаторе (задача 4).

### Исправленный каркас `_get_campaign_recipients()`

```python
def _get_campaign_recipients(
    campaign: CrmEmailCampaignRow,
    session: Session,
) -> list[tuple]:
    """Возвращает [(company, enriched, contact, email_to), ...]."""
    
    # 1. Определить целевые company_id
    if campaign.company_ids:  # требуется добавить колонку в ORM
        target_ids = campaign.company_ids
    else:
        # Динамическая фильтрация через filters JSON
        f = campaign.filters or {}
        query = session.query(CompanyRow).join(
            EnrichedCompanyRow, EnrichedCompanyRow.id == CompanyRow.id
        ).join(
            CrmContactRow, CrmContactRow.company_id == CompanyRow.id
        ).filter(
            CompanyRow.deleted_at.is_(None),
            CrmContactRow.stop_automation == 0,
        )
        
        if f.get("segment"):
            query = query.filter(EnrichedCompanyRow.segment == f["segment"])
        if f.get("cms") and f["cms"] != "unknown":
            query = query.filter(EnrichedCompanyRow.cms == f["cms"])
        if f.get("has_marquiz"):
            query = query.filter(EnrichedCompanyRow.has_marquiz == True)
        if f.get("is_network") == False:
            query = query.filter(EnrichedCompanyRow.is_network == False)
        if f.get("cities"):
            query = query.filter(CompanyRow.city.in_(f["cities"]))
        if f.get("funnel_stage"):
            query = query.filter(CrmContactRow.funnel_stage == f["funnel_stage"])
        
        target_ids = [c.id for c in query.all()]
    
    # 2. Исключить уже отправленных в этой кампании
    already_sent = set(
        row.company_id for row in
        session.query(CrmEmailLogRow.company_id)
        .filter(CrmEmailLogRow.campaign_id == campaign.id)
        .all()
    )
    target_ids = [cid for cid in target_ids if cid not in already_sent]
    
    # 3. Собрать данные для каждого получателя
    results = []
    seen_emails = set()  # дедупликация email
    for cid in target_ids:
        company = session.get(CompanyRow, cid)
        enriched = session.get(EnrichedCompanyRow, cid)
        contact = session.get(CrmContactRow, cid)
        if not company or not contact:
            continue
        # Выбрать первый валидный email
        emails = company.emails or []
        email_to = None
        for e in emails:
            if e and e not in seen_emails:
                email_to = e
                break
        if not email_to:
            continue
        seen_emails.add(email_to)
        results.append((company, enriched, contact, email_to))
    
    return results
```

*v11 · 2026-04-26 · v10 + 6 фиксов + 4 дополнения: post-reply playbook, возврат мелочей из ранних версий, географический фильтр убран, MAX_PER_DOMAIN объяснён и не нужен*
