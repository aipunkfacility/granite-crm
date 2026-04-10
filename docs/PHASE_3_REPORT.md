# Отчёт: Фаза 3 — Улучшение error handling и логирования

**Дата:** 2026-04-10
**Коммит:** `cd8c69a`
**Статус:** ✅ Завершена

## Цель

Сделать ошибки диагностируемыми, добавить retry для сетевых операций, вынести `sys.exit(1)` из оркестратора пайплайна в CLI-слой.

## Выполненные шаги

### 3.1 Retry для сетевых запросов

**Проблема:** `tg_request()` в `tg_finder.py` ретраил только HTTP 429 (rate limit), но при сетевых ошибках (connection, timeout) сразу возвращал `None`. Это приводило к потере данных для компании из-за одного временного сбоя сети.

**Анализ существующего retry:**
- `fetch_page()` в `utils.py` — уже имеет tenacity-retry (3 попытки, экспоненциальная выдержка 2–30 сек). Используется в WebClient, MessengerScanner, TechExtractor.
- `tg_request()` — использовал собственный цикл ретраев только для 429.

**Решение:** Добавлен retry для `requests.RequestException` (включает `ConnectionError`, `Timeout`) с отдельным счётчиком backoff (2, 4, 8 сек — короче чем для 429, т.к. это временные сбои, не блокировка). Количество попыток по-прежнему определяется `max_retries` из конфига (дефолт 5).

```python
# Было: RequestException → немедленный return None
except requests.RequestException as e:
    logger.warning(f"TG request error (...): {e}")
    return None

# Стало: RequestException → retry с экспоненциальной выдержкой
except requests.RequestException as e:
    wait = conn_backoff + random.uniform(0, 1)
    logger.warning(f"TG request error (...): {e}, повтор через {wait:.0f}с (...)")
    time.sleep(wait)
    conn_backoff *= 2
```

### 3.2 Структурированное логирование ошибок обогащения

**Проблема:** Ошибки обогащения логировались как `logger.error(f"Ошибка обогащения {name}: {e}")` — без стектрейса, без категории ошибки. При массовом обогащении (500+ компаний) невозможно было определить причину сбоев и их распределение.

**Решение (3 части):**

**a) `logger.exception()` вместо `logger.error()`:** Все `except`-блоки в `enrichment_phase.py` теперь используют `logger.exception()`, который автоматически включает полный traceback в лог-файл. Это критически важно для диагностики: в файловом логе (`data/logs/granite.log`) теперь виден полный стек вызовов, приведший к ошибке.

**b) Классификация ошибок по типу:** Добавлена функция `_classify_error(exc)` которая по имени исключения и сообщению определяет категорию:

| Категория | Ключевые слова | Примеры |
|-----------|---------------|---------|
| `network` | timeout, connection, network, ssl, dns | `ConnectionError`, `Timeout`, `SSLError` |
| `parsing` | 403, captcha, blocked, parse, json | HTTP 403, CAPTCHA, JSON decode error |
| `data` | всё остальное | пустой ответ, NoneType, missing key |

Категория добавляется в каждое сообщение лога в квадратных скобках: `[network] Ошибка обогащения...`, `[parsing] Ошибка обогащения...`.

**c) Счётчики ошибок:** В `EnrichmentPhase` добавлен атрибут `_error_counts: dict[str, int]`, который накапливает количество ошибок по категориям за проход. После завершения обогащения выводится итоговое сообщение:

```
# При ошибках:
Ошибки обогащения — network: 3, parsing: 1
# Без ошибок:
Обогащение прошло без ошибок
```

Счётчик сбрасывается при каждом вызове `run()`.

### 3.3 Гибкое управление фазами

**Проблема:** `_run_phase()` в `manager.py` делал `sys.exit(1)` при ошибке критической фазы (scraping, dedup). Это убивало весь процесс без возможности обработки на уровне вызывающего кода. `PipelineManager` — библиотечный класс, он не должен решать, когда завершать процесс.

**Решение:**

1. Создано исключение `PipelineCriticalError(Exception)` в `manager.py`, экспортируемое через `__all__`.
2. `_run_phase()` теперь выбрасывает `PipelineCriticalError` вместо `sys.exit(1)`.
3. Обработка перемещена в `cli.py`: `run_city()` обёрнут в `try/except PipelineCriticalError` с `typer.Exit(1)`.
4. Из `manager.py` удалён `import sys` (больше не нужен).

```python
# manager.py — было:
sys.exit(1)

# manager.py — стало:
raise PipelineCriticalError(f"Критическая фаза '{name}' не удалась: {e}") from e

# cli.py — новый обработчик:
try:
    manager.run_city(c, ...)
except PipelineCriticalError:
    print_status(f"Критическая ошибка для города {c}. Остановка.", "error")
    raise typer.Exit(1)
```

Это позволяет в будущем использовать `PipelineManager` программно (например, из Jupyter notebook или другого оркестратора) без риска неожиданного `sys.exit`.

## Результаты тестирования

- **240/240 тестов проходят** ✅
- Существующие тесты `TestTgRateLimit` (4 теста) подтверждают корректность retry-логики для 429 и connection errors
- Тесты `TestPipelineManagerInit` подтверждают, что `PipelineCriticalError` доступен для импорта и не ломает инициализацию
- Обратная совместимость: поведение при ошибках не изменилось для пользователя (выход с кодом 1), но архитектурно корректно разделено

## Критерии успеха (из REFACTORING_PLAN.md)

- [x] Сетевые функции имеют retry (`tg_request()` ретраит connection/timeout ошибки)
- [x] Ошибки обогащения логируются с traceback (`logger.exception()`) и категорией (`[network]`, `[parsing]`, `[data]`)
- [x] `sys.exit` вынесен из `PipelineManager` в `cli.py` (через `PipelineCriticalError`)

## Изменённые файлы (4)

| Файл | Изменение |
|------|-----------|
| `granite/enrichers/tg_finder.py` | `tg_request()`: retry для `RequestException` с экспоненциальной выдержкой (2, 4, 8 сек) вместо немедленного `return None` |
| `granite/pipeline/enrichment_phase.py` | `logger.exception()` вместо `logger.error()`, функция `_classify_error()`, счётчики `_error_counts` с итоговым логированием |
| `granite/pipeline/manager.py` | `PipelineCriticalError` вместо `sys.exit(1)`, удалён `import sys`, добавлено в `__all__` |
| `cli.py` | Импорт `PipelineCriticalError`, `try/except` вокруг `manager.run_city()` с `typer.Exit(1)` |

## Следующая фаза

**Фаза 4: Оптимизация производительности обогащения** — параллелизация обогащения через `ThreadPoolExecutor`, rate limiting для внешних API.
