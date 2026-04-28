<!-- Обновлено: 2026-04-28 -->
# Справочник API RetouchGrav CRM

> Полный справочник REST API эндпоинтов Granite CRM. Базовый URL: `http://localhost:8000/api/v1`. Документация Swagger: `http://localhost:8000/docs`.

---

## Общая информация

| Параметр | Значение |
|----------|----------|
| Базовый URL | `http://localhost:8000/api/v1` |
| Формат | JSON |
| Аутентификация | Нет (один пользователь, локально). Опционально: `GRANITE_API_KEY` в .env |
| CORS | `localhost:3000`, `localhost:5173` |
| Пагинация | `page` (default: 1), `per_page` (default: 50) |
| Кодировка | UTF-8 |

### Стандартные ответы

**Успех:** `{ok: true, ...}` или объект с данными

**Ошибка:**
```json
{
  "error": "Описание ошибки",
  "code": "ERROR_CODE",
  "detail": null
}
```

### Пагинированный ответ

```json
{
  "items": [...],
  "total": 1234,
  "page": 1,
  "per_page": 50
}
```

---

## 1. Health

### `GET /health`

Проверка доступности сервера и БД.

**Ответ:**
```json
{"status": "ok", "db": true}
```

### `GET /health/smtp`

Проверка подключения к SMTP-серверу. Использовать перед запуском email-кампании.

**Ответ `200`:**
```json
{"status": "ok", "smtp": "connected"}
```

**Ответ при ошибке:**
```json
{"status": "error", "smtp": "SMTP credentials not configured"}
```
или
```json
{"status": "error", "smtp": "Connection refused"}
```

---

## 2. Компании

### `GET /companies`

Список компаний с фильтрацией, сортировкой и пагинацией.

**Параметры запроса:**

| Параметр | Тип | Описание |
|----------|-----|----------|
| `search` | string | Поиск по названию (ilike) |
| `city[]` | string[] | Фильтр по городам (можно несколько) |
| `region` | string | Фильтр по региону |
| `segment` | string | Фильтр по сегменту: A, B, C, D, spam |
| `funnel_stage` | string | Фильтр по стадии воронки |
| `has_telegram` | bool | Есть/нет Telegram |
| `has_whatsapp` | bool | Есть/нет WhatsApp |
| `has_email` | bool | Есть/нет email |
| `has_vk` | bool | Есть/нет VK |
| `has_website` | bool | Есть/нет сайт |
| `has_address` | bool | Есть/нет адрес |
| `is_network` | bool | Является сетью |
| `has_marquiz` | bool | Есть Marquiz |
| `needs_review` | bool | Требует проверки |
| `stop_automation` | bool | Автоматизация приостановлена |
| `is_deleted` | bool | Показать удалённые |
| `min_score` | int | Минимальный CRM-score |
| `max_score` | int | Максимальный CRM-score |
| `min_tg_trust` | int | Минимальный TG Trust (0-3) |
| `cms` | string | Фильтр по CMS |
| `source` | string | Фильтр по источнику данных |
| `order_by` | string | Поле сортировки (crm_score, name, city, updated_at, last_contact_at) |
| `order_dir` | string | Направление: asc, desc |
| `page` | int | Номер страницы (default: 1) |
| `per_page` | int | Записей на странице (default: 50, max: 200) |

**Ответ:** `PaginatedResponse[CompanyResponse]`

### `GET /companies/{id}`

Карточка компании с обогащёнными и CRM-данными.

**Ответ:** `CompanyResponse`

### `PATCH /companies/{id}`

Обновление данных компании.

**Тело:** `UpdateCompanyRequest`
```json
{
  "name": "Новое название",
  "funnel_stage": "replied",
  "notes": "Позвонить завтра",
  "stop_automation": false,
  "phones": ["79991234567"],
  "emails": ["test@example.com"],
  "website": "https://example.com",
  "address": "г. Москва, ул. Ленина 1",
  "city": "Москва",
  "messengers": {"telegram": "@example"}
}
```

**Ответ:** `{ok: true}`

### `GET /companies/{id}/similar`

Похожие компании (для поиска дубликатов).

**Ответ:** `SimilarCompaniesResponse`

### `PATCH /companies/{id}/merge`

Слияние компаний. Указанные `source_ids` сливаются в текущую компанию.

**Тело:** `MergeRequest`
```json
{
  "source_ids": [42, 43]
}
```

**Ответ:** `{ok: true}`

### `POST /companies/{id}/re-enrich-preview`

Предпросмотр данных с сайта компании (скрапинг без сохранения).

**Ответ:** `ReEnrichPreviewResponse`

### `POST /companies/{id}/re-enrich-apply`

Применить данные после пересканирования.

**Тело:** `ReEnrichApplyRequest`

**Ответ:** `{ok: true}`

---

## 3. Касания

### `POST /companies/{id}/touches`

Записать касание (отправленное/полученное сообщение).

**Тело:** `CreateTouchRequest`
```json
{
  "channel": "email",
  "direction": "outgoing",
  "subject": "Ретушь для гравировки",
  "body": "Текст письма",
  "note": "Отправили первое письмо"
}
```

