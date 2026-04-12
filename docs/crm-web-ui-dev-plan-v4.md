# Granite CRM — Web UI: подробный дев-план (Версия 4.0 — финальная)

**Дата:** 2026-04-12
**Стек:** Next.js 16 (App Router), TypeScript, Tailwind CSS 4, shadcn/ui
**Управление состоянием и кэширование:** TanStack React Query v5
**Синхронизация URL-стейта:** nuqs
**Бэкенд:** Granite CRM REST API (FastAPI, `feat/web-search-scraper`, HEAD `703e969`)
**Аутентификация:** не требуется (локальное использование одним пользователем)

---

## 1. Архитектура

### 1.1 Принципы

*   **Next.js App Router** — маршрутизация средствами фреймворка. Server Components используются **только** для корневого Layout, Sidebar и метаданных. Все таблицы, панели, фильтры — `"use client"`.
*   **API-first** — UI это тонкая оболочка над существующим REST API. Все данные приходят через `/api/v1/...`.
*   **Настраиваемый API URL** — `NEXT_PUBLIC_CRM_API_URL` (dev: `http://localhost:8000`, prod: часть деплоя).
*   **Глубокие ссылки (Deep linking)** — состояние таблиц (пагинация, фильтры) хранится в URL Search Parameters через библиотеку `nuqs`.
*   **Реактивное кэширование** — TanStack React Query v5 для мгновенной навигации и инвалидации.
*   **Аутентификация не требуется** — проект для локального использования. JWT/OAuth не реализуются.
*   **Responsive** — основной viewport 1280px+ (десктоп), адаптивность до 1024px.

### 1.2 Структура маршрутов

Единый Layout с боковым Sidebar, контент рендерится через навигацию:

| # | Маршрут | Rendering | Назначение | Ключевые элементы |
|---|--------|-----------|-----------|-------------------|
| 1 | `/` | Server | Редирект на `/dashboard` | `redirect('/dashboard')` |
| 2 | `/dashboard` | Client | Обзор + KPI | Воронка, счётчики, таблица |
| 3 | `/companies` | Client | Список компаний | Datatable, фильтры, пагинация, side panel |
| 4 | `/tasks` | Client | Задачи/напоминания | Datatable, фильтры, CRUD |
| 5 | `/campaigns` | Client | Email-кампании | Список, создание, SSE-прогресс, статистика |
| 6 | `/followup` | Client | Очередь follow-up | Список, batch-send |
| 7 | `/templates` | Client | База шаблонов | Список, редактор с превью |

**Side Panel для компании:** открывается через `?companyId=123` в URL на странице `/companies`. Это не отдельный роут — просто query-параметр, управляющий видимостью панели поверх таблицы.

### 1.3 Физическая структура проекта

```
src/
├── app/
│   ├── layout.tsx               # Root layout — Server Component (meta, fonts, Providers)
│   ├── page.tsx                 # Server Component — redirect to /dashboard
│   ├── (main)/                  # Route group
│   │   ├── layout.tsx           # Server Component — Sidebar, Header (static, без данных)
│   │   ├── dashboard/page.tsx   # "use client" — KPI, funnel, таблица
│   │   ├── companies/page.tsx   # "use client" — таблица + side panel
│   │   ├── tasks/page.tsx       # "use client" — таблица задач
│   │   ├── campaigns/page.tsx   # "use client" — кампании + SSE
│   │   ├── followup/page.tsx    # "use client" — очередь follow-up
│   │   └── templates/page.tsx   # "use client" — редактор шаблонов
│   └── globals.css              # Tailwind CSS 4
├── lib/
│   ├── api-client.ts            # fetch-wrapper + error interceptor + API status tracking
│   ├── query-client.ts          # QueryClient с настройками (staleTime, gcTime)
│   ├── types.ts                 # TypeScript типы — Раздел 6
│   └── utils.ts                 # cn(), formatDate() и прочие хелперы
├── components/
│   ├── layout/
│   │   ├── sidebar.tsx          # Server Component — навигация через <Link>
│   │   └── header.tsx           # "use client" — индикатор API, breadcrumbs
│   ├── dashboard/               # "use client" — kpi-cards, funnel-chart, recent-table
│   ├── companies/               # "use client" — data-table, filters-bar, company-panel
│   ├── tasks/                   # "use client" — data-table, task-dialog
│   ├── campaigns/               # "use client" — list, create-dialog, run-progress, stats
│   ├── followup/                # "use client" — queue-list, batch-send-button
│   ├── templates/               # "use client" — template-list, template-editor
│   └── ui/                      # shadcn/ui (button, dialog, select, table, badge...)
└── hooks/
    ├── queries/                 # useCompanies, useCompany, useTasks, useFunnel, useFollowup...
    ├── mutations/               # useUpdateCompany, useCreateTask, usePatchTask...
    ├── use-sse.ts               # SSE Hook для кампаний
    └── use-api-status.ts        # Глобальный статус подключения к API
```

