# Granite CRM

**Локальная CRM для личного использования. Прода не будет.**

## Обзор

FastAPI сервер для управления контактами и email-рассылок.

```
Браузер (SPA) ──fetch()──▶ localhost:8000 ──SMTP──▶ Gmail
                                       │
                                       └── db/*.json
```

**Архитектура:**
- JSON-файлы в `db/` — источник данных
- IndexedDB в браузере — быстрый кэш
- `backups/` — автоматические бэкапы

## Быстрый старт

```bash
pip install -r requirements.txt
cp config.example.json config.json
# Отредактируйте config.json и создайте .env
start.bat
```

Проверка: http://localhost:8000/health

## Настройка Gmail

1. Включите двухфакторную аутентификацию
2. Создайте App Password: myaccount.google.com → Пароли приложений
3. Добавьте в `.env`:
```
GMAIL_APP_PASSWORD=your_16_char_password
```

## Аутентификация

При наличии переменной `CRM_API_TOKEN` в `.env`:
- GET: `/health`, `/template`, `/` — без токена
- POST/PUT/DELETE: требуется заголовок `Authorization: Bearer <token>`

## Примеры API

### Проверка сервера
```bash
curl http://localhost:8000/health
# {"status":"ok","server":"email-sender","db_files":2}
```

### Email рассылка
```bash
# Запуск
curl -X POST http://localhost:8000/send/batch \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{"contacts":[{"email":"test@example.com","name":"Test"}],"html":"<p>Hello</p>"}'

# Статус ( polling )
curl http://localhost:8000/send/status/JOB_ID

# SSE (реалтайм)
curl -N http://localhost:8000/send/stream/JOB_ID
```

### Работа с данными
```bash
# Список файлов
curl http://localhost:8000/db/list

# Сохранение
curl -X PUT http://localhost:8000/db/myfile.json \
  -H "Content-Type: application/json" \
  -d '[{"name":"Company","phone":"+1234567890"}]'
```

### Бэкапы
```bash
curl http://localhost:8000/backups
curl -X POST http://localhost:8000/db/myfile.json/restore
```

## Структура проекта

```
GRANITE CRM/
├── index.html              # SPA интерфейс
├── server/                 # FastAPI сервер
│   ├── __init__.py         # app, middleware, CORS
│   ├── config.py           # конфигурация, пути
│   ├── models.py           # Pydantic модели
│   ├── middleware.py       # auth middleware
│   ├── routers/            # API endpoints
│   │   ├── send.py         # email рассылка
│   │   ├── db.py           # CRUD файлов
│   │   ├── template.py     # шаблон писем
│   │   └── backup.py       # бэкапы
│   └── services/          # бизнес-логика
│       ├── email.py        # SMTP отправка
│       ├── batch.py        # async батч рассылка
│       └── backup.py      # создание бэкапов
├── js/                     # клиентские скрипты
├── css/                    # стили
├── db/                     # JSON файлы данных
├── backups/               # автоматические бэкапы
├── logs/                   # логи сервера
├── config.example.json    # пример конфига
├── .env                   # secrets (в gitignore)
└── requirements.txt       # Python зависимости
```

## Безопасность

- `config.json` и `.env` в `.gitignore`
- CORS только для `localhost` / `127.0.0.1`
- Path traversal защита
- Атомарная запись файлов
- Опциональный API токен

## Частые ошибки

**«Username and Password not accepted»**
- Пароль с пробелами → уберите пробелы
- App Password истёк → создайте новый

**«Сервер не отвечает»**
- `start.bat` закрыт → перезапустите
- Порт 8000 занят → закройте другое приложение

## Документация

Подробнее в `docs/`:
- `API_REFERENCE.md` — все API эндпоинты
- `BACKUP_RESTORE.md` — система бэкапов
- `Гайд по настройке рассылки.md` — настройка Gmail