**channel:** `email` | `tg` | `wa` | `manual`
**direction:** `outgoing` | `incoming`

**Ответ:** `{ok: true, id: 123}`

### `GET /companies/{id}/touches`

История касаний компании.

**Ответ:** `list[TouchResponse]`

### `DELETE /touches/{id}`

Удалить касание.

**Ответ:** `{ok: true}`

---

## 4. Задачи

### `POST /companies/{id}/tasks`

Создать задачу для компании.

**Тело:** `CreateTaskRequest`
```json
{
  "title": "Follow-up",
  "task_type": "follow_up",
  "priority": "high",
  "description": "Написать повторное письмо",
  "due_date": "2026-05-01"
}
```

**task_type:** `follow_up` | `send_portfolio` | `send_test_offer` | `check_response` | `other`
**priority:** `low` | `normal` | `high`

**Ответ:** `{ok: true, id: 456}`

### `GET /tasks`

Список задач с фильтрами.

| Параметр | Тип | Описание |
|----------|-----|----------|
| `status` | string | pending, in_progress, done, cancelled |
| `company_id` | int | Задачи конкретной компании |
| `task_type` | string | Тип задачи |

**Ответ:** `PaginatedResponse[TaskResponse]`

### `PATCH /tasks/{id}`

Обновить задачу.

**Тело:** `UpdateTaskRequest`
```json
{
  "status": "done",
  "priority": "normal"
}
```

**Ответ:** `{ok: true}`

### `DELETE /tasks/{id}`

Удалить задачу.

**Ответ:** `{ok: true}`

---

## 5. Шаблоны

### `GET /templates`

Список шаблонов сообщений.

**Параметры:** `channel` (опционально)

**Ответ:** `list[TemplateResponse]`

### `POST /templates`

Создать шаблон.

**Тело:** `CreateTemplateRequest`
```json
{
  "name": "cold_email_1",
  "channel": "email",
  "subject": "Помощь с подготовкой фото для гравировки",
  "body": "Здравствуйте, {company_name}!...",
  "body_type": "plain",
  "description": "Холодное письмо #1"
}
```

**Ограничения:**
- `name` — латиница, цифры, подчёркивание, кириллица (заглавная и строчная), max 64 символа
- `body_type=html` допускается только при `channel=email`
- `body` — максимум 500 000 символов

**Ответ:** `{ok: true, warnings: [...]}`

### `PUT /templates/{name}`

Обновить шаблон.

**Тело:** `UpdateTemplateRequest` (все поля опциональны)

**Ответ:** `{ok: true, warnings: [...]}`

### `DELETE /templates/{name}`

Удалить шаблон.

**Ответ:** `{ok: true}`

---

## 6. Кампании

### `POST /campaigns`

Создать email-кампанию.

**Тело:** `CreateCampaignRequest`
```json
{
  "name": "Холодные лиды МСК",
  "template_name": "cold_email_1",
  "filters": {
    "city": "Москва",
    "segment": "A",
    "min_score": 40
  }
}
```

**Ответ:** `{ok: true, id: 789}`

### `GET /campaigns`

Список кампаний.

**Ответ:** `PaginatedResponse[CampaignResponse]`

### `GET /campaigns/{id}`

Детали кампании с предпросмотром получателей и статистикой.

**Ответ:** `CampaignDetailResponse`

### `PATCH /campaigns/{id}`

Обновить кампанию (черновик или приостановленную).

**Тело:** `UpdateCampaignRequest`

**Ответ:** `{ok: true}`

### `DELETE /campaigns/{id}`

Удалить черновик.

**Ответ:** `{ok: true}`

### `POST /campaigns/{id}/run`

Запустить кампанию. Возвращает SSE-события с прогрессом.

**Ответ:** SSE stream
```
event: progress
data: {"sent": 10, "total": 50, "current": "Компания X"}

event: complete
data: {"sent": 50, "opened": 0, "errors": 2}
```

### `GET /campaigns/{id}/progress`

SSE-поток прогресса отправки кампании (аналог `/run`, но без запуска — только подписка на события).

**Ответ:** SSE stream
```
event: progress
data: {"sent": 15, "total": 50, "errors": 1, "current": "Компания Y"}

event: complete
data: {"sent": 50, "total": 50, "errors": 2}
```

### `GET /campaigns/{id}/stats`

Статистика кампании.

**Ответ:** `CampaignStatsResponse`

### `GET /campaigns/{id}/ab-stats`

Статистика A/B тестирования кампании. Количество отправок по вариантам A и B.

**Ответ:**
```json
{
  "variant_a_sent": 25,
  "variant_b_sent": 25,
  "variant_a_errors": 1,
  "variant_b_errors": 0
}
```

### `POST /campaigns/stale`

Сбросить «зависшие» кампании (running > 2 часов).

**Ответ:** `StaleCampaignsResponse`

---

## 7. Воронка

### `GET /funnel`

Распределение компаний по стадиям воронки.

