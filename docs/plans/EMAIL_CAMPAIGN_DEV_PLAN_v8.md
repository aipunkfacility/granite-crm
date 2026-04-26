# RetouchGrav — Email Campaign Dev Plan v8

> Александр · @ganjavagen · WhatsApp: +84 946 943 543  
> SMTP: ai.punk.facility@gmail.com (App Password)  
> База: ~6 000 компаний → **434 приоритетных цели**  
> v8 · 2026-04-26 · на основе v7 + финальные правки

---

## Содержание

1. [Что изменилось относительно v7](#1-что-изменилось-относительно-v7)
2. [Стратегия и волны](#2-стратегия-и-волны)
3. [Прогрев и здоровье домена](#3-прогрев-и-здоровье-домена)
4. [Шаблоны писем](#4-шаблоны-писем)
5. [Технический план](#5-технический-план)
6. [Roadmap по дням](#6-roadmap-по-дням)
7. [Переменные окружения](#7-переменные-окружения)

---

## 1. Что изменилось относительно v7

| Проблема в v7 | Решение в v8 |
|---------------|-------------|
| `time.sleep()` в BackgroundTask — работает, но блокирует тред на 45–120 сек не освобождая его для FastAPI | Оставить `time.sleep()` — это синхронная функция в threadpool, event loop не блокирует. Но добавить проверку статуса кампании прямо перед сном, а не после — иначе пауза фиксируется с опозданием на один цикл |
| `session.refresh(campaign)` на каждой итерации — 50 SELECT за сессию | Проверять статус каждые 5 писем вместо каждого — баланс между отзывчивостью и нагрузкой на SQLite |
| `paused_daily_limit` — новый статус, но не добавлен в `UpdateCampaignRequest` pattern и не документирован как разрешённый для перезапуска | Явно добавить в `CreateTaskRequest` / `UpdateCampaignRequest` pattern, в роутере — в список допустимых для `run` |
| Follow-up для тех кто **не открыл** (7 дней тишины) — упомянут в roadmap но не реализован в коде задачи 5 | Добавить отдельную функцию `_schedule_noreply_task()` — вызывается из `get_followup_queue` |
| `{city}` в теле письма — "Ищу контакты мастерских в Волгограде и области" звучит неестественно, как будто ты сам не знаешь куда пишешь | Убрать "Ищу контакты". Переформулировать: "Работаю с мастерскими в {city} и соседних городах" — звучит как уже действующий подрядчик, а не ищущий |
| Валидатор: длинное название > 80 символов исключается, но это может выкинуть нормальные компании с длинными официальными названиями | Проверять не длину названия, а наличие SEO-паттерна в нём (regex). Длина > 80 — только warning, не исключение |
| Bounce-скрипт: `imap.search` по нескольким критериям подряд накапливает UID в list, но Gmail возвращает UID в байтах — при пустом результате `uids[0]` это `b''`, а не пустой список | Исправить: проверять `if uids[0]` перед `extend` |
| SSE `/progress` — открывает новую сессию БД на каждый `asyncio.sleep(3)`, то есть потенциально 20+ сессий за минуту | Открывать сессию один раз до цикла, закрывать при выходе. Refresh кампании через `session.expire(campaign); session.refresh(campaign)` |
| Нет описания что делать с ответами — воронка после `replied` не раскрыта | Добавлена секция 2.4 «Воронка после ответа» |
| `cold_email_marquiz` — аудитория marquiz+tg_trust≥2 получает тот же шаблон что и все остальные, только с другими темами | Для marquiz-аудитории добавить короткий абзац про "вижу вы развиваете онлайн-присутствие" — это единственный сегмент где это уместно, потому что marquiz и живой TG — объективные факты, а не домыслы |
| Нет проверки что `contact` существует при генерации `unsubscribe_url` в sender — если CrmContactRow не создан, `contact.unsubscribe_token` упадёт с `AttributeError` | Guard-клауза: если `contact is None` — создать CrmContactRow на лету или использовать пустую строку |

---

## 2. Стратегия и волны

### 2.1 База

```
Всего в базе:                           ~6 000 компаний
Обработанные города:                    29 из 46
─────────────────────────────────────────────────────────
Сегмент A, не-сеть, валидный email:     175
Сегмент B, не-сеть, валидный email:     259
Приоритетная база:                      434 компании
Крупные сети (ручная работа):           8 компаний
─────────────────────────────────────────────────────────
17 городов ещё не обработаны → +100–200 контактов позже
```

### 2.2 Волны

Принцип: **одна переменная за раз**. Либо тестируем тему (фиксируем аудиторию), либо аудиторию (фиксируем тему).

| Фаза | Волна | Фильтр CRM | Размер | Шаблон | Цель |
|------|-------|-----------|--------|--------|------|
| **0** | Калибровка | `segment IN (A,B), is_network=0, email, случайные` | 50 | `cold_email_v1` тема A vs B | Найти лучшую тему |
| **1** | Marquiz | `has_marquiz=1 OR tg_trust≥2, is_network=0, A+B, email` | ~22 | `cold_email_marquiz` | Тёплая аудитория |
| **1** | Bitrix | `cms=bitrix, is_network=0, A+B, email` | ~41 | `cold_email_v1` (победитель) | — |
| **2** | Остаток A | `segment=A, is_network=0, cms NOT IN (bitrix), email` | ~112 | `cold_email_v1` (победитель) | Основной объём |
| **2** | Сегмент B | `segment=B, is_network=0, email` | ~259 | `cold_email_v1` (победитель) | Масштаб |

> **Волна Marquiz:** перед запуском — вручную просмотреть список из 22 компаний в CRM, убрать те где `name_best` явный SEO-заголовок. 10 минут работы.

> **Крупные сети (8 шт.):** писать **вручную**, отдельно от CRM-кампаний. Один email напрямую в головной офис. Цель — оптовый договор, не разовая ретушь.

### 2.3 A/B критерий победителя

Реальность выборки фазы 0: 25 писем на вариант. При open rate 20% это 5 открытий. Статистики нет — только практическая оценка.

**Критерий победителя (через 5 дней после последнего письма фазы 0):**

- Тема A: **≥ 2 ответа**, тема B: 0 → победитель A
- Тема B: **≥ 2 ответа**, тема A: 0 → победитель B  
- Обе по **1 ответу** → ничья, используем A
- **Обе по 0 ответов** → проблема не в теме. Остановиться, перечитать письмо, проверить не попали ли в спам. Волны не запускать.

### 2.4 Воронка после ответа

Это самое важное место — оба предыдущих плана здесь заканчивались. Расписываю подробно.

**Когда пришёл ответ:**

1. Перевести в CRM вручную: `email_sent / email_opened → replied`
2. Ответить в течение **2 часов** — в B2B скорость ответа критична
3. Авто-отмена follow-up задачи срабатывает через `CANCEL_FOLLOWUP_ON_STAGES` (уже в плане задачи 5.2)

**Типы ответов и что делать:**

| Ответ | Действие |
|-------|----------|
| "Интересно, расскажите подробнее" | Написать ниже (шаблон А) |
| "Пришлите примеры" | Отправить ссылку на сайт + 2–3 конкретных примера из портфолио |
| "Сколько стоит?" | Шаблон Б ниже |
| "Пришлите фото" (сразу готовы к тесту) | Обработать бесплатно, вернуть в течение дня |
| "Нет, не нужно" | Перевести в `not_interested`, не настаивать |
| Молчание после "Интересно" > 2 дней | Написать ещё раз: "Готов начать когда удобно — просто пришлите фото" |

**Шаблон ответа А — "расскажите подробнее":**
```
Конечно.

Работаю с любыми исходниками — старые, размытые, повреждённые,
низкое разрешение. Нейросети + ручная доводка под конкретный
станок (лазер или ударный — разная обработка).

Проще всего показать на вашем материале. Пришлите любое
сложное фото — сделаю бесплатно, посмотрите сами.

Александр
```

**Шаблон ответа Б — цена:**
```
Стандартный портрет — 700–1 000 ₽.
Сложный монтаж (замена фона, вырезка, склейка) — до 2 000 ₽.
Срочно (3–6 часов) — +50%.

При 10+ заказах в неделю — индивидуальные условия.
Оплата после того как примете результат.

Пришлите любое фото — покажу что получится, и тогда уже
обсудим конкретику.

Александр
```

**Переход `replied → interested`:** после того как клиент одобрил пробный результат и обсудили условия.

**Переход `interested → client`** (вне CRM-воронки): после первого оплаченного заказа. В CRM пометить в notes: "постоянный клиент с [дата]", объём заказов в неделю.

---

## 3. Прогрев и здоровье домена

### 3.1 Чеклист до первой отправки (День 1, 0 писем)

```
GMAIL
[ ] 2FA включена на ai.punk.facility@gmail.com
[ ] App Password создан: myaccount.google.com/apppasswords
    → "Другое приложение" → "granite-crm" → скопировать 16 символов
[ ] .env: SMTP_PASS=xxxx xxxx xxxx xxxx  (с пробелами или без — оба варианта работают)

ТЕСТ SMTP
[ ] python -c "from granite.email.sender import EmailSender; EmailSender().send(...)"
    → письмо пришло на свой ящик
[ ] Открыть письмо → Show original (Показать оригинал):
    SPF: PASS  ← Google управляет, не мы
    DKIM: PASS ← Google управляет, не мы
    (Если одно из них FAIL — проверить SMTP_USER в .env, он должен совпадать с From:)

ИНФРАСТРУКТУРА
[ ] Cloudflare Tunnel запущен:
    curl {BASE_URL}/health  →  {"status": "ok", "db": true}
[ ] Tracking pixel:
    curl {BASE_URL}/api/v1/track/open/test123.png  →  200, Content-Type: image/png
[ ] Unsubscribe GET (страница подтверждения, НЕ сразу отписывает):
    curl {BASE_URL}/api/v1/unsubscribe/ЛЮБОЙ_ТОКЕН  →  HTML со кнопкой
[ ] Unsubscribe POST (реальная отписка):
    curl -X POST {BASE_URL}/api/v1/unsubscribe/РЕАЛЬНЫЙ_ТОКЕН
    → HTML "Вы успешно отписаны" + в БД stop_automation=1, funnel_stage=not_interested

СКВОЗНОЙ ТЕСТ (важнее всех предыдущих вместе)
[ ] Создать тестовую кампанию: 1 получатель (свой email), шаблон cold_email_v1
[ ] Запустить → письмо пришло
[ ] Открыть письмо → в БД: funnel_stage = email_opened, crm_email_logs.status = opened
[ ] Нажать ссылку отписки → страница подтверждения → нажать кнопку
    → в БД: stop_automation = 1, funnel_stage = not_interested, crm_touches запись
[ ] Вернуть stop_automation = 0 в БД вручную (для дальнейших тестов)
```

### 3.2 График прогрева

| День | Лимит | Действие |
|------|-------|----------|
| 1 | 0 | Чеклист, инфраструктура |
| 2 | 10 | Фаза 0 старт |
| 3 | 20 | Фаза 0 |
| 4 | 20 | Фаза 0 финал |
| 5–6 | 0 | Пауза, мониторинг ответов и bounce |
| 7 | 30 | Волна 1 старт |
| 8 | 30 | |
| 9 | 50 | |
| 10+ | 50 | Рабочий режим |

### 3.3 Метрики здоровья

| Метрика | Норма | Стоп-сигнал | Где смотреть |
|---------|-------|-------------|-------------|
| Hard bounce rate | < 2% | ≥ 5% → стоп | `scripts/process_bounces.py` |
| Open rate (пиксель) | 10–25% | < 5% → Gmail в спаме? | CRM `/stats` |
| Reply rate | ≥ 1–3% | 0 за 5 дней → пересмотр письма | CRM вручную |
| Spam complaints | < 0.1% | ≥ 0.5% → стоп | Gmail Postmaster Tools |

> **Gmail Postmaster Tools** — бесплатный инструмент Google, показывает spam rate и репутацию домена. Зарегистрировать `gmail.com` нельзя (это Google-домен), но можно отслеживать репутацию по IP. Для personal Gmail достаточно следить за bounce rate вручную через process_bounces.py.

---

## 4. Шаблоны писем

### Принципы (финальные)

- Начало — с ситуации получателя, не с самопрезентации
- Нет слов: "Предлагаем", "Наша компания", "Коммерческое предложение", "Акция", "Скидка"
- `{city}` — персонализация без риска SEO-мусора
- Отписка — в конце каждого письма, plaintext ссылка
- Длина темы — до 50 символов
- Письмо умещается в экран телефона (150–200 слов)

### 4.1 `cold_email_v1` — основной

```
Имя в БД:   cold_email_v1
Канал:      email
body_type:  plain

─── ТЕМА A ───
Подготовка фото под гравировку — пришлите самый сложный случай

─── ТЕМА B ───
Ретушь под памятник: старые и плохие фото — в день заказа

─── ТЕЛО ───
Здравствуйте.

Работаю с мастерскими в {city} и соседних городах —
готовлю фотографии для гравировки на памятниках.

Берусь за сложные исходники: старые снимки, низкое разрешение,
повреждённые и замятые фото. Нейросети + ручная доводка.
Срок — 12–24 часа, срочно — 3–6 часов. От 700 ₽.
Оплата после того как примете результат.

Готов сделать 1–2 пробных бесплатно — на ваших реальных
исходниках, без обязательств.

Примеры работ: https://retouchgrav.netlify.app

Александр
@ganjavagen · wa.me/84946943543

---
Если не актуально — ответьте «нет», больше не напишу.
Отписаться: {unsubscribe_url}
```

**Изменения относительно v7:**
- "Ищу контакты мастерских" → "Работаю с мастерскими" — звучит как действующий подрядчик
- WhatsApp — ссылка `wa.me/84946943543` вместо голого номера, кликабельна в письме
- Убрана отдельная строка "ganjavagen@gmail.com" — лишнее, email виден в заголовке письма

---

### 4.2 `cold_email_marquiz` — Marquiz + tg_trust≥2

```
Имя в БД:   cold_email_marquiz
Канал:      email
body_type:  plain

─── ТЕМА A ───
Подготовка фото под гравировку — могу разгрузить вас на ретуши

─── ТЕМА B ───
Ретушь портретов для вашей мастерской — оплата после результата

─── ТЕЛО ───
Здравствуйте.

Вижу, что вы активно развиваете мастерскую в {city} —
и хочу предложить помощь с одной конкретной задачей.

Занимаюсь подготовкой портретных фото для гравировки на памятниках.
Берусь за всё что сложно: старые снимки 80-х, документные фото,
групповые — когда нужно вырезать одного человека, совсем плохое разрешение.

Нейросети + ручная доводка. 12–24 часа, срочно 3–6 часов.
От 700 ₽, оплата после результата для новых клиентов.

Начнём с бесплатной пробы: пришлите 1–2 ваших текущих исходника —
покажу результат на вашем материале.

Примеры работ: https://retouchgrav.netlify.app

Александр
@ganjavagen · wa.me/84946943543

---
Отписаться: {unsubscribe_url}
```

**Изменение относительно v7:** добавлен абзац "Вижу, что вы активно развиваете мастерскую" — это уместно **только** для этого сегмента, потому что наличие Marquiz и живого TG-канала — объективные факты, а не домыслы. Для остальных волн — не использовать.

---

### 4.3 `follow_up_email_v1` — follow-up через 7 дней

```
Имя в БД:   follow_up_email_v1
Канал:      email
body_type:  plain

─── ТЕМА ───
Re: подготовка фото под гравировку

─── ТЕЛО ───
Добрый день.

Писал на прошлой неделе про ретушь портретов для гравировки.

Оставлю ссылку на примеры — на случай если появится
сложный исходник: https://retouchgrav.netlify.app

Первый портрет бесплатно. Пришлите в ответ.

Александр · @ganjavagen

---
Отписаться: {unsubscribe_url}
```

Короче v7-версии — намеренно. Человек уже видел длинное письмо.

---

### 4.4 Заносить шаблоны в CRM

Через UI `/templates` или через API:

```bash
# Пример через curl (если API_KEY не задан — без заголовка)
curl -X POST http://localhost:8000/api/v1/templates \
  -H "Content-Type: application/json" \
  -d '{
    "name": "cold_email_v1",
    "channel": "email",
    "body_type": "plain",
    "subject": "Подготовка фото под гравировку — пришлите самый сложный случай",
    "body": "...",
    "description": "Основной холодный шаблон, Фаза 0 и Волны 2-4"
  }'
```

> `subject` в шаблоне — это тема по умолчанию. При создании кампании можно переопределить через `subject_a` / `subject_b`. Для A/B: `subject` в шаблоне = запасной вариант если `subject_a` не задан.

---

## 5. Технический план

### Что уже реализовано (не трогать)

| Компонент | Файл | Статус |
|-----------|------|--------|
| `subject_a` / `subject_b` в ORM + миграция | `granite/database.py` | ✅ |
| `CrmTemplateRow.render()` + `render_subject()` | `granite/database.py` | ✅ |
| Python `threading.Lock()` + атомарный UPDATE | `granite/api/campaigns.py` | ✅ |
| Tracking pixel + bot-фильтрация | `granite/api/tracking.py` | ✅ |
| SMTP retry на temporary errors | `granite/email/sender.py` | ✅ |
| `POST /campaigns/stale` watchdog | `granite/api/campaigns.py` | ✅ |
| `lifespan()` в app.py | `granite/api/app.py` | ✅ (в него добавить recovery) |

### Порядок реализации

```
Задача 1  →  Задача 2  →  Задача 3  →  Задача 4  →  Задача 5  →  Задача 6  →  Задача 7
Unsubscribe  Recovery    BackgroundTask  Валидатор   Follow-up   Bounce      Фронтенд
             + статус    + SSE           (validator)  задачи     (скрипт)    (минимум)
```

---

### Задача 1: Unsubscribe

**Зачем:** `{unsubscribe_url}` есть в шаблонах, но эндпоинта и токена в БД нет.

#### 1.1 Миграция

```python
# uv run cli.py db migrate "add_unsubscribe_token_to_contacts"
# Файл: alembic/versions/XXXX_add_unsubscribe_token_to_contacts.py

def upgrade() -> None:
    op.add_column(
        "crm_contacts",
        sa.Column("unsubscribe_token", sa.String(), nullable=True),
    )
    # Заполнить токены для существующих записей
    op.execute(
        "UPDATE crm_contacts SET unsubscribe_token = lower(hex(randomblob(16))) "
        "WHERE unsubscribe_token IS NULL"
    )
    op.alter_column("crm_contacts", "unsubscribe_token", nullable=False)
    op.create_index(
        "ix_crm_contacts_unsubscribe_token",
        "crm_contacts",
        ["unsubscribe_token"],
        unique=True,
    )

def downgrade() -> None:
    op.drop_index("ix_crm_contacts_unsubscribe_token", table_name="crm_contacts")
    op.drop_column("crm_contacts", "unsubscribe_token")
```

```bash
uv run cli.py db upgrade head
```

#### 1.2 ORM — CrmContactRow

```python
# granite/database.py — добавить в CrmContactRow:
import secrets

class CrmContactRow(Base):
    # ... существующие поля ...
    unsubscribe_token: Mapped[str] = mapped_column(
        String,
        nullable=False,
        default=lambda: secrets.token_hex(16),
        unique=True,
        index=True,
    )
```

#### 1.3 Эндпоинт

Создать файл `granite/api/unsubscribe.py`:

```python
"""
Эндпоинты отписки от рассылки.

GET  /api/v1/unsubscribe/{token}  — страница подтверждения (НЕ отписывает)
POST /api/v1/unsubscribe/{token}  — собственно отписка

GET не отписывает сразу — защита от почтовых клиентов (Outlook, Mail.ru),
которые префетчат все ссылки в письме при доставке.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from granite.api.deps import get_db
from granite.database import CrmContactRow, CrmTouchRow

router = APIRouter(tags=["unsubscribe"])

_PAGE = """<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>RetouchGrav</title>
  <style>
    body {{ font-family: sans-serif; max-width: 480px; margin: 80px auto;
            text-align: center; padding: 0 20px; color: #333; }}
    h2   {{ font-weight: 600; margin-bottom: 12px; }}
    p    {{ color: #666; margin-bottom: 24px; }}
    button {{ padding: 12px 28px; font-size: 15px; cursor: pointer;
              background: #e11d48; color: #fff; border: none;
              border-radius: 6px; }}
    button:hover {{ background: #be123c; }}
    a    {{ color: #999; font-size: 13px; }}
  </style>
</head>
<body>
  <h2>RetouchGrav</h2>
  <p>{msg}</p>
  {action}
  <br><br>
  <a href="https://retouchgrav.netlify.app">retouchgrav.netlify.app</a>
</body>
</html>"""


def _page(msg: str, action: str = "") -> HTMLResponse:
    return HTMLResponse(_PAGE.format(msg=msg, action=action))


@router.get("/unsubscribe/{token}", response_class=HTMLResponse)
def unsubscribe_page(token: str, db: Session = Depends(get_db)):
    """Страница подтверждения отписки. GET не отписывает."""
    contact = db.query(CrmContactRow).filter_by(unsubscribe_token=token).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Ссылка недействительна")

    if contact.stop_automation:
        return _page("Вы уже отписаны. Писем больше не будет.")

    return _page(
        msg="Подтвердите, что хотите отписаться от рассылки RetouchGrav.",
        action=f'<form method="POST" action="/api/v1/unsubscribe/{token}">'
               f'<button type="submit">Отписаться</button></form>',
    )


@router.post("/unsubscribe/{token}", response_class=HTMLResponse)
def unsubscribe_confirm(token: str, db: Session = Depends(get_db)):
    """Собственно отписка — только POST."""
    contact = db.query(CrmContactRow).filter_by(unsubscribe_token=token).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Ссылка недействительна")

    if contact.stop_automation:
        return _page("Вы уже отписаны.")

    contact.stop_automation = True
    contact.funnel_stage = "not_interested"
    contact.updated_at = datetime.now(timezone.utc)

    db.add(CrmTouchRow(
        company_id=contact.company_id,
        channel="email",
        direction="incoming",
        subject="Отписка",
        note="unsubscribe_link",
    ))
    db.commit()

    return _page("Вы успешно отписаны. Больше писем не будет.")
```

#### 1.4 Регистрация роутера в app.py

```python
# granite/api/app.py
from granite.api import unsubscribe as unsubscribe_router

app.include_router(
    unsubscribe_router.router,
    prefix="/api/v1",
)
```

#### 1.5 Auth bypass в middleware

В `api_key_auth_middleware` — добавить отписку в список публичных путей (рядом с `/track/`):

```python
# granite/api/app.py — в функции api_key_auth_middleware:
if (
    not request.url.path.startswith("/api/v1/")
    or request.url.path.startswith("/api/v1/track/")
    or request.url.path.startswith("/api/v1/unsubscribe/")  # ← добавить
    or request.method == "OPTIONS"
):
    return await call_next(request)
```

#### 1.6 Плейсхолдер `{unsubscribe_url}` в sender.py

```python
# granite/email/sender.py — в методе send(), перед render шаблона:

BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")

# Получить contact для unsubscribe_token
# contact может быть None если CrmContactRow не создан — guard-клауза:
if contact is not None and hasattr(contact, "unsubscribe_token"):
    unsubscribe_url = f"{BASE_URL}/api/v1/unsubscribe/{contact.unsubscribe_token}"
else:
    # Если нет токена — ссылка отписки ведёт на сайт (не идеально, но не падает)
    unsubscribe_url = f"{BASE_URL}/api/v1/unsubscribe/invalid"

render_kwargs["unsubscribe_url"] = unsubscribe_url
```

> `CrmTemplateRow.render()` делает `str.replace` — безопасно, XSS через этот плейсхолдер невозможен.

---

### Задача 2: Recovery + статус `paused_daily_limit`

#### 2.1 Recovery при старте в lifespan()

```python
# granite/api/app.py — в существующем lifespan():

@asynccontextmanager
async def lifespan(app: FastAPI):
    # ... существующий код инициализации ...

    # Recovery: кампании в статусе "running" при рестарте → "paused"
    # Они могли зависнуть если сервер упал в процессе отправки
    with db.session_scope() as session:
        stuck = (
            session.query(CrmEmailCampaignRow)
            .filter_by(status="running")
            .all()
        )
        for c in stuck:
            c.status = "paused"
            logger.warning(
                f"RECOVERY: кампания #{c.id} '{c.name}' "
                f"running → paused (рестарт сервера)"
            )
        if stuck:
            logger.info(f"RECOVERY: восстановлено {len(stuck)} кампаний")

    yield
    # ... существующий код очистки ...
```

#### 2.2 Статус `paused_daily_limit` — добавить в схемы и роутер

В `granite/api/schemas.py` найти pattern для статуса кампании и добавить:

```python
# Если есть UpdateCampaignRequest с pattern на status:
status: str = Field(
    pattern="^(draft|running|paused|paused_daily_limit|completed|error)$"
)
```

В `granite/api/campaigns.py` в роутере запуска — разрешить перезапуск из `paused_daily_limit`:

```python
# В функции run_campaign — проверка перед запуском:
RUNNABLE_STATUSES = {"draft", "paused", "paused_daily_limit"}

if campaign.status not in RUNNABLE_STATUSES:
    raise HTTPException(
        400,
        f"Кампания не может быть запущена из статуса '{campaign.status}'"
    )
```

---

### Задача 3: BackgroundTask + SSE-поллинг + оптимизация

#### 3.1 Новый endpoint запуска

Заменяет или рефакторит существующий `POST /campaigns/{id}/run`:

```python
# granite/api/campaigns.py

@router.post("/{campaign_id}/run")
async def run_campaign(
    campaign_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Запустить кампанию.
    - Проверяет что нет другой running-кампании
    - Атомарно меняет статус на running
    - Отправку запускает как BackgroundTask (в threadpool)
    - Прогресс клиент читает через GET /campaigns/{id}/progress (SSE)
    """
    # Проверить нет ли уже запущенной
    running = db.query(CrmEmailCampaignRow).filter_by(status="running").first()
    if running and running.id != campaign_id:
        raise HTTPException(
            409,
            f"Уже запущена кампания #{running.id} '{running.name}'. "
            f"Дождитесь завершения или поставьте на паузу."
        )

    # Атомарная смена статуса — защита от двойного клика
    result = db.execute(
        sa_text(
            "UPDATE crm_email_campaigns "
            "SET status='running', started_at=COALESCE(started_at, :now), updated_at=:now "
            "WHERE id=:id AND status NOT IN ('running', 'completed')"
        ),
        {"id": campaign_id, "now": datetime.now(timezone.utc)},
    )
    db.commit()

    if result.rowcount == 0:
        raise HTTPException(
            400,
            "Кампания не может быть запущена (уже running или completed)"
        )

    # Запустить фоновую задачу — FastAPI сам отправит в threadpool
    background_tasks.add_task(_send_campaign, campaign_id)
    return {"ok": True, "campaign_id": campaign_id, "status": "running"}
```

#### 3.2 Фоновая задача отправки

```python
# granite/api/campaigns.py

def _send_campaign(campaign_id: int) -> None:
    """
    Синхронная фоновая задача отправки писем.
    Запускается FastAPI в threadpool через BackgroundTasks.
    time.sleep() здесь безопасен — не блокирует event loop.
    """
    import time
    import random
    from granite.database import Database
    from granite.email.sender import EmailSender
    from granite.email.validator import validate_recipients

    EMAIL_DELAY_MIN   = int(os.getenv("EMAIL_DELAY_MIN", "45"))
    EMAIL_DELAY_MAX   = int(os.getenv("EMAIL_DELAY_MAX", "120"))
    EMAIL_DAILY_LIMIT = int(os.getenv("EMAIL_DAILY_LIMIT", "50"))
    FROM_NAME         = os.getenv("FROM_NAME", "Александр")
    BASE_URL          = os.getenv("BASE_URL", "http://localhost:8000")

    db = Database()
    session = db.get_session()
    sender = EmailSender()

    try:
        campaign = session.get(CrmEmailCampaignRow, campaign_id)
        if not campaign or campaign.status != "running":
            return

        template = (
            session.query(CrmTemplateRow)
            .filter_by(name=campaign.template_name)
            .first()
        )
        if not template:
            campaign.status = "error"
            session.commit()
            logger.error(f"Кампания {campaign_id}: шаблон '{campaign.template_name}' не найден")
            return

        # Получить и провалидировать получателей
        recipients_raw = _get_campaign_recipients(campaign, session)
        valid_recipients, warnings = validate_recipients(recipients_raw)

        if warnings:
            logger.warning(
                f"Кампания {campaign_id}: пропущено {len(warnings)} получателей: "
                + "; ".join(w["reason"] for w in warnings[:5])
            )

        sent = campaign.total_sent or 0
        errors = campaign.total_errors or 0

        for i, (company, enriched, contact, email_to) in enumerate(valid_recipients):

            # ── Проверка статуса (каждые 5 писем, не каждое) ──
            if i % 5 == 0:
                session.expire(campaign)
                session.refresh(campaign)
                if campaign.status != "running":
                    logger.info(
                        f"Кампания {campaign_id}: статус '{campaign.status}' → выход"
                    )
                    return

            # ── Глобальный дневной лимит ──
            last_24h = datetime.now(timezone.utc) - timedelta(hours=24)
            sent_today = (
                session.query(func.count(CrmEmailLogRow.id))
                .filter(CrmEmailLogRow.sent_at >= last_24h)
                .scalar()
                or 0
            )
            if sent_today >= EMAIL_DAILY_LIMIT:
                campaign.status = "paused_daily_limit"
                campaign.updated_at = datetime.now(timezone.utc)
                session.commit()
                logger.info(
                    f"Кампания {campaign_id}: дневной лимит {EMAIL_DAILY_LIMIT} достигнут"
                )
                return

            # ── Рендер шаблона ──
            city = (company.city or "").strip()
            unsubscribe_url = (
                f"{BASE_URL}/api/v1/unsubscribe/{contact.unsubscribe_token}"
                if contact and hasattr(contact, "unsubscribe_token")
                else ""
            )
            render_kwargs = {
                "from_name":       FROM_NAME,
                "city":            city,
                "company_name":    (company.name_best or "").strip(),
                "website":         company.website or "",
                "unsubscribe_url": unsubscribe_url,
            }

            # ── A/B тема ──
            subject = _get_ab_subject(
                company_id=company.id,
                subject_a=campaign.subject_a,
                subject_b=campaign.subject_b,
                template=template,
                render_kwargs=render_kwargs,
            )

            rendered_body = template.render(**render_kwargs)

            # ── Отправка ──
            try:
                tracking_id = sender.send(
                    company_id=company.id,
                    email_to=email_to,
                    subject=subject,
                    body_text=rendered_body,
                    template_name=template.name,
                    db_session=session,
                    campaign_id=campaign.id,
                )

                if tracking_id:
                    sent += 1
                    campaign.total_sent = sent

                    # Воронка
                    if contact:
                        from granite.api.stage_transitions import apply_outgoing_touch
                        apply_outgoing_touch(contact, "email")

                    # Touch log
                    session.add(CrmTouchRow(
                        company_id=company.id,
                        channel="email",
                        direction="outgoing",
                        subject=subject,
                        body=f"[campaign_id={campaign.id}, tracking_id={tracking_id}]",
                    ))

                    # Сохранять прогресс каждые 10 писем
                    if sent % 10 == 0:
                        campaign.updated_at = datetime.now(timezone.utc)
                        session.commit()

                else:
                    errors += 1
                    campaign.total_errors = errors

            except Exception as e:
                errors += 1
                campaign.total_errors = errors
                logger.error(
                    f"Кампания {campaign_id}: ошибка отправки "
                    f"company_id={company.id} email={email_to}: {e}"
                )

            # ── Задержка перед следующим письмом ──
            delay = random.randint(EMAIL_DELAY_MIN, EMAIL_DELAY_MAX)
            time.sleep(delay)

        # ── Кампания завершена ──
        campaign.status = "completed"
        campaign.completed_at = datetime.now(timezone.utc)
        campaign.updated_at = datetime.now(timezone.utc)
        session.commit()
        logger.info(f"Кампания {campaign_id}: завершена. Отправлено: {sent}, ошибок: {errors}")

    except Exception as e:
        logger.exception(f"Кампания {campaign_id}: критическая ошибка: {e}")
        try:
            campaign = session.get(CrmEmailCampaignRow, campaign_id)
            if campaign:
                campaign.status = "error"
                session.commit()
        except Exception:
            pass
    finally:
        session.close()
        db.engine.dispose()
```

#### 3.3 A/B распределение

```python
# granite/api/campaigns.py

def _get_ab_subject(
    company_id: int,
    subject_a: str | None,
    subject_b: str | None,
    template,
    render_kwargs: dict,
) -> str:
    """
    Детерминированное A/B распределение через MD5 company_id.
    Если subject_b не задан — используем subject_a или тему шаблона.
    MD5 даёт стабильное распределение: одна компания всегда в одном варианте,
    даже если кампанию перезапускают.
    """
    import hashlib

    # Тема A — из кампании или из шаблона
    a = subject_a or template.render_subject(**render_kwargs)

    if not subject_b:
        return a

    # Детерминированный выбор A/B
    h = int(hashlib.md5(str(company_id).encode()).hexdigest(), 16)
    return a if h % 2 == 0 else subject_b
```

#### 3.4 SSE-поллинг прогресса

```python
# granite/api/campaigns.py

@router.get("/{campaign_id}/progress")
async def campaign_progress(campaign_id: int, db: Session = Depends(get_db)):
    """
    SSE: состояние кампании из БД каждые 3 секунды.
    Отдельно от отправки — закрытие вкладки не останавливает рассылку.
    Открывает одну сессию на всё время соединения.
    """
    async def generate():
        # Одна сессия на весь стрим
        stream_session = db
        campaign = stream_session.get(CrmEmailCampaignRow, campaign_id)

        if not campaign:
            yield f"data: {json.dumps({'error': 'not_found'})}\n\n"
            return

        TERMINAL = {"completed", "error", "paused", "paused_daily_limit"}

        while True:
            # Обновить из БД без пересоздания сессии
            stream_session.expire(campaign)
            stream_session.refresh(campaign)

            payload = {
                "status":  campaign.status,
                "sent":    campaign.total_sent   or 0,
                "errors":  campaign.total_errors or 0,
                "opened":  campaign.total_opened or 0,
                "replied": campaign.total_replied or 0,
            }
            yield f"data: {json.dumps(payload)}\n\n"

            if campaign.status in TERMINAL:
                return

            await asyncio.sleep(3)

    return StreamingResponse(generate(), media_type="text/event-stream")
```

---

### Задача 4: Валидатор получателей

Создать файл `granite/email/validator.py`:

```python
"""
Валидация получателей перед отправкой кампании.
Возвращает (valid_list, warnings_list).
"""
import re

# Домены агрегаторов — не реальные мастерские
_AGGREGATOR_DOMAINS: frozenset[str] = frozenset({
    "memorial.ru", "vsepamyatniki.ru", "obeliski.ru",
    "mipomnim.ru", "uznm.ru", "monuments.su",
    "tsargranit.ru", "alshei.ru", "danila-master.ru",
})

# Минимальная проверка формата email
_EMAIL_RE = re.compile(r"^[\w._%+\-]+@[\w.\-]+\.\w{2,}$")

# SEO-паттерны в названии — исключаем, а не просто предупреждаем
_SEO_NAME_RE = re.compile(
    r"(?:памятник|надгробие|гравировк|изготовлен|ритуальн|гранит)",
    re.IGNORECASE,
)


def validate_recipients(
    recipients: list[tuple],
) -> tuple[list[tuple], list[dict]]:
    """
    Принимает список (company, enriched, contact, email_to).
    Возвращает (valid, warnings).
    warnings — список dict с ключами: company_id, name, reason.
    """
    valid: list[tuple] = []
    warnings: list[dict] = []
    seen_emails: set[str] = set()

    for company, enriched, contact, email_to in recipients:
        reason = _check(company, contact, email_to, seen_emails)
        if reason:
            warnings.append({
                "company_id": company.id,
                "name":       company.name_best or "",
                "reason":     reason,
            })
        else:
            seen_emails.add(email_to.lower())
            valid.append((company, enriched, contact, email_to))

    return valid, warnings


def _check(company, contact, email_to: str, seen: set[str]) -> str | None:
    """None = получатель валиден. Строка = причина исключения."""

    # Нет email
    if not email_to:
        return "нет email"

    email_lower = email_to.lower().strip()

    # Формат email
    if not _EMAIL_RE.match(email_lower):
        return f"невалидный формат email: {email_to}"

    # Дубль в этой кампании
    if email_lower in seen:
        return "дубль email"

    # Домен агрегатора
    domain = email_lower.split("@")[-1]
    if domain in _AGGREGATOR_DOMAINS:
        return f"агрегатор ({domain})"

    # Зарубежный домен (не российские мастерские)
    if domain.endswith(".by") or domain.endswith(".kz"):
        return f"зарубежный домен ({domain})"

    # stop_automation — вручную остановлено
    if contact and contact.stop_automation:
        return "отписан или stop_automation"

    # Пустое название
    name = (company.name_best or "").strip()
    if not name:
        return "пустое название компании"

    # SEO-заголовок в названии (исключаем, не просто предупреждаем)
    # Примеры: "Изготовление памятников Краснодар", "Гранитные надгробия недорого"
    if _SEO_NAME_RE.search(name) and len(name) > 20:
        return f"SEO-название ({name[:40]})"

    return None  # всё ок
```

> Изменение относительно v7: длина > 80 символов больше не является причиной исключения сама по себе. Исключаем по SEO-паттерну в названии. Нормальное ООО может иметь длинное официальное название.

---

### Задача 5: Follow-up задачи

#### 5.1 При открытии письма — задача через 7 дней

Добавить в `granite/api/tracking.py` после обновления `funnel_stage → email_opened`:

```python
# granite/api/tracking.py

def _maybe_create_followup_task(company_id: int, db: Session) -> None:
    """
    Создать follow-up задачу через 7 дней если её ещё нет.
    Вызывается при фиксации открытия письма.
    Задача: отправить follow_up_email_v1 если не ответили.
    """
    from granite.database import CrmTaskRow, CrmContactRow

    contact = db.get(CrmContactRow, company_id)
    if not contact:
        return

    # Уже ответили — задача не нужна
    DONE_STAGES = {"replied", "interested", "not_interested", "unreachable"}
    if contact.funnel_stage in DONE_STAGES:
        return

    # Уже есть активная follow-up задача
    existing = (
        db.query(CrmTaskRow)
        .filter(
            CrmTaskRow.company_id == company_id,
            CrmTaskRow.task_type == "follow_up",
            CrmTaskRow.status == "pending",
        )
        .first()
    )
    if existing:
        return

    db.add(CrmTaskRow(
        company_id=company_id,
        title="Follow-up: открыл письмо, не ответил",
        task_type="follow_up",
        priority="normal",
        status="pending",
        due_date=datetime.now(timezone.utc) + timedelta(days=7),
        description=(
            "Компания открыла письмо 7+ дней назад и не ответила.\n"
            "Отправить шаблон follow_up_email_v1 через CRM вручную."
        ),
    ))
    db.flush()
    logger.info(f"company_id={company_id}: создана follow-up задача (открытие письма)")
```

#### 5.2 Для тех кто НЕ открыл — задача check_response через 7 дней

Это пробел v7, который здесь закрывается. Добавить в `granite/api/followup.py` в логику формирования очереди:

```python
# granite/api/followup.py

def _maybe_create_check_response_task(
    company_id: int,
    last_sent_at: datetime,
    db: Session,
) -> None:
    """
    Создать задачу check_response если:
    - email отправлен > 7 дней назад
    - письмо не открыто
    - нет активной задачи
    Вызывается при формировании follow-up очереди.
    """
    from granite.database import CrmTaskRow

    days_since = (datetime.now(timezone.utc) - last_sent_at).days
    if days_since < 7:
        return

    existing = (
        db.query(CrmTaskRow)
        .filter(
            CrmTaskRow.company_id == company_id,
            CrmTaskRow.task_type.in_(["follow_up", "check_response"]),
            CrmTaskRow.status == "pending",
        )
        .first()
    )
    if existing:
        return

    db.add(CrmTaskRow(
        company_id=company_id,
        title="Check: не открыл письмо (7+ дней)",
        task_type="check_response",
        priority="low",
        status="pending",
        description=(
            "Письмо не открыто 7+ дней. "
            "Проверить корректность email, возможно адрес не рабочий. "
            "Отправить follow_up_email_v1 или пометить как unreachable."
        ),
    ))
    db.flush()
```

#### 5.3 Авто-отмена follow-up при ответе

Добавить в `granite/api/stage_transitions.py`:

```python
# granite/api/stage_transitions.py

CANCEL_FOLLOWUP_ON_STAGES = frozenset({
    "replied", "interested", "not_interested", "unreachable"
})

def _cancel_pending_followup(company_id: int, new_stage: str, db: Session) -> None:
    """Отменить pending follow-up задачи если компания перешла в финальную стадию."""
    if new_stage not in CANCEL_FOLLOWUP_ON_STAGES:
        return

    from granite.database import CrmTaskRow

    cancelled = (
        db.query(CrmTaskRow)
        .filter(
            CrmTaskRow.company_id == company_id,
            CrmTaskRow.status == "pending",
            CrmTaskRow.task_type.in_(["follow_up", "check_response"]),
        )
        .update({
            "status": "cancelled",
            "completed_at": datetime.now(timezone.utc),
        })
    )
    if cancelled:
        logger.info(
            f"company_id={company_id}: отменено {cancelled} задач follow-up "
            f"(переход → {new_stage})"
        )

# Вызывать _cancel_pending_followup() в apply_incoming_touch() после установки нового stage
```

---

### Задача 6: Bounce-парсинг

Создать файл `scripts/process_bounces.py`:

```python
"""
Читает IMAP Gmail, ищет bounce-уведомления (hard bounce),
помечает компании как unreachable.

Запуск вручную: uv run python -m scripts.process_bounces
Рекомендуется: каждые 2–3 дня после активных рассылок.
"""
import email
import imaplib
import os
import re
from datetime import datetime, timezone

from loguru import logger

IMAP_HOST = os.getenv("IMAP_HOST", "imap.gmail.com")
IMAP_USER = os.getenv("SMTP_USER")   # тот же аккаунт что и для отправки
IMAP_PASS = os.getenv("SMTP_PASS")   # тот же App Password

# SMTP-коды hard bounce — regex с границами слов,
# чтобы "550" не совпадало с IP-адресами вида "1.2.550.4"
_HARD_CODES_RE = re.compile(r"\b(550|551|552|553|554)\b")

_HARD_PHRASES = [
    "user unknown",
    "no such user",
    "mailbox not found",
    "address rejected",
    "recipient invalid",
    "recipient not found",
    "no such recipient",
    "does not exist",
    "invalid address",
    "account does not exist",
]

# Критерии поиска bounce-писем в Gmail
_SEARCH_CRITERIA = [
    '(FROM "MAILER-DAEMON" UNSEEN)',
    '(FROM "mailer-daemon@googlemail.com" UNSEEN)',
    '(SUBJECT "Delivery Status Notification" UNSEEN)',
    '(SUBJECT "Undelivered Mail Returned" UNSEEN)',
    '(SUBJECT "Mail delivery failed" UNSEEN)',
]


def process_bounces() -> int:
    if not IMAP_USER or not IMAP_PASS:
        logger.error("SMTP_USER или SMTP_PASS не заданы в .env")
        return 0

    from granite.database import Database, CrmEmailLogRow, CrmContactRow

    db = Database()
    processed = 0

    try:
        with imaplib.IMAP4_SSL(IMAP_HOST) as imap:
            imap.login(IMAP_USER, IMAP_PASS)
            imap.select("INBOX")

            # Собрать UID bounce-писем по всем критериям
            seen_uids: set[bytes] = set()
            uid_list: list[bytes] = []

            for criteria in _SEARCH_CRITERIA:
                _, uids = imap.search(None, criteria)
                if uids[0]:  # проверка на пустой b'' ← исправлен баг v7
                    for uid in uids[0].split():
                        if uid not in seen_uids:
                            seen_uids.add(uid)
                            uid_list.append(uid)

            logger.info(f"Bounce: найдено {len(uid_list)} непрочитанных уведомлений")

            for uid in uid_list:
                _, data = imap.fetch(uid, "(RFC822)")
                if not data or not data[0]:
                    continue

                msg = email.message_from_bytes(data[0][1])

                bounce_email = _extract_bounced_email(msg)
                if not bounce_email:
                    imap.store(uid, "+FLAGS", "\\Seen")
                    continue

                if not _is_hard_bounce(msg):
                    # Soft bounce — помечаем как прочитанное, не обрабатываем
                    imap.store(uid, "+FLAGS", "\\Seen")
                    continue

                # Обновить БД
                with db.session_scope() as session:
                    log = (
                        session.query(CrmEmailLogRow)
                        .filter_by(email_to=bounce_email)
                        .order_by(CrmEmailLogRow.sent_at.desc())
                        .first()
                    )
                    if log and log.status != "bounced":
                        log.status = "bounced"
                        log.bounced_at = datetime.now(timezone.utc)

                        contact = (
                            session.query(CrmContactRow)
                            .filter_by(company_id=log.company_id)
                            .first()
                        )
                        if contact:
                            contact.funnel_stage = "unreachable"
                            contact.stop_automation = True
                            contact.updated_at = datetime.now(timezone.utc)

                        processed += 1
                        logger.info(
                            f"Bounce: {bounce_email} → company #{log.company_id} unreachable"
                        )

                imap.store(uid, "+FLAGS", "\\Seen")

    except imaplib.IMAP4.error as e:
        logger.error(f"IMAP ошибка: {e}")

    db.engine.dispose()
    logger.info(f"Bounce-обработка завершена. Помечено: {processed}")
    return processed


def _extract_bounced_email(msg) -> str | None:
    """Извлечь email адрес получателя из bounce-уведомления."""
    for part in msg.walk():
        if part.get_content_type() in ("message/delivery-status", "text/plain"):
            content = part.get_payload(decode=True)
            if content:
                text = content.decode("utf-8", errors="ignore")
                match = re.search(
                    r"Final-Recipient:.*?<?([\w._%+\-]+@[\w.\-]+\.\w{2,})>?",
                    text,
                    re.IGNORECASE,
                )
                if match:
                    return match.group(1).lower()
    return None


def _is_hard_bounce(msg) -> bool:
    """True если это hard bounce (постоянная ошибка доставки)."""
    text = msg.as_string().lower()
    if _HARD_CODES_RE.search(text):
        return True
    return any(phrase in text for phrase in _HARD_PHRASES)


if __name__ == "__main__":
    process_bounces()
```

---

### Задача 7: Фронтенд — минимальные изменения

Существующий UI кампаний работает. Добавить три вещи:

#### 7.1 Поле `subject_b` в форме создания кампании

В существующий диалог создания — добавить под `subject_a`:

```tsx
// granite-web/src/components/campaigns/CampaignFormDialog.tsx

<FormField name="subject_a" label="Тема письма" required />

<Collapsible>
  <CollapsibleTrigger asChild>
    <Button variant="ghost" size="sm" className="text-muted-foreground">
      + Добавить вариант B для A/B теста
    </Button>
  </CollapsibleTrigger>
  <CollapsibleContent className="space-y-2 mt-2">
    <FormField name="subject_b" label="Тема B" />
    <p className="text-xs text-muted-foreground">
      Компании делятся 50/50 по ID. Победитель — по количеству ответов за 5 дней.
    </p>
  </CollapsibleContent>
</Collapsible>
```

#### 7.2 Причина паузы в карточке кампании

```tsx
// granite-web/src/components/campaigns/CampaignCard.tsx

{campaign.status === "paused_daily_limit" && (
  <Alert variant="warning" className="mt-3">
    <AlertDescription>
      Достигнут дневной лимит отправки. Продолжите завтра — нажмите «Запустить».
    </AlertDescription>
  </Alert>
)}

{campaign.status === "error" && (
  <Alert variant="destructive" className="mt-3">
    <AlertDescription>
      Ошибка кампании. Проверьте логи сервера.
    </AlertDescription>
  </Alert>
)}
```

#### 7.3 Recovery-баннер при загрузке списка кампаний

```tsx
// granite-web/src/app/campaigns/page.tsx

const recoveredCampaigns = campaigns.filter(
  c => c.status === "paused" && c.was_recovered  // поле из API если добавить
);

// Или проще — показывать все paused кампании у которых started_at != null:
const stuckCampaigns = campaigns.filter(
  c => c.status === "paused" && c.started_at
);

{stuckCampaigns.length > 0 && (
  <Alert variant="warning" className="mb-4">
    <AlertTitle>Кампании восстановлены после рестарта сервера</AlertTitle>
    <AlertDescription>
      {stuckCampaigns.map(c => c.name).join(", ")} — статус изменён на «пауза».
      Запустите вручную когда готовы.
    </AlertDescription>
  </Alert>
)}
```

---

## 6. Roadmap по дням

### День 1 — Инфраструктура и разработка (0 писем)

```
УТРО — окружение
[ ] Gmail 2FA + App Password → .env SMTP_PASS
[ ] Cloudflare Tunnel запущен → .env BASE_URL
[ ] curl {BASE_URL}/health → ok

ДЕНЬ — разработка (по порядку, каждый пункт завершить до следующего)
[ ] Задача 1.1–1.2: миграция + ORM unsubscribe_token
    uv run cli.py db upgrade head
    python -c "from granite.database import CrmContactRow; print('ok')"

[ ] Задача 1.3–1.5: файл unsubscribe.py + регистрация роутера + auth bypass

[ ] Задача 1.6: плейсхолдер unsubscribe_url в sender.py

[ ] Задача 2.1: recovery в lifespan()

[ ] Задача 2.2: paused_daily_limit в схемах и роутере

ВЕЧЕР — первый сквозной тест
[ ] Создать тестовую кампанию (1 получатель = свой email)
[ ] Запустить → письмо пришло ✓
[ ] Открыть → tracking сработал, funnel_stage = email_opened ✓
[ ] Кликнуть отписку → страница подтверждения ✓
[ ] POST отписки → stop_automation=1, funnel_stage=not_interested ✓
[ ] Вернуть stop_automation=0 вручную
```

### День 2 — Доработки + Фаза 0 старт (10 писем)

```
УТРО — разработка
[ ] Задача 3: BackgroundTask + SSE + A/B функция
    - Новый POST /campaigns/{id}/run (заменяет старый)
    - GET /campaigns/{id}/progress (SSE из БД)
    - _get_ab_subject()
    - _send_campaign() (фоновая задача)

[ ] Задача 4: granite/email/validator.py

[ ] Задача 3.1 миграция: total_errors в crm_email_campaigns
    uv run cli.py db migrate "add_total_errors_to_campaigns"
    uv run cli.py db upgrade head

ДЕНЬ — шаблоны
[ ] Добавить шаблоны в CRM через UI /templates:
    - cold_email_v1 (plain, тема A как subject)
    - cold_email_marquiz (plain)
    - follow_up_email_v1 (plain)

ВЕЧЕР — Фаза 0, первые 10 писем
[ ] Создать кампанию: сегмент A, is_network=0, 10 получателей
    subject_a = "Подготовка фото под гравировку — пришлите самый сложный случай"
    subject_b = "Ретушь под памятник: старые и плохие фото — в день заказа"
[ ] Запустить → проверить логи → проверить SSE прогресс в UI
[ ] Следить за отправкой первых 3–5 писем
```

### День 3–4 — Фаза 0 продолжение + follow-up + bounce

```
УТРО День 3
[ ] Задача 5.1: _maybe_create_followup_task() в tracking.py
[ ] Задача 5.2: _maybe_create_check_response_task() в followup.py
[ ] Задача 5.3: _cancel_pending_followup() в stage_transitions.py
[ ] Задача 6: scripts/process_bounces.py

ДЕНЬ День 3
[ ] Кампания: ещё 20 писем (сегмент A, следующие 20)
[ ] Мониторить логи, проверить bounce rate

ДЕНЬ День 4
[ ] Ещё 20 писем (итого Фаза 0: 50 писем за 3 дня)
[ ] Запустить process_bounces.py → проверить результат
```

### День 5–6 — Пауза и анализ (0 писем)

```
[ ] Посчитать: сколько ответов по теме A, сколько по теме B
[ ] Применить критерий из секции 2.3 → выбрать победителя
[ ] Ответить всем кто написал (шаблоны из секции 2.4)
[ ] Задача 7: обновления фронтенда (subject_b, причина паузы, баннер)
[ ] Если 0 ответов за 5 дней → стоп, пересматриваем письмо
```

### День 7–9 — Волна 1: Marquiz + Bitrix (30 писем/день)

```
[ ] Вручную проверить список Marquiz (22 компании)
    → убрать компании с SEO-названиями (валидатор отловит часть, но глаза надёжнее)
[ ] Кампания Marquiz: шаблон cold_email_marquiz, 22 получателя
[ ] Кампания Bitrix: шаблон cold_email_v1 (тема-победитель), 41 получатель
[ ] process_bounces.py
[ ] Мониторинг ответов, обработка воронки вручную
```

### День 10+ — Волны 2–4, рабочий режим (50 писем/день)

```
[ ] Волна 2: остаток сегмента A (~112 компаний, 3 дня)
[ ] Волна 3: сегмент B (259 компаний, 6 дней)
[ ] process_bounces.py — каждые 2–3 дня
[ ] Follow-up задачи — обрабатывать ежедневно через /tasks
[ ] Крупные сети (8 шт.) — написать вручную в любой удобный день
[ ] После обработки оставшихся 17 городов — добавить новые компании в очередь
```

---

## 7. Переменные окружения

Итоговый `.env` — полный список:

```bash
# ── SMTP (Gmail) ──────────────────────────────────────────────
SMTP_HOST=smtp.gmail.com
SMTP_PORT=465
SMTP_USER=ai.punk.facility@gmail.com
SMTP_PASS=xxxx xxxx xxxx xxxx   # App Password, 16 символов

# ── IMAP (bounce, тот же аккаунт) ─────────────────────────────
IMAP_HOST=imap.gmail.com
# IMAP_USER и IMAP_PASS берутся из SMTP_USER/SMTP_PASS в process_bounces.py

# ── Отправка ──────────────────────────────────────────────────
FROM_NAME=Александр
EMAIL_DELAY_MIN=45      # секунд между письмами (минимум)
EMAIL_DELAY_MAX=120     # секунд между письмами (максимум)
EMAIL_DAILY_LIMIT=50    # глобальный лимит за 24 часа

# ── Инфраструктура ────────────────────────────────────────────
BASE_URL=https://crm.yourdomain.com   # Cloudflare Tunnel, постоянный домен
# BASE_URL=https://xxxx.ngrok.io       # ngrok для тестирования

# ── CRM ───────────────────────────────────────────────────────
GRANITE_API_KEY=        # оставить пустым для локальной работы
DEBUG=false
```

---

*v8 · 2026-04-26 · На основе v7 + исправления: статус paused_daily_limit, guard-клауза для contact, SEO-фильтр в валидаторе, check_response для не открывших, оптимизация SSE-сессии, исправлен баг IMAP uids[0], follow-up для обоих сценариев, воронка после ответа*
