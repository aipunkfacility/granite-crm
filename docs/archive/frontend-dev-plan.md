Изучил весь код бэкенда и документ по фронтенду. Вот детальный дев-план для агента.

---

# Детальный дев-план: Granite CRM Frontend

## Общая оценка текущего состояния

Бэкенд полностью готов. API покрывает все необходимые экраны. Есть несколько важных уточнений к документу дизайна, которые нужно учесть.

---

## Поправки к исходному документу

**Неточности в API-таблице из документа:**
- Эндпоинт `/companies/{id}` возвращает поле `name`, не `name_best` (это поле CompanyRow, в EnrichedCompanyRow — `name`)
- Поле `score_segment` не существует — правильное название `segment`
- Для создания задач нужен `POST /companies/{id}/tasks`, которого нет в таблице
- Отсутствуют полезные эндпоинты: `/cities`, `/regions`, `/pipeline/status`, `/campaigns`, `/templates`, `GET /tasks` с join-данными

**Важные поведенческие детали из кода:**
- `stop_automation` — integer (0/1), не boolean, хотя в ответе маппится в bool
- `funnel_stage` имеет 9 допустимых значений (включая `unreachable`)
- `task_type` — `call` удалён, допустимые: `follow_up`, `send_portfolio`, `send_test_offer`, `check_response`, `other`
- `segment` может быть `spam` (score=0) — нужно отображать
- Кампании возвращают SSE при `/campaigns/{id}/run` — нужен специальный обработчик
- `deleted_at` — компании могут быть soft-deleted, фильтрация уже на бэке

---

## Фаза 0: Инициализация (1 день)

### 0.1 Создание проекта

```bash
npx create-next-app@latest granite-web --typescript --tailwind --eslint --app --src-dir --import-alias "@/*"
cd granite-web
npx shadcn@latest init
```

Конфиг shadcn: style=default, base color=slate, CSS variables=yes.

### 0.2 Зависимости

```bash
npm install @tanstack/react-query@^5 axios lucide-react
npm install @tanstack/react-query-devtools --save-dev
```

shadcn компоненты (установить сразу все нужные):
```bash
npx shadcn@latest add table card badge button input select textarea dialog sheet toast tabs separator skeleton
```

### 0.3 Структура проекта

```
src/
├── app/
│   ├── layout.tsx
│   ├── page.tsx
│   ├── companies/
│   │   ├── page.tsx
│   │   └── [id]/page.tsx
│   ├── followup/page.tsx
│   ├── tasks/page.tsx
│   ├── campaigns/
│   │   ├── page.tsx
│   │   └── [id]/page.tsx
│   ├── pipeline/page.tsx
│   └── stats/page.tsx
├── components/
│   ├── layout/
│   │   ├── sidebar.tsx
│   │   └── page-header.tsx
│   ├── companies/
│   │   ├── company-table.tsx
│   │   ├── company-filters.tsx
│   │   ├── company-card.tsx
│   │   ├── company-crm-panel.tsx
│   │   └── segment-badge.tsx
│   ├── followup/
│   │   ├── followup-list.tsx
│   │   └── followup-item.tsx
│   ├── tasks/
│   │   ├── task-list.tsx
│   │   └── task-item.tsx
│   ├── campaigns/
│   │   ├── campaign-list.tsx
│   │   ├── campaign-card.tsx
│   │   └── campaign-run-progress.tsx
│   ├── pipeline/
│   │   └── pipeline-status-table.tsx
│   └── shared/
│       ├── pagination.tsx
│       ├── empty-state.tsx
│       ├── error-boundary.tsx
│       └── loading-skeleton.tsx
├── lib/
│   ├── api/
│   │   ├── client.ts          # axios instance
│   │   ├── companies.ts
│   │   ├── followup.ts
│   │   ├── tasks.ts
│   │   ├── campaigns.ts
│   │   ├── templates.ts
│   │   ├── stats.ts
│   │   └── pipeline.ts
│   ├── hooks/
│   │   ├── use-companies.ts
│   │   ├── use-followup.ts
│   │   ├── use-tasks.ts
│   │   ├── use-campaigns.ts
│   │   └── use-stats.ts
│   ├── types/
│   │   └── api.ts             # TypeScript типы из Pydantic схем
│   └── utils.ts
├── constants/
│   └── funnel.ts              # FUNNEL_STAGES, SEGMENT_CONFIG
└── providers/
    └── query-provider.tsx
```

