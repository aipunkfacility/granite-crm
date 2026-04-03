# Отчёт об аудите безопасности Granite CRM

**Дата:** 2026-04-03  
**Репозиторий:** https://github.com/aipunkfacility/granite-crm  
**Коммиты:** 11 | **Стек:** Python (FastAPI) + Vanilla JS (IndexedDB/Dexie)  
**Назначение:** Локальная CRM для рассылки email и управления контактами гранитных мастерских  

---

## Сводка критических находок

| Уровень | Кол-во | Описание |
|---------|--------|----------|
| 🔴 Критический | 3 | Отсутствие аутентификации, CORS `*`, утечка данных в git |
| 🟠 Высокий | 4 | Отсутствие rate-limiting, XSS через шаблон, ошибки в тестах, SMPT-пароль в JSON |
| 🟡 Средний | 5 | Утечка ошибок, отсутствие CSP, голые except, no input sanitization, template RCE |
| 🔵 Низкий | 4 | CDN без SRI, hardcoded URLs, устаревший test_server.py, отстутствие версионирования API |

**Итого: 16 проблем.**

---

## 1. Критические проблемы

### 1.1 Отсутствие аутентификации и авторизации

**Файл:** `server/__init__.py`, все `server/routers/*.py`  
**Все 14 API-эндпоинтов полностью открыты** — без токенов, API-ключей, Basic Auth или любой другой формы аутентификации.

Это означает, что любой процесс на машине (или злоумышленник, получивший доступ к локальной сети) может:
- **Чтение:** `GET /db/list`, `GET /db/{filename}` — полный дамп всех контактов (телефоны, email, Telegram, WhatsApp).
- **Запись/Удаление:** `PUT /db/{filename}`, `DELETE /db/{filename}` — уничтожение или подмена данных.
- **Email-рассылка:** `POST /send/single`, `POST /send/batch` — отправка писем от вашего имени произвольным адресатам.
- **Управление шаблонами:** `POST /template` — подмена содержимого рассылки.
- **Восстановление бэкапов:** `POST /restore/{backup_name}` — откат данных.

**Рекомендация:** Добавить хотя бы API-токен в заголовке `Authorization: Bearer <token>`. Для локального использования достаточно простого токена из `.env`:

```python
# server/config.py
API_TOKEN = os.environ.get("CRM_API_TOKEN", "")

# server/__init__.py — middleware
@app.middleware("http")
async def auth_middleware(request, call_next):
    if request.url.path != "/health":
        token = request.headers.get("Authorization", "").replace("Bearer ", "")
        if token != config.API_TOKEN:
            return JSONResponse(status_code=401, content={"detail": "Unauthorized"})
    return await call_next(request)
```

---

### 1.2 CORS разрешён для всех источников

**Файл:** `server/__init__.py`, строки 58–64

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

Комбинация `allow_origins=["*"]` + `allow_credentials=True` **позволяет любому сайту в интернете выполнять авторизованные запросы** к вашему локальному серверу (CSRF-атака). Злоумышленная страница может прочитать все контакты и инициировать рассылку, если вы откроете её в браузере.

