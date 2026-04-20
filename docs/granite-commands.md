# Granite CRM — Справочник команд

## Условные обозначения

- `uv run cli.py` — основной CLI, запускается из корня проекта
- Глобальный ключ: `--config / -c` — путь к config.yaml (по умолчанию `config.yaml`)

---

## 1. Скрапинг и пайплайн

### `run` — полный цикл для города

```bash
uv run cli.py run ГОРОД [ОПЦИИ]
```

| Опция | Сокращение | По умолч. | Описание |
|-------|-----------|-----------|----------|
| `ГОРОД` | — | обязательно | Название города, регион или `all` |
| `--force` | `-f` | False | Очистить старые данные, начать заново |
| `--no-scrape` | — | False | Пропустить скрапинг (использовать кэш) |
| `--re-enrich` | — | False | Перезапустить только обогащение |
| `--resume` | `-r` | False | Пропустить завершённые города |
| `--city-list` | `-l` | — | Файл со списком городов |

Примеры:
```bash
uv run cli.py run Астрахань              # один город
uv run cli.py run all -r                  # все города, пропуск завершённых
uv run cli.py run all -l cities.txt       # города из файла
uv run cli.py run Ярославль --re-enrich   # только обогащение
uv run cli.py run Астрахань -f            # с нуля
```

Пайплайн по порядку: скрапинг → дедупликация → обогащение → reverse lookup → детекция сетей → скоринг → экспорт.

### `precheck` — предзаполнение кэша категорий jsprav

```bash
uv run cli.py precheck [ГОРОД] [--force]
```

| Аргумент/Опция | По умолч. | Описание |
|----------------|-----------|----------|
| `ГОРОД` | `all` | Город или все |
| `--force` | False | Перепроверить закэшированные |

Первый запуск: 18-28 мин (1098 городов). Повторный — мгновенно из кэша.

```bash
uv run cli.py precheck              # все города
uv run cli.py precheck Астрахань    # один город
uv run cli.py precheck --force      # перепроверить всё
```

---

## 2. Экспорт

### `export` — экспорт данных из БД

```bash
uv run cli.py export ГОРОД [--format ФОРМАТ]
```

| Параметр | По умолч. | Описание |
|----------|-----------|----------|
| `ГОРОД` | обязательно | Город или `all` |
| `--format / -f` | `csv` | Формат: `csv` или `md` |

Результат: `data/export/{city}_enriched.csv` или `data/export/{city}_report.md`

### `export-preset` — экспорт по пресету

```bash
uv run cli.py export-preset ГОРОД ПРЕСЕТ
```

Доступные пресеты (из config.yaml):
- `hot_leads` — есть TG/WA + высокий CRM-скор
- `high_score` — сегмент A
- `with_telegram` — все с Telegram
- `cold_email` — нет мессенджеров, есть email
- `manual_search` — нет мессенджеров (нужен прозвон), формат Markdown
- `full_dump` — все обогащённые компании

```bash
uv run cli.py export-preset all hot_leads
uv run cli.py export-preset Астрахань with_telegram
```

---

## 3. Справочники и статус

### `seed-cities` — заполнить справочник городов

```bash
uv run cli.py seed-cities
```

Заполняет таблицу `cities_ref` из `data/regions.yaml`.

### `cities-status` — статус обработки городов

```bash
uv run cli.py cities-status
```

Показывает raw/companies/enriched по каждому городу, сгруппировано по региону. Метки: `+` = enriched, `*` = populated.

### `unmatched` — неразрешённые города

```bash
uv run cli.py unmatched
```

Города из данных, которых нет в `regions.yaml`.

---

## 4. База данных (Alembic)

### Через CLI