### 1.4 API Client и React Query

**Два слоя:**

1.  **`api-client.ts`** — тонкий fetch-wrapper. Базовый URL из `NEXT_PUBLIC_CRM_API_URL`. Перехватывает network errors → обновляет глобальный статус через `use-api-status.ts`. При первой ошибке включает фоновый пинг `/health` (каждые 15 сек) до восстановления. Не использует axios — достаточно нативного fetch.

2.  **React Query хуки** — инкапсулируют queryKey, queryFn, кэширование.

```typescript
// hooks/queries/useCompanies.ts
import { useQuery, keepPreviousData } from '@tanstack/react-query';
import { getCompanies } from '@/lib/api-client';
import type { CompanyFilters } from '@/lib/types';

export const useCompanies = (filters: CompanyFilters) => {
  return useQuery({
    queryKey: ['companies', filters],
    queryFn: () => getCompanies(filters),
    placeholderData: keepPreviousData,
  });
};
```

**Инвалидация:** при завершении мутации (PATCH компании, POST задачи) → `queryClient.invalidateQueries({ queryKey: ['companies'] })`. React Query обновит данные прозрачно на фоне.

### 1.5 Соглашения по компонентам

| Слой | Директива | Данные | Примеры |
|---|---|---|---|
| `app/layout.tsx`, `app/(main)/layout.tsx` | Server Component | Нет API-вызовов | HTML-обёртка, `<html>`, `<body>`, Sidebar |
| `components/layout/sidebar.tsx` | Server Component | Нет (статические ссылки) | Навигация, `usePathname()` для active state |
| `components/layout/header.tsx` | `"use client"` | API status из контекста | Индикатор подключения |
| Все `components/*/*.tsx` | `"use client"` | React Query хуки | Таблицы, панели, диалоги |
| Все `app/(main)/*/page.tsx` | `"use client"` | React Query хуки | Страницы с данными |

**Загрузка:** на клиенте отображаются спиннеры или skeleton-компоненты. SSR pre-fetching данных не используется — CRM не требует SEO и усложняет код.

---

## 2. Фазы реализации

### Фаза 0 — Фундамент и Инфраструктура

*   **Root Layout** (`app/layout.tsx`) — Server Component с `<html>`, `<body>`, шрифтами, метаданными. Оборачивает children в `<QueryClientProvider>`.
*   **Main Layout** (`app/(main)/layout.tsx`) — Server Component с Sidebar и `<Outlet />` (Next.js: `{children}`).
*   **Sidebar** — Server Component. Навигация через `<Link>`. Активный пункт определяется через `usePathname()` (клиентский хелпер внутри серверного компонента не нужен — достаточно сравнения в CSS/className через `clsx`).
*   **API Client** (`lib/api-client.ts`) — fetch-wrapper с базовым URL, обработкой ошибок, JSON-парсингом.
*   **API Status** (`hooks/use-api-status.ts`) — React Context + хук. Глобальный state: `"connected"` / `"error"`. Header рендерит индикатор на основе этого контекста.
*   **Types** (`lib/types.ts`) — все TypeScript типы из Раздела 6.
*   **shadcn/ui init** — установить `button`, `dialog`, `select`, `table`, `badge`, `input`, `textarea`, `dropdown-menu`, `pagination`, `tooltip`, `skeleton`, `card`, `alert`, `switch`, `tabs`.

### Фаза 1 — Dashboard

*   **Источники данных (3 параллельных запроса):**
    *   `GET /api/v1/funnel` → `{new: N, email_sent: N, ...}`.
    *   `GET /api/v1/companies?per_page=1` → `total` = общее число компаний.
    *   `GET /api/v1/tasks?per_page=1` → `total` = общее число задач.
