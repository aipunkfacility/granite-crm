# Granite Workshops DB

Сбор базы гранитных мастерских и производителей памятников по областям России. Поиск контактов (телефон, email, Telegram, WhatsApp, VK) для дальнейшей связи.

## Как работает

Запускаешь город из конфига — программа сама:

1. Определяет область (из `config.yaml`)
2. Подтягивает все населённые пункты этой области (из `data/regions.yaml`)
3. Автоматически ищет поддомены и категории на jsprav.ru через API (`/api/cities/`)
4. Парсит каждый город из источников: jsprav, firecrawl, 2GIS, yell, firmsru
5. Дедуплицирует — сливает дубли по телефону и сайту (Union-Find)
6. **Обогащение, проход 1** — сканирует сайты на мессенджеры, ищет Telegram по телефону и названию, определяет CMS
7. **Обогащение, проход 2** — для компаний без сайта/email: поиск через firecrawl с заполнением недостающих полей
8. Детекция филиальных сетей (один домен или телефон у 2+ компаний в пределах области)
9. Определяет сегмент (A/B/C/D) по скорингу
10. Экспортирует в CSV или Markdown

Всё локально. Никаких GitHub Actions, никаких облачных сервисов.

## Установка

```bash
pip install -r requirements.txt
playwright install chromium
```

Firecrawl CLI (если используется для точечного поиска):
```bash
npm install -g firecrawl-cli
firecrawl login
```

## Запуск

```bash
# Одна область (все города парсятся автоматически)
python cli.py run "Ростов-на-Дону"

# С очисткой старых данных
python cli.py run "Ростов-на-Дону" --force

# Пропустить парсинг, только дедупликация и обогащение
python cli.py run "Ростов-на-Дону" --no-scrape

# Перезапустить только точечное обогащение (сохранить scrape+dedup, заполнить пустые website/email)
python cli.py run "Ростов-на-Дону" --re-enrich

# Все города из конфига
python cli.py run all

# Экспорт
python cli.py export "Ростов-на-Дону" --format csv
python cli.py export "Ростов-на-Дону" --format md

# Экспорт по пресету
python cli.py export-preset "Ростов-на-Дону" hot_leads
```

### Управление базой данных (Alembic миграции)

```bash
# Проверить, нужна ли миграция
python cli.py db check

# Создать миграцию (после изменения моделей в database.py)
python cli.py db migrate "add last_contacted_at to companies"

# Применить миграцию
python cli.py db upgrade head

# Откатить на одну версию назад
python cli.py db downgrade -1

# История миграций
python cli.py db history -v

# Текущая версия схемы
python cli.py db current

# Пометить существующую БД как актуальную (для миграции на Alembic)
python cli.py db stamp head
```

Подробнее: [docs/DATABASE_GUIDE.md](docs/DATABASE_GUIDE.md)

### run.bat (Windows)

Файл `run.bat` в корне проекта. Настройки:

```bat
set CITY=Астрахань          :: Город из config.yaml
set RE_ENRICH=--re-enrich   :: Раскомментировать для перезапуска обогащения
:: set FORCE=--force         :: Раскомментировать для очистки и запуска с нуля
```

## Структура

