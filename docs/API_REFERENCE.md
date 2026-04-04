# API Reference

## Base URL

```
http://localhost:8000
```

**Примечание:** Это локальная CRM для личного использования. Сервер работает только на localhost.

---

## Аутентификация

При наличии переменной `CRM_API_TOKEN` в `.env`:

| Метод | Эндпоинты | Требует токен |
|-------|-----------|---------------|
| GET | `/health`, `/template`, `/` | Нет |
| POST/PUT/DELETE | Все остальные | Да |

**Заголовок:**
```
Authorization: Bearer YOUR_TOKEN
```

**Ответ при ошибке 401:**
```json
{"detail": "Unauthorized"}
```

---

## Эндпоинты

### Health Check

| | |
|---|---|
| **GET** | `/health` |

Проверка работоспособности сервера.

```bash
curl http://localhost:8000/health
```

**Response:**
```json
{
  "status": "ok",
  "server": "email-sender",
  "timestamp": "2026-04-04T12:00:00",
  "db_files": 2
}
```

---

## Email Endpoints

### Отправить одно письмо

| | |
|---|---|
| **POST** | `/send/single` |

**Request Body:**
```json
{
  "email": "recipient@example.com",
  "name": "Имя получателя",
  "html": "<h1>Hello</h1>"  // опционально
}
```

```bash
curl -X POST http://localhost:8000/send/single \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{"email":"test@example.com","name":"Test","html":"<h1>Hello</h1>"}'
```

**Success Response:**
```json
{
  "success": true,
  "message": "Sent",
  "request_id": "af98fba1"
}
```

**Error Response:**
```json
{
  "success": false,
  "error": "Authentication failed",
  "error_type": "smtp_error",
  "request_id": "af98fba1"
}
```

---

### Запустить рассылку

| | |
|---|---|
| **POST** | `/send/batch` |

Асинхронная рассылка. Проверяйте статус через `/send/status/{job_id}` или `/send/stream/{job_id}` (SSE).

**Request Body:**
```json
{
  "contacts": [
    {"email": "user1@example.com", "name": "User 1"},
    {"email": "user2@example.com", "name": "User 2"}
  ],
  "html": "<p>Текст рассылки</p>"  // опционально
}
```

```bash
curl -X POST http://localhost:8000/send/batch \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "contacts":[
      {"email":"user1@example.com","name":"User 1"},
      {"email":"user2@example.com","name":"User 2"}
    ],
    "html":"<p>Batch email</p>"
  }'
```

**Response:**
```json
{
  "job_id": "bb0b18f4-4fcb-46f0-adc9-1f8ed21d1b26",
  "total": 2,
  "status": "started"
}
```

---

### Статус рассылки (polling)

| | |
|---|---|
| **GET** | `/send/status/{job_id}` |

```bash
curl http://localhost:8000/send/status/bb0b18f4-4fcb-46f0-adc9-1f8ed21d1b26
```

**Response:**
```json
{
  "job_id": "bb0b18f4-...",
  "total": 2,
  "sent": 1,
  "failed": 0,
  "status": "completed",
  "results": [
    {"email": "user1@example.com", "success": true, "error": "", "error_type": ""},
    {"email": "user2@example.com", "success": true, "error": "", "error_type": ""}
  ]
}
```

**Статусы:** `started` → `completed` | `cancelled`

---

### SSE статус рассылки (реалтайм)

| | |
|---|---|
| **GET** | `/send/stream/{job_id}` |

Server-Sent Events для мгновенного обновления прогресса без polling.

```bash
curl -N http://localhost:8000/send/stream/JOB_ID
```

**Events:**

1. **init** — начальное состояние job:
```json
{
  "event": "init",
  "job_id": "...",
  "total": 10,
  "sent": 0,
  "failed": 0,
  "status": "started",
  "results": []
}
```

2. **result** — результат каждого письма:
```json
{
  "event": "result",
  "email": "user@example.com",
  "success": true,
  "error": "",
  "sent": 1,
  "failed": 0,
  "total": 10
}
```

3. **done** — завершение:
```json
{
  "event": "done",
  "status": "completed",
  "sent": 8,
  "failed": 2,
  "total": 10
}
```

**Пример на JavaScript:**
```javascript
const source = new EventSource('/send/stream/' + jobId);

source.addEventListener('init', (e) => {
  const data = JSON.parse(e.data);
  console.log('Started:', data.total, 'emails');
});

source.addEventListener('result', (e) => {
  const data = JSON.parse(e.data);
  console.log('Sent:', data.sent, '/', data.total);
});

source.addEventListener('done', (e) => {
  const data = JSON.parse(e.data);
  console.log('Completed:', data.sent, 'sent,', data.failed, 'failed');
  source.close();
});
```