*   **KPI-карточки (4 шт.):**
    1.  Всего компаний (из `companies.total`).
    2.  Активных задач (из `tasks.total`, или `?status=pending`).
    3.  Конверсия email: `email_opened / email_sent * 100`% (из funnel).
    4.  Ответивших (из `funnel.replied`).
*   **Funnel Chart** — div-based. Каждая стадия — горизонтальный bar, ширина пропорциональна числу. Цвета из Tailwind palette (от серого `new` до зелёного `interested`).
*   **Таблица "Последние компании"** — `/companies?per_page=5&order_by=crm_score&order_dir=desc`. Кликабельные строки (ведут на `/companies?companyId={id}`).

### Фаза 2 — Компании: Список, Фильтры и Side Panel

#### Фаза 2a — Таблица и URL-фильтры

*   **URL-стейт через `nuqs`:** все фильтры синхронизированы с URL.
    ```typescript
    // companies/page.tsx
    const [search, setSearch] = useQueryState('search', { defaultValue: '' });
    const [stage, setStage] = useQueryState('funnel_stage');
    const [page, setPage] = useQueryState('page', { defaultValue: '1', parse: Number });
    const [orderBy, setOrderBy] = useQueryState('order_by', { defaultValue: 'crm_score' });
    const [orderDir, setOrderDir] = useQueryState('order_dir', { defaultValue: 'desc' });
    ```
*   **Пример URL:** `/companies?page=2&search=ООО&funnel_stage=new&funnel_stage=email_sent`
*   **Фильтры (текущий бэкенд):**
    *   `funnel_stage` — строка, одно значение. Multi-select — после бэкенд-обновления (п. 3.1).
    *   `has_telegram` — toggle (0/1).
    *   `has_email` — toggle (0/1).
    *   `min_score` — number input.
    *   `city`, `search` — текстовые поля.
*   **Сортировка:** клик по заголовку колонки → обновляет `order_by` и `order_dir` в URL.
    *   Допустимые `order_by`: `crm_score`, `name_best`, `city`, `funnel_stage`.
*   **Пагинация:** shadcn `Pagination` → обновляет `page` в URL.
*   **Колонки таблицы:** Название, Город, Стадия (badge), CRM Score, Email (иконка-индикатор), TG (иконка), WA (иконка), Последний контакт.

#### Фаза 2b — Company Detail (Side Panel)

*   **Открытие:** клик на строку → `setCompanyId(id)`. Панель появляется справа (400px width), таблица сужается. URL: `/companies?companyId=123`. Закрытие — крестик или `setCompanyId(null)`.
*   **Данные:** `GET /api/v1/companies/{id}` через `useCompany(id)`. Панель показывает skeleton пока загружается.
*   **Поля (секции):**

    *   **Шапка:** название, город, сегмент, CRM score (badge).
    *   **Контакты:** телефоны, emails, сайт, telegram, whatsapp, vk — кликабельные ссылки.
    *   **CRM-статус:** funnel_stage (dropdown для смены), stop_automation (Switch toggle), заметки (textarea).
    *   **Счётчики:** email_sent / email_opened / tg_sent / wa_sent.

*   **PATCH-мутации:**
    *   `funnel_stage` — `<Select>` со всеми стадиями. При выборе → `PATCH /api/v1/companies/{id}` → инвалидация кэша.
    *   `notes` — `<Textarea>` с автосохранением: `onBlur` + `Cmd/Ctrl+Enter`. Индикатор "Сохранено ✓" (green) / "Не сохранено" (yellow) / "Ошибка" (red).
    *   `stop_automation` — shadcn `<Switch>`. При toggle → PATCH. Визуально: если включён — оранжевый badge "Автоматизация остановлена".

*   **Вкладки внутри панели:**
    1.  **Касания** — `GET /api/v1/companies/{id}/touches` → хронология (channel badge, direction, subject, date). Пустое состояние: "Нет записей".
    2.  **Задачи** — список задач этой компании + кнопка "+ Задача" → модальное окно создания.
    3.  **Отправить** — кнопки "Telegram" и "WhatsApp" → `POST /api/v1/companies/{id}/send` с `channel: "tg"` или `"wa"`. После бэкенд-доработки (п. 3.3) — также кнопка "Email".