```
├── cli.py                   # Точка входа (typer CLI)
├── config.yaml              # Настройки: города, источники, скоринг, пресеты
├── database.py              # ORM-модели БД + класс Database (SQLite, WAL, Alembic)
├── models.py                # Pydantic-модели данных
├── utils.py                 # Транслитерация, нормализация телефонов, HTTP-запросы
├── regions.py               # Справочник: область → список городов
├── category_finder.py       # Автопоиск поддоменов jsprav.ru через API
├── messenger_search.py      # Утилиты поиска мессенджеров
├── alembic.ini              # Конфигурация Alembic
├── alembic/
│   ├── env.py               # Среда миграций (определение URL БД)
│   ├── script.py.mako       # Шаблон для генерации миграций
│   └── versions/            # Файлы миграций
│       └── ..._initial_schema.py
├── docs/
│   └── DATABASE_GUIDE.md    # Подробный гайд по БД
├── run.bat                  # Быстрый запуск на Windows
├── data/
│   ├── regions.yaml         # Справочник: 40 областей, 566 городов
│   ├── category_cache.yaml  # Кэш найденных поддоменов и категорий
│   ├── granite.db           # SQLite база (WAL-режим)
│   ├── logs/
│   │   └── granite.log      # Логи (rotating, 10 MB)
│   └── export/              # CSV/MD экспорт
├── scrapers/
│   ├── base.py              # Общий интерфейс скреперов
│   ├── jsprav.py            # Jsprav.ru (JSON-LD, быстрый)
│   ├── jsprav_playwright.py # Jsprav.ru (Playwright, глубокий, выключен)
│   ├── dgis.py              # 2GIS (выключен)
│   ├── yell.py              # Yell.ru (выключен)
│   ├── firmsru.py           # Firmsru.ru (выключен)
│   └── firecrawl.py         # Firecrawl CLI (поиск + скрапинг сайтов)
├── dedup/
│   ├── phone_cluster.py     # Кластеризация по общим телефонам
│   ├── name_matcher.py      # Поиск дубликатов по названиям (fuzzy)
│   ├── site_matcher.py      # Кластеризация по домену сайта
│   ├── merger.py            # Слияние записей + генерация conflicts.md
│   └── validator.py         # Валидация телефонов, email, сайтов
├── enrichers/
│   ├── messenger_scanner.py # Поиск TG/WA/VK парсингом ссылок из HTML
│   ├── tg_finder.py         # Поиск Telegram по телефону и названию
│   ├── tg_trust.py          # Анализ профиля TG (аватар, описание, бот/канал)
│   ├── tech_extractor.py    # Определение CMS сайта
│   ├── classifier.py        # Скоринг и сегментация A/B/C/D
│   └── network_detector.py  # Поиск филиальных сетей (домен/телефон, в пределах города)
├── pipeline/
│   ├── manager.py           # Основной конвейер (все фазы)
│   ├── checkpoint.py        # Возобновление с прерванного этапа
│   └── status.py            # Вывод статуса
├── exporters/
│   ├── csv.py               # Экспорт в CSV (utf-8-sig, сортировка по score, пресеты)
│   └── markdown.py          # Экспорт в Markdown (пресеты)
├── tests/                   # Тесты (137 шт.)
│   ├── test_classifier.py
│   ├── test_dedup.py
│   ├── test_enrichers.py
│   ├── test_migrations.py   # Тесты Alembic миграций (upgrade/downgrade/FK)
│   ├── test_pipeline.py
│   ├── test_scrapers.py
│   └── test_utils.py
├── scripts/                 # Отдельные утилиты (legacy)
└── agents/                  # Промпты для AI-агентов
```

## Конфигурация

### config.yaml — основные настройки

- **`cities`** — список городов с областями, населением, координатами, статусом
- **`scraping`** — общие настройки: задержки, таймауты, user-agent rotation, потоки
- **`sources`** — каждый источник: `enabled: true/false`, категории, поддомены
  - `firecrawl` — запросы для поиска (`queries`)
  - `jsprav` — категория, `subdomain_map` для нестандартных поддоменов
  - `dgis`, `yell`, `firmsru`, `jsprav_playwright` — по умолчанию выключены
  - `google_maps`, `avito` — заглушки (выключены)
- **`dedup`** — настройки дедупликации (порог, слияние по телефону/сайту)
- **`enrichment`** — настройки обогащения:
  - `messenger_pages` — страницы сайта для сканирования мессенджеров
  - `tg_finder` — задержки, поиск через Google
  - `tg_trust` — штраф за пустой профиль
  - `tech_keywords` — ключевые слова для определения: оборудование, производство, портрет, конструктор сайта
