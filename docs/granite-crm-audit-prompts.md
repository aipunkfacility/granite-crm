# Granite CRM — Промпты для поэтапного аудита проекта

> Набор из **8 промптов** для AI-агента. Каждый промпт — отдельная стадия аудита.
> Перед первым промптом агенту нужно дать файл **granite-crm-audit-guide.md**.
> Промпты выполняются **строго последовательно**, результаты каждого этапа записываются в `worklog.md`.

---

## Мастер-промпт: общие правила для всех этапов

```
## Общие правила для агента-аудитора:

1. Ты — аудитор кода. Твоя задача — находить реальные баги, уязвимости и потери данных.
2. НЕ предлагай стилистические улучшения, рефакторинг "для красоты" или "best practices" без конкретной причины.
3. Каждая находка должна содержать:
   - Файл и строку (если возможно)
   - Категорию (SSRF / DATA_LOSS / BUG / ORM_DRIFT / SECURITY / TEST)
   - Серьёзность (CRITICAL / HIGH / MEDIUM / LOW)
   - Конкретное описание: что не так, какие данные повреждены, как это проявляется
   - Как воспроизвести или доказать проблему
4. Читай каждый файл ПОЛНОСТЬЮ перед анализом. Не делай выводов по фрагментам.
5. Используй Grep и Read для поиска паттернов по всему проекту.
6. Результаты записывай в /home/z/my-project/download/audit-findings-phase-{N}.md
7. В /home/z/my-project/worklog.md пиши: что проверил, что нашёл, сколько находок.
8. Проверяй предыдущие этапы в worklog.md перед началом.
9. НЕ трогай исходный код. Только чтение и отчёт.
10. Если находишь >20 проблем в одном файле — выдели этот файл как "требующий полной переработки" и перейди к следующему.
11. После завершения этапа остановись и жди инструкции.
```

---

## Промпт 1: Разведка и карта потоков данных

```
## Этап 1: Разведка и картирование потоков данных

### Контекст:
У тебя есть гайд по аудиту: /home/z/my-project/download/granite-crm-audit-guide.md.
Ты аудируешь проект granite-crm-db — скрапер компаний с пайплайном обогащения и экспорта.

### Твоя задача:
Провести разведку проекта и составить полную карту потоков данных. Это фундамент для всех последующих этапов.

### Что сделать:

1. **Структура проекта:**
   - Прочитай README.md, pyproject.toml / setup.py / requirements.txt
   - Список всех Python-файлов (glob **/*.py)
   - Структура директорий (tree)
   - Точки входа (cli.py, __main__.py, web-сервер)

2. **ORM-модели и таблицы БД:**
   - Найди все SQLAlchemy модели (Base, Column, Table)
   - Составь таблицу: название таблицы → ORM-класс → ключевые поля → типы
   - Найди все ForeignKey связи
   - Проверь: есть ли Alembic? Сколько миграций?

3. **Карта потоков данных:**
   - Для каждого потока (Scraping → Dedup → Enrichment → Scoring → Export):
     - Вход: откуда данные поступают (CLI, config, HTTP, файл)
     - Обработчик: какой класс/функция обрабатывает
     - Выход: куда данные сохраняются (какая таблица, какой формат)
     - Трансформация: Pydantic → ORM, dict → Row, JSON → Python
   - Нарисуй в тексте схему переходов между модулями
   - Найди оркестратор (PipelineManager или аналог)

4. **Конфигурация:**
   - Формат config.yaml
   - Как загружается (yaml.safe_load / Pydantic / OmegaConf)
   - Где используются значения конфига
   - Есть ли валидация конфига?

5. **Внешние зависимости (HTTP-запросы):**
   - Найди ВСЕ места с requests.get, fetch_page, aiohttp, subprocess.run
   - Для каждого: какой URL, откуда берётся, есть ли валидация

6. **Тесты:**
   - Сколько тестов? (pytest --collect-only)
   - Файлы с тестами и что они покрывают
   - Фикстуры, моки

### Формат результата:

Запиши в /home/z/my-project/download/audit-findings-phase-1.md:

```markdown
# Этап 1: Разведка и карта потоков

## 1. Структура проекта
- Файлов: N
- Директории: ...
- Точки входа: ...

## 2. Таблицы БД и ORM-модели
| Таблица | ORM-класс | Поля | FK |

