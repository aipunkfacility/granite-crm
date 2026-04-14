# opencode.md — Granite CRM / OpenCode Session Rules

> Этот файл загружается OpenCode при каждом старте сессии.
> Иерархия: `.agents/rules.md` > `opencode.md` > `GEMINI.md` > `AGENTS.md` > `AGENT_CAPABILITIES.md`
> Общие стандарты кода: в `AGENTS.md`.

---

## 🤖 Режим работы агента

- Перед сложной задачей — используй встроенный `task` инструмент для параллельных подзадач.
- При работе с пайплайном — читай `data/logs/granite.log` (200 строк) прежде чем что-то менять.
- При аудите/мониторинге/отладке скреперов — сначала открой соответствующий `SKILL.md` в `.agents/skills/`.

## 🛠️ Доступные инструменты

### Основные (встроенные)

| Инструмент | Использование |
|------------|---------------|
| `bash` | Запуск CLI: `uv run cli.py`, тесты `uv run pytest`, SQL-запросы |
| `read` / `glob` / `grep` | Чтение кода, поиск файлов |
| `edit` / `write` | Изменение кода |
| `webfetch` / `websearch` | Веб-поиск и документация |
| `skill` | Загрузка специализированных скиллов |

### MCP-серверы (подключены)

| MCP | Назначение |
|-----|------------|
| **SQLite** | Прямые SQL-запросы к `data/granite.db` |
| **Playwright** | Браузерная отладка, проверка HTML источников |
| **Context7** | Актуальная документация библиотек |

## 🐍 Зависимости и запуск

- **Package manager:** ТОЛЬКО `uv`. Никакого `pip install`.
- **Запуск CLI:** `uv run cli.py [команда]`
- **Тесты:** `uv run pytest`
- **Добавить пакет:** `uv add <package>` (с подтверждения пользователя)

## 🔐 Безопасность (Allow/Deny)

### Разрешено без подтверждения:
- `uv run pytest tests/` и любые pytest-команды
- `uv run cli.py run ... --force` для городов из config.yaml
- `uv run cli.py db check` и `uv run cli.py db current`
- Чтение любых файлов проекта
- `git status`, `git log`, `git diff`

### Требует подтверждения:
- `uv run cli.py db upgrade head` — изменение схемы БД
- `uv run cli.py db migrate` — создание новой миграции
- `uv add <package>` — изменение зависимостей
- Удаление записей из БД
- `git push`, `git commit`
- Изменения в `config.yaml`

### Запрещено:
- Запись в `data/granite.db` напрямую (только через CLI)
- `DROP TABLE`, `TRUNCATE`
- Удаление файлов из `alembic/versions/`
- `pip install` в любом виде

## 🔧 Использование MCP

### SQLite — запросы к БД

```sql
-- Статистика по городу
SELECT city, COUNT(*) as total, SUM(CASE WHEN crm_score = 0 THEN 1 ELSE 0 END) as zero_score
FROM enriched_companies
GROUP BY city;
```

### Playwright — отладка скреперов

```
Открыть URL: https://yaroslavl.jsprav.ru/izgotovlenie-i-ustanovka-pamyatnikov-i-nadgrobij/
Найти элемент: .company-card
Скриншот: да
```

### Context7 — документация

```
Запрос: SQLAlchemy 2.x session_scope async
Лимит токенов: 5000
```

## 📋 Скиллы (Workspace Skills)

| Скилл | Когда использовать |
|-------|----------------|
| **granite-coder** | Изменение кода в granite/ |
| **pipeline-monitor** | Пайплайн завис/упал |
| **scraper-debugger** | Скрепер даёт 0 результатов |
| **Data Auditor** | Аудит качества данных |
| **github** | Issues, PR, CI |

Активация скилла:
```
/skill granite-coder
/skill pipeline-monitor
```

---

*Последнее обновление: 2026-04-13 · Агент: OpenCode*