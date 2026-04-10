# План расширения: Crawlee, 2GIS/Yell скраперы, async

> Продолжение `docs/REFACTORING_PLAN.md`.
> Задачи, которые меняют возможности пайплайна, а не только чистят код.
> Дата: 2026-04-10

---

## Фаза 6: Интеграция Crawlee for Python

**Цель:** Добавить Crawlee как движок для reverse-lookup обогащения — искать компанию по имени/телефону в 2GIS и Yell, чтобы найти дополнительные контакты, адреса, мессенджеры, которых нет в исходных данных.

### Почему Crawlee, а не Playwright напрямую

Текущие скраперы `DgisScraper` и `YellScraper` используют Playwright напрямую. Проблемы:
- **Нет анти-bot защиты** — Playwright + stealth плагин, но 2GIS/Yell активно детектят ботов. Бан по IP после 20-50 запросов, капчи.
- **Нет proxy rotation** — один IP на всю сессию. Нет встроенного механизма ротации.
- **Нет rate limiting** — задержки захардкожены в коде (`adaptive_delay(0.8, 2.0)`), не адаптируются к ответам сервера.
- **Нет retry с backoff** — при 403/429 скрапер просто логирует ошибку и пропускает карточку. Данные теряются.
- **Нет session pool** — каждая сессия — чистая. Нет cookie-персистентности между запросами.

Crawlee for Python даёт:
- **Session pool** — управление куками, отпечатками, ротация сессий при блокировке.
- **Proxy rotation** — встроенная поддержка proxy-пулов.
- **Rate limiting** — адаптивный, на основе ответов сервера.
- **Retry + enqueue links** — автоматический retry при блокировке, очередь URL.
- **Anti-block** — эмуляция отпечатков браузера между запросами.

### 6.1 Добавить Crawlee в проект

```bash
pip install crawlee
```

Обновить `requirements.txt`.

### 6.2 Создать `granite/enrichers/reverse_lookup.py`

**Концепция:** Reverse lookup — поиск по уже известным компаниям в других источниках, чтобы дополнить данные.

```python
class ReverseLookupEnricher:
    """Ищет компанию в 2GIS и Yell по имени/телефону/адресу.

    Используется ПОСЛЕ основного обогащения, для компаний где:
    - Нет мессенджеров (TG, WA, VK)
    - Нет email
    - Нет сайта
    - Мало данных в целом (CRM-скор < 15)

    Вход: CompanyRow из БД.
    Выход: обновлённые messengers, phones, emails, website — пишутся в EnrichedCompanyRow.
    """
```

**Логика для одной компании:**
1. Сформировать поисковый запрос: `"{name} {city}"` или `"{phone}"` (если есть телефон).
2. Запросить 2GIS API (или парсинг) через Crawlee — найти карточку компании.
3. Извлечь из карточки: телефоны, сайт, мессенджеры (TG, WA, VK), email, адрес.
4. Запросить Yell через Crawlee — то же самое.
5. Слить с существующими данными (union, без перезаписи).
6. Записать в `EnrichedCompanyRow`.

### 6.3 Реализация Crawlee-скрапера для 2GIS

**Подход:** Crawlee `PlaywrightCrawler` (или `BeautifulSoupCrawler` если хватит).

2GIS предоставляет два пути доступа:
1. **2GIS API** (`https://catalog.api.2gis.ru/3.0/items`) — нужен API-ключ, но это самый надёжный путь. Бесплатный tier: 1000 запросов/день.
2. **Парсинг сайта** (`https://2gis.ru/{city}/search/...`) — нужен Crawlee для обхода защиты.

**Рекомендация:** Начать с API. Если лимитов недостаточно — добавить Crawlee-парсинг как fallback.

```python
# Вариант А: 2GIS API (простой, надёжный)
SEARCH_URL = "https://catalog.api.2gis.ru/3.0/items"
params = {
    "q": f"{company_name} {city}",
    "key": API_KEY,
    "region_id": region_id,  # из словаря город → region_id
    "fields": "items.contact_groups,items.point",
}

# Вариант Б: Crawlee парсинг (если API недоступен)
# PlaywrightCrawler с session pool + proxy rotation
```

### 6.4 Реализация Crawlee-скрепера для Yell

Yell.ru не имеет открытого API. Только парсинг сайта.