## 3. Карта потоков данных
(текстовая схема с переходами)

## 4. Конфигурация
- Формат: ...
- Валидация: есть/нет
- Проблемы: ...

## 5. Внешние HTTP-запросы
| Файл | Функция | URL-источник | Валидация |

## 6. Тесты
- Всего: N
- Покрытие модулей: ...

## 7. Ключевые наблюдения
- Потенциальные точки риска: ...
- Файлы, требующие внимания: ...
```

### Запись в worklog:
```
---
Task ID: audit-1
Agent: audit-recon
Task: Разведка и картирование потоков данных

Work Log:
- Прочитал структуру проекта (N файлов)
- Составил карту потоков (N потоков)
- Нашёл N таблиц, N FK-связей
- Обнаружил N внешних HTTP-вызовов
- Проверил N тестов

Stage Summary:
- Ключевые потоки: ...
- Рискованные точки: ...
- Файлы для детальной проверки: ...
```
```

---

## Промпт 2: Аудит входных точек

```
## Этап 2: Аудит по входным точкам

### Контекст:
Ты провёл Этап 1 (разведку). Читай результаты из /home/z/my-project/download/audit-findings-phase-1.md.
Гайд по аудиту: /home/z/my-project/download/granite-crm-audit-guide.md (раздел 3).

### Твоя задача:
Проверить ВСЕ входные точки проекта на предмет багов, уязвимостей и потери данных.
Иди от входа к выходу, по цепочке данных.

### Что проверить:

**Входная точка 1: Конфигурация**
- Читай config.yaml полностью
- Читай код загрузки конфига (load_config, yaml.safe_load и т.д.)
- Проверь: есть ли Pydantic-валидация? Если нет — это находка.
- Для каждого поля config.yaml: используется ли оно в коде? (grep)
- Что происходит при malformed config.yaml (отсутствующее поле, неверный тип)?
- Есть ли hardcoded defaults в коде, которые конфликтуют с config?

**Входная точка 2: CLI / Аргументы командной строки**
- Читай cli.py полностью
- Как парсятся аргументы? (argparse, click, typer)
- Есть ли валидация значений аргументов?
- Что происходит при неверных аргументах?
- Загрузка конфига: multiple load? кэширование? race conditions?

**Входная точка 3: Внешние данные (скрапинг)**
- Для каждого скрапера: что он парсит? Какой формат ожидает?
- Читай Pydantic-модели входных данных (RawCompany и т.д.)
- Проверь: что происходит при невалидном HTML / отсутствующих полях?
- Есть ли retry-логика? timeout?

**Входная точка 4: Оркестратор / Pipeline**
- Читай PipelineManager (или аналог) полностью
- Как он создаёт фазы? Eager или lazy?
- Проверь checkpoint-логику: что при повреждённом checkpoint? При --force?
- Что происходит при падении одной фазы? Пропускаются ли остальные?

### Формат находок:

Для каждой проблемы:
```markdown
### [CODE-001] {краткое название}
- **Файл:** `path/to/file.py:line`
- **Категория:** BUG / SECURITY / DATA_LOSS / CONFIG
- **Серьёзность:** CRITICAL / HIGH / MEDIUM / LOW
- **Поток данных:** откуда → куда
- **Описание:** конкретно что не так
- **Влияние:** что ломается у пользователя
- **Как воспроизвести:** шаги
```

### Запись результата:
- /home/z/my-project/download/audit-findings-phase-2.md
- Worklog в /home/z/my-project/worklog.md
```

---

## Промпт 3: Аудит безопасности (SSRF и инъекции)