---

### Отменить рассылку

| | |
|---|---|
| **POST** | `/send/cancel/{job_id}` |

```bash
curl -X POST http://localhost:8000/send/cancel/bb0b18f4-... \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**Response:**
```json
{"status": "cancelled"}
```

---

### Шаблон письма

| | |
|---|---|
| **GET** | `/template` |
| **POST** | `/template` |

**GET** — получить текущий шаблон:
```bash
curl http://localhost:8000/template
```

**POST** — обновить шаблон:
```bash
curl -X POST http://localhost:8000/template \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{"html":"<html>...</html>"}'
```

---

## Database Endpoints

### Список файлов

| | |
|---|---|
| **GET** | `/db/list` |

```bash
curl http://localhost:8000/db/list
```

**Response:**
```json
{
  "files": [
    {"name": "Rostov.json", "size": 25299, "modified": "2026-04-02T23:04:56"},
    {"name": "Moscow.json", "size": 18432, "modified": "2026-04-01T12:30:00"}
  ]
}
```

---

### Читать файл

| | |
|---|---|
| **GET** | `/db/{filename}` |

```bash
curl http://localhost:8000/db/Rostov.json
```

**Response:** массив контактов или объект JSON.

---

### Сохранить файл

| | |
|---|---|
| **PUT** | `/db/{filename}` |

Автоматически создаёт бэкап перед сохранением.

```bash
curl -X PUT http://localhost:8000/db/data.json \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{"contacts":[{"name":"Test","phone":"+123"}]}'
```

**Response:**
```json
{
  "success": true,
  "file": "data.json",
  "size": 45,
  "backup": "data.json.20260403_044857.bak"
}
```

---

### Удалить файл

| | |
|---|---|
| **DELETE** | `/db/{filename}` |

Создаёт бэкап перед удалением.

```bash
curl -X DELETE http://localhost:8000/db/data.json \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**Response:**
```json
{
  "success": true,
  "file": "data.json",
  "backup": "data.json.20260403_044857.bak"
}
```

---

### Бэкапы файла

| | |
|---|---|
| **GET** | `/db/{filename}/backups` |

```bash
curl http://localhost:8000/db/Rostov.json/backups
```

**Response:**
```json
{
  "file": "Rostov.json",
  "backups": [
    {"name": "Rostov.json.20260403_044857.bak", "size": 22583, "modified": "..."},
    {"name": "Rostov.json.20260402_120000.bak", "size": 22450, "modified": "..."}
  ]
}
```

---

## Backup Endpoints

### Все бэкапы

| | |
|---|---|
| **GET** | `/backups` |

```bash
curl http://localhost:8000/backups
```

**Response:**
```json
{
  "backups": [
    {"name": "Rostov.json.20260403_000048.bak", "size": 22583, "created": "..."},
    {"name": "Moscow.json.20260402_180000.bak", "size": 18432, "created": "..."}
  ]
}
```

---

### Восстановить из бэкапа

| | |
|---|---|
| **POST** | `/restore/{backup_name}` |

```bash
curl -X POST http://localhost:8000/restore/Rostov.json.20260403_000048.bak
```

**Response:**
```json
{
  "success": true,
  "backup": "Rostov.json.20260403_000048.bak",
  "contacts": [...]
}
```

---

### Восстановить файл (автоматически последний бэкап)

| | |
|---|---|
| **POST** | `/db/{filename}/restore` |

```bash
curl -X POST http://localhost:8000/db/Rostov.json/restore
```

**Response:**
```json
{
  "success": true,
  "file": "Rostov.json",
  "restored_from": "Rostov.json.20260403_044857.bak"
}
```

---

## Типы ошибок

| error_type | Описание | Решение |
|------------|----------|---------|
| `smtp_error` | Ошибка SMTP или авторизации | Проверьте App Password |
| `connection_error` | Сетевая ошибка, таймаут | Проверьте интернет-соединение |
| `invalid_email` | Неверный формат email | Проверьте адрес получателя |
| `unknown_error` | Неизвестная ошибка | Смотрите логи сервера |

---

## HTTP Status Codes

| Code | Значение |
|------|----------|
| 200 | Успех |
| 400 | Неверный запрос (валидация) |
| 401 | Не авторизован |
| 404 | Файл или job не найден |
| 500 | Ошибка сервера |