**Подход:** Crawlee `PlaywrightCrawler`.

```python
# Поиск: https://www.yell.ru/search?text={name}+{city}
# Карточка компании: извлечь телефоны, email, сайт, мессенджеры
# Пагинация: если результатов > 1 — проверить первые 3-5
```

### 6.5 Интеграция в пайплайн

**Когда запускать:** После `EnrichmentPhase`, перед `NetworkDetector`.

```
ScrapingPhase → DedupPhase → EnrichmentPhase → ReverseLookup → NetworkDetector → ScoringPhase → ExportPhase
```

**Кого обогащать:** Не все компании, а только те, где данных мало:
```python
# Кандидаты на reverse lookup:
candidates = [c for c in companies
    if not c.messengers          # нет мессенджеров
    and not c.emails             # нет email
    and c.crm_score < 30         # низкий скор
]
```

**Контроль нагрузки:**
- Лимит запросов: настраиваемый в config.yaml (дефолт: 100/день на источник).
- Rate limiting: 1-2 сек между запросами к 2GIS, 2-3 сек к Yell.
- Proxy: если есть — из пула. Если нет — с одного IP, но с adaptive delay.

### 6.6 Конфигурация

```yaml
enrichment:
  reverse_lookup:
    enabled: false          # по умолчанию выключено (пока тестируем)
    sources:
      dgis:
        enabled: true
        api_key: ""         # из .env: DGIS_API_KEY
        max_requests_per_day: 100
      yell:
        enabled: true
        max_requests_per_day: 50
    min_crm_score: 30       # обогащать только с скором ниже этого
    delay_between_requests: 2.0  # секунды
```

### 6.7 Секция config.yaml для dgis/yell (актуализация)

Текущий конфиг (минимальный):
```yaml
dgis:
  enabled: false           # ← это для scraping_phase (начальный сбор)
  max_retries: 3
  search_category: "изготовление памятников"
yell:
  enabled: false           # ← это для scraping_phase
```

Нужно разделить: `sources.dgis` (скрапинг) и `enrichment.reverse_lookup.sources.dgis` (обогащение). Это разные задачи с разной логикой.

### Тестирование фазы 6

```bash
# Единичные тесты на моках (без реальных API)
python -m pytest tests/test_reverse_lookup.py -v

# Ручной тест: одна компания
# В интерактивной сессии:
from granite.enrichers.reverse_lookup import ReverseLookupEnricher
enricher = ReverseLookupEnricher(config, db)
enricher.lookup_company(company_id=42)  # одна компания

# Проверить, что данные дополнились
python cli.py run "Волгоград" --no-scrape --re-enrich
```

**Критерии успеха:**
- [ ] Crawlee установлен и работает.
- [ ] `ReverseLookupEnricher` находит компании в 2GIS/Yell по имени.
- [ ] Данные сливаются без перезаписи существующих.
- [ ] Rate limiting работает (логи показывают задержки).
- [ ] При отсутствии proxy — не банится после 20 запросов (adaptive delay).
- [ ] Единичные тесты на моках проходят.

---

## Фаза 7: Починка/замена скраперов 2GIS и Yell (начальный сбор)

**Цель:** Сделать dgis.py и yell.py рабочими источниками для начального скрапинга (фаза 1). Сейчас они используют Playwright напрямую с хрупкими CSS-селекторами — нужно либо починить, либо переписать на Crawlee.

### Проблемы текущих скраперов

**DgisScraper (dgis.py):**
- Селекторы `div[class*='card'], div[class*='firm']` — слишком общие. 2GIS переезал на React, классы меняются при каждом деплое.
- Скролл + 3 итерации — не обходит пагинацию. Максимум 1 страница результатов.
- Нет извлечения сайта из карточки (`website=None` всегда).
- Нет извлечения email.
- Нет обработки пагинации ("Показать ещё").

**YellScraper (yell.py):**
- Селекторы `div.company-card, div.listing-item` — могут не совпадать с реальной разметкой.
- Нет обработки пагинации (только первая страница).
- Формат `base_path` в конфиге `/catalog/izgotovlenie_pamyatnikov/` — устарел, Yell мог изменить URL-структуру.

### 7.1 Оценка: починить или переписать на Crawlee