```
## Этап 3: Аудит безопасности — SSRF, XSS, инъекции

### Контекст:
Читай предыдущие результаты: /home/z/my-project/download/audit-findings-phase-{1,2}.md
Гайд: /home/z/my-project/download/granite-crm-audit-guide.md (раздел 4.1).

### Твоя задача:
Найти ВСЕ уязвимости безопасности. Особенно SSRF — самый частый вектор в скраперах.

### Пошаговая проверка:

**Шаг 1: Найти все HTTP-запросы**
```
grep -rn "requests\.\(get\|post\|head\|put\)\|fetch_page\|aiohttp\|httpx\|urlopen\|subprocess.run" --include="*.py"
```
Для КАЖДОГО вызова проверь:
1. Откуда берётся URL? (config / scraped HTML / user input / hardcoded)
2. Есть ли валидация URL перед запросом?
3. Проверяется ли IP на localhost / internal / cloud-metadata (169.254.169.254)?
4. Проверяется ли scheme (только http/https)?
5. Есть ли DNS-резолв до запроса (защита от DNS rebinding)?
6. Есть ли timeout? Какой?
7. Есть ли retry? Ограничен ли?

**Шаг 2: Проверить URL-валидаторы**
- Найди `is_safe_url`, `_is_internal_url`, `validate_url` и аналоги
- Читай их полностью
- Проверь порядок операций: cleanup URL до или после SSRF-проверки?
- Проверь: mutable default arguments?
- Проверь: обрабатываются ли редиректы?

**Шаг 3: Найти модули, которые НЕ вызывают валидатор**
- Сравни список HTTP-вызовов со списком вызовов is_safe_url
- Каждый HTTP-вызов без валидации = находка CRITICAL/HIGH

**Шаг 4: subprocess / OS-команды**
```
grep -rn "subprocess\|os.system\|os.popen\|eval(\|exec(" --include="*.py"
```
- Пользовательский ввод в команде?
- Shell=True без необходимости?

**Шаг 5: SQL-инъекции**
```
grep -rn "text(\|raw_connection\|execute.*f\"\|execute.*%\|execute.*format" --include="*.py"
```
- Raw SQL с интерполяцией строк?

**Шаг 6: XSS / template injection**
```
grep -rn "markdown\|innerHTML\|render_template\|f\".*<.*>\"" --include="*.py"
```
- URL в Markdown без очистки scheme?
- User-controlled данные в HTML/template без escape?

**Шаг 7: Утечки данных в логах**
```
grep -rn "logger\.\(info\|debug\|warning\|error\)" --include="*.py"
```
- Логируются ли пароли, API-ключи, полные URL с credentials?
- Есть ли PII в логах?

### Формат находок:

```markdown
### [SEC-001] SSRF через {файл}
- **Файл:** `path/to/file.py:line`
- **Серьёзность:** CRITICAL / HIGH
- **Вектор:** URL берётся из {источник}, валидация отсутствует
- **Атака:** attacker-controlled URL → запрос к internal service
- **Пример:** `requests.get(url)` без is_safe_url()
- **Рекомендация:** добавить is_safe_url() перед запросом
```

### Запись результата:
- /home/z/my-project/download/audit-findings-phase-3.md
- Worklog в /home/z/my-project/worklog.md
```

---

## Промпт 4: Аудит потери данных и ORM-drift

```
## Этап 4: Потеря данных, ORM ↔ Alembic drift, маппинг

### Контекст:
Читай предыдущие результаты: /home/z/my-project/download/audit-findings-phase-{1,2,3}.md
Гайд: /home/z/my-project/download/granite-crm-audit-guide.md (разделы 4.2 и 4.4).

### Твоя задача:
Найти все места, где данные теряются при преобразованиях, и расхождения между ORM и Alembic.

### Пошаговая проверка:

**Шаг 1: ORM ↔ Alembic drift**
- Читай ВСЕ ORM-модели в database.py (или models.py)
- Читай ВСЕ Alembic-миграции (alembic/versions/*.py)
- Составь таблицу: ORM-таблица → Alembic-миграция → совпадение
- Проверь КАЖДУЮ колонку, FK, индекс
- Особенно: ON DELETE CASCADE/SET NULL — есть ли в миграции?
- Проверь: есть ли таблицы в ORM, которых нет в Alembic?
- Проверь: есть ли колонки в ORM, которых нет в Alembic?

**Шаг 2: Pydantic ↔ ORM маппинг**
- Найди все места, где Pydantic-модель конвертируется в ORM-Row:
```
grep -rn "session.add\|session.merge\|Row(" --include="*.py" | grep -v test
```
- Для каждого вызова Row(...): все ли поля из Pydantic передаются?
- Сравни Pydantic-модель и ORM-Row: какие поля совпадают, какие отличаются?
- Проверь типы: Pydantic `list[float]` vs ORM `String` — как конвертируется?

**Шаг 3: Маппинг при слиянии (merge/dedup)**
- Читай merge/dedup логику полностью
- Что возвращает merge_cluster()? Все ли поля?
- Что передаётся в CompanyRow()? Все ли поля из merge_cluster?
- Проверь: messengers, merged_from, geo — сохраняются ли?

**Шаг 4: Обогащение (enrichment)**
- Читай enrichment_phase.py полностью
- После обогащения: какие поля обновляются? Все ли сохраняются?
- Проверь: session.commit() — есть ли? Не двойной ли?
- Проверь: session.flush() vs commit — правильный ли порядок?

**Шаг 5: Экспорт (export)**
- Читай ВСЕ экспортёры (CSV, Markdown, JSON)
- Какие поля экспортируются? Все ли доступные?
- Проверь: данные не теряются при форматировании?
- Проверь: кодировка (UTF-8), обработка None/пустых значений

**Шаг 6: JSON-парсинг**
- Найди все json.loads() и json.dumps()
- Проверь: обработка malformed JSON?
- Проверь: вложенные структуры парсятся корректно?

### Формат находок:

```markdown
### [DATA-001] Потеря поля {field} при {операция}
- **Файл:** `path/to/file.py:line`
- **Категория:** DATA_LOSS / ORM_DRIFT / TYPE_MISMATCH
- **Серьёзность:** HIGH / MEDIUM
- **Описание:** поле X теряется при конвертации Pydantic → ORM
- **Доказательство:** в Pydantic есть поле X, в ORM Row() не передаётся
- **Влияние:** данные X недоступны в последующих фазах / API
```

### Запись результата:
- /home/z/my-project/download/audit-findings-phase-4.md
- Worklog в /home/z/my-project/worklog.md
```

