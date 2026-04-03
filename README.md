# Email Sender + CRM Data Server

## Обзор

FastAPI сервер для двух задач:
1. **Email рассылка** — через Gmail SMTP
2. **CRM данные** — JSON файлы на диске

```
CRM (браузер) ──fetch()──▶ Сервер (localhost:8000) ──SMTP──▶ Gmail
                                      │
                                      └── crm/db/*.json
```

**Архитектура хранения:**
- `crm/db/*.json` — главный источник
- IndexedDB в браузере — быстрый кэш
- `crm/backups/` — автоматические бэкапы

## Быстрый старт

```bash
cd crm
pip install -r requirements.txt
cp config.example.json config.json
# Отредактируйте config.json и .env
start.bat
```

Проверка: http://localhost:8000/health

## Установка Gmail

1. Включите двухфакторную аутентификацию
2. Создайте App Password: myaccount.google.com → Пароли приложений
3. Добавьте в `.env`:
```
GMAIL_APP_PASSWORD=your_16_char_password
```

## curl примеры

### Проверка сервера

```bash
curl http://localhost:8000/health
# {"status":"ok","server":"email-sender","db_files":2}
```

### Отправка одного письма

```bash
curl -X POST http://localhost:8000/send/single \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","name":"Test","html":"<h1>Hello</h1>"}'
```

### Рассылка (async)

```bash
# Запуск
curl -X POST http://localhost:8000/send/batch \
  -H "Content-Type: application/json" \
  -d '{
    "contacts":[
      {"email":"user1@example.com","name":"User 1"},
      {"email":"user2@example.com","name":"User 2"}
    ],
    "html":"<p>Batch email</p>"
  }'
# {"job_id":"bb0b18f4-...","total":2,"status":"started"}

# Проверка статуса
curl http://localhost:8000/send/status/bb0b18f4-...

# Отмена
curl -X POST http://localhost:8000/send/cancel/bb0b18f4-...
```

### Работа с базой

```bash
# Список файлов
curl http://localhost:8000/db/list

# Чтение
curl http://localhost:8000/db/Rostov.json

# Сохранение (с автобэкапом)
curl -X PUT http://localhost:8000/db/data.json \
  -H "Content-Type: application/json" \
  -d '{"contacts":[{"name":"Test","phone":"+123"}]}'

# Удаление (с бэкапом)
curl -X DELETE http://localhost:8000/db/data.json
```

### Бэкапы и восстановление

```bash
# Все бэкапы
curl http://localhost:8000/backups

# Бэкапы конкретного файла
curl http://localhost:8000/db/Rostov.json/backups

# Восстановление
curl -X POST http://localhost:8000/restore/Rostov.json.20260403_000048.bak
```

### Шаблон письма

```bash
# Получить
curl http://localhost:8000/template

# Обновить
curl -X POST http://localhost:8000/template \
  -H "Content-Type: application/json" \
  -d '{"html":"<html>...</html>"}'
```

## Типы ошибок email

| Тип | Причина | Решение |
|-----|---------|---------|
| `smtp_error` | SMTP/авторизация | Проверьте App Password |
| `connection_error` | Сеть/таймаут | Проверьте интернет |
| `invalid_email` | Неверный email | Проверьте формат |
| `unknown_error` | Другое | Смотрите логи |

## Структура файлов

```
crm/
├── server.py              # FastAPI сервер
├── config.json            # SMTP настройки
├── .env                   # Пароли (gitignore)
├── db/                    # Данные CRM
│   └── *.json
├── backups/               # Автобэкапы
│   └── *.bak
└── logs/
    └── crm_server.log     # Логи (ротация 5MB × 5)
```

## Частые ошибки

**«Username and Password not accepted»**
- Пароль с пробелами → уберите пробелы
- App Password истёк → создайте новый

**«Сервер не отвечает»**
- `start.bat` закрыт → перезапустите
- Порт 8000 занят → закройте другое приложение

**JSON повреждён**
- API вернёт ошибку с путём к бэкапу
- Восстановите: `POST /restore/{backup_name}`

## Безопасность

- `config.json` и `.env` в `.gitignore`
- Только localhost (127.0.0.1)
- Path traversal защита
- Атомарная запись файлов