### Фаза 3 — Задачи (Tasks)

*   **Список:** `GET /api/v1/tasks` → пагинированный.
    *   Фильтры в URL: `status`, `priority`, `company_id`.
    *   *Multi-select по `status` — после бэкенд-обновления (п. 3.1).*
*   **Поля ответа:** `id`, `company_id`, `title`, `task_type`, `priority`, `status`, `due_date`, `created_at`.
    *   `company_name` — добавляется через JOIN на бэкенде (п. 3.5). **Фронтенд не должен resolve название компании сам** — это N+1 проблема при пагинации.
*   **Task types:** `follow_up`, `send_portfolio`, `send_test_offer`, `check_response`, `other` (после бэкенд-обновления п. 3.6). До обновления — `follow_up`, `send_portfolio`, `call`, `other`.
*   **Колонки:** Название компании, Заголовок, Тип (badge), Приоритет (color dot), Статус (badge), Дедлайн, Действия.
*   **Быстрые действия:**
    *   Чекбокс → toggle `pending ↔ done`. Оптимистичный апдейт: UI меняется мгновенно, PATCH идёт в фоне. При ошибке — rollback.
    *   Клик по строке → открытие модального окна редактирования.
    *   Кнопка удаления (trash icon) → `DELETE /api/v1/tasks/{id}` с подтверждением (`AlertDialog`).
*   **Создание задачи:** кнопка "+ Задача" в header'е. Модальное окно:
    *   `title` (Input, required).
    *   `task_type` (Select).
    *   `priority` (Select: low/normal/high).
    *   `due_date` (DatePicker).
    *   `company_id` (опционально, если создаётся из контекста компании — презаполняется).
    *   `description` (Textarea).

### Фаза 4 — Кампании (Campaigns)

*   **Список:** `GET /api/v1/campaigns` → массив (не пагинирован). Колонки: Название, Шаблон, Статус (badge), Отправлено, Открыто, Ответили, Дата.
*   **Создание:** кнопка "+ Кампания" → Dialog:
    *   `name` (Input, required).
    *   `template_name` (Select из GET /templates — после п. 3.2).
    *   `filters` — группа: `city` (Input), `segment` (Input), `min_score` (Number).
*   **Детали:** клик на кампанию → раскрытие карточки с:
    *   Статистика: `GET /api/v1/campaigns/{id}/stats` → `open_rate` и т.д.
    *   Фильтры, с которыми была создана.
    *   Кнопка "Запустить" (если `status != running`).
*   **Запуск (SSE):**
    *   Кнопка "Запустить" → `POST /api/v1/campaigns/{id}/run`.
    *   Хук `useCampaignSSE` подписывается на `text/event-stream`.
    *   **UI прогресса:** progress bar + `"Отправлено: {sent} из {total}"` + текущий email.
    *   По завершении — уведомление toast: `"Кампания завершена: {sent} писем отправлено"`.
    *   Кнопка "Отмена" — закрывает EventSource (бэкенд пометит кампанию как `paused`).
*   **SSE формат (документация для хука):**
    ```
    data: {"status": "started", "total": 42}
    data: {"sent": 1, "total": 42, "current": "shop1@mail.ru"}
    data: {"sent": 2, "total": 42, "current": "shop2@mail.ru"}
    ...
    data: {"status": "completed", "sent": 42, "total": 42}
    ```
    Ошибки: `data: {"error": "Campaign not found"}` / `data: {"error": "Already running"}` / `data: {"error": "Template 'xxx' not found"}`.
*   **Лимиты бэкенда:** 3 сек между отправками, батч-коммит каждые 10, макс. 100 за запуск.
*   **Tracking pixel:** бэкенд автоматически вставляет `<img>` в письма. UI не участвует.

### Фаза 5 — Очередь Follow-up