**Рекомендация:**

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000", "http://127.0.0.1:8000"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type", "Authorization"],
)
```

---

### 1.3 Персональные данные клиентов в открытом репозитории

**Файлы:** `db/*.json` (6 файлов, ~80 KB данных)  
**Git-история:** коммиты содержат CSV/Excel с контактами, данные о клиентах.

В репозитории на GitHub хранятся реальные данные клиентов:
- Названия компаний (X-granit, и др.)
- Телефоны: `+7 (952) 580-13-35` и т.д.
- Email-адреса: `info@x-granit.ru` и т.д.
- Telegram: `https://t.me/Psiholirik_161`
- WhatsApp ссылки
- История рассылок с датами (`touch_history`)

**Правовые риски:**
- Нарушение ФЗ-152 «О персональных данных» (РФ) — обработка и публикация ПДн без согласия.
- GDPR — если среди контактов есть лица из ЕС.
- Уголовная ответственность по ст. 137 УК РФ (нарушение неприкосновенности частной жизни).

**Рекомендация:**
1. Немедленно удалить `db/*.json` из git-истории:
   ```bash
   git filter-branch --force --index-filter \
     'git rm -rf --cached --ignore-unmatch db/' \
     --prune-empty --tag-name-filter cat -- --all
   git push origin --force --all
   ```
2. Добавить `db/` в `.gitignore`.
3. Рассмотреть возможность удаления всего репозитория и создания нового без истории.
4. Получить согласия на обработку ПДн у всех контактов.

---

## 2. Высокие проблемы

### 2.1 Отсутствие rate-limiting на эндпоинтах рассылки

**Файлы:** `server/routers/send.py`, `server/services/batch.py`  
**Эндпоинты:** `POST /send/single`, `POST /send/batch`

Нет ограничений на количество запросов. Злоумышленник (или любой локальный процесс) может:
- Отправить массовую рассылку, вызвав блокировку Gmail-аккаунта.
- Перегрузить SMTP-сервер.
- Сгенерировать reputационный ущерб домена отправителя.

**Рекомендация:** Добавить ограничение через `slowapi`:

```python
from slowapi import Limiter
limiter = Limiter(key_func=get_remote_address)

@router.post("/single")
@limiter.limit("10/minute")
async def send_single(request: Request, body: SingleEmail):
    ...
```

---

### 2.2 Stored XSS через email-шаблон

**Файл:** `server/routers/template.py`, `js/email-sender.js`

Шаблон письма (`POST /template`) сохраняется как произвольный HTML и подставляется в `innerHTML` без санитизации при просмотре в модальном окне:

```javascript
// email-sender.js, строка 119
'<div class="email-preview-inner">' + templateHtml + '</div>'
```

Атакующий, получивший доступ к API, может внедрить вредоносный JS через шаблон, который выполнится при просмотре превью в браузере.

**Рекомендация:** Санитизировать HTML перед отображением в превью. Использовать DOMPurify или аналоги. Отображать шаблон в `<iframe>` с `sandbox`.

---

### 2.3 SMTP-пароль в config.json (plaintext)

**Файл:** `config.example.json`, строка 5

```json
{
  "sender_password": "",
  ...
}
```

Хотя `.env` для пароля предусмотрен (строка 30–33 в `config.py`), `config.json` всё ещё содержит поле `sender_password`. Если пользователь заполнит его напрямую (а не через `.env`), пароль будет храниться в plaintext. Кроме того, `config.json` может случайно попасть в git.

**Рекомендация:**
1. Удалить `sender_password` из `config.json` и `config.example.json`.
2. Использовать только `.env` для хранения пароля.
3. Добавить проверку: если `sender_password` найден в `config.json` — выводить warning.

---

### 2.4 Тесты не проходят (устаревшие)

**Файл:** `test_server.py`, строки 124–139

Тесты ссылаются на функции и атрибуты, которых больше нет в текущей кодовой базе после рефакторинга:

```python
# test_server.py:127 — проверяет Inline onclick, который удалён
assert "onclick=\"Render.editArea('" not in content
assert "data-area-edit" in content  # Этот атрибут тоже не существует
```

Это означает, что CI/CD (если есть) молча пропускает ошибки.

**Рекомендация:** Переписать тесты под актуальную структуру проекта. Добавить pytest и覆盖率.

---

## 3. Средние проблемы

### 3.1 Утечка информации об ошибках

**Файлы:** `server/routers/db.py` (строка 47, 77), `server/services/batch.py` (строки 38, 81)

Детали исключений (`str(e)`) возвращаются клиенту в HTTP-ответах 500:

```python
raise HTTPException(status_code=500, detail=str(e))
```

Это может раскрыть:
- Пути к файлам на сервере
- Структуру директорий
- Версии библиотек
- SQL-запросы (если бы БД была SQL)

**Рекомендация:** Логировать полную ошибку, а клиенту возвращать обобщённое сообщение:

```python
logger.error(f"Failed to read {safe_name}: {e}")
raise HTTPException(status_code=500, detail="Internal server error")
```

---

### 3.2 Отсутствие Content-Security-Policy заголовков

**Файл:** `server/__init__.py`

Сервер отдаёт HTML/JS без CSP-заголовков. Браузер не ограничен в загрузке скриптов и ресурсов, что увеличивает поверхность атаки при XSS.

**Рекомендация:** Добавить middleware:

```python
@app.middleware("http")
async def csp_middleware(request, call_next):
    response = await call_next(request)
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self' 'unsafe-inline' "
        "cdn.jsdelivr.net unpkg.com; style-src 'self' 'unsafe-inline' "
        "fonts.googleapis.com; font-src fonts.gstatic.com"
    )
    return response
```

---

### 3.3 Голые `except` (bare except) без логирования

**Файлы:** `server/routers/db.py` (строка 103), `server/services/batch.py` (строки 53, 103, 127)

```python
except:
    pass
```

Такие конструкции скрывают ошибки и делают отладку невозможной. Ошибка чтения существующего JSON-файла (строка 103 в `db.py`) молча игнорируется, и файл перезаписывается без проверки.

**Рекомендация:** Заменить все `except:` на `except Exception as e:` с логированием.

---

### 3.4 Отсутствие валидации email на сервере

**Файлы:** `server/models.py`, `server/services/email.py`

Модель `SingleEmail` и `BatchContact` не валидируют формат email. Значение `email` — просто строка без проверок. Некорректный email приведёт к SMTP-ошибке, но запрос будет принят и обработан.

```python
class SingleEmail(BaseModel):
    email: str  # Нет валидации формата
    name: str
```

**Рекомендация:**

```python
from pydantic import EmailStr

class SingleEmail(BaseModel):
    email: EmailStr
    name: str
```

---

### 3.5 Запись шаблона в любой путь (Template RCE)

**Файл:** `server/routers/template.py`, строки 19–28

```python
template_path = os.path.join(
    config.get("BASE_DIR", ""), config.get("template_file", "email_template.html")
)
with open(template_path, "w", encoding="utf-8") as f:
    f.write(body.html)
```

Поле `BASE_DIR` в config не устанавливается (ключ отсутствует в `config.example.json`), поэтому `config.get("BASE_DIR", "")` возвращает `""`. Если злоумышленник сможет модифицировать `config.json` (например, через уязвимость в другом эндпоинте), он сможет записать произвольный контент в любой файл.

Кроме того, шаблон может содержать `<script>` теги, которые выполнятся при открытии письма в клиенте (Stored XSS через email).

**Рекомендация:**
1. Жёстко задать `template_path` в `config.py` (не из конфига).
2. Добавить проверку, что путь находится внутри `BASE_DIR`.
3. Санитизировать HTML-шаблон перед сохранением.

---

## 4. Низкие проблемы

### 4.1 CDN-зависимости без SRI (Subresource Integrity)

**Файл:** `index.html`, строки 7–11

```html
<script src="https://cdn.jsdelivr.net/npm/papaparse@5.4.1/papaparse.min.js"></script>
<script src="https://unpkg.com/dexie@3.2.7/dist/dexie.js"></script>
<script src="https://cdn.jsdelivr.net/npm/exceljs@4.4.0/dist/exceljs.min.js"></script>
```

CDN без SRI уязвим к атаке Man-in-the-Middle. Злоумышленник на пути следования трафика может подменить JS-файл и выполнить произвольный код.

**Рекомендация:** Добавить `integrity` и `crossorigin` атрибуты:

```html
<script src="https://cdn.jsdelivr.net/npm/papaparse@5.4.1/papaparse.min.js"
        integrity="sha384-..."
        crossorigin="anonymous"></script>
```

---

### 4.2 Жёстко закодированный URL сервера

**Файл:** `js/email-sender.js`, строка 3

```javascript
SERVER_URL: 'http://localhost:8000',
```

В то время как `js/db.js` использует `window.location.origin` (строки 39–41), модуль `EmailSender` использует жёстко заданный `localhost:8000`. Это сломает рассылку, если сервер запущен на другом порту или хосте.

**Рекомендация:** Использовать общую константу `SERVER_URL` из `db.js`.

---

### 4.3 Устаревший `test_server.py`

**Файл:** `test_server.py`

Тесты написаны для старой монолитной структуры (`import server` — `server.py` больше не существует после рефакторинга). Тесты импортируют `server.send_single_email`, но после разделения на модули эта функция находится в `server.services.email`. Несколько тестов обращаются к несуществующим атрибутам.

**Рекомендация:** Полностью переписать тесты под новую модульную структуру. Использовать pytest и httpx.AsyncClient для тестирования FastAPI-эндпоинтов.

---

### 4.4 Отсутствие версионирования API

**Файл:** `server/routers/*.py`

Все эндпоинты расположены в корневом пути (`/db/`, `/send/`, `/backups/`). Любые изменения в API сломают существующих клиентов без возможности обратной совместимости.

**Рекомендация:** Перенести эндпоинты под `/api/v1/`.

---

## 5. Архитектурные замечания

### 5.1 JSON-файлы как база данных

Хранение данных в JSON-файлах с ручной блокировкой через `os.replace()` — рабочее решение для прототипа, но имеет ограничения:

| Проблема | Влияние |
|----------|---------|
| Нет ACID-транзакций | При сбое питания данные могут быть повреждены |
| Нет конкурентного доступа | Два запроса на запись одновременно → потеря данных |
| Нет индексов | Полный скан при каждом поиске |
| Нет querying | Фильтрация только на клиенте |

**Для локального использования с одним пользователем — допустимо.** Но при росте данных или многопользовательском сценарии рекомендуется перейти на SQLite ( встроена в Python).

---

### 5.2 Dual Storage (IndexedDB + Server JSON)

Клиент использует IndexedDB (Dexie) как кэш и сервер как источник истины. Синхронизация односторонняя:
- Загрузка: `loadFromServer()` — сервер → IndexedDB (put, без удаления)
- Сохранение: `saveToServer()` — IndexedDB → сервер (перезапись файлов по областям)

**Проблема:** Если контакт удалён на сервере вручную, клиент всё равно сохранит его обратно при следующем `saveToServer()`. Нет механизма reconciliation.

---

### 5.3 SMTP-подключение в async-контексте

**Файл:** `server/services/email.py`, `server/services/batch.py`

`smtplib.SMTP` — синхронная библиотека, но используется в `async` функциях. Это блокирует event loop на время SMTP-операций, делая сервер неотзывчивым для других запросов.

**Рекомендация:** Использовать `aiosmtplib` или оборачивать в `asyncio.to_thread()`:

```python
server = await asyncio.to_thread(
    smtplib.SMTP, config["smtp_server"], config["smtp_port"], timeout=smtp_timeout
)
```

---

## 6. Положительные аспекты

| Что сделано хорошо | Где |
|--------------------|-----|
| Path traversal защита | `os.path.basename()` во всех файловых эндпоинтах |
| Атомарная запись файлов | `os.replace()` в `db.py:114` |
| Автоматические бэкапы | Перед каждой записью/удалением |
| Ротация логов | `RotatingFileHandler` с 5MB / 5 файлов |
| `.gitignore` для секретов | `config.json`, `.env`, `logs/`, `backups/` |
| HTML-экранирование | `esc()` и `escAttr()` в `utils.js` |
| Debounce сохранений | `saveToServerDebounced()` — 1 сек задержка |
| Валидация размера JSON | `max_json_size` — 10 MB лимит |
| Responsive UI | Мобильная адаптация через CSS |

---

## 7. Приоритеты исправления

### Немедленно (день 1)
1. **Удалить `db/*.json` из git-истории** — критический риск утечки ПДн.
2. **Добавить `db/` в `.gitignore`.**
3. **Ограничить CORS** до `localhost` / `127.0.0.1`.
4. **Добавить API-токен** для аутентификации.

### Краткосрочно (неделя 1)
5. Добавить rate-limiting на рассылку.
6. Исправить тесты.
7. Добавить CSP-заголовки.
8. Убрать `sender_password` из `config.json`.
9. Добавить `EmailStr` валидацию.

### Среднесрочно (месяц 1)
10. Перенести SMTP в `asyncio.to_thread()`.
11. Добавить SRI для CDN.
12. Заменить голые `except`.
13. Переписать `test_server.py` под pytest.
14. Исправить дублирование `SERVER_URL`.

---

## 8. Структура проекта

```
granite-crm/
├── index.html                    # SPA-интерфейс CRM
├── start.bat                     # Запуск сервера
├── config.example.json           # Шаблон конфигурации
├── requirements.txt              # fastapi, uvicorn, python-dotenv
├── email_template.html           # Шаблон письма для рассылки
├── test_server.py                # Устаревшие тесты
├── server/
│   ├── __init__.py               # FastAPI app, CORS, middleware
│   ├── config.py                 # Конфигурация, пути
│   ├── models.py                 # Pydantic модели
│   ├── routers/
│   │   ├── send.py               # Email рассылка
│   │   ├── db.py                 # CRUD JSON-файлов
│   │   ├── template.py           # Управление шаблоном
│   │   └── backup.py             # Бэкапы и восстановление
│   └── services/
│       ├── email.py              # SMTP-отправка
│       ├── batch.py              # Асинхронная пакетная рассылка
│       └── backup.py             # Создание/поиск бэкапов
├── js/
│   ├── utils.js                  # Утилиты, константы
│   ├── state.js                  # Состояние приложения
│   ├── db.js                     # IndexedDB + серверная синхронизация
│   ├── render.js                 # Рендеринг UI
│   ├── batch.js                  # Массовые операции
│   ├── import-export.js          # Импорт CSV/JSON, экспорт XLSX
│   ├── email-sender.js           # Модальное окно рассылки
│   └── backup-manager.js         # Управление бэкапами в UI
├── css/                          # Модульная система стилей
├── db/                           # ⚠️ Данные клиентов (должны быть в .gitignore)
│   ├── Rostov.json
│   ├── Krasnodar.json
│   ├── Saratov.json
│   ├── Stavropol.json
│   ├── Stavropol-0.json
│   └── test3.json
└── docs/
    ├── API_REFERENCE.md
    ├── BACKUP_RESTORE.md
    ├── PLAN_EMAIL_INTEGRATION.md
    └── Гайд по настройке рассылки.md
```

---

*Отчёт подготовлен автоматически. Проанализированы все файлы проекта, git-история, конфигурации и зависимости.*
