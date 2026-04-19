# Granite CRM — Руководство по работе с БД и CLI

## 1. Общие принципы

### Архитектура данных

БД SQLite (`data/granite.db`) работает в **WAL-режиме** — это значит, что чтение и запись могут происходить одновременно без блокировок. Пайплайн и API могут работать параллельно.

Данные проходят через **5 фаз конвейера**:

```
Парсинг → Дедупликация → Обогащение → Скоринг → Экспорт
  ↓           ↓              ↓            ↓          ↓
raw_        companies     enriched_     enriched_    CSV/
companies    (уникальные)  companies    companies    Markdown
```

### Таблицы БД

| Таблица | Назначение | Заполняется |
|---------|-----------|-------------|
| `cities_ref` | Справочник городов (из `data/regions.yaml`) | `seed-cities` |
| `unmatched_cities` | Города, не найденные в справочнике | Автоматически при парсинге |
| `raw_companies` | Сырые данные со скраперов | Фаза «Парсинг» |
| `companies` | Уникальные компании (после дедупа) | Фаза «Дедупликация» |
| `enriched_companies` | Обогащённые данные (мессенджеры, CMS, скоринг) | Фаза «Обогащение + Скоринг» |
| `crm_contacts` | CRM-карточки (воронка, касания, заметки) | `seed-contacts` + API |
| `crm_touches` | Лог всех касаний (email, TG, WA, ручные) | API |
| `crm_tasks` | Задачи follow-up | API |
| `crm_templates` | Шаблоны сообщений (email, TG, WA) | `seed-templates` |
| `crm_email_logs` | Лог отправленных писем (tracking) | Кампании |
| `crm_email_campaigns` | Email-рассылки | API |

### Конфигурация

Всё управление — через `config.yaml` (корень проекта). Ключевые секции:

- `database.path` — путь к БД (по умолчанию `data/granite.db`)
- `sources` — какие скраперы включены
- `enrichment` — настройки обогащения, reverse lookup
- `scoring.weights` — веса для CRM-скора
- `export_presets` — пресеты экспорта (hot_leads, cold_email, ...)

---

## 2. Инициализация

### 2.1. Первый запуск — создать БД и справочник городов

```bash
cd /home/z/my-project/granite-crm

# 1. БД создаётся автоматически при первом запуске любой команды.
# Нет нужды запускать миграции вручную — auto_migrate сработает.

# 2. Заполнить справочник городов из data/regions.yaml
UV_CACHE_DIR=/home/z/.cache/uv uv run python cli.py seed-cities
```

После этого в таблице `cities_ref` появятся ~1098 городов из `data/regions.yaml`.

### 2.2. Инициализация CRM-данных

```bash
# Создать CRM-карточки для всех существующих компаний
UV_CACHE_DIR=/home/z/.cache/uv uv run python -m scripts.seed_crm_contacts

# Создать стартовые шаблоны сообщений (cold_email_1, tg_intro, wa_intro, ...)
UV_CACHE_DIR=/home/z/.cache/uv uv run python -m scripts.seed_crm_templates
```

### 2.3. Проверка статуса

```bash
# Сводка по городам: сколько raw / companies / enriched
UV_CACHE_DIR=/home/z/.cache/uv uv run python cli.py cities-status

# Города, которые не нашлись в справочнике (для ручного разбора)
UV_CACHE_DIR=/home/z/.cache/uv uv run python cli.py unmatched
```

Пример вывода `cities-status`:

```
Астраханская область:
   +  Астрахань: raw=45 comp=38 enriched=38
   *  Ахтубинск: raw=12 comp=10 enriched=0
     Нариманов: raw=8 comp=7 enriched=7

Всего городов: 3
  + = enriched  * = populated (переназначенный)
```

---

## 3. Парсинг и обогащение (pipeline)

### 3.1. Полный цикл для одного города

```bash
# Основная команда — парсинг + дедуп + обогащение + скоринг + экспорт
UV_CACHE_DIR=/home/z/.cache/uv uv run python cli.py run "Астрахань"
```

Пайплайн проходит фазы по очереди, с чекпоинтами. Если обогащение упадёт — при повторном запуске оно начнётся с того места, где остановилось.

### 3.2. Все города