*   **Список:** `GET /api/v1/followup?limit=100` → массив с рекомендациями.
*   **Колонки:** Компания, Город, Стадия, Дней с последнего контакта, Рекомендуемый канал (badge), Шаблон, Действие (badge), Кнопка "Отправить".
*   **Fallback каналов:** если `recommended_channel = tg`, но TG отсутствует → `wa`. Если и WA нет → `channel_available = false` (кнопка disabled, tooltip: "Нет контактных данных").
*   **Индивидуальная отправка:** кнопка "Отправить" → `POST /api/v1/companies/{company_id}/send` с `channel` и `template_name` из очереди. После успеха — refetch очереди.
*   **Batch Send ("Отправить всё"):**
    *   **Критично:** используется `for...of` с `await` (строгая последовательность, concurrency = 1). **Не `Promise.all`** — браузер ограничивает до 6 одновременных соединений, а бэкенду нужна последовательность для корректной обработки.
    *   UI: progress bar + счётчик + Warning alert (жёлтый): *"Не закрывайте вкладку во время массовой отправки"*.
    *   Кнопка "Стоп" — прерывает цикл. Уже отправленные не откатываются.
*   **Skip:** нет отдельного endpoint. Для пропуска — открыть Company Detail Panel (кнопка-ссылка) и сменить стадию вручную.

### Фаза 6 — Шаблоны (Templates)

*   **CRUD** через `GET/POST/PATCH/DELETE /api/v1/templates` (после бэкенд-доработки п. 3.2).
*   **Список:** grid или table. Колонки: Имя, Канал (badge), Предпросмотр (первые 50 символов body).
*   **Существующие шаблоны в БД:** `cold_email_1` (email), `follow_up_email` (email), `tg_intro` (tg), `tg_follow_up` (tg), `wa_intro` (wa), `wa_follow_up` (wa).
*   **Редактор:** клик на шаблон → side panel или dialog.
    *   `name` (Input, disabled для существующих — первичный ключ).
    *   `channel` (Select: email/tg/wa).
    *   `subject` (Input, только для email-шаблонов).
    *   `body` (Textarea или простой WYSIWYG).
    *   **Подсветка переменных:** `{from_name}`, `{city}` — выделяются цветом/фоном в textarea (остальные переменные зарезервированы на будущее: `{company_name}`, `{website}`).
    *   **Превью:** кнопка "Превью" → подставляет тестовые данные → отображает результат.
*   **Создание:** кнопка "+ Шаблон" → dialog с полями name, channel, subject, body.

### Фаза 7 — Дополнения

*   Индивидуальная email-отправка из Company Detail Panel (п. 3.3).
*   Кнопка "Отправить тест" в Follow-up (создаёт task с `send_test_offer` type — п. 3.6).

### Фаза 8 — Полировка

*   Страница настроек (опционально): тестовые подключения TG/WA/Email.
*   Dark mode (опционально).
*   Виртуализация длинных списков (`@tanstack/react-virtual`).

---

## 3. Требования к бэкенду (Backend Requirements)

Перед или параллельно с разработкой UI:

### 3.1 Массивы в фильтрах (приоритет: средний)

`GET /api/v1/companies` и `GET /api/v1/tasks` — поддержка массивов в query-параметрах:

```python
# companies.py
@router.get("/companies")
async def list_companies(
    funnel_stage: Optional[List[str]] = Query(None),  # было: Optional[str]
    ...
):
    if funnel_stage:
        stmt = stmt.where(CrmContactRow.funnel_stage.in_(funnel_stage))
```

Формат запроса: `?funnel_stage=new&funnel_stage=email_sent`.

Аналогично для `GET /tasks?status=pending&status=in_progress`.

### 3.2 CRUD для шаблонов (приоритет: высокий)

Создать `granite/api/templates.py`:

| Метод | Endpoint | Описание |
|---|---|---|
| `GET` | `/api/v1/templates` | Список всех шаблонов |
| `GET` | `/api/v1/templates/{name}` | Один шаблон по имени |
| `POST` | `/api/v1/templates` | Создать шаблон |
| `PATCH` | `/api/v1/templates/{name}` | Обновить шаблон |
| `DELETE` | `/api/v1/templates/{name}` | Удалить шаблон |

Таблица `crm_templates` уже существует в БД (миграция `20260411_add_crm_tables`). Зарегистрировать роутер в `app.py`.

### 3.3 Индивидуальный Email-API (приоритет: средний)

`POST /api/v1/companies/{id}/send-email` — отправка email конкретной компании вне кампании.

Тело: `{subject: str, body: str, template_name?: str}`.

Логика: взять первый email из `emails[]`, рендерить шаблон (если `template_name` указан), отправить через `granite.email.sender`, записать touch, обновить счётчики и стадию.