---

## Промпт 5: Аудит логики и багов

```
## Этап 5: Аудит логики — баги, краши, edge cases

### Контекст:
Читай предыдущие результаты: /home/z/my-project/download/audit-findings-phase-{1,2,3,4}.md
Гайд: /home/z/my-project/download/granite-crm-audit-guide.md (раздел 4.3).

### Твоя задача:
Найти баги в бизнес-логике: некорректные проверки, краши на edge cases, неправильные типы.

### Пошаговая проверка:

**Шаг 1: None / falsy / empty — потенциальные краши**
```
grep -rn "\.get(\|\.lower()\|\.upper()\|\.strip()\|\.split(" --include="*.py" | grep -v test
```
Для каждого вызова проверь:
- `.get("key", default)` — если key есть со значением None, вернёт None, не default
- `.lower()` на None → AttributeError
- `.split()` на int → AttributeError
- `if not x` — отбрасывает 0, "", [], False (использовать `if x is None`)

**Шаг 2: Type errors — неправильные типы**
```
grep -rn "float(\|int(\|str(\|len(" --include="*.py" | grep -v test
```
- `float(x)` — x может быть None / str / list → TypeError
- `len(x)` — x может быть int / None → TypeError
- Строковая конкатенация с int: `"text" + 123`

**Шаг 3: Ошибки guard-порядка**
- Найди места, где проверка значения идёт ПОСЛЕ использования:
  ```python
  result = data["key"].lower()  # краш если data["key"] = None
  if result: ...                 # поздно
  ```
- Должно быть: сначала проверка, потом использование

**Шаг 4: Exception handling — слишком широкий except**
```
grep -rn "except Exception\|except:" --include="*.py" | grep -v test
```
- `except Exception` — ловит всё, включая KeyboardInterrupt, SystemExit
- Отсутствие logging в except — ошибка "молчит"
- bare `except:` — ловит вообще всё включая SystemExit

**Шаг 5: Off-by-one и boundary**
- Range checks: `range(0, len(x))` — не включает последний элемент?
- Pagination: `offset + limit > total`?
- Date/time: timezone-aware vs naive datetime?

**Шаг 6: Concurrency issues**
- Shared mutable state (global dict, list, class variable)
- Thread-safety: Race conditions при multi-threading
- SQLite: "database is locked" — есть ли busy_timeout?

**Шаг 7: Resource leaks**
- `open()` без `with`
- Session без close / dispose
- Playwright browser без close
- tempfile без cleanup

**Шаг 8: Dead code и неиспользуемые импорты**
```
grep -rn "import .*  # unused\|TODO\|FIXME\|HACK\|XXX" --include="*.py"
```
- Мёртвый код от предыдущих правок
- Unused imports
- Commented-out code

### Формат находок:

```markdown
### [BUG-001] {краткое описание}
- **Файл:** `path/to/file.py:line`
- **Серьёзность:** CRITICAL / HIGH / MEDIUM / LOW
- **Тип:** CRASH / WRONG_RESULT / SILENT_ERROR / RESOURCE_LEAK / DEAD_CODE
- **Описание:** что именно не так
- **Входные данные для воспроизведения:** конкретные значения, на которых ломается
- **Ожидаемое поведение vs фактическое:**
- **Стек-трейс (если краш):** (предполагаемый)
```

### Запись результата:
- /home/z/my-project/download/audit-findings-phase-5.md
- Worklog в /home/z/my-project/worklog.md
```