```bash
# Все ~1098 городов (долго!)
UV_CACHE_DIR=/home/z/.cache/uv uv run python cli.py run all

# Все города региона (если передать название региона)
UV_CACHE_DIR=/home/z/.cache/uv uv run python cli.py run "Московская область"
```

### 3.3. Флаги запуска

```bash
# --force: удалить старые данные и начать заново
UV_CACHE_DIR=/home/z/.cache/uv uv run python cli.py run "Астрахань" --force

# --no-scrape: пропустить парсинг, использовать кэш (если raw уже есть)
UV_CACHE_DIR=/home/z/.cache/uv uv run python cli.py run "Астрахань" --no-scrape

# --re-enrich: пересобрать обогащение (сохранить scrape + dedup)
UV_CACHE_DIR=/home/z/.cache/uv uv run python cli.py run "Астрахань" --re-enrich
```

### 3.4. Чекпоинты

Пайплайн запоминает, на какой фазе остановился. Стадии:

| Стадия | Что означает |
|--------|-------------|
| `start` | Город ещё не начинали |
| `scraped` | Парсинг завершён |
| `deduped` | Дедупликация завершена |
| Фаза обогащения не чекпоинтится | При перезапуске обогащение пойдёт заново |

---

## 4. Экспорт данных

### 4.1. Базовый экспорт

```bash
# CSV (по умолчанию)
UV_CACHE_DIR=/home/z/.cache/uv uv run python cli.py export "Астрахань"

# Markdown
UV_CACHE_DIR=/home/z/.cache/uv uv run python cli.py export "Астрахань" --format md

# Все города
UV_CACHE_DIR=/home/z/.cache/uv uv run python cli.py export all
```

Файлы сохраняются в `data/exports/`.

### 4.2. Экспорт по пресетам

Пресеты настроены в `config.yaml` → `export_presets`:

| Пресет | Описание | Формат |
|--------|----------|--------|
| `hot_leads` | Есть TG/WA + высокий CRM-скор | CSV |
| `high_score` | Сегмент A (скор >= 50) | CSV |
| `with_telegram` | Все с найденным Telegram | CSV |
| `cold_email` | Нет мессенджеров, но есть email | CSV |
| `manual_search` | Нет мессенджеров — нужен прозвон | Markdown |
| `full_dump` | Все обогащённые компании | CSV |

```bash
# Экспорт горячих лидов по Астрахани
UV_CACHE_DIR=/home/z/.cache/uv uv run python cli.py export-preset "Астрахань" hot_leads

# Все города, только с TG
UV_CACHE_DIR=/home/z/.cache/uv uv run python cli.py export-preset all with_telegram
```

---

## 5. API-сервер (CRM)

### 5.1. Запуск

```bash
# Базовый запуск (порт 8000)
UV_CACHE_DIR=/home/z/.cache/uv uv run python cli.py api

# С hot reload для разработки
UV_CACHE_DIR=/home/z/.cache/uv uv run python cli.py api --reload --port 3000

# С аутентификацией (API-key)
GRANITE_API_KEY=your-secret-key UV_CACHE_DIR=/home/z/.cache/uv uv run python cli.py api
```

При запуске API:

- БД создаётся автоматически если не существует
- Swagger-docs: `http://localhost:8000/docs`
- OpenAPI JSON: `http://localhost:8000/openapi.json`
- Health check: `GET /health`

### 5.2. Аутентификация

Если задана переменная `GRANITE_API_KEY` — все `/api/v1/*` запросы требуют заголовок:

```
X-API-Key: your-secret-key
```

Без переменной — аутентификация отключена (dev-режим). `/health`, `/docs`, `/openapi.json` доступны без ключа всегда.

### 5.3. Основные эндпоинты