- **`scoring`** — **вложенная** структура:
  ```yaml
  scoring:
    weights:       # Баллы за каждый признак
      has_website: 5
      has_telegram: 15
      has_whatsapp: 10
      ...
    levels:        # Пороги для сегментов
      segment_A: 50
      segment_B: 30
      segment_C: 15
  ```
- **`export_presets`** — готовые фильтры для экспорта (hot_leads, producers_only, with_telegram, cold_email, manual_search, full_dump)
- **`logging`** — уровень логов, ротация, формат
- **`database`** — путь к SQLite (`data/granite.db`)

### data/regions.yaml — города по областям

Статичный справочник (40 областей, 566 городов). Каждая область содержит полный список населённых пунктов. При запуске города скреперы проходят по всем пунктам его области.

Нужно добавить город — просто допиши в файл. Для jsprav.ru поддомены определяются автоматически через API (`/api/cities/`), кэшируются в `data/category_cache.yaml`. Ручные замены — через `subdomain_map` в config.yaml.

## База данных

SQLite с WAL-режимом (параллельные записи без "database is locked"). `busy_timeout=5000ms`. Схема управляется через **Alembic** — миграции применяются автоматически при запуске `Database()`.

Подробная документация: [docs/DATABASE_GUIDE.md](docs/DATABASE_GUIDE.md)

### Таблицы

| Таблица | Назначение | Записей |
|---------|-----------|---------|
| **`raw_companies`** | Сырые данные из скреперов (source, name, phones, website, emails, city) | Много (дубли) |
| **`companies`** | После дедупликации (merged_from, name_best, phones, website, emails, messengers) | Уникальные |
| **`enriched_companies`** | Обогащённые данные (messengers, tg_trust, cms, crm_score, segment, is_network). Связь 1:1 с `companies` по `id` (FK с `ON DELETE CASCADE`) | = companies |
| **`pipeline_runs`** | История запусков конвейера (city, stage, status, timestamps) | Логи |

### Связи

```
raw_companies.merged_into ──→ companies.id       (много-к-одному)
enriched_companies.id ──────→ companies.id       (1:1, PK = FK, CASCADE)
```

### Миграции

Схема БД версионирована через Alembic. При изменении ORM-моделей в `database.py` создайте миграцию:

```bash
python cli.py db check          # проверить, есть ли изменения
python cli.py db migrate "... " # создать миграцию
python cli.py db upgrade head   # применить
```

Автоматически: `Database()` вызывает `alembic upgrade head` при инициализации, поэтому при обычном запуске (`python cli.py run ...`) миграции применяются сами.

## Конвейер

```
run "Астрахань"
  │
  ├─ Фаза 0: Поиск категорий
  │   Автопоиск поддоменов jsprav.ru через API
  │   Проверка категорий HEAD-запросом
  │   Кэширование → data/category_cache.yaml
  │
  ├─ Фаза 1: Скрапинг
  │   Для каждого города Астраханской области:
  │   jsprav (JSON-LD) → firecrawl (поиск+скрапинг) → [dgis, yell, firmsru — выключены]
  │   Всё сохраняется в raw_companies (БД)
  │
  ├─ Фаза 2: Дедупликация
  │   Кластеризация по телефонам → сайтам (Union-Find)
  │   name_matcher существует но сейчас НЕ используется
  │   Слияние дубликатов → companies (БД)
  │
  ├─ Фаза 3: Обогащение (проход 1)
  │   Для каждой компании:
  │   → сканирование сайта на мессенджеры (парсинг ссылок из HTML)
  │   → поиск TG по телефону (t.me/+7XXX)
  │   → поиск TG по названию (генерация юзернеймов)
  │   → анализ профиля TG: +1 аватар, +1 описание, -1 канал, -1 бот
  │   → определение CMS (Bitrix, WordPress, Tilda и др.)
  │
  ├─ Фаза 3b: Точечный поиск (проход 2, firecrawl)
  │   Для компаний без сайта или email:
  │   → firecrawl search "Название Город" → берём лучший URL
  │   → firecrawl scrape URL → извлекаем email, телефоны
  │   → сканируем найденный сайт на мессенджеры и CMS
  │   Пауза 2 сек между запросами
  │
  ├─ Фаза 4: Детекция сетей
  │   Поиск компаний с филиалами (один домен/телефон у 2+ компаний)
  │   Поиск только в пределах одного города (не между городами)
  │   Нормализация телефонов: 8xxx → 7xxx
  │
  ├─ Фаза 5: Скоринг
  │   Расчёт CRM-score по весам из config.yaml
  │   Сегментация: A (≥50), B (≥30), C (≥15), D
  │
  └─ Фаза 6: Экспорт
      Автоматический CSV + пресеты при завершении
      Сортировка по crm_score (убывание)
      data/export/{город}_enriched.csv
```

