# RetouchGrav CRM

AI-провайдер ретуши для гравировки на памятниках + CRM для поиска и аутрича гранитных мастерских по всей России.

**Публичный сайт:** https://retouchgrav.netlify.app

---

## Экосистема

RetouchGrav состоит из нескольких компонентов:

| Компонент | Назначение |
|-----------|-----------|
| **granite-crm** (бэкенд) | Скрапинг мастерских, скоринг, воронка, рассылки |
| **granite-web** (фронтенд) | UI для управления контактами и рассылками |
| **monument-web** (лендинг) | Публичный сайт retouchgrav.netlify.app |
| **memorial-img** | Хостинг изображений для email-шаблонов |

Подробнее: [docs/architecture/ecosystem.md](docs/architecture/ecosystem.md)

---

## Быстрый старт

```bash
uv sync                              # Зависимости
uv run playwright install chromium   # Скраперы
uv run cli.py seed-cities            # Справочник городов
uv run cli.py run "Астрахань"        # Собрать данные по городу
uv run cli.py api --port 8000        # Запустить API

cd granite-web && npm install && npm run dev  # Фронтенд
```

Подробнее: [docs/guides/getting-started.md](docs/guides/getting-started.md)

---

## Структура проекта

```
├── cli.py                 # CLI (typer): run, export, db, api
├── config.yaml            # Города, источники, скоринг, пресеты
├── granite/               # Бэкенд
│   ├── api/               # FastAPI REST API
│   ├── pipeline/          # Пайплайн (скрапинг → скоринг → экспорт)
│   ├── scrapers/          # Парсеры (jsprav, web_search, 2GIS, Yell)
│   ├── enrichers/         # Обогащение (TG, CMS, мессенджеры)
│   ├── dedup/             # Дедупликация (Union-Find)
│   ├── email/             # Email-отправка + tracking pixel
│   ├── messenger/         # TG/WA отправка (mock)
│   ├── exporters/         # CSV/Markdown экспорт
│   └── templates.py       # EmailTemplate + TemplateRegistry
├── granite-web/           # Next.js фронтенд
├── alembic/               # Миграции БД
├── data/
│   ├── granite.db         # SQLite (WAL)
│   ├── email_templates.json  # Шаблоны писем (source of truth)
│   ├── regions.yaml       # 40 областей, 566 городов
│   └── export/            # CSV/MD экспорт
└── docs/                  # Документация
```

---

## Основные команды

```bash
# Пайплайн
uv run cli.py run "Город"              # Полный цикл
uv run cli.py run "Город" --force      # С нуля
uv run cli.py run "Город" --re-enrich  # Только обогащение
uv run cli.py run all -r               # Все города, пропуск готовых

# API
uv run cli.py api --port 8000          # Запустить API
uv run cli.py api --port 8000 --reload # Hot reload

# БД
uv run cli.py db check                 # Проверить расхождения
uv run cli.py db migrate "описание"    # Создать миграцию
uv run cli.py db upgrade head          # Применить миграции

# Экспорт
uv run cli.py export "Город" --format csv
uv run cli.py export-preset "Город" hot_leads
```

Полный справочник: [docs/guides/cli-reference.md](docs/guides/cli-reference.md)

---

## Навигация по документации

| Документ | Описание |
|----------|----------|
| [docs/project-context.md](docs/project-context.md) | **Что это, зачем, для кого, как работает** — единая точка входа |
| [docs/architecture/ecosystem.md](docs/architecture/ecosystem.md) | Как связаны CRM, лендинг, email, изображения |
| [docs/architecture/api.md](docs/architecture/api.md) | Справочник всех API-эндпоинтов |
| [docs/architecture/database.md](docs/architecture/database.md) | Схема БД, миграции, ORM-модели |
| [docs/landing/README.md](docs/landing/README.md) | Лендинг RetouchGrav: секции, цены, связь с CRM |
| [docs/guides/getting-started.md](docs/guides/getting-started.md) | Быстрый старт (от нуля до работающей системы) |
| [docs/guides/cli-reference.md](docs/guides/cli-reference.md) | Полный справочник CLI-команд |
| [docs/guides/crm-user-guide.md](docs/guides/crm-user-guide.md) | Как пользоваться CRM (сценарии) |
| [docs/guides/email-sending.md](docs/guides/email-sending.md) | Настройка и отправка email-рассылок |
| [docs/guides/roadmap.md](docs/guides/roadmap.md) | Дорожная карта проекта |
| [docs/frontend/design-system.md](docs/frontend/design-system.md) | Дизайн-система CRM |
| [docs/business/market-analysis.md](docs/business/market-analysis.md) | Анализ рынка ретуши для памятников |
| [docs/business/marketing-strategy.md](docs/business/marketing-strategy.md) | Стратегия B2B-аутрича |

---

## Агентские файлы

| Файл | Назначение |
|------|-----------|
| `GEMINI.md` | Контекст и инструкции для Google Gemini |
| `AGENTS.md` | Стандарты разработки для AI-агентов |
| `QWEN.md` | Контекст и инструкции для Qwen Code |

---

## Требования

- **Python** 3.12+ (менеджер пакетов: `uv`, НЕ pip)
- **Node.js** 18+ (для фронтенда)
- **Playwright** (для скраперов с JS-рендерингом)