| Метод | Путь | Описание |
|-------|------|----------|
| `GET` | `/api/v1/companies` | Список компаний (12 фильтров, пагинация, сортировка) |
| `GET` | `/api/v1/companies/{id}` | Карточка компании |
| `PATCH` | `/api/v1/companies/{id}` | Обновить CRM-поля (воронка, заметки, stop_automation) |
| `POST` | `/api/v1/companies/{id}/touches` | Залогировать касание |
| `GET` | `/api/v1/companies/{id}/touches` | История касаний |
| `POST` | `/api/v1/companies/{id}/tasks` | Создать задачу |
| `GET` | `/api/v1/companies/{id}/tasks` | Задачи компании |
| `GET` | `/api/v1/tasks` | Все задачи (с фильтрами) |
| `PATCH` | `/api/v1/tasks/{id}` | Обновить задачу |
| `DELETE` | `/api/v1/tasks/{id}` | Удалить задачу |
| `GET` | `/api/v1/campaigns` | Список кампаний |
| `POST` | `/api/v1/campaigns` | Создать кампанию |
| `POST` | `/api/v1/campaigns/{id}/run` | Запустить рассылку (SSE) |
| `GET` | `/api/v1/campaigns/{id}/stats` | Статистика кампании |
| `POST` | `/api/v1/campaigns/stale` | Сброс застрявших кампаний |
| `GET` | `/api/v1/templates` | Список шаблонов |
| `POST` | `/api/v1/templates` | Создать шаблон |
| `PUT` | `/api/v1/templates/{name}` | Обновить шаблон |
| `DELETE` | `/api/v1/templates/{name}` | Удалить шаблон |
| `GET` | `/api/v1/followup` | Очередь follow-up (кому написать сегодня) |
| `GET` | `/api/v1/funnel` | Воронка (распределение по стадиям) |
| `GET` | `/api/v1/stats` | Агрегированная статистика |
| `POST` | `/api/v1/companies/{id}/send` | Отправить через TG/WA |
| `GET` | `/api/v1/track/open/{id}.png` | Tracking pixel (email open) |

### 5.4. Примеры запросов

```bash
# Список компаний (первые 10, по убыванию CRM-скора)
curl -s "http://localhost:8000/api/v1/companies?page=1&per_page=10&order_by=crm_score&order_dir=desc"

# Компании с Telegram в Москве
curl -s "http://localhost:8000/api/v1/companies?city=Москва&has_telegram=1"

# Очередь follow-up (сегмент A)
curl -s "http://localhost:8000/api/v1/followup?segment=A"

# Статистика по городу
curl -s "http://localhost:8000/api/v1/stats?city=Астрахань"

# Создать касание (исходящее письмо)
curl -s -X POST "http://localhost:8000/api/v1/companies/1/touches" \
  -H "Content-Type: application/json" \
  -d '{"channel": "email", "direction": "outgoing", "subject": "Ретушь памятников"}'

# С аутентификацией
curl -s -H "X-API-Key: your-secret-key" "http://localhost:8000/api/v1/companies"
```

### 5.5. Генерация TypeScript-типов для фронтенда

```bash
npx openapi-typescript http://localhost:8000/openapi.json -o src/types/api.ts
```

---

## 6. Управление миграциями

Все команды через `db` subcommand:

```bash
# Текущая версия схемы
UV_CACHE_DIR=/home/z/.cache/uv uv run python cli.py db current

# История миграций
UV_CACHE_DIR=/home/z/.cache/uv uv run python cli.py db history

# Применить миграции до head
UV_CACHE_DIR=/home/z/.cache/uv uv run python cli.py db upgrade head

# Откатить на одну версию назад
UV_CACHE_DIR=/home/z/.cache/uv uv run python cli.py db downgrade -1

# Проверить, нужны ли миграции
UV_CACHE_DIR=/home/z/.cache/uv uv run python cli.py db check

# Создать новую миграцию (autogenerate из изменений в database.py)
UV_CACHE_DIR=/home/z/.cache/uv uv run python cli.py db migrate "описание"

# Пометить БД как head (без выполнения миграций)
UV_CACHE_DIR=/home/z/.cache/uv uv run python cli.py db stamp head
```

---

## 7. Вспомогательные скрипты

