<!-- Обновлено: 2026-04-25 -->
# Архитектура экосистемы RetouchGrav

> Техническая документация о том, как компоненты RetouchGrav связаны между собой: потоки данных, общая дизайн-система, развёртывание.

---

## 1. Обзор экосистемы

RetouchGrav — не монолит, а экосистема из трёх независимо развёртываемых компонентов и одного общего ресурса:

| Компонент | Репозиторий | Хостинг | Стек |
|-----------|------------|---------|------|
| Лендинг | monument-web | Netlify | Статический HTML/CSS/JS |
| CRM бэкенд | granite-crm | Локально (uvicorn) | Python, FastAPI, SQLite |
| CRM фронтенд | granite-crm/granite-web/ | Локально (Next.js dev) | Next.js 16, TypeScript, shadcn/ui |
| Изображения для email | monument-web (отдельный сайт) | Netlify (memorial-img) | Статический хостинг |

Каждый компонент можно обновлять и деплоить независимо. Связь — через URL, REST API и общие файлы (email-шаблон).

---

## 2. Лендинг (monument-web)

**URL:** https://retouchgrav.netlify.app
**Репо:** github.com/aipunkfacility/monument-web
**Хостинг:** Netlify (основной, автодеплой из main), GitHub Pages (зеркало)

Статический сайт без сборщика. Все файлы — чистый HTML/CSS/JS. Деплой — push в main ветку, Netlify автоматически обновляет сайт. Секции: Hero, Advantages, Process, Portfolio, Pricing, FAQ, CTA.

**Аналитика:** Яндекс.Метрика (счётчик 108345194, 14+ целей). Работает независимо от CRM.

**Контакты:** Кнопки Telegram и WhatsApp — прямые ссылки (`t.me/`, `wa.me/`). Формы заявки нет — контакты идут через мессенджеры или email. CRM получает данные не с лендинга напрямую, а через скрапинг источников.

**Подробнее:** [landing/README.md](../landing/README.md)

---

## 3. Email-шаблон

**Исходник:** `monument-web/email/email-improved-light.html`
**Загрузка в CRM:** Файловый аплоад через UI (или API `POST /templates`)
**Изображения:** `memorial-img.netlify.app` (отдельный Netlify-сайт)

### Путь email-шаблона

```
monument-web/email/email-improved-light.html
       │
       │  Разработчик обновляет шаблон в репо monument-web
       ▼
  UI CRM: Templates → Upload .html file
       │
       │  FileReader.readAsText() → POST /api/v1/templates {body_type: "html", body: "..."}
       ▼
  CrmTemplateRow (SQLite: body_type="html", body=HTML-код)
       │
       │  Кампания запускается → шаблон рендерится с плейсхолдерами
       ▼
  EmailSender.send() → SMTP → почтовый ящик мастерской
       │
       │  Письмо содержит ссылку на retouchgrav.netlify.app
       ▼
  Мастерская переходит на лендинг → TG/WA кнопка → прямой чат
```

### Ограничения email-шаблонов

- **Inline-стили обязательны.** Почтовые клиенты вырезают `<style>` из `<head>`.
- **Табличная вёрстка.** `<div>` + flex/grid не работают в Outlook. Только `<table>`.
- **Внешние изображения блокируются.** Gmail/Outlook показывают «Показать картинки» при первом открытии. Изображения с `memorial-img.netlify.app` не загрузятся автоматически.
- **Ширина 600px.** Стандарт для email-клиентов.
- **Плейсхолдеры** — только в текстовом содержимом тегов. Значения экранируются через `html.escape()`.

**Подробнее о рассылках:** [guides/email-sending.md](../guides/email-sending.md)

---

## 4. CRM (granite-crm + granite-web)

### Бэкенд

- **FastAPI** — REST API на `/api/v1`
- **SQLite** — база данных в `data/granite.db` (WAL-режим)
- **Alembic** — версионирование схемы БД
- **SMTP** — отправка email через собственный почтовый сервер
- **Tracking pixel** — 1x1 PNG для отслеживания открытий писем

### Фронтенд

- **Next.js 16** — SSR/CSR с App Router
- **shadcn/ui** — UI-компоненты (таблицы, карточки, формы, диалоги)
- **TanStack Query v5** — кэширование и синхронизация данных с API
- **Tailwind CSS 4** — стилизация

### Взаимодействие бэкенд ↔ фронтенд

```
Next.js (localhost:3000)
       │
       │  fetch("/api/v1/companies?...")
       ▼
FastAPI (localhost:8000) → CORS: localhost:3000, localhost:5173
       │
       │  SQLAlchemy → SQLite (data/granite.db)
       ▼
  JSON response → React Query cache → UI update
```

