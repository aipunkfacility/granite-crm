<!-- Обновлено: 2026-04-25 -->
# Фронтенд RetouchGrav CRM — Обзор

> Архитектура и паттерны фронтенда на Next.js 16.

---

## Стек

| Технология | Версия | Назначение |
|-----------|--------|-----------|
| Next.js | 16 | Фреймворк (App Router) |
| TypeScript | 5 | Типизация |
| Tailwind CSS | 4 | Стилизация |
| shadcn/ui | latest | UI-компоненты |
| TanStack Query | v5 | Кэширование и синхронизация с API |
| axios | latest | HTTP-клиент |

---

## Структура src/

```
src/
├── app/                    # Next.js App Router
│   ├── layout.tsx          # Корневой layout (QueryProvider, ThemeProvider)
│   ├── page.tsx            # Редирект → /companies
│   ├── companies/          # Список компаний + карточка [id]
│   ├── campaigns/          # Email-кампании
│   ├── templates/          # Шаблоны сообщений
│   ├── tasks/              # Задачи
│   ├── followup/           # Очередь follow-up
│   ├── review/             # На проверке
│   ├── pipeline/           # Мониторинг пайплайна
│   └── stats/              # Статистика
├── components/
│   ├── ui/                 # shadcn/ui (button, card, input, select, table...)
│   ├── companies/          # CompanyTable, CompanySheet, CompaniesFilters, BatchActionsBar...
│   ├── templates/          # TemplateFormDialog, TemplateCard, TemplatePreviewDialog
│   └── layout/             # Sidebar, AdminLoginDialog, ThemeToggle
├── lib/
│   ├── api/                # API-клиент
│   │   ├── client.ts       # axios-инстанс (baseURL из NEXT_PUBLIC_API_URL)
│   │   ├── companies.ts    # Методы для /companies
│   │   ├── campaigns.ts    # Методы для /campaigns
│   │   ├── templates.ts    # Методы для /templates
│   │   ├── tasks.ts        # Методы для /tasks
│   │   ├── followup.ts     # Методы для /followup
│   │   ├── pipeline.ts     # Методы для /pipeline
│   │   ├── stats.ts        # Методы для /stats
│   │   └── admin.ts        # Методы для /admin
│   ├── hooks/              # React Query хуки
│   │   ├── use-companies.ts
│   │   ├── use-campaigns.ts
│   │   ├── use-templates.ts
│   │   ├── use-tasks.ts
│   │   ├── use-followup.ts
│   │   ├── use-pipeline.ts
│   │   └── use-stats.ts
│   ├── types/              # TypeScript-типы
│   │   └── api.ts          # Типы, соответствующие Pydantic-схемам бэкенда
│   ├── admin-context.tsx   # Контекст режима администратора
│   └── utils.ts            # Утилиты (cn, форматирование)
├── constants/
│   └── funnel.ts           # Стадии воронки, сегменты
└── providers/
    └── query-provider.tsx  # TanStack Query провайдер
```

---

## API-клиент

`src/lib/api/client.ts` — axios-инстанс с базовым URL из `NEXT_PUBLIC_API_URL`:

```typescript
import axios from 'axios';

const apiClient = axios.create({
  baseURL: `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/v1`,
});
```

Каждый модуль (companies.ts, campaigns.ts и т.д.) экспортирует функции, которые используют `apiClient`:

```typescript
// lib/api/companies.ts
export const getCompanies = (params: CompanyFilters) =>
  apiClient.get('/companies', { params });

export const getCompany = (id: number) =>
  apiClient.get(`/companies/${id}`);
```

---

## React Query паттерны

### Чтение (useQuery)

```typescript
// lib/hooks/use-companies.ts
export function useCompanies(filters: CompanyFilters) {
  return useQuery({
    queryKey: ['companies', filters],
    queryFn: () => getCompanies(filters),
  });
}
```

### Запись (useMutation)

```typescript
export function useCreateCampaign() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: createCampaign,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['campaigns'] });
    },
  });
}
```

### Поллинг

Для данных, которые обновляются часто (статус пайплайна, прогресс кампаний):

```typescript
useQuery({
  queryKey: ['pipeline-status'],
  queryFn: getPipelineStatus,
  refetchInterval: 10000, // каждые 10 секунд
});
```

---

## Как добавить новую страницу

1. Создай директорию `src/app/{page-name}/`
2. Создай `page.tsx` — серверный компонент или клиентский
3. Добавь API-методы в `src/lib/api/{module}.ts`
4. Создай React Query хук в `src/lib/hooks/use-{module}.ts`
5. Добавь ссылку в Sidebar (`src/components/layout/sidebar.tsx`)

---

## Как добавить новый API-метод + хук

1. **API-метод:**
```typescript
// src/lib/api/example.ts
import apiClient from './client';

export const getExample = (id: number) =>
  apiClient.get(`/example/${id}`);
```

2. **Хук:**
```typescript
// src/lib/hooks/use-example.ts
import { useQuery } from '@tanstack/react-query';
import { getExample } from '../api/example';

export function useExample(id: number) {
  return useQuery({
    queryKey: ['example', id],
    queryFn: () => getExample(id),
  });
}
```

3. **Использование в компоненте:**
```typescript
const { data, isLoading } = useExample(42);
```

---

## Дизайн-система

CRM использует shadcn/ui компоненты с RetouchGrav mineral palette. Подробности: [design-system.md](design-system.md)

---

## Связанные документы

- [Дизайн-система](design-system.md)
- [Контекст проекта](../project-context.md)
- [Справочник API](../architecture/api.md)
