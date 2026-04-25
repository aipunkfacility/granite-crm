<!-- Обновлено: 2026-04-25 -->
# Быстрый старт RetouchGrav CRM

> От нуля до работающей системы за 5 минут.

---

## Требования

| Компонент | Версия | Зачем |
|-----------|--------|-------|
| Python | 3.12+ | Бэкенд (используется `str \| None` синтаксис) |
| uv | latest | Менеджер пакетов (НЕ pip) |
| Node.js | 18+ | Фронтенд |
| npm | 9+ | Зависимости фронтенда |

---

## Установка

### 1. Бэкенд

```bash
# Клонирование
git clone https://github.com/aipunkfacility/granite-crm.git
cd granite-crm

# Зависимости
uv sync

# Playwright (для скраперов с JS-рендерингом)
uv run playwright install chromium
```

### 2. Фронтенд

```bash
cd granite-web
npm install
cd ..
```

---

## Настройка

### .env (опционально)

```bash
cp .env.example .env
```

Ключевые переменные:

| Переменная | Обязательно | Описание |
|-----------|-------------|----------|
| `FROM_NAME` | Нет | Имя для плейсхолдера `{from_name}` |
| `GRANITE_ADMIN_PASSWORD` | Рекомендуется | Пароль режима администратора в CRM |
| `DGIS_API_KEY` | Нет | Ключ 2GIS (для reverse lookup) |
| `GRANITE_API_KEY` | Нет | Ключ авторизации API |

Без .env система запускается — ключи нужны только для расширенных функций.

### config.yaml

Основной конфигурационный файл. По умолчанию работает «из коробки». Города перечислены в `data/regions.yaml` (40 областей, 566 городов).

---

## Первый запуск

### Шаг 1: Заполнить справочник городов

```bash
uv run cli.py seed-cities
```

Создаёт записи в таблице `cities_ref` из `data/regions.yaml`.

### Шаг 2: Запустить пайплайн для города

```bash
uv run cli.py run "Астрахань"
```

Это запустит полный цикл: скрапинг → дедупликация → обогащение → скоринг → экспорт. Занимает 10-30 минут в зависимости от города. Миграции БД применяются автоматически при первом запуске.

### Шаг 3: Запустить API

```bash
uv run cli.py api --port 8000
```

Проверка: откройте `http://localhost:8000/health` — должно вернуть `{"status": "ok", "db": true}`.

Документация API: `http://localhost:8000/docs` — интерактивный Swagger UI.

### Шаг 4: Запустить фронтенд

```bash
cd granite-web
npm run dev
```

Откройте `http://localhost:3000` — должна загрузиться CRM с данными.

---

## Проверка

| Что проверить | Как |
|--------------|-----|
| Бэкенд работает | `curl http://localhost:8000/health` |
| API возвращает компании | `curl http://localhost:8000/api/v1/companies?per_page=5` |
| Фронтенд подключается | Откройте `http://localhost:3000` — должен быть список компаний |
| Пайплайн обработал город | `uv run cli.py cities-status` — показывает raw/companies/enriched по каждому городу |

---

## Лендинг RetouchGrav

Публичный сайт проекта: https://retouchgrav.netlify.app

Если нужно запустить лендинг локально:
```bash
git clone https://github.com/aipunkfacility/monument-web.git
# Открыть index.html в браузере — статический сайт, без сервера
```

Подробнее: [docs/landing/README.md](../landing/README.md)

---

## Следующие шаги

| Хочу... | Куда |
|---------|------|
| Узнать все CLI-команды | [cli-reference.md](cli-reference.md) |
| Понять, как пользоваться CRM | [crm-user-guide.md](crm-user-guide.md) |
| Настроить email-рассылку | [email-sending.md](email-sending.md) |
| Понять структуру проекта | [project-context.md](../project-context.md) |
| Посмотреть схему БД | [architecture/database.md](../architecture/database.md) |