| Скрипт | Команда | Назначение |
|--------|---------|------------|
| `scripts/seed_crm_templates.py` | `uv run python -m scripts.seed_crm_templates` | 6 стартовых шаблонов (email, TG, WA) |
| `scripts/seed_crm_contacts.py` | `uv run python -m scripts.seed_crm_contacts` | CRM-карточки для всех companies |
| `scripts/propagate_messengers.py` | `uv run python -m scripts.propagate_messengers` | Протянуть мессенджеры из enriched в companies |
| `scripts/enrich_jsprav_messengers.py` | `uv run python -m scripts.enrich_jsprav_messengers` | Добыть TG/WA из jsprav-профилей |
| `scripts/update_city_status.py` | `uv run python -m scripts.update_city_status` | Обновить статус городов в справочнике |
| `scripts/audit_database.py` | `uv run python -m scripts.audit_database` | Аудит целостности БД |
| `scripts/db_validate.py` | `uv run python -m scripts.db_validate` | Валидация данных и FK-связей |
| `scripts/benchmark.py` | `uv run python -m scripts.benchmark` | Бенчмарк запросов к БД |

---

## 8. Удаление и пересоздание БД

Если нужно начать с чистого листа:

```bash
# Удалить БД и логи
rm -f /home/z/my-project/granite-crm/data/granite.db
rm -f /home/z/my-project/granite-crm/data/crm.log

# При следующем запуске (API, pipeline, или seed-cities)
# БД пересоздастся автоматически с актуальной схемой
```

---

## 9. Типичный workflow

### Сценарий: новый город

```bash
# 1. Заполнить справочник городов (один раз)
UV_CACHE_DIR=/home/z/.cache/uv uv run python cli.py seed-cities

# 2. Запустить полный pipeline
UV_CACHE_DIR=/home/z/.cache/uv uv run python cli.py run "Волгоград"

# 3. Проверить результат
UV_CACHE_DIR=/home/z/.cache/uv uv run python cli.py cities-status

# 4. Экспортировать горячих лидов
UV_CACHE_DIR=/home/z/.cache/uv uv run python cli.py export-preset "Волгоград" hot_leads

# 5. Запустить API для CRM-работы
GRANITE_API_KEY=secret UV_CACHE_DIR=/home/z/.cache/uv uv run python cli.py api
```

### Сценарий: работа с CRM

```bash
# 1. Инициализировать CRM-данные (один раз, после первого парсинга)
UV_CACHE_DIR=/home/z/.cache/uv uv run python -m scripts.seed_crm_contacts
UV_CACHE_DIR=/home/z/.cache/uv uv run python -m scripts.seed_crm_templates

# 2. Запустить API
UV_CACHE_DIR=/home/z/.cache/uv uv run python cli.py api

# 3. В Swagger (/docs) или через curl:
#    - Просмотреть очередь follow-up
#    - Отправить холодное письмо
#    - Залогировать касание
#    - Обновить воронку
```

### Сценарий: дообогащение после обновления кода

```bash
# Пересобрать обогащение для города (не трогая парсинг)
UV_CACHE_DIR=/home/z/.cache/uv uv run python cli.py run "Астрахань" --re-enrich
```

---

## 10. Переменные окружения

| Переменная | По умолчанию | Описание |
|-----------|-------------|----------|
| `GRANITE_CONFIG` | `config.yaml` | Путь к конфигу |
| `GRANITE_API_KEY` | (пусто) | API-ключ для аутентификации. Пусто = dev-режим |
| `CORS_ORIGINS` | `localhost:3000,localhost:5173` | CORS origins для фронтенда |
| `FROM_NAME` | (пусто) | Имя для подстановки в шаблоны |
| `DGIS_API_KEY` | (пусто) | Ключ 2GIS API |
| `CRAWLEE_PROXY_URL` | (пусто) | Proxy для Crawlee-скраперов |
| `STALE_CAMPAIGN_MINUTES` | `10` | Таймаут для сброса застрявших кампаний |

---

## 11. Важные правила

1. **Перед любыми операциями с БД — бэкап.** Если удаляете или модифицируете данные, сделайте копию `data/granite.db`.

2. **WAL-режим.** Не удаляйте файлы `-wal` и `-shm` пока есть активные процессы. Они — часть БД.

3. **Не редактируйте БД напрямую.** Все изменения — через CLI или API. Прямые SQL-запросы могут нарушить FK-целостность.

4. **Чекпоинты города.** Если нужно перезапустить город с нуля — используйте `--force`, не удаляйте таблицы вручную.

5. **`run all` занимает часы.** Для тестирования используйте один город. Для массового запуска — screen/tmux.

6. **Logs.** Логи пишутся в `data/logs/granite.log` (ротация 10 MB, хранение 30 дней). API-логи — в `data/crm.log`.