```bash
uv run cli.py db upgrade [РЕВИЗИЯ]     # применить миграции (default: head)
uv run cli.py db downgrade [РЕВИЗИЯ]   # откатить (default: -1)
uv run cli.py db history [-v] [-r RANGE]  # история миграций
uv run cli.py db current               # текущая версия схемы
uv run cli.py db migrate "описание"    # создать миграцию (autogenerate)
uv run cli.py db stamp [РЕВИЗИЯ]       # пометить версию без выполнения
uv run cli.py db check                 # проверить расхождения ORM ↔ БД
```

### Напрямую через Alembic

```bash
uv run alembic upgrade head
uv run alembic downgrade -1
uv run alembic history
uv run alembic current
uv run alembic revision --autogenerate -m "описание"
```

---

## 5. API-сервер

### `api` — запустить CRM API

```bash
uv run cli.py api [--port ПОРТ] [--reload]
```

| Опция | По умолч. | Описание |
|-------|-----------|----------|
| `--port / -p` | 8000 | Порт сервера |
| `--reload` | False | Hot reload (разработка) |

### Основные эндпоинты

Базовый URL: `http://localhost:8000/api/v1`
Документация: `/docs` (Swagger), `/redoc`

| Метод | Путь | Описание |
|-------|------|----------|
| `GET` | `/health` | Проверка здоровья (DB ping) |
| **Компании** | | |
| `GET` | `/companies` | Список (пагинация, фильтры, сортировка) |
| `GET` | `/companies/{id}` | Карточка компании |
| `PATCH` | `/companies/{id}` | Обновить CRM-поля |
| `GET` | `/companies/{id}/similar` | Похожие компании |
| `PATCH` | `/companies/{id}/merge` | Слияние компаний |
| `GET` | `/cities` | Список городов |
| `GET` | `/regions` | Список регионов |
| **Касания** | | |
| `POST` | `/companies/{id}/touches` | Записать касание |
| `GET` | `/companies/{id}/touches` | История касаний |
| `DELETE` | `/touches/{id}` | Удалить касание |
| **Задачи** | | |
| `POST` | `/companies/{id}/tasks` | Создать задачу |
| `GET` | `/tasks` | Все задачи |
| `PATCH` | `/tasks/{id}` | Обновить задачу |
| `DELETE` | `/tasks/{id}` | Удалить задачу |
| **Кампании** | | |
| `POST` | `/campaigns` | Создать кампанию |
| `GET` | `/campaigns` | Список кампаний |
| `GET` | `/campaigns/{id}` | Детали кампании |
| `PATCH` | `/campaigns/{id}` | Обновить (draft/paused) |
| `DELETE` | `/campaigns/{id}` | Удалить draft |
| `POST` | `/campaigns/{id}/run` | Запустить (SSE прогресс) |
| `GET` | `/campaigns/{id}/stats` | Статистика кампании |
| **Рассылка** | | |
| `POST` | `/companies/{id}/send` | Отправить сообщение (TG/WA) |
| `GET` | `/templates` | Шаблоны сообщений |
| `POST` | `/templates` | Создать шаблон |
| **Аналитика** | | |
| `GET` | `/funnel` | Воронка по стадиям |
| `GET` | `/followup` | Очередь follow-up |
| `GET` | `/stats` | Агрегированная статистика |
| **Экспорт** | | |
| `GET` | `/export/{city}.csv` | CSV-экспорт по городу |
| **Пайплайн** | | |
| `GET` | `/pipeline/status` | Статус пайплайна по городам |
| `POST` | `/pipeline/run` | Запустить пайплайн (SSE) |
| **Трекинг** | | |
| `GET` | `/track/open/{id}.png` | Пиксель открытия email |

Фильтры `GET /companies`: `city[]`, `region`, `segment`, `funnel_stage`, `has_telegram`, `has_whatsapp`, `has_email`, `min_score`, `search`, `page`, `per_page`, `order_by`, `order_dir`.

---

## 6. Скрипты (scripts/)

### Валидация и чистка БД

```bash
uv run scripts/db_validate.py [--db ПУТЬ] [--fix] [--json ФАЙЛ] [--conflicts-only]
```

Проверяет/чистит email и телефоны в raw_companies, companies, enriched_companies. Без `--fix` — только отчёт.