---

## Промпт 6: Модульный аудит (поштучно)

```
## Этап 6: Модульный аудит — каждый модуль целиком

### Контекст:
Читай предыдущие результаты: /home/z/my-project/download/audit-findings-phase-{1,2,3,4,5}.md
Гайд: /home/z/my-project/download/granite-crm-audit-guide.md (раздел 5).
Карта потоков: /home/z/my-project/download/audit-findings-phase-1.md.

### Твоя задача:
Пройти по КАЖДОМУ модулю проекта целиком. Найти проблемы, которые не попали в предыдущие этапы.

### Как работать:
Для каждого модуля ниже:
1. Читай ВСЕ файлы модуля полностью
2. Проверяй по чеклисту
3. Проверяй взаимодействия с другими модулями (импорты, вызовы)
4. Если находка уже есть в предыдущих фазах — пропусти, но отметь "уже найдено в phase X"

### Модули для проверки:

**Модуль 1: pipeline/**
- Читай: manager.py, enrichment_phase.py, dedup_phase.py, scoring_phase.py, scraping_phase.py, checkpoint.py
- Чеклист:
  - [ ] Размер файлов (>300 строк = signal для рефакторинга)
  - [ ] Single Responsibility: один класс — одна задача?
  - [ ] DRY: повторяющийся код?
  - [ ] Error handling: каждая фаза обрабатывает свои ошибки?
  - [ ] Session management: commit/rollback/close правильный?
  - [ ] Logging: достаточно для debug в production?

**Модуль 2: dedup/**
- Читай: merger.py, name_matcher.py, phone_cluster.py, validator.py, site_matcher.py
- Чеклист:
  - [ ] Алгоритмы: O(n²)? Есть ли оптимизация?
  - [ ] Кластеризация: корректные границы кластеров?
  - [ ] Слияние: все ли поля сохраняются?
  - [ ] Валидация URL: полная? Правильный порядок?
  - [ ] Edge cases: пустые строки, None, дубликаты

**Модуль 3: enrichers/**
- Читай: classifier.py, tg_finder.py, tg_trust.py, messenger_scanner.py, tech_extractor.py
- Чеклист:
  - [ ] HTTP-запросы: есть ли rate limiting? Timeout?
  - [ ] Null-checks: ответ API может быть None?
  - [ ] Hardcoded значения: города, отрасли, URL?
  - [ ] Dead code: неиспользуемые функции/параметры?

**Модуль 4: scrapers/**
- Читай: ВСЕ файлы в scrapers/
- Чеклист:
  - [ ] DRY: общие паттерны вынесены?
  - [ ] Rate limiting: запросы к одному домену?
  - [ ] Timeout: есть ли? Адекватный ли?
  - [ ] Retry: есть ли? Экспоненциальный backoff?
  - [ ] Resource cleanup: браузер, tempfile?
  - [ ] Parsing: хрупкий regex vs robust parser?

**Модуль 5: exporters/**
- Читай: ВСЕ файлы в exporters/
- Чеклист:
  - [ ] Encoding: UTF-8?
  - [ ] None/empty handling
  - [ ] XSS в Markdown: URL scheme whitelist?
  - [ ] CSV: правильное экранирование? Запятые в значениях?
  - [ ] Полнота: все ли нужные поля экспортируются?

**Модуль 6: database.py + models.py**
- Читай полностью
- Чеклист:
  - [ ] Все ли таблицы имеют __repr__?
  - [ ] to_dict() — полные ли?
  - [ ] Connection pool settings (SQLite-specific)
  - [ ] Session lifecycle management

**Модуль 7: tests/**
- Читай ВСЕ тестовые файлы
- Чеклист:
  - [ ] Слабые assertions: `>=`, `is not None` вместо точных значений
  - [ ] Отсутствующие negative-тесты (None, empty, invalid)
  - [ ] Duplicated fixtures
  - [ ] Mocks: правильные ли? Не слишком широкие?
  - [ ] Coverage: какие модули НЕ покрыты тестами?

### Формат результата:
- /home/z/my-project/download/audit-findings-phase-6.md
- Worklog в /home/z/my-project/worklog.md
- Для каждого модуля: таблица файлов → найденные проблемы → статус
```

