# GEMINI.md — Granite CRM / Antigravity Session Rules

> Этот файл загружается Antigravity при каждом старте сессии.
> Иерархия: `.agents/rules.md` > `GEMINI.md` > `AGENTS.md` > `AGENT_CAPABILITIES.md`
> Здесь: Antigravity-специфичные настройки.
> Общие стандарты кода: в `AGENTS.md`.

---

## 🤖 Режим работы агента

- Перед сложной задачей — ВСЕГДА используй `sequentialthinking` MCP. Этот проект сложнее чем кажется.
- При работе с пайплайном — читай `data/logs/granite.log` (200 строк) прежде чем что-то менять.
- При аудите/мониторинге/отладке скреперов — сначала открой соответствующий `SKILL.md` в `.agents/skills/`.
- **Superpowers (Core Framework)** — используй навыки из `.agents/skills/` для TDD, планирования и отладки. Эти навыки являются ПРИОРИТЕТНЫМИ и ОБЯЗАТЕЛЬНЫМИ.

## 🛠️ MCP-инструменты

| MCP | Когда использовать |
|-----|--------------------|
| `sqlite` → `granite.db` | Проверка данных, аудит, отладка. Читать всегда. Писать — только если явно попросили. |
| `playwright` | Отладка скреперов, проверка HTML-разметки источников. |
| `context7` | Перед написанием кода с SQLAlchemy / FastAPI / Alembic / Playwright — всегда проверять актуальный API. |
| `github` | Создание issues, просмотр истории. Не пушить код без подтверждения. |
| `sequentialthinking` | Планирование перед любой задачей сложнее чтения файла. |
| `superpowers:*` | Набор навыков для TDD, систематической отладки и планирования. |

**Важно:** не открывай больше 50 инструментов суммарно. При Tool Bloat агент деградирует.

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
- `cat`, `grep`, `head`, `tail` на любых файлах проекта
- `git status`, `git log`, `git diff`

### Требует подтверждения:
- `uv run cli.py db upgrade head` — изменение схемы БД
- `uv run cli.py db migrate` — создание новой миграции
- `uv add <package>` — изменение зависимостей
- `DELETE FROM` в любой таблице SQLite
- `git push`, `git commit`
- Любые изменения в `config.yaml`

### Запрещено:
- Запись в `data/granite.db` через MCP без явной команды пользователя
- `DROP TABLE`, `TRUNCATE`
- Удаление файлов из `alembic/versions/`
- `pip install` в любом виде

## 🖥️ Среда выполнения

- OS: **Windows**, PowerShell. Пути формата `f:\Dev\...`
- Python 3.12 (`.venv` в корне проекта, управляется через `uv`)
- БД: `data/granite.db` — WAL mode, busy_timeout=5000ms. Не держи соединение открытым долго.
- Не открывай браузер для документации — используй Context7 MCP.

## 📋 Артефакты

При завершении нетривиальной задачи — создай Artifact:
- **Аудит данных** → Markdown-таблица с найденными проблемами
- **Изменение кода** → краткое описание что изменено и почему
- **Отладка пайплайна** → диагноз + шаги воспроизведения

## 🦸 Superpowers — Systematic Workflow

Проект использует методологию Superpowers. Основные требования:
1. **Writing Plans** — всегда создавай план перед выполнением задачи.
2. **Test-Driven Development** — пиши тест ДО реализации кода.
3. **Systematic Debugging** — не предлагай фиксы без нахождения Root Cause.
4. **Verification Before Completion** — всегда проверяй результат перед завершением.

---
*Последнее обновление: 2026-04-18 · Версия Antigravity: 1.20.3+*