### 3.4 `has_whatsapp` фильтр (приоритет: низкий)

Добавить в `GET /api/v1/companies`:
```python
has_whatsapp: Optional[int] = Query(None)
# → EnrichedCompanyRow.messengers (JSON) содержит ключ "whatsapp"
```

### 3.5 `company_name` в ответе `/tasks` (приоритет: высокий)

JOIN в `GET /api/v1/tasks`:
```python
stmt = (
    select(CrmTaskRow, CompanyRow.name_best.label("company_name"))
    .outerjoin(CompanyRow, CrmTaskRow.company_id == CompanyRow.id)
    .order_by(CrmTaskRow.created_at.desc())
)
```

Ответ добавляет поле `"company_name": "ООО Гранит-М"` (или `null` если компания удалена). Это единственный допустимый способ — фронтенд не должен resolve название сам (N+1 при пагинации).

### 3.6 Обновление task types (приоритет: высокий)

В `granite/api/schemas.py`:
```python
# Было:
task_type: str = Field(default="follow_up", pattern="^(follow_up|send_portfolio|call|other)$")

# Стало:
task_type: str = Field(default="follow_up", pattern="^(follow_up|send_portfolio|send_test_offer|check_response|other)$")
```

Удалить `call`, добавить `send_test_offer` и `check_response`. Обновить `update-templates-tasktypes.md` seed-скрипт.

### 3.7 Агрегирующий `/stats` endpoint (приоритет: низкий, опционально)

```
GET /api/v1/stats → {
  "companies_total": 1500,
  "tasks_total": 42,
  "tasks_pending": 15,
  "campaigns_total": 5,
  "campaigns_completed": 3
}
```

Без этого Dashboard делает 3 запроса (`/companies?per_page=1`, `/tasks?per_page=1`, `/funnel`). С `/stats` — 2 запроса (`/stats` + `/funnel`).

---

## 4. Funnel State Machine

Реализовано в `granite/api/stage_transitions.py`:

```
new → email_sent → email_opened → tg_sent → wa_sent → replied → interested
                                                                      ↘ not_interested
                                                                      ↘ unreachable
```

**Исходящие касания (outgoing):**

| Текущая стадия | `email` | `tg` | `wa` |
|---|---|---|---|
| `new` | → `email_sent` | → `tg_sent` | → `wa_sent` |
| `email_sent` | — | → `tg_sent` | → `wa_sent` |
| `email_opened` | — | → `tg_sent` | → `wa_sent` |
| `tg_sent` | — | — | → `wa_sent` |
| `wa_sent` | — | — | — |
| `replied` / `interested` / `not_interested` / `unreachable` | — | — | — |

**Входящие касания (incoming):** любая стадия (кроме `interested` / `not_interested`) → `replied`. Побочный эффект: `stop_automation = true`.

**Follow-up правила (бэкенд):**

| Стадия | Дней ожидания | Канал | Шаблон | Действие |
|---|---|---|---|---|
| `new` | 0 | email | `cold_email_1` | Отправить холодное письмо |
| `email_sent` | 4 | tg | `tg_intro` | Написать в Telegram |
| `email_opened` | 2 | tg | `tg_intro` | Написать в TG (открыл письмо!) |
| `tg_sent` | 4 | wa | `wa_intro` | Написать в WhatsApp |
| `wa_sent` | 7 | email | `follow_up_email` | Финальное письмо |

Fallback каналов: `tg` → `wa` → `channel_available = false`.

---

## 5. SSE Events Reference

**Endpoint:** `POST /api/v1/campaigns/{campaign_id}/run`
**Content-Type:** `text/event-stream`

```
data: {"status": "started", "total": 42}

data: {"sent": 1, "total": 42, "current": "shop1@mail.ru"}

data: {"sent": 2, "total": 42, "current": "shop2@mail.ru"}

...

data: {"status": "completed", "sent": 42, "total": 42}
```

Ошибки (не прерывают stream):
```
data: {"error": "Campaign not found"}
data: {"error": "Already running"}
data: {"error": "Template 'xxx' not found"}
```

**Хук `use-sse.ts`:**
```typescript
interface CampaignSSECallbacks {
  onProgress: (sent: number, total: number, current: string) => void;
  onComplete: (sent: number, total: number) => void;
  onError: (message: string) => void;
}

function useCampaignSSE(
  campaignId: number | null,
  callbacks: CampaignSSECallbacks
): { isRunning: boolean; cancel: () => void }
```