### 0.4 Настройка клиента

`src/lib/api/client.ts`:
```typescript
import axios from 'axios'

export const apiClient = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000/api/v1',
  timeout: 15000,
})

// Перехватчик ошибок — парсит ErrorResponse из бэка
apiClient.interceptors.response.use(
  (r) => r,
  (err) => {
    const msg = err.response?.data?.error ?? err.message
    return Promise.reject(new Error(msg))
  }
)
```

`.env.local`:
```
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
```

---

## Фаза 1: Типы и API-слой (0.5 дня)

### 1.1 TypeScript типы

Файл `src/lib/types/api.ts` — строгое соответствие Pydantic схемам бэкенда:

```typescript
// Из CompanyResponse
export interface Company {
  id: number
  name: string
  phones: string[]
  website: string | null
  address: string | null
  emails: string[]
  city: string
  region: string
  messengers: Record<string, string>
  telegram: string | null
  whatsapp: string | null
  vk: string | null
  segment: 'A' | 'B' | 'C' | 'D' | 'spam' | null
  crm_score: number
  cms: string | null
  has_marquiz: boolean
  is_network: boolean
  tg_trust: Record<string, unknown>
  funnel_stage: FunnelStage
  email_sent_count: number
  email_opened_count: number
  tg_sent_count: number
  wa_sent_count: number
  last_contact_at: string | null
  notes: string
  stop_automation: boolean
}

export type FunnelStage =
  | 'new' | 'email_sent' | 'email_opened'
  | 'tg_sent' | 'wa_sent' | 'replied'
  | 'interested' | 'not_interested' | 'unreachable'

export type Segment = 'A' | 'B' | 'C' | 'D' | 'spam'

export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  per_page: number
}

// ... Task, Campaign, FollowupItem, Stats и т.д.
```

### 1.2 Константы воронки и сегментов

`src/constants/funnel.ts`:
```typescript
export const FUNNEL_STAGES: Record<FunnelStage, { label: string; color: string }> = {
  new: { label: 'Новый', color: 'slate' },
  email_sent: { label: 'Письмо отправлено', color: 'blue' },
  email_opened: { label: 'Письмо открыто', color: 'indigo' },
  tg_sent: { label: 'Написали в TG', color: 'violet' },
  wa_sent: { label: 'Написали в WA', color: 'green' },
  replied: { label: 'Ответили', color: 'emerald' },
  interested: { label: 'Заинтересованы', color: 'teal' },
  not_interested: { label: 'Не интересно', color: 'orange' },
  unreachable: { label: 'Недоступен', color: 'red' },
}

export const SEGMENT_CONFIG: Record<Segment, { label: string; variant: string }> = {
  A: { label: 'A', variant: 'success' },
  B: { label: 'B', variant: 'info' },
  C: { label: 'C', variant: 'warning' },
  D: { label: 'D', variant: 'secondary' },
  spam: { label: 'Spam', variant: 'destructive' },
}
```

---

## Фаза 2: Layout и навигация (0.5 дня)

### 2.1 Root Layout

`src/app/layout.tsx` — провайдеры, sidebar, Toaster.

### 2.2 Sidebar

`src/components/layout/sidebar.tsx`:

Навигация:
```
🏢 Компании        /companies
📋 Follow-up       /followup
✅ Задачи          /tasks
📧 Кампании        /campaigns
🔧 Пайплайн        /pipeline
📊 Статистика      /stats
```

Sidebar должен показывать badge с количеством для Follow-up (из `/stats` или отдельного запроса) — это мотивирует открыть очередь.

---

## Фаза 3: Экран компаний — неделя 1, дни 1-3

### 3.1 Хук useCompanies

```typescript
// src/lib/hooks/use-companies.ts
export function useCompanies(params: CompanyFilters) {
  return useQuery({
    queryKey: ['companies', params],
    queryFn: () => fetchCompanies(params),
    staleTime: 30_000,
    placeholderData: keepPreviousData, // не мигает при смене страницы
  })
}
```

Параметры фильтрации (все из API):
- `city[]` — массив (мультиселект)
- `segment` — A/B/C/D/spam
- `funnel_stage`
- `has_telegram` — 0/1
- `has_whatsapp` — 0/1
- `has_email` — 0/1
- `min_score`
- `search` — поиск по имени
- `page`, `per_page`
- `order_by`, `order_dir`