**Вариант А: Починить текущие (быстро, рискованно)**
- Обновить CSS-селекторы под текущую разметку 2GIS/Yell.
- Добавить пагинацию.
- Добавить извлечение сайта и email.
- Минус: сломается при следующем редизайне. Нет анти-bot.

**Вариант Б: Переписать на Crawlee (дольше, надёжнее)**
- Использовать Crawlee `PlaywrightCrawler` с session pool.
- Анти-bot: ротация сессий, отпечатки, adaptive delay.
- Автоматический retry при блокировке.
- Минус: зависимость от Crawlee, больше кода.

**Вариант В: Гибридный**
- Оставить Playwright для рендеринга JS (2GIS/Yell — SPA).
- Добавить Crawlee-обёртку только для session management, proxy, rate limiting.
- Скрапинг логика — кастомная, через Playwright API.

**Рекомендация:** Вариант В. Crawlee для управления сессиями, Playwright для рендеринга. Это не требует переписывания всей логики скрапинга, но даёт анти-bot защиту.

### 7.2 Переписать DgisScraper

**Что должно извлекаться:**
- Название
- Телефоны (все из карточки)
- Адрес
- Сайт
- Email
- Мессенджеры (TG, WA, VK, Instagram)
- Гео-координаты (если есть)
- Рейтинг (если есть — полезно для скоринга)

**Пагинация:**
- Кнопка "Показать ещё" или бесконечный скролл.
- Лимит: 10 страниц (configurable).

**Anti-bot:**
- Crawlee session pool (2-3 сессии на город).
- Задержка между скроллами: 1-2 сек.
- При 403/captcha — сменить сессию, подождать 30 сек, повторить.

### 7.3 Переписать YellScraper

**Что должно извлекаться:**
- То же что DgisScraper.
- Плюс: категория из Yell (полезно для сегментации).

**Anti-bot:**
- Аналогично DgisScraper.

### 7.4 Интеграция в scraping_phase.py

Текущая логика `scraping_phase.py`:
- JspravScraper — работает без Playwright.
- Playwright-скреперы (dgis, yell, jsprav_pw) запускаются в одном `playwright_session()`.

С Crawlee это меняется:
- Crawlee управляет своим браузером.
- Но можно запускать Crawlee внутри существующего Playwright контекста, или отдельно.

**Рекомендация:** Отдельный Crawlee-контекст для dgis/yell. Не смешивать с существующим `playwright_session()`.

### 7.5 Category finder для 2GIS и Yell

Аналогично `category_finder.py` для jsprav — автопоиск категорий:
- 2GIS: рубрикатор фиксированный, можно захардкодить маппинг "памятники" → `rubric_id`.
- Yell: каталог, можно HEAD-запросами проверить доступность категорий.

### Тестирование фазы 7

```bash
# Тесты на моках
python -m pytest tests/test_scrapers.py -v -k "dgis or yell"

# Ручной тест: один город
python cli.py run "Волгоград" --force
# Проверить: raw_companies содержит записи с source='2gis' и source='yell'

# Проверить селекторы (headless):
python -c "
from granite.scrapers.dgis import DgisScraper
# ... запустить на одном городе, вывести первые 3 результата
"
```

**Критерии успеха:**
- [ ] DgisScraper находит компании в 2GIS (не пустой список).
- [ ] YellScraper находит компании в Yell (не пустой список).
- [ ] Извлекаются: телефоны, сайт, email, мессенджеры, адрес, гео.
- [ ] Пагинация работает (больше 1 страницы результатов).
- [ ] Anti-bot: не банится после 50 запросов.
- [ ] Данные сохраняются в `raw_companies` с правильным `source`.
- [ ] Дедупликация корректно сливает записи из разных источников.

---

## Фаза 8: Частичная async-миграция (опционально)

**Цель:** Ускорить enrichment за счёт async HTTP-запросов. Не переписывать весь пайплайн.

### Почему не весь пайплайн

- **ScrapingPhase** — уже работает через `ThreadPoolExecutor`. Playwright sync API — нельзя сделать async без полного переписывания.
- **DedupPhase** — CPU-bound (fuzzy matching), async не поможет.
- **EnrichmentPhase** — I/O-bound (HTTP-запросы к сайтам, Telegram, 2GIS, Yell). **Здесь async даёт реальный выигрыш.**
- **ScoringPhase** — CPU-bound, мгновенный.
- **ExportPhase** — мгновенный.