**Ответ:** `FunnelResponse`
```json
{
  "new": 1200,
  "email_sent": 350,
  "email_opened": 80,
  "tg_sent": 15,
  "wa_sent": 10,
  "replied": 25,
  "interested": 8,
  "not_interested": 12,
  "unreachable": 30
}
```

### `POST /companies/{id}/funnel/transition`

Перевести компанию на новую стадию воронки.

**Тело:**
```json
{
  "stage": "replied"
}
```

**Допустимые стадии:** `new`, `email_sent`, `email_opened`, `tg_sent`, `wa_sent`, `replied`, `interested`, `not_interested`, `unreachable`

---

## 8. Follow-up

### `GET /followup`

Очередь компаний для повторного контакта.

**Параметры:** `city` (опционально)

**Ответ:** `list[FollowupItemResponse]`

Каждый элемент содержит: компанию, рекомендованный канал, шаблон, количество дней с последнего контакта.

### `POST /followup/check`

Проверить и создать follow-up задачи для компаний, которым пора написать повторно.

**Ответ:** `{ok: true, created: 5}`

---

## 9. Мессенджеры

### `POST /companies/{id}/send`

Отправить сообщение через мессенджер (mock/dry-run, реальные отправки заблокированы РКН).

**Тело:** `SendMessageRequest`
```json
{
  "channel": "tg",
  "template_name": "tg_intro",
  "text": "Произвольный текст"
}
```

**channel:** `tg` | `wa`. Указать `template_name` или `text` (не оба).

**Ответ:** `MessengerResultResponse`

---

## 10. Пайплайн

### `GET /pipeline/status`

Статус пайплайна по городам.

**Параметры:** `region` (опционально)

**Ответ:** `PipelineStatusResponse`

### `GET /pipeline/cities`

Справочник городов.

**Ответ:** `PipelineCitiesResponse`

### `POST /pipeline/run`

Запустить пайплайн для города (SSE).

**Тело:** `PipelineRunRequest`
```json
{
  "city": "Волгоград",
  "force": false,
  "re_enrich": false
}
```

**Ответ:** SSE stream с прогрессом

---

## 11. Статистика

### `GET /stats`

Агрегированная статистика CRM.

**Параметры:** `city` (опционально)

**Ответ:** `StatsResponse`
```json
{
  "total_companies": 5847,
  "funnel": {"new": 1200, ...},
  "segments": {"A": 450, "B": 1100, "C": 2400, "D": 1800},
  "top_cities": [{"city": "Волгоград", "count": 1200}],
  "with_telegram": 890,
  "with_whatsapp": 1200,
  "with_email": 3500
}
```

---

## 12. Трекинг

### `GET /track/open/{tracking_id}.png`

Tracking pixel — 1x1 прозрачный PNG. Фиксирует открытие email-письма, обновляет `opened_at` в `crm_email_logs`.

---

## 13. Экспорт

### `GET /export/{city}.csv`

Экспорт компаний по городу в CSV (UTF-8 BOM).

---

## 14. Города и регионы

### `GET /cities`

Список уникальных городов в базе.

**Ответ:** `PaginatedResponse[str]`

### `GET /regions`

Список уникальных регионов.

**Ответ:** `PaginatedResponse[str]`

---

## 15. Admin

Роутер `granite/api/admin.py`. Требуется переменная окружения `GRANITE_ADMIN_PASSWORD` — без неё все эндпоинты возвращают `403`.

### `POST /admin/login`

Аутентификация администратора. Возвращает HMAC-токен с TTL 30 минут.

**Тело:**
```json
{
  "password": "my_secret_password"
}
```

**Ответ `200`:**
```json
{
  "token": "1745800000:a3f2b1c...",
  "expires_in": 1800
}
```

**Ошибки:**

| Код | Условие |
|-----|---------|
| `403` | `GRANITE_ADMIN_PASSWORD` не задана |
| `401` | Неверный пароль |

### `POST /companies/batch/approve`

Массовое подтверждение компаний — снять флаг `needs_review`.

**Заголовок:** `X-Admin-Token: <token>` (получен из `/admin/login`)

**Тело:**
```json
{
  "company_ids": [1, 2, 3]
}
```

**Ответ:**
```json
{"ok": true, "processed": 3}
```

**Ошибки:**

| Код | Условие |
|-----|---------|
| `401` | Токен отсутствует или недействителен |
| `403` | Admin-режим не настроен |

### `POST /companies/batch/spam`

Массовая пометка компаний как спам. Устанавливает `segment=spam`, `deleted_at`, `stop_automation=1`.

**Заголовок:** `X-Admin-Token: <token>`

**Тело:**
```json
{
  "company_ids": [5, 6],
  "reason": "aggregator"
}
```

**reason:** `aggregator` | `closed` | `wrong_category` | `duplicate_contact` | `other`

**Ответ:**
```json
{"ok": true, "processed": 2}
```

**Ошибки:**

| Код | Условие |
|-----|---------|
| `401` | Токен отсутствует или недействителен |
| `403` | Admin-режим не настроен |