URL-синхронизация фильтров — использовать `useSearchParams` из Next.js. Это критично: пользователь должен иметь возможность скопировать URL с фильтрами.

### 3.2 Таблица компаний

Колонки (финальный вариант, с учётом реальных данных):

| # | Колонка | Поле | Примечания |
|---|---------|------|-----------|
| 1 | Название | `name` | Кликабельная, ведёт на карточку |
| 2 | Город | `city` | |
| 3 | Сегмент | `segment` | SegmentBadge |
| 4 | Score | `crm_score` | Число, сортируется |
| 5 | Телефон | `phones[0]` | `tel:` ссылка |
| 6 | Мессенджеры | `telegram`, `whatsapp` | Иконки-ссылки |
| 7 | Воронка | `funnel_stage` | Badge |
| 8 | Последний контакт | `last_contact_at` | Относительно: "3 дня назад" |

**Важно для сортировки:** бэкенд поддерживает `order_by` только для `crm_score`, `name_best`, `city`, `funnel_stage`. Не реализовывать сортировку по другим колонкам.

### 3.3 Карточка компании

Страница `/companies/[id]` — two-column layout:
- Левая (2/3): детали компании
- Правая (1/3): CRM-панель

**Левая колонка:**
1. Header: название, город/регион, сегмент+score
2. Контакты: телефоны (с иконкой копирования), email, сайт
3. Мессенджеры: кнопки "Открыть TG", "Открыть WA", "Открыть VK" — открывают ссылку
4. Технические данные: CMS, is_network, has_marquiz, tg_trust.trust_score
5. История касаний (Tabs: касания / задачи)

**Правая колонка (CRM Panel):**
1. Текущая стадия + кнопки смены стадии (все 9 вариантов в select или кнопки)
2. Заметки (textarea с debounced autosave — 1 сек задержки)
3. Stop automation toggle
4. Создать задачу (быстрая форма: тип + дата + приоритет)

**Autosave заметок:**
```typescript
const mutation = useMutation({
  mutationFn: (notes: string) => updateCompany(id, { notes }),
})
const debouncedSave = useDebouncedCallback(mutation.mutate, 1000)
```

---

## Фаза 4: Follow-up очередь — неделя 1, дни 4-5

### 4.1 Хук useFollowup

```typescript
export function useFollowup(params: FollowupFilters) {
  return useQuery({
    queryKey: ['followup', params],
    queryFn: () => fetchFollowup(params),
    refetchInterval: 60_000, // обновлять каждую минуту
  })
}
```

Параметры: `city[]`, `segment`, `page`, `per_page`.

### 4.2 Карточка follow-up

Каждый элемент списка:
- Название компании (ссылка)
- Город, сегмент
- Рекомендованный канал (цветной badge)
- Действие (текст из `action`)
- Кнопки: "Написал" (меняет стадию) + иконки для копирования контакта
- `channel_available=false` → серая карточка с пометкой "нет контакта"

**"Написал" — что делать:**
```typescript
// 1. POST /companies/{id}/touches с channel + direction=outgoing
// 2. Invalidate query ['followup']
// 3. Toast "✓ Касание записано"
```

---

## Фаза 5: Задачи — неделя 2, день 1

### 5.1 Список задач

GET `/tasks` уже возвращает `company_name` и `company_city` через JOIN. Это важно — не нужен отдельный запрос за данными компании.

Фильтры: `status`, `priority`, `task_type`.

Колонки: Задача, Компания (ссылка), Тип, Приоритет, Статус, Срок.

### 5.2 Управление задачами

PATCH `/tasks/{id}` для обновления статуса.

Быстрое закрытие: чекбокс рядом с задачей → `status: 'done'`.

**Важно:** DELETE `/tasks/{id}` тоже существует — добавить кнопку удаления.

---

## Фаза 6: Кампании — неделя 2, день 2

### 6.1 Список кампаний

Отображать статус с цветом: draft=серый, running=синий (пульсирующий), paused=жёлтый, completed=зелёный.

Показывать open_rate в процентах.

### 6.2 Создание кампании

Форма: имя + выбор шаблона (загружается из GET `/templates`) + фильтры (город, сегмент, min_score).

### 6.3 Запуск кампании — SSE

**Это нетривиально.** Бэкенд отдаёт Server-Sent Events:

