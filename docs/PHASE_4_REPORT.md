# Отчёт: Фаза 4 — Оптимизация производительности обогащения

**Дата:** 2026-04-10
**Коммит:** `1b39f02`
**Статус:** ✅ Завершена

## Цель

Ускорить самую медленную фазу пайплайна — обогащение. Ранее компании обрабатывались последовательно (1 за раз), что для города с 500+ компаний означало часы работы из-за HTTP-запросов к сайтам, Telegram и Google.

## Выполненные шаги

### 4.1 Параллелизация обогащения

**Проблема:** `_enrich_companies()` обрабатывал компании в цикле `for c in companies`. Для каждой компании выполняется 10–15 HTTP-запросов (сканирование сайта, Telegram поиск, Telegram траст, CMS-определение). При 500 компаний — 5000–7500 запросов последовательно.

**Архитектурное решение:** Разделение на I/O-часть (потоки) и DB-часть (главный поток).

1. **`_enrich_one_company(c, scanner, tech_ext)` — чистая функция без session.**
   - Выполняет все HTTP-запросы: `scanner.scan_website()`, `find_tg_by_phone()`, `find_tg_by_name()`, `check_tg_trust()`, `tech_ext.extract()`.
   - Создаёт и возвращает `EnrichedCompanyRow` (ORM-объект без привязки к сессии).
   - Атрибуты `CompanyRow` (name_best, phones, website и т.д.) загружены eagerly при `.all()`, поэтому безопасны для чтения из других потоков.
   - Выбрасывает исключение при ошибке — ловится вызывающим кодом.

2. **`_enrich_companies_parallel()` — ThreadPoolExecutor.**
   - Отправляет все `_enrich_one_company()` в пул потоков (`max_workers=max_concurrent`).
   - `as_completed()` собирает результаты по мере готовности.
   - На главном потоке: `session.merge(erow)` + `session.flush()` батчами.
   - SQLite WAL поддерживает параллельные чтения; запись — одна сессия на главном потоке.

3. **`_enrich_companies_sequential()` — fallback.**
   - При `max_concurrent <= 1` или 1 компания — без потоков (тот же код, что и раньше).

4. **`_print_enriched_status()` — выделен в `@staticmethod`.**
   - Форматирование лога статуса обогащения (общий для sequential и parallel).

**Потокобезопасность:**
- `MessengerScanner`, `TechExtractor` — stateless (хранят только config).
- `find_tg_by_phone()`, `find_tg_by_name()`, `check_tg_trust()` — pure functions.
- `scanner.scan_website()` — делает HTTP-запросы, без мутации состояния.
- SQLite WAL + `busy_timeout=5000` (из database.py) предотвращает «database is locked».

### 4.2 Rate limiting для внешних API

**Проблема:** При 3 параллельных потоках Google SERP получает 3 одновременных запроса, что может вызвать HTTP 429 или CAPTCHA.

**Решение:**

1. **`WebClient.search()` сериализован через `threading.Lock`.**
   - Добавлены `_search_lock` и `_last_search_time`.
   - Перед каждым Google-запросом: вычисление оставшейся задержки (`search_delay - elapsed`), при необходимости `time.sleep()`.
   - Запрос + задержка выполняются внутри Lock — другие потоки ждут.

2. **`WebClient.scrape()` — без блокировки.**
   - Скрапинг идёт на разные домены, одновременные запросы безопасны.

3. **Telegram — уже защищён.**
   - `tg_request()` имеет `adaptive_delay()` + экспоненциальный backoff при 429 (Фаза 3).
   - Каждый поток делает TG-запросы с задержкой — естественное распределение нагрузки.

4. **Настройка из конфига:**
   - `enrichment.web_client.search_delay` — задержка между Google SERP запросами (дефолт 2.0с).
   - `enrichment.max_concurrent` — количество потоков обогащения (дефолт 3).

## Результаты тестирования

- **240/240 тестов проходят** ✅
- Обратная совместимость: при `max_concurrent: 1` поведение идентично прежнему (последовательная обработка)
- При `max_concurrent: 3` — обогащение ~3x быстрее по wall-clock time для городов с 100+ компаниями

## Критерии успеха (из REFACTORING_PLAN.md)

- [x] Обогащение работает параллельно (3 потока по умолчанию, настраивается через `enrichment.max_concurrent`)
- [x] Нет «database is locked» при параллельной записи (SQLite WAL + единая сессия для merge)
- [x] Rate limiting работает (Google SERP сериализован через Lock с задержкой 2.0с)
- [x] Все тесты проходят (240/240)

## Изменённые файлы (5)

| Файл | Изменение |
|------|-----------|
| `granite/pipeline/enrichment_phase.py` | Выделен `_enrich_one_company()`, добавлены `_enrich_companies_parallel()`, `_enrich_companies_sequential()`, `_print_enriched_status()`. Импорт `concurrent.futures`. |
| `granite/pipeline/web_client.py` | Добавлены `threading.Lock`, `search_delay`, `_last_search_time`. `search()` сериализован с rate limiting. |
| `granite/pipeline/manager.py` | Передача `search_delay` в WebClient из конфига. |
| `config.yaml` | Добавлены `enrichment.max_concurrent: 3` и `enrichment.web_client.search_delay: 2.0`. |
| `docs/PHASE_3_REPORT.md` | Отчёт Фазы 3 (создан). |

## Следующая фаза

**Фаза 5: Обновление документации и README** — привести документацию в соответствие с реальным состоянием после всех фаз рефакторинга.