Реализация: `new EventSource(...)` не поддерживает POST → использовать `fetch` с `ReadableStream` или `@microsoft/fetch-event-source`. При `cancel()` — закрыть stream (бэкенд пометит кампанию как `paused`).

---

## 6. TypeScript Types

```typescript
// ===== Funnel =====
type FunnelStage =
  | 'new' | 'email_sent' | 'email_opened'
  | 'tg_sent' | 'wa_sent'
  | 'replied' | 'interested' | 'not_interested' | 'unreachable';

const FUNNEL_STAGES: FunnelStage[] = [
  'new', 'email_sent', 'email_opened', 'tg_sent', 'wa_sent',
  'replied', 'interested', 'not_interested', 'unreachable',
];

const FUNNEL_STAGE_LABELS: Record<FunnelStage, string> = {
  new: 'Новые',
  email_sent: 'Email отправлен',
  email_opened: 'Email открыт',
  tg_sent: 'TG отправлено',
  wa_sent: 'WA отправлено',
  replied: 'Ответили',
  interested: 'Заинтересованы',
  not_interested: 'Не заинтересованы',
  unreachable: 'Недоступны',
};

interface FunnelCounts {
  new: number;
  email_sent: number;
  email_opened: number;
  tg_sent: number;
  wa_sent: number;
  replied: number;
  interested: number;
  not_interested: number;
  unreachable: number;
}

// ===== Company =====
interface Company {
  id: number;
  name: string;
  phones: string[];
  website: string | null;
  emails: string[];
  city: string | null;
  segment: string | null;
  crm_score: number | null;
  cms: string | null;
  has_marquiz: boolean | null;
  is_network: boolean | null;
  telegram: string | null;
  whatsapp: string | null;
  vk: string | null;
  messengers: Record<string, string>;
  tg_trust: Record<string, unknown>;
  funnel_stage: FunnelStage | null;
  email_sent_count: number;
  email_opened_count: number;
  tg_sent_count: number;
  wa_sent_count: number;
  last_contact_at: string | null;
  notes: string | null;
  stop_automation: boolean;
}

interface CompanyListResponse {
  items: Company[];
  total: number;
  page: number;
  per_page: number;
}

interface CompanyFilters {
  city?: string;
  segment?: string;
  funnel_stage?: FunnelStage | FunnelStage[];
  has_telegram?: 0 | 1;
  has_email?: 0 | 1;
  has_whatsapp?: 0 | 1;          // после п. 3.4
  min_score?: number;
  search?: string;
  page?: number;
  per_page?: number;
  order_by?: 'crm_score' | 'name_best' | 'city' | 'funnel_stage';
  order_dir?: 'asc' | 'desc';
}

interface UpdateCompanyRequest {
  funnel_stage?: FunnelStage;
  notes?: string;
  stop_automation?: boolean;
}

// ===== Touch =====
type TouchChannel = 'email' | 'tg' | 'wa' | 'manual';
type TouchDirection = 'outgoing' | 'incoming';

interface Touch {
  id: number;
  channel: TouchChannel;
  direction: TouchDirection;
  subject: string;
  body: string;
  note: string;
  created_at: string;
}

// ===== Task =====
type TaskType = 'follow_up' | 'send_portfolio' | 'send_test_offer' | 'check_response' | 'other';
type TaskPriority = 'low' | 'normal' | 'high';
type TaskStatus = 'pending' | 'in_progress' | 'done' | 'cancelled';

interface Task {
  id: number;
  company_id: number;
  company_name: string | null;    // после п. 3.5 (JOIN). null если компания удалена.
  title: string;
  task_type: TaskType;
  priority: TaskPriority;
  status: TaskStatus;
  due_date: string | null;
  created_at: string;
}

interface TaskListResponse {
  items: Task[];
  total: number;
  page: number;
  per_page: number;
}

interface CreateTaskRequest {
  title?: string;
  description?: string;
  due_date?: string;
  priority?: TaskPriority;
  task_type?: TaskType;
}

interface UpdateTaskRequest {
  status?: TaskStatus;
  priority?: TaskPriority;
  title?: string;
}

// ===== Campaign =====
type CampaignStatus = 'draft' | 'running' | 'completed' | 'paused';

interface Campaign {
  id: number;
  name: string;
  template_name: string;
  status: CampaignStatus;
  filters: Record<string, unknown>;
  total_sent: number;
  total_opened: number;
  total_replied: number;
  open_rate?: number;
  created_at: string;
}

interface CampaignStats {
  id: number;
  name: string;
  status: CampaignStatus;
  total_sent: number;
  total_opened: number;
  total_replied: number;
  open_rate: number;
}

interface CreateCampaignRequest {
  name?: string;
  template_name?: string;
  filters?: {
    city?: string;
    segment?: string;
    min_score?: number;
  };
}

// ===== Follow-up =====
interface FollowupItem {
  company_id: number;
  name: string;
  city: string | null;
  funnel_stage: FunnelStage;
  days_since_last_contact: number;
  recommended_channel: 'email' | 'tg' | 'wa';
  channel_available: boolean;
  template_name: string;
  action: string;
  telegram: string | null;
  whatsapp: string | null;
  emails: string[];
  crm_score: number | null;
  segment: string | null;
}

// ===== Messenger =====
type SendChannel = 'tg' | 'wa';   // после п. 3.3: 'tg' | 'wa' | 'email'

interface SendMessageRequest {
  channel: SendChannel;
  template_name?: string;
  text?: string;
}

interface SendMessageResponse {
  ok: boolean;
  channel: string;
  contact_id: string | null;
  error: string | null;
}

// ===== Template (после п. 3.2) =====
interface Template {
  name: string;
  channel: 'email' | 'tg' | 'wa';
  subject: string | null;
  body: string;
  variables: string[];
  created_at?: string;
  updated_at?: string;
}
```