```typescript
function runCampaign(campaignId: number, onProgress: (e: SSEEvent) => void) {
  const es = new EventSource(
    `${API_BASE}/campaigns/${campaignId}/run`
  )
  es.onmessage = (e) => {
    const data = JSON.parse(e.data)
    onProgress(data)
    if (data.status === 'completed' || data.error) {
      es.close()
    }
  }
  es.onerror = () => es.close()
  return () => es.close() // cleanup
}
```

Отображать прогресс-бар (sent/total).

**Ограничение:** `EventSource` не поддерживает кастомные заголовки. Если потребуется API-key аутентификация — придётся использовать fetch с ReadableStream.

---

## Фаза 7: Пайплайн — неделя 2, день 3

### 7.1 Статус пайплайна

GET `/pipeline/status` — таблица городов:

Колонки: Город, Регион, Стадия (scraped/deduped/enriched), Raw, Компании, Обогащено, Прогресс (progress bar), Сегменты.

### 7.2 Запуск пайплайна

POST `/pipeline/run` — тоже SSE. Аналогично кампаниям.

Форма: город (autocomplete из GET `/pipeline/cities`), force checkbox, re-enrich checkbox.

### 7.3 Справочник городов

GET `/pipeline/cities` — таблица: Город, Регион, is_populated, is_doppelganger.

---

## Фаза 8: Статистика — неделя 2, день 4

GET `/stats` — одна страница, 6 виджетов:

1. **Итого компаний** — большое число
2. **Воронка** — горизонтальные блоки (9 стадий) с числами
3. **Сегменты** — pie-chart или bar: A/B/C/D/spam
4. **Топ-10 городов** — bar chart горизонтальный
5. **Мессенджеры** — три числа: TG / WA / Email
6. **Фильтр по городу** — select, перезагружает все виджеты

Для графиков: использовать `recharts` (уже есть в проекте Next.js как зависимость через shadcn).

---

## Критические детали, которые легко упустить

### Обработка ошибок

Бэкенд всегда возвращает `ErrorResponse { error, code, detail }`. Interceptor в axios должен распаковывать `error` поле, иначе пользователь увидит "Request failed with status 422" вместо понятного сообщения.

### Мультиселект городов

API принимает `city[]` как повторяющийся query параметр:
```
/companies?city=Москва&city=Казань
```
axios по умолчанию сериализует массивы как `city[]=Москва`. Нужна явная настройка:
```typescript
paramsSerializer: (params) => qs.stringify(params, { arrayFormat: 'repeat' })
```

### Оптимистичные обновления

Для смены стадии воронки и обновления заметок — использовать `onMutate` / `onError` / `onSettled` TanStack Query для optimistic updates. Без этого интерфейс будет «тормозить» при частых кликах.

### `keepPreviousData` при пагинации

Без этого таблица будет мигать (исчезать и появляться) при переключении страниц:
```typescript
placeholderData: keepPreviousData
```

### Относительное время

Поле `last_contact_at` — ISO string. Использовать `date-fns/formatDistanceToNow` или `Intl.RelativeTimeFormat` — не устанавливать лишние библиотеки вроде moment.js.

### stop_automation

В бэкенде это `Integer` (0/1), хотя в ответе маппится как `boolean`. Слать в PATCH как `boolean`. При `stop_automation=true` — визуально отмечать компанию (серый фон строки или иконка предупреждения).

---

## Порядок реализации для агента

```
День 1:  Фаза 0 + Фаза 1 (инит, типы, API-слой)
День 2:  Фаза 2 + Фаза 3 (layout, список компаний)
День 3:  Фаза 3 (карточка компании)
День 4:  Фаза 4 (follow-up очередь)
День 5:  Фаза 5 (задачи)
День 6:  Фаза 6 (кампании + SSE)
День 7:  Фаза 7 (пайплайн + SSE)
День 8:  Фаза 8 (статистика + графики)
День 9:  Полировка: loading states, error states, empty states
День 10: Тестирование на реальных данных (granite.db с ~6000 компаний)
```

---

## Что НЕ делать (экономия времени)

- Не добавлять аутентификацию — локальное использование
- Не делать тёмную тему — shadcn поддерживает, но пустая трата времени
- Не писать unit-тесты для компонентов — не окупится для MVP
- Не делать i18n — интерфейс будет на русском как в документе
- Не оптимизировать bundle size до запуска в production
- Не добавлять PWA/offline — данные всегда с localhost:8000