---

## Промпт 7: Сводный отчёт

```
## Этап 7: Сводный отчёт аудита

### Контекст:
Все этапы завершены. Читай ВСЕ файлы находок:
- /home/z/my-project/download/audit-findings-phase-1.md
- /home/z/my-project/download/audit-findings-phase-2.md
- /home/z/my-project/download/audit-findings-phase-3.md
- /home/z/my-project/download/audit-findings-phase-4.md
- /home/z/my-project/download/audit-findings-phase-5.md
- /home/z/my-project/download/audit-findings-phase-6.md

### Твоя задача:
Свести ВСЕ находки в единый отчёт с приоритизацией и планом исправлений.

### Что сделать:

**1. Дедупликация**
- Убрать дубликаты (одна проблема найдена в разных фазах)
- Оставить наиболее подробное описание
- Учесть: одна корневая причина → несколько проявлений (объединить)

**2. Классификация**
- По категории: SECURITY / DATA_LOSS / BUG / ORM_DRIFT / CONFIG / TEST / ARCHITECTURE
- По серьёзности: CRITICAL / HIGH / MEDIUM / LOW
- По файлу: какие файлы затронуты

**3. Приоритизация для исправлений**
- Группы по приоритету (как в гайде, раздел 6):
  - Группа 1: CRITICAL + HIGH + падающие тесты
  - Группа 2: ORM + pipeline bugs
  - Группа 3: Deep security fixes
  - Группа 4: Defensive checks
  - Группа 5: Architecture
  - Группа 6: Housekeeping

**4. План исправлений для каждой группы**
- Конкретные файлы и изменения
- Порядок исправлений внутри группы
- Команда для проверки: `pytest tests/ -q`
- Риск: что может сломаться при исправлении

### Формат сводного отчёта:

Запиши в /home/z/my-project/download/audit-report-final.md:

```markdown
# Итоговый отчёт аудита: {project_name}

## Сводка
- Всего находок: N (CRITICAL: N, HIGH: N, MEDIUM: N, LOW: N)
- Затронутых файлов: N
- Фаз аудита: 6

## Распределение по категориям
| Категория | CRITICAL | HIGH | MEDIUM | LOW | Итого |
|---|---|---|---|---|---|
| SECURITY | | | | | |
| DATA_LOSS | | | | | |
| BUG | | | | | |
| ORM_DRIFT | | | | | |
| CONFIG | | | | | |
| TEST | | | | | |
| ARCHITECTURE | | | | | |

## Топ-10 самых критичных находок
1. ...
2. ...

## Все находки (полный список)
### CRITICAL
#### [SEC-001] ...
...

### HIGH
...

### MEDIUM
...

### LOW
...

## План исправлений

### Группа 1: CRITICAL + HIGH (приоритет — немедленно)
| # | ID | Файл | Описание | Изменение |
|---|---|---|---|---|
| 1 | SEC-001 | file.py | ... | ... |
→ Проверка: `pytest tests/ -q`

### Группа 2: ORM + pipeline bugs
...

### Группа 3: Deep security fixes
...

### Группа 4: Defensive checks
...

### Группа 5: Architecture
...

### Группа 6: Housekeeping
...

## Файлы, требующие наибольшего внимания (top-5)
1. file.py — N находок (CRITICAL: N, HIGH: N)
2. ...
```

### Запись в worklog:
```
---
Task ID: audit-7
Agent: audit-reporter
Task: Сводный отчёт аудита

Work Log:
- Объединил находки из 6 фаз
- Дедуплицировал: было N, стало N уникальных
- Распределил по группам приоритета
- Составил план исправлений

