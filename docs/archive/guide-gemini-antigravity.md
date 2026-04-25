# Gemini CLI + Antigravity IDE — Полный гайд по конфигурации

> **Дата обновления:** 2026-04-17
> **Инструменты:** Gemini CLI (v0.23+), Google Antigravity IDE (Preview)
> **Назначение:** Справочник по файлам конфигурации, инструкциям, правилам, воркфлоу, скиллам

---

## Содержание

1. [Что такое Gemini CLI и Antigravity IDE](#1-что-такое-gemini-cli-и-antigravity-ide)
2. [CLI vs IDE — ключевые различия](#2-cli-vs-ide--ключевые-различия)
3. [Файловая система и пути](#3-файловая-система-и-пути)
4. [GEMINI.md — файл инструкций](#4-geminimd--файл-инструкций)
5. [AGENTS.md — универсальный стандарт](#5-agentsmd--универсальный-стандарт)
6. [settings.json — полная схема](#6-settingsjson--полная-схема)
7. [.geminiignore](#7-geminiignore)
8. [Команды](#8-команды)
9. [MCP серверы](#9-mcp-серверы)
10. [Antigravity: Rules (Правила)](#10-antigravity-rules-правила)
11. [Antigravity: Workflows (Воркфлоу)](#11-antigravity-workflows-воркфлоу)
12. [Antigravity: Skills (Навыки)](#12-antigravity-skills-навыки)
13. [Antigravity: Artifacts (Артефакты)](#13-antigravity-artifacts-артефакты)
14. [Antigravity: Settings (Настройки IDE)](#14-antigravity-settings-настройки-ide)
15. [Antigravity: Manager View и параллельные агенты](#15-antigravity-manager-view-и-параллельные-агенты)
16. [Конфликт GEMINI.md (#16058)](#16-конфликт-geminimd-16058)
17. [Безопасность](#17-безопасность)
18. [Проблемы и решения](#18-проблемы-и-решения)
19. [Лучшие практики](#19-лучшие-практики)
20. [Чеклист настройки нового проекта](#20-чеклист-настройки-нового-проекта)
21. [Совместное использование CLI + IDE](#21-совместное-использование-cli--ide)

---

## 1. Что такое Gemini CLI и Antigravity IDE

### Gemini CLI

**Gemini CLI** — AI coding assistant для терминала от Google. Работает с моделями Gemini (2.5 Pro, 3 Pro) и сторонними через API.

- **Платформы:** macOS, Linux, Windows (WSL)
- **Установка:** `npm install -g @anthropic-ai/gemini-cli` или `npx @anthropic-ai/gemini-cli`
- **Репозиторий:** github.com/google-gemini/gemini-cli
- **Статус:** Стабильный, активно развивается

### Antigravity IDE

**Google Antigravity** — полноценная настольная IDE нового поколения от Google. **НЕ расширение и НЕ форк VS Code** — самостоятельная IDE.

- **Анонс:** 18 ноября 2025 (вместе с Gemini 3 Pro)
- **Платформы:** Windows, macOS, Linux
- **AI-движок:** Gemini 3 Pro (с поддержкой сторонних моделей)
- **Сайт:** https://antigravity.google
- **Документация:** https://antigravity.google/docs
- **Статус:** Публичный предпросмотр, **бесплатно**

### Философия Antigravity — «Агент-первый»

Вместо написания кода строка за строкой вы **оркестрируете автономных агентов**. Роль разработчика — «архитектор» и «оркестратор», а не «писатель кода».

---

## 2. CLI vs IDE — ключевые различия

### Режимы работы Antigravity

| Режим | Описание | Аналог в CLI |
|-------|----------|-------------|
| **Editor View** | Классический IDE с автодополнением Tab, инлайн-командами | Базовая сессия CLI |
| **Manager View** | Центр управления для запуска параллельных агентов | Нет аналога |

### Полная таблица различий

| Возможность | Gemini CLI | Antigravity IDE |
|------------|-----------|----------------|
| **Интерфейс** | Терминал | GUI (полноценный редактор) |
| **Параллельные агенты** | Нет (один за раз) | Да (Swarm в Manager View) |
| **Браузерный контроль** | Нет | Да (встроенный Chrome) |
| **Artifacts** | Нет | Да (планы, скриншоты, записи) |
| **Subagent** | Нет | Да (подагенты) |
| **Knowledge Editor** | Нет | Да (редактор знаний) |
| **Workflows** | Нет (Custom Commands) | Да (слэш-команды, вложенные) |
| **Rules (типы активации)** | Нет | Manual, Always On, Model Decision, Glob |
| **Headless / CI/CD** | Да (`gemini -p`) | Нет |
| **SSH / скриптинг** | Да | Нет |
| **Терминальный доступ** | Да | Нет |
| **Проверка кода (Preview)** | Нет | Да (встроенный превью) |
| **Checkpointing** | Да (`--checkpointing`) | Нет (автосохранение) |
| **YOLO-режим** | Да (опасно) | Strict Mode (безопаснее) |
| **Файловая система** | `~/.gemini/` | `~/.gemini/` + `~/.antigravity/` |
| **Лимиты (сброс)** | 24 часа | 5 часов |
| **Токены** | Gemini Code Assist (CLI) | Gemini Code Assist (IDE, отдельные) |
| **MCP-конфиг** | `settings.json` → `mcpServers` | `~/.gemini/antigravity/mcp_config.json` |

### Когда что использовать

| Сценарий | Выбор |
|----------|-------|
| Быстрый фикс в терминале | Gemini CLI |
| CI/CD пайплайн | Gemini CLI |
| SSH на удалённом сервере | Gemini CLI |
| Автоматизация через скрипты | Gemini CLI |
| Визуальная разработка | Antigravity IDE |
| Параллельные задачи | Antigravity IDE |
| Браузерная автоматизация | Antigravity IDE |
| Работа с командой (GUI) | Antigravity IDE |
| Оркестрация сложных задач | Antigravity IDE |

---

## 3. Файловая система и пути

### Общая структура

```
~/.gemini/                          ← ОБЩИЙ корень (ВАЖНО!)
├── GEMINI.md                       ← ⚠️ КОНФЛИКТ: и CLI, и IDE пишут сюда
├── settings.json                   ← Настройки Gemini CLI
├── oauth_creds.json                ← OAuth-учётные данные
├── extensions/                     ← Расширения Gemini CLI
├── skills/                         ← Скиллы Gemini CLI (глобальные)
├── tmp/                            ← Временные файлы
└── antigravity/                    ← Подкаталог Antigravity
    ├── mcp_config.json             ← MCP-серверы Antigravity
    ├── conversations/              ← История разговоров
    ├── brain/                      ← «Мозг» Antigravity
    ├── global_workflows/           ← Глобальные воркфлоу
    └── skills/                     ← Скиллы Antigravity (глобальные)

~/.antigravity/                     ← Данные приложения Antigravity
├── Artifacts/                      ← Артефакты (планы, скриншоты, записи)
└── Knowledge Items/                ← Элементы знаний
```

### Проектная структура

```
<project>/
├── GEMINI.md                       ← Контекст (CLI + IDE)
├── AGENTS.md                       ← Универсальный стандарт (высший приоритет)
├── .geminiignore                   ← Исключения для Gemini CLI
├── .gemini/
│   ├── settings.json               ← Проектные настройки CLI
│   ├── rules/                      ← Правила проекта (CLI)
│   └── skills/                     ← Скиллы проекта (CLI)
└── .agents/
    ├── rules/                      ← Правила проекта (Antigravity)
    │   ├── my-rule.md              ← Manual/AlwaysOn/ModelDecision/Glob
    │   └── another-rule.md
    └── skills/                     ← Скиллы проекта (Antigravity)
        └── my-skill/
            └── SKILL.md
```

### Таблица: кто что использует

| Файл / Путь | Gemini CLI | Antigravity IDE |
|-------------|-----------|----------------|
| `~/.gemini/GEMINI.md` | ✅ Глобальный контекст | ✅ Глобальные правила |
| `~/.gemini/settings.json` | ✅ Настройки CLI | ⚠️ Частично (MCP отдельно) |
| `~/.gemini/oauth_creds.json` | ✅ OAuth | ✅ Общий OAuth |
| `~/.gemini/antigravity/mcp_config.json` | ❌ | ✅ MCP Antigravity |
| `~/.gemini/antigravity/skills/` | ❌ | ✅ Глобальные скиллы |
| `~/.gemini/antigravity/global_workflows/` | ❌ | ✅ Глобальные воркфлоу |
| `~/.gemini/antigravity/conversations/` | ❌ | ✅ История |
| `~/.gemini/skills/` | ✅ Скиллы CLI | ❌ |
| `~/.gemini/extensions/` | ✅ Расширения CLI | ❌ |
| `~/.antigravity/` | ❌ | ✅ Данные приложения |
| `./GEMINI.md` | ✅ Проектный контекст | ✅ Проектный контекст |
| `./AGENTS.md` | ✅ (сниженный приоритет) | ✅ Высший приоритет |
| `./.geminiignore` | ✅ Исключения | ❌ |
| `./.agents/rules/` | ❌ | ✅ Правила проекта |
| `./.agents/skills/` | ❌ | ✅ Скиллы проекта |

---

## 4. GEMINI.md — файл инструкций

### Что это

Markdown-файл с инструкциями для модели. Загружается автоматически, содержимое отправляется с каждым промптом. «Долгосрочная память» Gemini.

### Иерархия загрузки (Gemini CLI)

| # | Уровень | Путь | Когда |
|---|---------|------|-------|
| 1 | Глобальный | `~/.gemini/GEMINI.md` | Всегда |
| 2 | Workspace | `./GEMINI.md` + родительские директории | При запуске из проекта |
| 3 | JIT | `GEMINI.md` рядом с файлами | При обращении к файлу |

### Иерархия загрузки (Antigravity IDE)

| # | Уровень | Путь | Приоритет |
|---|---------|------|-----------|
| 1 | Универсальный | `./AGENTS.md` | **Наивысший** |
| 2 | Проектный | `./GEMINI.md` | Ниже AGENTS.md |
| 3 | Глобальный | `~/.gemini/GEMINI.md` | Самый низкий |

**Workspace-настройки перезаписывают пользовательские:** `.gemini/settings.json` (проект) > `~/.gemini/settings.json` (глобал).

### Синтаксис

Обычный Markdown. Пример:

```markdown
# Project: My Web App

## General Instructions
- Отвечать на русском по умолчанию
- Предпочитать функциональный подход

## Project Overview
- TypeScript + React + Express
- PostgreSQL через Prisma
- Bun как package manager

## Project Structure
- `src/components/` — React компоненты
- `src/api/` — Express маршруты
- `src/lib/` — общие утилиты
- `prisma/` — схема БД и миграции

## Build & Test
- `bun install` — install
- `bun run dev` — dev server
- `bun run test` — все тесты
- `bun run lint` — линтинг

## Coding Style
- 2 пробела для отступов
- TypeScript strict mode, no `any`
- Named exports over default
- Zod для валидации

## Constraints
- Не удалять файлы без подтверждения
- Не устанавливать пакеты без спроса
- Не писать секреты в код
```

### Модульность — @import

```markdown
# Main GEMINI.md

Основной контекст.

@./coding-style.md              # текущая директория
@../shared/conventions.md       # родительская
@/absolute/path/to/rules.md     # абсолютный путь
```

#### Правила @import

- Максимальная глубина вложенности: **5 уровней**
- Нет glob-паттернов (нельзя `@./components/*.md`)
- Импорты внутри код-блоков (` ``` `) игнорируются
- Циклические импорты автоматически блокируются
- Отсутствующие файлы — graceful failure (ошибка в тексте)

### Размер и лимиты

- **Gemini 2.5 Pro / 3 Pro:** до 1,000,000 токенов контекста
- **Antigravity Rules:** лимит **12 000 символов** на файл
- **Рекомендация для CLI:** GEMINI.md до 2000-3000 слов (проектный), до 500 слов (глобальный)
- GEMINI.md добавляется к системному промпту — расходует место в контексте
- При 50% заполнения контекста качество ответов падает

### Кастомизация имени файла (только CLI)

```json
{
  "context": {
    "fileName": ["AGENTS.md", "CONTEXT.md", "GEMINI.md"]
  }
}
```

---

## 5. AGENTS.md — универсальный стандарт

### Что это

Кроссплатформенный стандарт файла инструкций. Работает в Cursor, Claude Code, OpenCode, Antigravity IDE и других инструментах.

### Приоритет в Antigravity IDE

**AGENTS.md имеет НАИВЫСШИЙ приоритет** — выше, чем GEMINI.md.

### Рекомендация

Используйте **AGENTS.md** как основной файл инструкций, если работаете с несколькими инструментами. GEMINI.md — для специфики Gemini.

```markdown
# AGENTS.md (корень проекта)

## Универсальные правила для всех AI-ассистентов

- Отвечать на русском
- TypeScript strict, no any
- Коммиты по Conventional Commits
- ...
```

---

## 6. settings.json — полная схема

### Пути

- **Глобальный:** `~/.gemini/settings.json`
- **Проектный:** `.gemini/settings.json`

### Настройки контекста

```json
{
  "context": {
    "discoveryMaxDirs": 200,
    "loadMemoryFromIncludeDirectories": false,
    "fileName": ["GEMINI.md"],
    "fileFiltering": {
      "respectGitIgnore": true,
      "respectGeminiIgnore": true,
      "enableRecursiveFileSearch": true,
      "enableFuzzySearch": true,
      "customIgnoreFilePaths": []
    }
  }
}
```

| Настройка | Описание | Дефолт |
|-----------|----------|--------|
| `discoveryMaxDirs` | Макс. директорий для сканирования | `200` |
| `loadMemoryFromIncludeDirectories` | Сканировать include-директории | `false` |
| `fileName` | Имена файлов | `["GEMINI.md"]` |
| `respectGitIgnore` | Учитывать .gitignore | `true` |
| `respectGeminiIgnore` | Учитывать .geminiignore | `true` |
| `enableRecursiveFileSearch` | Рекурсивный поиск | `true` |
| `enableFuzzySearch` | Нечёткий поиск | `true` |

### Настройки модели

```json
{
  "model": {
    "name": "gemini-2.5-pro",
    "maxSessionTurns": -1,
    "compressionThreshold": 0.5,
    "disableLoopDetection": false
  }
}
```

| Настройка | Описание | Дефолт |
|-----------|----------|--------|
| `name` | Модель | auto |
| `maxSessionTurns` | Макс. ходов (-1 = бесконечно) | — |
| `compressionThreshold` | Доля контекста для сжатия | `0.5` |
| `disableLoopDetection` | Отключить детектор циклов | `false` |

### Настройки безопасности

```json
{
  "security": {
    "disableYoloMode": false,
    "disableAlwaysAllow": false,
    "enableConseca": false,
    "blockGitExtensions": true,
    "allowedExtensions": [".ts", ".js", ".py"],
    "folderTrust.enabled": true,
    "environmentVariableRedaction.enabled": false,
    "toolSandboxing": false
  }
}
```

| Настройка | Описание | Дефолт |
|-----------|----------|--------|
| `disableYoloMode` | Запретить YOLO-режим | `false` |
| `disableAlwaysAllow` | Запретить «Разрешить всегда» | `false` |
| `enableConseca` | LLM-генерация политик безопасности | `false` |
| `blockGitExtensions` | Блокировать git-расширения | `true` |
| `folderTrust.enabled` | Доверие к папкам | `true` |
| `environmentVariableRedaction.enabled` | Скрывать секреты из env | `false` |
| `toolSandboxing` | Изоляция инструментов | `false` |

### Настройки UI

```json
{
  "ui": {
    "hideContextSummary": false,
    "footer": {
      "hideContextPercentage": true
    },
    "compactToolOutput": true
  },
  "tools": {
    "truncateToolOutputThreshold": 40000
  }
}
```

### Экспериментальные

```json
{
  "experimental": {
    "memoryManager": false,
    "contextManagement": false
  }
}
```

| Настройка | Описание |
|-----------|----------|
| `memoryManager` | Субагент-менеджер памяти |
| `contextManagement` | Управление контекстом |

### MCP серверы (Gemini CLI)

```json
{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/path"],
      "cwd": "/working/dir",
      "timeout": 15000
    }
  }
}
```

**Важно:** Antigravity IDE использует **отдельный** файл для MCP: `~/.gemini/antigravity/mcp_config.json`. Конфигурация MCP **не синхронизируется** между CLI и IDE.

---

## 7. .geminiignore

### Что это

Файл `.geminiignore` в корне проекта. Исключает файлы и директории из контекста. Синтаксис аналогичен `.gitignore`.

### Пример

```gitignore
# Директории
node_modules/
dist/
build/
.next/
__pycache__/
.venv/

# Файлы
*.min.js
*.map
*.log
package-lock.json

# Конфигурация
.env
.env.local
apikeys.txt
credentials.json

# Медиа
*.png
*.jpg
*.svg
*.ico

# Тяжёлые файлы
*.csv
*.sql
```

### Правила

- Пустые строки и `#` комментарии игнорируются
- Glob-паттерны: `*`, `**`, `?`
- `/` в конце — только директории
- **`!` negation НЕ РАБОТАЕТ КОРРЕКТНО** (Issue #5444)
- Изменения требуют перезапуска сессии
- Учитывается при поиске файлов, `@`-подстановках, чтении

### Workaround для `!`

Вместо отрицательных паттернов:
```json
{
  "context": {
    "fileFiltering": {
      "customIgnoreFilePaths": ["/path/to/allowlist.txt"]
    }
  }
}
```

---

## 8. Команды

### Gemini CLI

| Команда | Описание |
|---------|----------|
| `/init` | Создать стартовый GEMINI.md |
| `/memory show` | Показать загруженный контекст |
| `/memory reload` | Перезагрузить контекст |
| `/memory add <текст>` | Добавить в `~/.gemini/GEMINI.md` |
| `/settings` | Интерактивное редактирование настроек |
| `/restore [id]` | Откат к checkpoint'у |
| `/checkpoint` | Создать checkpoint вручную |
| `/copy` | Копировать последний ответ |
| `/mcp` | Показать MCP-серверы |
| `/tools` | Список инструментов |
| `!command` | Shell-команда напрямую |
| `gemini --checkpointing` | Запуск с checkpointing |
| `gemini --yolo` | YOLO-режим (ОПАСНО) |
| `gemini -p "prompt"` | Однократный запрос (non-interactive) |

### Antigravity IDE

| Действие | Описание |
|----------|----------|
| `Cmd/Ctrl + ,` | Открыть настройки |
| `/workflow-name` | Вызвать воркфлоу |
| `@agent-name` | Упомянуть агента/сабагента |
| Customizations panel → Rules | Управление правилами |
| Customizations panel → Workflows | Управление воркфлоу |
| Customizations panel → Skills | Управление скиллами |
| Knowledge Editor | Редактор знаний |

---

## 9. MCP серверы

### Gemini CLI

Конфигурация в `~/.gemini/settings.json`:

```json
{
  "mcpServers": {
    "myserver": {
      "command": "python3",
      "args": ["-m", "my_mcp_server"],
      "cwd": "./mcp_tools",
      "timeout": 15000
    }
  }
}
```

Управление:
```bash
gemini mcp add <name>    # добавить
/mcp                     # список активных
```

### Antigravity IDE

Конфигурация в `~/.gemini/antigravity/mcp_config.json`:

```json
{
  "mcpServers": {
    "myserver": {
      "type": "local",
      "command": ["npx", "-y", "@modelcontextprotocol/server-everything"],
      "environment": { "MY_VAR": "value" },
      "enabled": true
    }
  }
}
```

### ⚠️ Критическое отличие

MCP-конфигурация **НЕ синхронизируется** между CLI и IDE. Нужно настраивать отдельно для каждого.

### Влияние на контекст

Каждый MCP-сервер добавляет описания своих инструментов в промпт. При многих серверах контекст разрастается.

---

## 10. Antigravity: Rules (Правила)

### Что это

Правила — это структурированные инструкции для Antigravity. Отличаются от GEMINI.md тем, что поддерживают **режимы активации**.

### Типы активации

| Тип | Описание | Когда применяется |
|-----|----------|-------------------|
| **Manual** | Активируется вручную | Через @mention в чате |
| **Always On** | Всегда активно | Каждый запрос |
| **Model Decision** | Модель решает сама | На основе описания правила |
| **Glob** | По шаблону файлов | При работе с файлами, подходящими под паттерн |

### Пути

| Тип | Путь |
|-----|------|
| Глобальные | `~/.gemini/GEMINI.md` (через UI: Customizations → Rules → + Global) |
| Проектные | `<project>/.agents/rules/<name>.md` |

### Лимиты

- **12 000 символов** на файл правила
- Поддержка `@filename` для включения содержимого других файлов

### Создание через UI

1. Customizations panel → Rules → «+ Workspace» (или «+ Global»)
2. Заполнить имя, описание, тип активации
3. Если Glob — указать паттерн (например, `*.py`, `src/**/ *.ts`)
4. Написать содержимое правила (Markdown)

### Пример правила (Always On)

**Файл:** `.agents/rules/typescript-strict.md`

```markdown
# TypeScript Strict Mode Rule

## Activation: Always On

All TypeScript code must:
- Use strict mode
- Have no `any` types
- Use explicit return types for functions
- Use Zod for runtime validation of external data
- Prefer `interface` over `type` for object shapes
```

### Пример правила (Glob)

**Файл:** `.agents/rules/python-style.md`

```markdown
# Python Code Style

## Activation: Glob: **/*.py

For all Python files:
- Follow PEP 8
- Use type hints for all function parameters and return values
- Use dataclasses or pydantic models for structured data
- Docstrings for all public functions and classes
- Maximum line length: 100 characters
```

### Пример правила (Model Decision)

**Файл:** `.agents/rules/security-review.md`

```markdown
# Security Review

## Activation: Model Decision

When the task involves:
- Authentication or authorization changes
- Database queries with user input
- File system operations
- API endpoint modifications
- Cryptographic operations

Apply these security checks:
1. Input validation for all user-provided data
2. Parameterized queries (no string interpolation in SQL)
3. Proper error handling (no stack traces to users)
4. Rate limiting considerations
5. CORS configuration review
```

---

## 11. Antigravity: Workflows (Воркфлоу)

### Что это

Последовательности шагов для повторяющихся задач. Аналог кастомных команд в OpenCode.

### Пути

| Тип | Путь |
|-----|------|
| Глобальные | `~/.gemini/antigravity/global_workflows/` |
| Проектные | Через UI (Customizations → Workflows → + Workspace) |

### Вызов

```
/workflow-name
```

### Возможности

- Вложенные воркфлоу (один воркфлоу может вызывать другой)
- Агент может **автоматически генерировать воркфлоу** на основе истории разговоров
- Лимит: **12 000 символов** на файл

### Пример воркфлоу

```markdown
# Code Review Workflow

## Steps:
1. Get the list of changed files from the last commit: `git diff --name-only HEAD~1`
2. For each changed file, read the full content
3. Analyze for:
   - Security vulnerabilities
   - Performance issues
   - Code style violations
   - Missing error handling
4. Generate a summary report with:
   - Issues found (severity: critical/warning/info)
   - Specific line references
   - Suggested fixes
5. If critical issues found, create a TODO list
```

### Пример вложенного воркфлоу

```markdown
# Full Feature Development

## Steps:
1. /plan-feature          ← вызывает другой воркфлоу
2. Implement the planned changes
3. /run-tests
4. /code-review
5. If review passes, /create-pr
```

---

## 12. Antigravity: Skills (Навыки)

### Что это

Переиспользуемые наборы инструкций для специфических задач. Аналог скиллов в OpenCode.

### Пути

| Инструмент | Глобальные | Проектные |
|-----------|-----------|-----------|
| **Gemini CLI** | `~/.gemini/skills/` | `.gemini/skills/` |
| **Antigravity IDE** | `~/.gemini/antigravity/skills/` | `.agents/skills/` |

**Важно:** Скиллы CLI и Antigravity **разделены** — живут в разных директориях.

### Формат

```markdown
---
name: my-skill
description: Description of what the skill does
---

# Skill Instructions

Step-by-step instructions for the AI...
```

### Пример скилла

**Файл:** `.agents/skills/git-release/SKILL.md`

```markdown
---
name: git-release
description: Create release notes from git history using conventional commits
---

# Git Release Notes Generator

## Instructions

1. Run `git log --oneline <last-tag>..HEAD`
2. Group commits by type:
   - `feat:` → Features
   - `fix:` → Bug Fixes
   - `perf:` → Performance
   - `refactor:` → Code Refactoring
   - `docs:` → Documentation
3. Generate markdown changelog
4. Include breaking changes section if any
5. Skip `chore:` and `style:` commits
```

---

## 13. Antigravity: Artifacts (Артефакты)

### Что это

Специфичная для Antigravity функция. Артефакты — это промежуточные и финальные результаты работы агентов.

### Типы артефактов

| Тип | Описание |
|-----|----------|
| **Plans** | План-задачи, сгенерированный агентом |
| **Screenshots** | Скриншоты состояния (например, после выполнения) |
| **Browser recordings** | Записи браузерных сессий |
| **Code diffs** | Изменения в коде |
| **Test results** | Результаты тестирования |

### Путь хранения

```
~/.antigravity/Artifacts/
```

### Artifact Review Policy

Настройка в IDE:

| Значение | Описание |
|----------|----------|
| **Always Proceed** | Артефакты применяются без подтверждения |
| **Request Review** | Пользователь подтверждает каждый артефакт |

### Нет аналога в CLI

Артефакты — уникальная функция Antigravity. В CLI для верификации используются checkpointing и ручная проверка.

---

## 14. Antigravity: Settings (Настройки IDE)

### Доступ

- **Горячая клавиша:** `Cmd + ,` (Mac) / `Ctrl + ,` (Windows/Linux)
- Вкладка Settings в Agent Manager
- Editor → Settings → Open Antigravity User Settings

### Основные настройки

| Настройка | Значения | Описание |
|-----------|----------|----------|
| Artifact Review Policy | Always Proceed / Request Review | Подтверждение артефактов |
| Terminal Command Auto Execution | Request Review / Always Proceed | Автовыполнение команд |
| Agent Non-Workspace File Access | Allow / Deny | Доступ к файлам вне проекта |
| Enable Telemetry | true / false | Сбор данных |
| Agent Modes | Planning / Fast | Глубокое планирование vs быстрое выполнение |

### Agent Modes

| Режим | Описание | Когда использовать |
|-------|----------|-------------------|
| **Planning** | Агент сначала глубоко планирует, потом действует | Сложные задачи, много файлов |
| **Fast** | Агент действует быстро, минимальное планирование | Простые фиксы, понятные задачи |

---

## 15. Antigravity: Manager View и параллельные агенты

### Что это

Manager View — «центр управления миссиями» для запуска и наблюдения за **несколькими агентами параллельно**.

### Возможности

- Запуск нескольких агентов одновременно
- Мониторинг состояния каждого агента в реальном времени
- Разделение задач между агентами по воркспейсам
- Оркестрация: агент может создавать подагенты (subagent)
- Визуальные индикаторы прогресса

### Использование

1. Открыть Manager View в Antigravity
2. Создать новую «миссию» (mission)
3. Назначить задачу и агента
4. Запустить — агент работает параллельно
5. Мониторить прогресс, просматривать артефакты
6. Принимать или отклонять результаты

### Нет аналога в CLI

Gemini CLI работает с одним агентом за раз. Для параллелизма в CLI нужно открывать несколько терминальных сессий.

---

## 16. Конфликт GEMINI.md (#16058)

### Описание

**Issue:** https://github.com/google-gemini/gemini-cli/issues/16058
**Открыт:** 7 января 2026
**Статус:** Internal roadmap item

### Суть проблемы

**Оба инструмента используют один и тот же файл:** `~/.gemini/GEMINI.md`

- Antigravity автоматически создаёт/модифицирует `~/.gemini/GEMINI.md` при добавлении глобальных правил через UI
- Gemini CLI читает и модифицирует тот же файл
- Результат: **загрязнение конфигурации** — инструкции одного инструмента «утекают» в другой

### Последствия

- Непредсказуемое поведение AI в обоих инструментах
- Путаница — непонятно, какой инструмент изменил файл
- Конфликты правил

### Предложенные решения

**Вариант 1:** Подкаталог для Antigravity
```
~/.gemini/GEMINI.md              ← Только Gemini CLI
~/.gemini/antigravity/RULES.md   ← Только Antigravity
```

**Вариант 2:** Отдельный каталог
```
~/.gemini/GEMINI.md              ← Gemini CLI
~/.antigravity/GEMINI.md         ← Antigravity
```

### Что разделено (работает)

| Сущность | Gemini CLI | Antigravity IDE |
|----------|-----------|----------------|
| Скиллы | `~/.gemini/skills/` | `~/.gemini/antigravity/skills/` |
| MCP | `settings.json` → `mcpServers` | `antigravity/mcp_config.json` |
| Воркфлоу | Custom Commands | `antigravity/global_workflows/` |
| Расширения | `~/.gemini/extensions/` | Встроенный магазин |

### Что НЕ разделено (проблема)

| Сущность | Путь | Проблема |
|----------|------|----------|
| **Глобальный контекст** | `~/.gemini/GEMINI.md` | Общий файл |
| **OAuth** | `~/.gemini/oauth_creds.json` | Общий (ожидаемо) |

### Workaround (до официального фикса)

Добавьте комментарии-разделители в `~/.gemini/GEMINI.md`:

```markdown
<!-- GEMINI CLI ONLY -->
- CLI-specific rules here

<!-- ANTIGRAVITY IDE ONLY -->
- IDE-specific rules here
```

Или используйте **AGENTS.md** как основной файл — он имеет высший приоритет в Antigravity и не конфликтует.

---

## 17. Безопасность

### Общие риски

| Риск | CLI | IDE | Защита |
|------|-----|-----|--------|
| YOLO-режим | `--yolo` (опасно) | Strict Mode | `disableYoloMode: true` |
| Секреты в GEMINI.md | ✅ | ✅ | Не хранить секреты |
| Деструктивные команды | ✅ | ✅ | Пермиссии в IDE |
| MCP-код на машине | ✅ | ✅ | Только доверенные серверы |
| Утечка env-переменных | ✅ | ✅ | `environmentVariableRedaction: true` |
| Баны ToS (#20632) | ✅ | ✅ | Не нарушать ToS |
| Недоверенные папки | Folder Trust | — | `folderTrust.enabled: true` |

### Специфичные для CLI

| Риск | Защита |
|------|--------|
| `rm -rf` без подтверждения | `security.disableAlwaysAllow: true` |
| Git force push | Ручной контроль коммитов |
| Импорт системных файлов | `validateImportPath` (но абсолютные пути работают) |

### Специфичные для IDE

| Риск | Защита |
|------|--------|
| Автовыполнение терминальных команд | Terminal Command Auto Execution → Request Review |
| Доступ к файлам вне воркспейса | Agent Non-Workspace File Access → Deny |
| Непроверенные артефакты | Artifact Review Policy → Request Review |

---

## 18. Проблемы и решения

### Gemini CLI

| # | Проблема | Workaround |
|---|----------|-----------|
| #12738 | GEMINI.md игнорируется | `/memory show` → проверить путь |
| #16905 | Модель игнорирует «Do not modify» | «CRITICAL: NEVER...» вместо мягких формулировок |
| #13651 | Токен-лимит исчерпывается | `.geminiignore`, `discoveryMaxDirs: 50`, явные `@` |
| #2479 | Высокое потребление токенов | `/memory show` → проверить загруженные файлы |
| #5444 | `!` в .geminiignore не работает | `customIgnoreFilePaths` в settings.json |
| #3434 | Запрос .geminiignore | Реализовано |
| #12093 | Качество модели (центральный) | Структурированные промпты |

### Antigravity IDE

| # | Проблема | Workaround |
|---|----------|-----------|
| #16058 | Конфликт GEMINI.md с CLI | AGENTS.md + комментарии-разделители |
| #20632 | Массовые баны ToS | Не нарушать ToS, следить за лимитами |
| — | MCP `type` не принимается | Проверить формат mcp_config.json |
| — | PATH не наследуется | Настроить environment в MCP-конфиге |
| — | Лимиты сбрасываются каждые 5ч | Планировать работу |

### Общие

| Проблема | Workaround |
|----------|-----------|
| MCP не синхронизируется | Настраивать отдельно для CLI и IDE |
| Скиллы разделены | Определять в обоих местах или использовать AGENTS.md |
| OAuth общий — бан одного влияет на другой | Разные аккаунты если возможно |

---

## 19. Лучшие практики

### Для обоих инструментов

1. **AGENTS.md как основной файл** — универсальный, без конфликтов, высший приоритет в IDE
2. **GEMINI.md — для Gemini-специфики** — настройки MCP, особенности Gemini API
3. **Не хранить секреты** — использовать переменные окружения
4. **Контролировать размер GEMINI.md** — до 2000 слов проектный, до 500 глобальный
5. **Использовать `.geminiignore`** — исключать тяжёлые файлы
6. **Проверять `/memory show`** (CLI) или Customizations panel (IDE)

### Только для Gemini CLI

7. **`--checkpointing`** для отката изменений
8. **`/memory add`** для «журнала решений» — AI не противоречит прошлым решениям
9. **Не использовать `--yolo`** без крайней необходимости
10. **`model.compressionThreshold: 0.5`** — начинать новую сессию при 50% контекста

### Только для Antigravity IDE

11. **Rules с правильной активацией** — Manual для редких правил, Always On для критичных
12. **Glob-правила** — активировать по типу файла (Python, TypeScript, etc.)
13. **Workflows для повторяющихся задач** — code review, feature development, deployment
14. **Manager View для параллельных задач** — несколько агентов для разных компонентов
15. **Artifact Review → Request Review** — не применять результаты вслепую
16. **MCP настраивать отдельно** — через `antigravity/mcp_config.json`

---

## 20. Чеклист настройки нового проекта

### Общие шаги

- [ ] Создать `./AGENTS.md` (основной файл инструкций)
- [ ] Создать `./GEMINI.md` (Gemini-специфичные инструкции)
- [ ] Создать `.geminiignore` (исключения)
- [ ] Создать `.agents/rules/` (правила для Antigravity)
- [ ] Создать `.agents/skills/` (скиллы для Antigravity)
- [ ] Настроить MCP-серверы (отдельно для CLI и IDE)

### Gemini CLI (один раз)

- [ ] Создать `~/.gemini/GEMINI.md` (глобальные правила)
- [ ] Настроить `~/.gemini/settings.json` (модель, безопасность, контекст)
- [ ] Настроить MCP-серверы в settings.json
- [ ] Создать `.gemini/settings.json` (проектные настройки)

### Antigravity IDE (один раз)

- [ ] Установить с https://antigravity.google
- [ ] Настроить через `Cmd/Ctrl + ,` (Artifact Policy, Terminal Auto Exec)
- [ ] Создать глобальные воркфлоу (если нужно)
- [ ] Настроить MCP через `~/.gemini/antigravity/mcp_config.json`

---

## 21. Совместное использование CLI + IDE

### Рекомендованная структура проекта

```
project/
├── AGENTS.md                    ← ОСНОВНОЙ (универсальный, высший приоритет)
├── GEMINI.md                    ← Gemini-специфичный контекст
├── .geminiignore                ← Исключения (только CLI)
├── .gemini/
│   └── settings.json            ← Настройки CLI
├── .agents/
│   ├── rules/                   ← Правила Antigravity
│   │   ├── typescript-strict.md  (Always On)
│   │   ├── python-style.md       (Glob: **/*.py)
│   │   └── security-review.md    (Model Decision)
│   └── skills/                  ← Скиллы Antigravity
│       └── git-release/SKILL.md
└── opencode.json                ← Если используете ещё и OpenCode
    └── instructions: ["GEMINI.md", "AGENTS.md"]
```

### Стратегия разделения контекста

| Что | Куда | Почему |
|-----|------|--------|
| Универсальные правила | `AGENTS.md` | Работает везде, без конфликтов |
| Gemini CLI-специфика | `GEMINI.md` | Читается CLI, не конфликтует |
| Gemini CLI-специфика | `.gemini/settings.json` | Только CLI |
| Antigravity правила | `.agents/rules/` | Только Antigravity |
| Antigravity скиллы | `.agents/skills/` | Только Antigravity |
| Antigravity MCP | `~/.gemini/antigravity/mcp_config.json` | Только Antigravity |
| Gemini CLI MCP | `~/.gemini/settings.json` → `mcpServers` | Только CLI |
| Глобальные личные правила | `~/.gemini/GEMINI.md` с комментариями-разделителями | Общий файл (workaround) |

### Правило для `~/.gemini/GEMINI.md` (общий файл)

```markdown
# Global Rules

## Общие (для CLI и IDE)
- Отвечать на русском
- TypeScript strict, no any
- Conventional Commits

## Gemini CLI Only
- Использовать checkpointing
- Не выполнять rm -rf без подтверждения

## Antigravity IDE Only
- Всегда запрашивать review для артефактов
- Использовать Planning mode для сложных задач
```

---

## Источники

### Gemini CLI
- https://geminicli.com/docs/cli/gemini-md/
- https://geminicli.com/docs/reference/memport/
- https://geminicli.com/docs/cli/settings
- https://geminicli.com/docs/cli/gemini-ignore/
- https://github.com/google-gemini/gemini-cli
- https://github.com/addyosmani/gemini-cli-tips
- GitHub Issues: #12738, #16905, #13651, #2479, #5444, #3434, #12093

### Antigravity IDE
- https://antigravity.google/docs
- https://antigravity.google/docs/rules-workflows
- https://antigravity.google/docs/mcp
- https://antigravity.google/docs/skills
- https://antigravity.google/docs/agent-modes-settings
- https://github.com/google-gemini/gemini-cli/issues/16058
- The Verge: Google Antigravity IDE announcement
- Google Cloud Blog: Choosing Antigravity or Gemini CLI
- Reddit: r/GoogleAntigravityIDE