## Чекпоинты

Конвейер запоминает прогресс в БД. При перезапуске — продолжает с прерванного этапа:

| Этап | Что проверяется | Следующая фаза |
|------|-----------------|----------------|
| `start` | Пусто | Скрапинг |
| `scraped` | Есть raw_companies | Дедупликация |
| `deduped` | Есть companies | Обогащение |
| `enriched` | enriched_companies ≥ companies | Скоринг + экспорт |

Флаги:
- `--force` — полная очистка данных по городу, старт с нуля
- `--no-scrape` — пропустить скрапинг, начать с дедупликации
- `--re-enrich` — пропустить скрапинг и дедупликацию, запустить только точечный поиск (заполнение недостающих website/email через firecrawl)

## Сегменты

| Сегмент | Порог | Описание |
|---------|-------|----------|
| A | ≥ 50 | Есть TG + WA + сайт, высокий скор |
| B | ≥ 30 | Есть мессенджеры + сайт/производство |
| C | ≥ 15 | Есть контакты или сайт |
| D | < 15 | Мало данных, нужна ручная проверка |

Пороги настраиваются в `config.yaml` → `scoring.levels`.

## TG Trust

Анализ Telegram-профиля при скрапинге:

| Признак | Изменение score |
|---------|-----------------|
| Есть аватарка | +1 |
| Есть описание | +1 |
| Это канал/группа | -1 |
| Это бот | -1 |

`trust_score ≥ 2` — живой бизнес-контакт. `trust_score = 0` — мёртвый/фейк.

## Messenger Scanner

Ищет ссылки на мессенджеры парсингом HTML (не из шаблонов конфига):
1. Загружает главную страницу → ищет ссылки t.me, wa.me, vk.com
2. Если TG не найден — ищет страницу контактов по тексту ссылок и URL
3. На странице контактов ищет доп. страницы (о нас, производство, каталог) — до 3 штук
4. Фильтрует: пропускает кнопки "поделиться" (share, joinchat)

## Экспорт

### CSV

Файл: `data/export/{город}_enriched.csv`, кодировка UTF-8 BOM.

Поля: id, name, phones, address, website, emails, segment, crm_score, is_network, cms, has_marquiz, telegram, vk, whatsapp.

Сортировка по crm_score (убывание) — лучшие контакты первыми.

### Пресеты

Готовые фильтры из `config.yaml` → `export_presets`:

| Пресет | Описание |
|--------|----------|
| `hot_leads` | Есть TG + производство + высокий приоритет |
| `producers_only` | Производители без ретуши, не контактированные |
| `with_telegram` | Все компании с Telegram |
| `cold_email` | Нет мессенджеров, но есть email и живой сайт |
| `manual_search` | Есть производство, но нет мессенджеров — нужен прозвон |
| `full_dump` | Все обогащённые компании |

```bash
python cli.py export-preset "Волгоград" hot_leads
python cli.py export-preset all with_telegram
```

## Тесты

137 тестов покрывают: дедупликацию, классификатор, обогащение (TG finder, TG trust, tech extractor, messenger scanner), экспорт (CSV, Markdown, пресеты), скреперы, утилиты, миграции БД.

```bash
# Все тесты
python -m pytest tests/ -v

# Только миграции
python -m pytest tests/test_migrations.py -v
```