Stage Summary:
- Итого уникальных находок: N
- CRITICAL: N, HIGH: N, MEDIUM: N, LOW: N
- Отчёт: /home/z/my-project/download/audit-report-final.md
```
```

---

## Промпт 8: Исправления — Группа 1 (CRITICAL + HIGH)

```
## Этап 8: Исправление находок — Группа 1 (CRITICAL + HIGH)

### Контекст:
Аудит завершён. Сводный отчёт: /home/z/my-project/download/audit-report-final.md.
Ты начинаешь исправления с Группы 1 (CRITICAL + HIGH + падающие тесты).

### Правила исправлений (КРИТИЧЕСКИ ВАЖНО):

1. Читай файл ПОЛНОСТЬЮ перед редактированием
2. НЕ трогай файлы, не указанные в задании
3. После КАЖДОГО исправления: `pytest tests/ -q` — все тесты должны проходить
4. Если тесты упали — фиксируй СРАЗУ, не продолжай
5. Используй Edit, не Write (не перезаписывай файлы целиком)
6. Один логический шаг → одна правка → тесты → коммит
7. Не рефактори то, что не просили
8. Добавляй `__all__` в новые модули
9. Добавляй docstring к новым функциям/классам
10. Не добавляй зависимости без необходимости

### Твоя задача:
Исправить ВСЕ находки из Группы 1 из отчёта.

### Порядок работы:

Для каждой находки в Группе 1:
1. Прочитай файл полностью
2. Найди проблемное место
3. Внеси минимальное исправление (только то, что нужно)
4. Запусти `pytest tests/ -q`
5. Если тесты упали — проанализируй почему, зафикси
6. Запиши в worklog: что исправил, результат тестов

### После исправления всей группы:
1. Запусти `pytest tests/ -q` — финальная проверка
2. Запиши итог в worklog
3. Перечисли исправленные файлы

### Формат записи в worklog:
```
---
Task ID: audit-fix-1
Agent: audit-fixer
Task: Исправление Группы 1 (CRITICAL + HIGH)

Work Log:
- [FIX-001] file.py:line — исправил ... → pytest: N/N passed
- [FIX-002] file.py:line — исправил ... → pytest: N/N passed
- ...

Stage Summary:
- Исправлено: N находок из Группы 1
- Файлов изменено: N
- Тесты: N/N passed
- Осталось в Группе 2: N находок
```
```

---

## Как пользоваться этими промптами

### Инструкция для пользователя:

1. **Подготовка:** закинь агенту файл `granite-crm-audit-guide.md` и дай **Мастер-промпт** (общие правила).

2. **Запуск по этапам:**
   - Скорми агенту **Промпт 1** (разведка). Дождись завершения.
   - Проверь результат в `audit-findings-phase-1.md`.
   - Скорми **Промпт 2**. Дождись завершения.
   - И так далее до **Промпта 7** (сводный отчёт).

3. **Исправления:**
   - Промпт 8 — для Группы 1 (CRITICAL + HIGH).
   - После Группы 1 — напиши аналогичный промпт для Группы 2, заменив ссылки на нужные находки.

4. **Критическое правило:** **НЕ запускай этапы параллельно.** Каждый этап опирается на результаты предыдущего.

### Структура файлов после аудита:

```
download/
├── audit-findings-phase-1.md    # Разведка и карта
├── audit-findings-phase-2.md    # Входные точки
├── audit-findings-phase-3.md    # Безопасность
├── audit-findings-phase-4.md    # Данные + ORM
├── audit-findings-phase-5.md    # Логика + баги
├── audit-findings-phase-6.md    # Модульный аудит
└── audit-report-final.md        # Сводный отчёт
```

### Тайминг (ориентировочно):

| Промпт | Сложность | Время агента |
|---|---|---|
| 1. Разведка | Низкая | 2-3 мин |
| 2. Входные точки | Средняя | 5-8 мин |
| 3. Безопасность | Высокая | 8-12 мин |
| 4. Данные + ORM | Высокая | 8-12 мин |
| 5. Логика | Средняя | 5-8 мин |
| 6. Модульный | Высокая | 10-15 мин |
| 7. Сводный отчёт | Средняя | 3-5 мин |
| 8. Исправления Группы 1 | Высокая | 10-20 мин |