### 8.1 Async HTTP-клиент

Заменить `requests` → `httpx` (async) в enrichment-модулях:
- `messenger_scanner.scan_website()`
- `tg_finder.find_tg_by_phone()`
- `tg_finder.find_tg_by_name()`
- `web_client.search()`
- `web_client.scrape()`
- `reverse_lookup.lookup_company()` (из Фазы 6)

```python
# granite/http_client.py — единый async HTTP-клиент
import httpx

async_client = httpx.AsyncClient(
    timeout=30,
    follow_redirects=True,
    limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
)
```

### 8.2 Async EnrichmentPhase

```python
class EnrichmentPhase:
    async def run(self, city: str) -> int:
        companies = ...
        # Параллельное обогащение с semaphore
        sem = asyncio.Semaphore(3)  # max concurrent
        tasks = [self._enrich_one(c, sem) for c in companies]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        ...

    async def _enrich_one(self, company, sem):
        async with sem:
            # messenger scan (async HTTP)
            # tg finder (async HTTP)
            # tech extract (async HTTP)
            ...
```

### 8.3 Точка входа

В `cli.py`:
```python
if asyncio.iscoroutinefunction(phase.run):
    asyncio.run(phase.run(city))
else:
    phase.run(city)
```

Или обёртка:
```python
def _run_async(coro):
    """Запустить корутину из sync-кода."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop and loop.is_running():
        # Внутри существующего event loop — создаём задачу
        return loop.create_task(coro)
    return asyncio.run(coro)
```

### 8.4 SQLite + async

SQLite не поддерживает async нативно. Варианты:
- **aiosqlite** — async обёртка над sqlite3. Работает, но под капотом — поток.
- **Оставить sync** для БД, async только для HTTP. Это самый простой вариант — обогащение делает async HTTP-запросы, потом собирает результаты и пишет в БД через sync `session_scope()`.

**Рекомендация:** Async только для HTTP. БД остаётся sync. Это даёт основной выигрыш (HTTP — узкое место), не усложняя код.

### Тестирование фазы 8

```bash
python -m pytest tests/ -v
# Сравнить скорость:
time python cli.py run "Астрахань" --force  # до
time python cli.py run "Астрахань" --force  # после
```

**Критерии успеха:**
- [ ] EnrichmentPhase работает через async HTTP.
- [ ] Нет "database is locked" (БД — sync, запись батчами).
- [ ] Обогащение ускорилось минимум в 2x (3 параллельных запроса вместо 1).
- [ ] Все тесты проходят.
- [ ] Обратная совместимость: sync-вызов `phase.run()` всё ещё работает.

---

## Зависимости между новыми фазами

```
РЕФАКТОРИНГ (REFACTORING_PLAN.md)
  Фаза 0-5
      ↓
РАСШИРЕНИЕ (этот документ)
  Фаза 6 (Crawlee + reverse lookup)  ← может идти параллельно с 7
      ↓
  Фаза 7 (2GIS/Yell скраперы)       ← зависит от 6 (общий Crawlee-инфраструктура)
      ↓
  Фаза 8 (async, опционально)        ← зависит от 6+7 (async HTTP-клиент единый)
```

### Можно делать параллельно:
- Фаза 7 может идти параллельно с Фазой 6, если 2GIS/Yell переписываются на Crawlee независимо от reverse_lookup.

### Что должно быть завершено до старта:
- **Фаза 0 из REFACTORING_PLAN.md** — хотя бы удаление мёртвого кода. Иначе агент будет путаться в устаревших импортах.
- **Фаза 1** (code smells) — желательно, но не обязательно.

---

## Приоритет

| Фаза | Влияние на бизнес | Сложность | Приоритет |
|------|-------------------|-----------|-----------|
| 6 — Crawlee reverse lookup | Высокое (больше контактов) | Средняя | **P1** |
| 7 — 2GIS/Yell скраперы | Высокое (больше источников) | Средняя | **P1** |
| 8 — Async | Среднее (скорость) | Высокая | P2 |

Фазы 6 и 7 дают больше данных. Фаза 8 — быстрее обработку. Начать с 6 и 7.
