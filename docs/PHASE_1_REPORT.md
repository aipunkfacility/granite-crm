# Отчёт: Фаза 1 — Исправление code smells

**Дата:** 2026-04-10
**Коммит:** `d7c563b`
**Статус:** ✅ Завершена

## Цель

Устранить дублирование, циклические зависимости и мелкие архитектурные проблемы без изменения поведения.

## Выполненные шаги

### 1.1 Убрать дублирование regex телефонов

**Проблема:** Один и тот же regex для извлечения российских телефонов `(\+?7[\s\-()]*\d{3}[\s\-()]*\d{3}[\s\-()]*\d{2}[\s\-()]*\d{2})` был скопирован в 3 файла: `web_search.py`, `web_client.py`, `messenger_scanner.py`. Любое изменение паттерна требовало синхронного редактирования всех файлов — источник ошибок.

**Решение:** Добавлена функция `extract_phones(text: str) -> list[str]` в `granite/utils.py` (рядом с `extract_emails`). Функция возвращает список уникальных телефонов из текста, сохраняя оригинальный формат. Все 3 файла заменены на вызов общей функции. Неиспользуемый `import re` удалён из `web_client.py`.

**Файлы:** `granite/utils.py`, `granite/scrapers/web_search.py`, `granite/pipeline/web_client.py`, `granite/enrichers/messenger_scanner.py`

### 1.2 Убрать циклическую зависимость database.py ↔ cli.py

**Проблема:** `database.py` (строка 220) делал `from granite.cli import _validate_config` внутри `Database.__init__()`, а `cli.py` импортировал `Database` на уровне модуля. Это работало только благодаря отложенному импорту (внутри `try/except`), но было хрупким — любое изменение порядка импортов могло сломать старт приложения.

**Решение:** Создан новый модуль `granite/config_validator.py` с функцией `validate_config(config: dict) -> bool`. Оба файла (`database.py` и `cli.py`) теперь импортируют из него. В `cli.py` функция импортирована с алиасом `_validate_config` для совместимости с остальным кодом в `load_config()`. Старое определение функции (64 строки) удалено из `cli.py`.

**Файлы:** `granite/config_validator.py` (новый), `granite/database.py`, `cli.py`

### 1.3 Исправить двойную проверку SSRF в validator.py

**Проблема:** `dedup/validator.py` содержал: (1) обёртку `_is_internal_url()` которая делала `not is_safe_url(url)`, и (2) функцию `validate_website()` которая вызывала обе проверки последовательно — сначала `_is_internal_url(url)`, затем `is_safe_url(url)` — избыточно и запутанно. Также в файле были свои копии `INTERNAL_HOSTS` и `BLOCKED_IP_RANGES` хотя `is_safe_url()` в `utils.py` уже содержала полную проверку.

**Решение:** Оставлена единая проверка через `is_safe_url()`. Удалены: функция `_is_internal_url()`, константы `INTERNAL_HOSTS` и `BLOCKED_IP_RANGES`, неиспользуемый `import requests` и `import ipaddress`. Файл сократился с 106 до 74 строк.

**Файлы:** `granite/dedup/validator.py`

### 1.4 Объявить _needs_playwright в JspravScraper.__init__

**Проблема:** `self._needs_playwright` устанавливался динамически только в методе `scrape()` (строки 316, 324), а читался через `getattr(jsprav, '_needs_playwright', False)` в `scraping_phase.py`. Хрупко — если `scrape()` не вызывался или не дошёл до установки флага, атрибут не существовал и `getattr` молча возвращал `False`.

**Решение:** Добавлено `self._needs_playwright = False` в `JspravScraper.__init__()` (явная инициализация атрибута). В `scraping_phase.py` заменён `getattr(jsprav, '_needs_playwright', False)` на прямой доступ `jsprav._needs_playwright`, и `getattr(jsprav, '_declared_total', None)` на `jsprav._declared_total`.

**Файлы:** `granite/scrapers/jsprav.py`, `granite/pipeline/scraping_phase.py`

### 1.5 Почистить dedup/name_matcher.py экспорт

**Проблема:** Модуль `name_matcher.py` экспортировался из `dedup/__init__.py`, но `dedup_phase.py` не использовал его (комментарий: «без name_matcher»). При этом модуль тестировался в `test_dedup.py` (12 тестов) и потенциально полезен для будущих улучшений дедупликации.

**Решение:** Модуль оставлен на месте (тесты зависят от него). Экспорт из `dedup/__init__.py` сохранён. Добавлен TODO-комментарий в `dedup_phase.py` с указанием, как подключить `find_name_matches` для дедупликации по названиям.

**Файлы:** `granite/pipeline/dedup_phase.py`

## Результаты тестирования

- **240/240 тестов проходят** ✅
- Циклические импорты устранены: `import granite.database` больше не тянет `cli.py`
- Проверка импортов: `python -c "from granite import Database, RawCompany, Source"` — OK
- Удалён неиспользуемый `import re` из `web_client.py`

## Критерии успеха (из REFACTORING_PLAN.md)

- [x] Один regex для телефонов в `utils.py`, используется везде
- [x] Нет циклических импортов (`import granite; import granite.cli` без ошибок)
- [x] `validator.py` — одна проверка URL вместо двух
- [x] Все тесты проходят (240/240)

## Изменённые файлы (12)

| Файл | Изменение |
|------|-----------|
| `granite/utils.py` | Добавлена `extract_phones()` |
| `granite/scrapers/web_search.py` | Замена regex на `extract_phones()` |
| `granite/pipeline/web_client.py` | Замена regex на `extract_phones()`, удалён `import re` |
| `granite/enrichers/messenger_scanner.py` | Замена regex на `extract_phones()` |
| `granite/config_validator.py` | **Новый файл** — `validate_config()` |
| `granite/database.py` | Импорт `validate_config` из `config_validator` |
| `cli.py` | Удалена локальная `_validate_config` (64 строки), импорт из `config_validator` |
| `granite/dedup/validator.py` | Упрощена SSRF-проверка, удалены `_is_internal_url`, `BLOCKED_IP_RANGES`, `INTERNAL_HOSTS` |
| `granite/scrapers/jsprav.py` | `_needs_playwright = False` в `__init__` |
| `granite/pipeline/scraping_phase.py` | Убраны `getattr()` вызовы |
| `granite/pipeline/dedup_phase.py` | Добавлен TODO для name_matcher |
| `docs/granite-crm-dev-plan.md` | Удалён (неактуальный) |
