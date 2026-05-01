# AGENTS.md — Granite CRM

Стандарты разработки для AI-агентов.
Иерархия: `.agents/rules.md` > `.agents/opencode.md` > `GEMINI.md` > `AGENTS.md`.
Общие правила см. в `.agents/rules.md`.

---

## 📌 Контекст

**Что это:** Python-пайплайн сбора базы ритуальных мастерских + FastAPI CRM.
**Стек:** Python 3.12, SQLAlchemy 2.x, Alembic, FastAPI, SQLite (WAL), asyncio/httpx.
**Package manager:** **только `uv`** — никогда `pip install`.

| Компонент | Файл |
|----------|------|
| ORM + БД | `granite/database.py` |
| Шаблоны | `granite/templates.py` — EmailTemplate + TemplateRegistry (JSON as source of truth) |
| Шаблоны JSON | `data/email_templates.json` — единственный источник шаблонов |
| Пайплайн | `granite/pipeline/` |
| Скреперы | `granite/scrapers/` (jsprav, jsprav_playwright) ⚠️ dgis/yell отключены, web_search работает |
| Обогащение | `granite/enrichers/` (tg_finder, messenger_scanner, tech_extractor, classifier, network_detector, reverse_lookup) |
| CRM API | `granite/api/` |
| БД | `data/granite.db` (~6000 компаний, 29 городов) |
| Фронтенд | `granite-web/` (Next.js, TypeScript) |

---

## 🐍 Python — ключевые правила

### Зависимости
```bash
uv add <package>    # добавить
uv remove <package> # удалить
uv sync         # синхронизировать
uv run cli.py <cmd>  # запустить CLI
```

### БД и сессии
```python
# ✅ ВСЕГДА — session_scope
with db.session_scope() as session:
    ...  # commit() вызывается автоматически

# ❌ НИКОГДА внутри session_scope
session.commit()  # уже делает сам

# ❌ НЕ передавать session между потоками
```

### HTTP
```python
# ✅ ВСЕГДА — проверка URL
if is_safe_url(url):
    await fetch_page(url)

# ⏱ Таймауты: 15с одиночный, 8с batch-scraping
# fetch_page() уже с retry — не оборачивать
```

### Async vs Sync
- `config.enrichment.async_enabled: true` → `httpx.AsyncClient` из `http_client.py`
- Иначе → `ThreadPoolExecutor` в `_enrich_companies_parallel()`
- Не смешивать без `run_async()`

### Стиль
- Type hints + docstrings на публичных методах
- Max 100 символов строка (ruff)
- Импорты: stdlib → third-party → `granite.*`

### Данные
```python
# Нормализация URL мессенджеров
normalize_messenger_url(url, type)

# Фильтрация мусора
is_seo_title(name)

# Телефоны
normalize_phones()
```

---

## 🗄️ Изменения схемы БД — через Alembic

```bash
uv run cli.py db check          # проверить расхождения
uv run cli.py db migrate "desc" # создать миграцию
uv run cli.py db upgrade head   # применить
```

**Нельзя:**
- `Base.metadata.create_all()` в production
- Прямые `ALTER TABLE` / `CREATE TABLE` в SQLite
- Удалять файлы из `alembic/versions/`

---

## 🧪 Тестирование

```bash
uv run pytest tests/ -v              # все
uv run pytest tests/test_enrichers.py -v
uv run pytest tests/test_pipeline.py -v
uv run pytest tests/test_migrations.py -v
uv run pytest -k "async" -v         # только async
```

- Моки HTTP через `unittest.mock.patch`
- Тесты с БД: `Database(auto_migrate=False)`

---

## 🚀 Пайплайн

```bash
uv run playwright install chromium   # один раз при настройке
uv run cli.py seed-cities           # один раз при первом запуске
uv run cli.py run "Город"          # полный цикл
uv run cli.py run "Город" --force   # с нуля
uv run cli.py run "Город" --re-enrich # только обогащение
uv run cli.py run all              # все города
uv run cli.py scan-networks       # глобальный сканер агрегаторов
uv run cli.py cities-status        # проверить статусы городов
```

**Чекпоинты:** пайплайн запоминает прогресс. Поля `pipeline_status`, `pipeline_phase` в `cities_ref`.

---

## ⚠️ Частые ошибки

1. **Lazy load в потоках** — читать `r.phones`/`r.emails` только с `joinedload()`
2. **`needs_review` / `review_reason`** — флаг требует валидации
3. **Таймаут 15с everywhere** — для detail-страниц jsprav хватит 8с
4. **Голый `except Exception:`** — минимум `_classify_error()`
5. **`config.yaml` во время работы** — читается один раз при старте
6. **`DROP TABLE` через MCP** — `uv run cli.py run "Город" --force`
7. **`pip install`** — только `uv add`
8. **Шаблоны в БД** — не править `crm_templates`, правь `data/email_templates.json` + `POST /templates/reload`
9. **Seed-скрипты** — `seed_crm_templates.py` и `seed_templates.py` удалены, больше не нужны

---

## 🌐 FastAPI

```bash
uv run cli.py api --port 8000          # запустить
uv run cli.py api --port 8000 --reload   # hot reload
```

- Изменения данных: `session_scope()`, не raw SQL
- Endpoints: `app.include_router()` в `granite/api/app.py`
- Pydantic схемы: `granite/api/schemas.py`
- Зависимость `get_db`: auto-commit, rollback при ошибке
- TemplateRegistry: `app.state.template_registry` — инжектируется при старте, доступен в роутерах через `request.app.state.template_registry`

---

## 📁 Структура

```
granite/
├── scrapers/      # BaseScraper → scrape()
│   ├── base.py, jsprav.py, jsprav_playwright.py
│   ├── dgis.py, dgis_constants.py ⚠️ отключены
│   ├── web_search.py
│   ├── yell.py ⚠️ отключен
│   └── _playwright.py
├── enrichers/    # добавить в __init__.py
│   ├── tg_finder.py, tg_trust.py
│   ├── messenger_scanner.py
│   ├── tech_extractor.py
│   ├── classifier.py
│   ├── network_detector.py
│   └── reverse_lookup.py
├── pipeline/    # *_phase.py → manager.py
├── api/        # router → app.py
├── dedup/      # Union-Find (осторожно)
├── email/     # отправка + tracking pixel
├── messenger/ # TG/WA (mock)
├── exporters/ # CSV/Markdown экспорт
├── templates.py # EmailTemplate + TemplateRegistry (JSON → память)
└── data/     # справочники
```

---

## 🔒 Безопасность

- `is_safe_url()` перед HTTP
- SQL: без f-string, `ilike` → экранировать `%_`
- Секреты: `.env` / переменные окружения
- API-key аутентификация: `GRANITE_API_KEY` в .env → middleware проверяет `X-API-Key` заголовок (через `hmac.compare_digest`). Публичные маршруты: `/health`, `/docs`, `/api/v1/track/*`, `/api/v1/unsubscribe/*`, OPTIONS

---

## 🎯 Скиллы

Для специфичных задач — загрузить skill:

| Скилл | Задача |
|-------|--------|
| **granite-coder** | Изменение кода в `granite/` |
| **pipeline-monitor** | Пайплайн завис/упал |
| **scraper-debugger** | Скрепер 0 результатов |
| **Data Auditor** | Аудит качества данных |
| **github** | Issues, PR, CI |

---

*Granite CRM · Обновлено: 2026-04-26*