Поллинг каждые 30 секунд для статусных данных (пайплайн, кампании). SSE (Server-Sent Events) для прогресса отправки кампаний. WebSocket не используется — не нужен для одного пользователя.

**Подробнее об API:** [api.md](api.md)
**Подробнее о БД:** [database.md](database.md)
**Подробнее о фронтенде:** [frontend/overview.md](../frontend/overview.md)

---

## 5. Потоки данных

### Сценарий 1: Скрапинг → Кампания → Лендинг

Основной сценарий работы — найти мастерские и установить контакт:

```
1. uv run cli.py run "Волгоград"
   → Скрапинг (jsprav, web_search) → raw_companies
   → Дедупликация → companies
   → Обогащение (TG, CMS, email) → enriched_companies
   → Скоринг (A/B/C/D) → enriched_companies.segment

2. CRM UI: Компании → Фильтр: сегмент A, город Волгоград
   → Выбрать 50 компаний → Создать кампанию

3. CRM UI: Кампании → Создать → Выбрать шаблон → Запустить
   → EmailSender: персонализированные письма → SMTP
   → Каждое письмо содержит ссылку на retouchgrav.netlify.app

4. Мастерская открывает письмо (tracking pixel фиксирует opened_at)
   → Кликает на ссылку → видит лендинг
   → Нажимает TG/WA кнопку → прямой чат
```

### Сценарий 2: Лендинг → Ручной контакт

Когда потенциальный клиент сам находит лендинг:

```
1. Яндекс/Google → retouchgrav.netlify.app
   → Метрика фиксирует визит

2. Клиент нажимает Telegram/WhatsApp кнопку
   → Открывается прямой чат с владельцем RetouchGrav

3. Владелец вручную добавляет контакт в CRM
   (автоматической интеграции лендинг → CRM нет)
```

### Сценарий 3: Follow-up

Повторный контакт с мастерской, которая не ответила:

```
1. CRM: Follow-up → Список компаний для повторного контакта
   → Рекомендованный канал (email/TG/WA)
   → Рекомендованное время

2. Владелец нажимает "Сделано" → записывается касание
   → Воронка: Письмо отправлено → Написали в TG / Ответили
```

---

## 6. Общая дизайн-система

Оба визуальных компонента экосистемы (лендинг и CRM) используют единую дизайн-систему RetouchGrav DS v3.1 с разной реализацией:

### Цветовая палитра (Mineral Palette)

| Токен | Цвет | Hex | Лендинг | CRM |
|-------|------|-----|---------|-----|
| Labradorite | Фиолетовый | #7C8CF8 | Акценты, кнопки | shadcn primary |
| Malachite | Зелёный | #34D399 | Успех, CTA | shadcn success |
| Amber | Золотой | #FBBF24 | Цены, внимание | shadcn warning |
| Garnet | Красный | #F43F5E | Ошибки | shadcn destructive |

### Шрифты

| Шрифт | Назначение | Лендинг | CRM |
|-------|-----------|---------|-----|
| Outfit | Заголовки | Google Fonts | next/font |
| Inter | Основной текст | Google Fonts | next/font |

### Реализация

| Аспект | Лендинг | CRM |
|--------|---------|-----|
| Компоненты | Custom HTML/CSS | shadcn/ui |
| Стилизация | CSS custom properties | Tailwind CSS 4 |
| Glassmorphism | Да (`backdrop-filter: blur()`) | Нет (админ-панель) |
| Dark/Light | JS toggle + CSS variables | next-themes + Tailwind |
| Анимации | CSS transitions | Tailwind + framer-motion |

**Полная DS лендинга:** `monument-web/DESIGN_SYSTEM.md`
**CRM DS:** [frontend/design-system.md](../frontend/design-system.md)

---

## 7. Хостинг изображений (memorial-img.netlify.app)

**Назначение:** Картинки для email-шаблонов (примеры работ, портфолио).

**Почему отдельный сайт:** Email-клиенты не загружают изображения по относительным путям. Нужен абсолютный URL на общедоступный хостинг. Netlify выбран для консистентности с основным лендингом.

**Ограничения:** Gmail и Outlook блокируют внешние изображения при первом открытии. Пользователь видит «Показать картинки» и должен нажать вручную. Это известное ограничение email-клиентов, не исправляемое на уровне CRM. Возможное решение в будущем — CID-встраивание (MIME-вложения).

**Содержимое:**
- `male.jpg` — пример ретуши (мужской портрет)
- `female.jpg` — пример ретуши (женский портрет)

**Обновление:** Push в `monument-web` репозиторий, Netlify автодеплоит.
