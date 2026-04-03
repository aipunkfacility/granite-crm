# План: Email-рассылка из CRM (локальный сервер)

## Архитектура

```
CRM (browser) ──fetch()──▶ Python Server (FastAPI) ──SMTP──▶ Gmail
```

---

## Фаза 1: Серверная часть

### 1.1 Конфигурация SMTP
- **Файл:** `email/config.json`
- Вынести SMTP-настройки из скрипта в конфиг
- Убрать хардкод пароля, добавить `.gitignore` для конфига
- Поля: `smtp_server`, `smtp_port`, `sender_email`, `sender_password`, `email_subject`, `template_file`, `delay_min`, `delay_max`

### 1.2 FastAPI сервер
- **Файл:** `email/server.py`
- Зависимости: `fastapi`, `uvicorn`, `smtplib` (stdlib)
- Эндпоинты:
  - `GET /health` — проверка связи
  - `POST /send/single` — отправить одно письмо (email, name, html)
  - `POST /send/batch` — запустить пачку с задержками (список контактов)
  - `GET /send/status/{job_id}` — статус текущей рассылки
  - `POST /send/cancel/{job_id}` — отмена рассылки
  - `GET /template` — получить HTML-шаблон
  - `POST /template` — обновить HTML-шаблон
- Фоновая обработка batch через `asyncio.create_task`
- Хранение статуса job в памяти (dict)
- CORS middleware для localhost

### 1.3 Тестирование сервера
- Проверка `/health`
- Отправка тестового письма через `/send/single`
- Проверка batch с 2-3 контактами

---

## Фаза 2: Клиентская часть (CRM)

### 2.1 Модуль email-sender.js
- **Файл:** `crm/js/email-sender.js`
- Функции:
  - `EmailSender.checkServer()` — проверка доступности сервера
  - `EmailSender.openModal()` — открыть модалку рассылки
  - `EmailSender.renderPreview(contacts)` — превью получателей
  - `EmailSender.startBatch(contacts)` — запуск рассылки
  - `EmailSender.pollStatus(jobId)` — опрос прогресса
  - `EmailSender.cancelBatch(jobId)` — отмена
  - `EmailSender.onComplete(results)` — обработка результатов

### 2.2 UI модалки рассылки
- **Стили:** `crm/css/styles.css` — новые классы
- **Содержимое модалки:**
  - Заголовок: «Email-рассылка»
  - Статус сервера (🟢/🔴)
  - Список получателей (скроллируемый, с именами и email)
  - Превью шаблона (iframe или div)
  - Кнопки: «Отправить», «Отмена», «Закрыть»
  - Прогресс-бар: «Отправлено 3/15»
  - Лог отправки: `[✓] info@granit.ru — OK`, `[✗] bad@mail.ru — ошибка`

### 2.3 Интеграция в CRM
- **Файл:** `crm/index.html`
  - Добавить кнопку «📧 Рассылка» в хедер контактов
  - Подключить `email-sender.js`
- **Файл:** `crm/js/batch.js`
  - Добавить `Batch.sendEmails()` — собирает выбранные контакты с email, открывает модалку
- **Файл:** `crm/js/render.js`
  - Обновить batch-бар: добавить кнопку рассылки
  - После успешной отправки — автоматический `recordTouch(id, 'email', 'рассылка')`

---

## Фаза 3: Надёжность и UX

### 3.1 Обработка ошибок
- Сервер недоступен → toast с инструкцией запуска
- SMTP ошибка → показать в логе, не прерывать batch
- Дубликаты email → предупреждение перед отправкой
- Контакты без email → исключение из списка

### 3.2 История и отчёт
- После рассылки — модалка с итогами:
  - Всего: 15, Успешно: 13, Ошибки: 2
  - Список ошибок с причинами
- Автоматическая отметка успешных контактов в CRM
- Экспорт отчёта в JSON (опционально)

### 3.3 Документация
- **Файл:** `email/README.md`
  - Установка зависимостей
  - Запуск сервера
  - Настройка config.json
  - Использование из CRM

---

## Зависимости между фазами

```
Фаза 1.1 → 1.2 → 1.3
                  ↓
Фаза 2.1 → 2.2 → 2.3
                  ↓
Фаза 3.1 → 3.2 → 3.3
```

Фаза 2 может начаться параллельно с 1.3 (мокап сервера).

---

## Новые файлы

| Файл | Назначение |
|------|-----------|
| `email/config.json` | SMTP конфиг |
| `email/server.py` | FastAPI сервер |
| `email/requirements.txt` | Python зависимости |
| `crm/js/email-sender.js` | UI рассылки |
| `email/README.md` | Документация |

## Изменяемые файлы

| Файл | Изменения |
|------|----------|
| `crm/index.html` | Кнопка + скрипт |
| `crm/css/styles.css` | Стили модалки |
| `crm/js/batch.js` | `Batch.sendEmails()` |
| `crm/js/render.js` | Кнопка в batch-баре |
| `.gitignore` | `email/config.json` |
