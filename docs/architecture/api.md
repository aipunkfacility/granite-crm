<!-- Обновлено: 2026-04-25 -->
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

Проверка доступности SMTP-сервера.

**Ответ:**
```json
{"status": "ok", "smtp": true}
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
| `include_deleted` | int | Показать удалённые (0/1) |
| `min_score` | int | Минимальный CRM-score |
| `max_score` | int | Максимальный CRM-score |
| `tg_trust_min` | int | Минимальный TG Trust (0-3) |
| `tg_trust_max` | int | Максимальный TG Trust (0-3) |
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

### `POST /companies/{id}/mark-spam`

Пометить компанию как спам.

**Тело:**
```json
{
  "reason": "Нежелательный контакт"
}
```

**Ответ:** `{ok: true}`

### `POST /companies/{id}/unmark-spam`

Восстановить компанию из спама.

**Ответ:** `{ok: true}`

### `POST /companies/{id}/mark-duplicate`

Пометить компанию как дубликат.

**Тело:**
```json
{
  "target_id": 42
}
```

**Ответ:** `{ok: true}`

### `POST /companies/{id}/resolve-review`

Разрешить статус needs_review.

**Тело:**
```json
{
  "action": "approve",
  "reason": "Проверено",
  "target_id": null
}
```

**action:** `approve` | `spam` | `duplicate`. `reason` и `target_id` опциональны.

**Ответ:** `{ok: true}`

### `POST /companies/batch/approve`

Массово снять флаг needs_review (требует admin).

**Тело:**
```json
{
  "company_ids": [1, 2, 3]
}
```

**Ответ:** `{ok: true, updated: 3}`

### `POST /companies/batch/spam`

Массово пометить как спам (требует admin).

**Тело:**
```json
{
  "company_ids": [4, 5, 6]
}
```

**Ответ:** `{ok: true, updated: 3}`

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

### `GET /companies/{id}/touches/{touch_id}`

Получить конкретное касание.

**Ответ:** `TouchResponse`

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

### `GET /companies/{id}/tasks`

Список задач для конкретной компании.

**Ответ:** `list[TaskResponse]`

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

**Параметры:**

| Параметр | Тип | Описание |
|----------|-----|----------|
| `channel` | string | Фильтр по каналу (опционально) |
| `include_retired` | int | Включить архивные шаблоны (0/1, default: 0) |

**Ответ:** `PaginatedResponse[TemplateResponse]`

### `GET /templates/{name}`

Получить шаблон по имени.

**Ответ:** `TemplateResponse`

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
- `name` — только `[a-z0-9_]`
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
  "subject_a": "Тема письма A",
  "subject_b": "Тема письма B",
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

### `GET /campaigns/{id}/stats`

Статистика кампании.

**Ответ:** `CampaignStatsResponse`

### `GET /campaigns/{id}/ab-stats`

Статистика A/B тестирования кампании.

**Ответ:**
```json
{
  "variants": {
    "A": {"subject": "Тема A", "sent": 50, "opened": 10, "replied": 3, "reply_rate": 6.0},
    "B": {"subject": "Тема B", "sent": 50, "opened": 15, "replied": 5, "reply_rate": 10.0}
  },
  "winner": "B",
  "note": "Variant B has higher reply rate"
}
```

### `GET /campaigns/{id}/progress`

SSE-стрим прогресса кампании.

**Ответ:** SSE stream
```
event: progress
data: {"sent": 10, "total": 50, "current": "Компания X"}

event: complete
data: {"sent": 50, "opened": 0, "errors": 2}
```

### `POST /campaigns/stale`

Сбросить «зависшие» кампании (running дольше `STALE_CAMPAIGN_MINUTES` из env, по умолчанию 10 минут).

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

---

## 8. Follow-up

### `GET /followup`

Очередь компаний для повторного контакта.

**Параметры:** `city` (опционально)

**Ответ:** `list[FollowupItemResponse]`

Каждый элемент содержит: компанию, рекомендованный канал, шаблон, количество дней с последнего контакта.

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

> **Примечание:** В таблице `crm_email_logs` поле `campaign_id` — внешний ключ с `ON DELETE SET NULL` (не просто INTEGER).

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

## 15. Справочники

### `GET /cms-types`

Список уникальных значений CMS.

**Ответ:** `list[str]`

### `GET /source-types`

Список уникальных значений источников данных.

**Ответ:** `list[str]`

---

## 16. Администрирование

### `POST /admin/login`

Аутентификация администратора.

**Тело:**
```json
{
  "password": "admin_password"
}
```

**Ответ:** `{ok: true, token: "..."}`