### Пропагация мессенджеров

```bash
uv run scripts/propagate_messengers.py [--db ПУТЬ] [--dry-run]
```

Каскадирует messengers из raw_companies → companies → enriched_companies через merged_from.

### Обогащение мессенджеров из jsprav

```bash
uv run scripts/enrich_jsprav_messengers.py [--db ПУТЬ] [--cities Г1 Г2] [--dry-run]
```

Скрапит detail-страницы jsprav для мессенджеров (TG, VK, WA, Viber, OK).

### Заполнение CRM-контактов

```bash
uv run -m scripts.seed_crm_contacts
```

Создаёт crm_contacts для компаний без CRM-записей (funnel_stage='new').

### Заполнение шаблонов сообщений

```bash
uv run -m scripts.seed_crm_templates
```

UPSERT 6 встроенных шаблонов (email/tg/wa — intro + follow-up). Плейсхолдеры: `{from_name}`, `{city}`, `{company_name}`, `{website}`.

### Обновление статуса городов

```bash
uv run scripts/update_city_status.py
```

Меняет статус в config.yaml с `pending` → `completed` для городов с данными.

### Аудит БД

```bash
uv run scripts/audit_database.py [--city ГОРОД] [--output ФАЙЛ] [--db ПУТЬ]
```

Генерирует Markdown-отчёт: статистика, качество по городам, аномалии скоринга, дубли, CMS, TG trust.

### Бенчмарк обогащения

```bash
uv run scripts/benchmark.py [N] [MAX_CONCURRENT]
```

Сравнивает sync vs async обогащение. N=15 компаний по умолчанию.

---

## 7. Резервное копирование

### CLI

```bash
uv run backup_db.py ПУТЬ_К_БД ПУТЬ_БЭКАПА
```

Hot-backup SQLite через `sqlite3.connect.backup()`.

### Windows bat-файлы

| Файл | Что делает |
|------|-----------|
| `run.bat` | `uv run cli.py run ГОРОД` (настроить CITY/FORCE/RE_ENRICH) |
| `run_all.bat` | `uv run cli.py run all` (resume from checkpoints) |
| `backup_db.bat` | Бэкап `data/granite.db` → `backups/granite_YYYY-MM-DD_HH-MM-SS.db` |
| `enrich_jsprav.bat` | Интерактивное меню для enrich_jsprav_messengers.py |
| `propagate.bat` | Интерактивное меню для propagate_messengers.py |

---

## 8. Frontend (granite-web/)

```bash
cd granite-web
npm run dev       # Dev-сервер
npm run build     # Production-сборка
npm run start     # Запуск production
npm run lint      # ESLint
```

---

## 9. Тестирование

```bash
uv run pytest                              # Все тесты
uv run pytest tests/test_crm_api.py        # Конкретный файл
uv run pytest tests/test_jsprav_base.py    # Тесты jsprav
uv run pytest --cov=granite                # С покрытием
```

---

## 10. Переменные окружения

| Переменная | Описание |
|-----------|----------|
| `DATABASE_URL` | URL БД (переопределяет config.yaml) |
| `DGIS_API_KEY` | Ключ 2GIS API |
| `TELEGRAM_API_ID` | Telegram API ID |
| `TELEGRAM_API_HASH` | Telegram API hash |
| `TELESCAN_API_KEY` | Ключ Telescan (опционально) |
| `TG_SESSION_PATH` | Путь к сессии Telethon |
| `WA_API_URL` | URL WhatsApp API |
| `WA_API_TOKEN` | Токен WhatsApp API |
| `FROM_NAME` | Имя для плейсхолдера `{from_name}` |
| `GRANITE_API_KEY` | Ключ авторизации API (если задан) |
| `CORS_ORIGINS` | CORS origins (через запятую) |
| `GRANITE_CONFIG` | Путь к config.yaml |
| `DEBUG` | Показывать детали ошибок в API |