---

## 7. Сводная оценка компонентов

| Роут | API Calls | UI Компоненты | Сложность |
|---|---|---|---|
| `/dashboard` | `GET /funnel`, `GET /companies?per_page=1`, `GET /tasks?per_page=1` | KPI Cards, Funnel Chart, Recent Table | Средняя |
| `/companies` | `GET /companies`, `GET /companies/{id}`, `PATCH`, `GET /touches`, `POST /tasks`, `POST /send` | Datatable, Filters Bar, Side Panel, Tabs | Высокая |
| `/tasks` | `GET /tasks`, `POST /tasks`, `PATCH /tasks/{id}`, `DELETE /tasks/{id}` | Datatable, Checkbox, Dialog | Средняя |
| `/campaigns` | `GET /campaigns`, `POST /campaigns`, `GET /{id}`, `POST /{id}/run` (SSE), `GET /{id}/stats` | List, Dialog, Progress Bar, Stats Cards | Высокая |
| `/followup` | `GET /followup`, `POST /send` | List, Batch Send (sequential), Warning Alert | Средняя |
| `/templates` | `GET/POST/PATCH/DELETE /templates` | Grid/List, Editor, Variable Highlight, Preview | Средняя |

---

## 8. Запуск среды разработки

```bash
# Фронтенд (Next.js)
NEXT_PUBLIC_CRM_API_URL=http://localhost:8000 bun run dev

# Бэкенд (FastAPI)
python cli.py api
# или
uvicorn granite.api.app:app --reload --port 8000
```

---

## 9. Порядок работы

```
БЭКЕНД (параллельно)          ФРОНТЕНД (последовательно)
─────────────────────         ─────────────────────────
п. 3.2 Templates CRUD  ──┐
п. 3.5 company_name JOIN ─┤  Фаза 0: Фундамент
п. 3.6 Task types       ─┘  Фаза 1: Dashboard
                              │
п. 3.1 Массивы фильтров ──┐   │
п. 3.3 Email send       ─┤   ├─ Фаза 2: Компании
                              ├─ Фаза 3: Задачи
                              ├─ Фаза 4: Кампании
                              │
п. 3.4 has_whatsapp     ──┐   │
п. 3.7 /stats           ─┘   ├─ Фаза 5: Follow-up
                              ├─ Фаза 6: Шаблоны
                              ├─ Фаза 7: Дополнения
                              └─ Фаза 8: Полировка
```

**Блокировки:** Фаза 6 (Templates UI) заблокирована до п. 3.2. Остальные фазы можно начинать без бэкенд-доработок (с ограничениями функциональности).
