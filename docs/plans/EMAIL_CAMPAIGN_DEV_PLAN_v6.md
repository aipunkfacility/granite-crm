# RetouchGrav — Email Campaign Dev Plan v6
### Итоговая версия с правками архитектурного ревью v5

> Александр · @ganjavagen · +7 (494) 694-35-43  
> База: ~6 000 компаний → **434 приоритетных цели** (A+B, не-сеть, валидный email)  
> v6 · 2026-04-26 · Закрывает все проблемы v5

---

## Содержание

1. [Что исправлено относительно v5](#1-что-исправлено-относительно-v5)
2. [Стратегия и волны](#2-стратегия-и-волны)
3. [Прогрев домена](#3-прогрев-домена)
4. [Шаблоны писем](#4-шаблоны-писем)
5. [Технический план](#5-технический-план)
6. [Roadmap по дням](#6-roadmap-по-дням)

---

## 1. Что исправлено относительно v5

| Проблема в v5 | Решение в v6 |
|---------------|-------------|
| Background Task теряется при рестарте сервера — кампания зависает в `running` навсегда | Recovery при старте приложения: `running` → `paused`, ручной перезапуск |
| Двойной клик на "Запустить" порождает два параллельных фоновых процесса | Атомарная блокировка через `SELECT FOR UPDATE` + проверка перед стартом |
| Глобальный лимит 50/день мог считаться по-кампании вместо глобально | Явный `COUNT(*) WHERE sent_at >= last_24h` без фильтра по campaign_id |
| `{company_name}` в шаблоне Marquiz — 58% компаний имеют SEO-мусор в имени | Фраза убрана; ручная проверка списка волны 1 обязательна |
| Отписка через `tracking_id` письма — хрупко при нескольких письмах | Постоянный `unsubscribe_token` в `CrmContactRow`, не зависит от кампании |
| 50 писем с первого дня при холодном домене — риск бана у mail.ru/Яндекс | График прогрева: 10 → 20 → 30 → 50 |
| Bounce-уведомления вручную — будут теряться | Парсинг bounce + авто `funnel_stage = unreachable` |
| SPF/DKIM/DMARC проверяются "параллельно с" Днём 1 | Обязательный чеклист до первой отправки |
| Метрика победителя A/B не зафиксирована | Критерий выбора: reply rate ≥ 3% за 5 дней |

---

## 2. Стратегия и волны

### 2.1 Реальное состояние базы

```
Всего в базе:                           ~6 000 компаний
Обработанные города:                    29 из 46
Сегмент A, не-сеть, валидный email:     175
Сегмент B, не-сеть, валидный email:     259
────────────────────────────────────────────────────────
Приоритетная база:                      434 компании
Крупные сети (ручная работа):           8 компаний
```

### 2.2 Волны

Принцип: **тестируем только одну переменную за раз**. Либо тему (фиксируем аудиторию), либо аудиторию (фиксируем тему).

| Фаза | Волна | Аудитория | Размер | Шаблон | Цель |
|------|-------|-----------|--------|--------|------|
| **0** | Калибровка | Сегмент A, email, случайные 50 | 50 | `cold_email_v1`, тема A vs B | Найти лучшую тему |
| **1** | Marquiz | Marquiz=1, tg_trust≥2, A+B | ~22 | `cold_email_marquiz` | Тёплая аудитория |
| **1** | Bitrix | CMS=bitrix, A+B | ~41 | `cold_email_v1` (победитель) | Деловой тон |
| **2** | Остаток A | Tilda+WP, A | ~60–80 | `cold_email_v1` (победитель) | Основной сегмент |
| **2** | Остаток B | B | ~259 | `cold_email_v1` (победитель) | Масштаб |

> **Важно по волне 1 / Marquiz:** Перед запуском вручную проверить список — убедиться что `company_name` не SEO-мусор (нет "Изготовление памятников Краснодар" и подобных). 22 компании — проверяется за 10 минут.

---

## 3. Прогрев домена

### 3.1 Обязательный чеклист до первой отправки

Всё нижеперечисленное должно быть проверено **до Дня 2**, не параллельно с ним.

```
[ ] SPF-запись настроена:
    v=spf1 include:_spf.yourdomain.com ~all
    Проверка: mxtoolbox.com/spf

[ ] DKIM-запись настроена и подпись генерируется в sender.py
    Проверка: dkimvalidator.com

[ ] DMARC-запись настроена (начать с p=none для мониторинга):
    v=DMARC1; p=none; rua=mailto:dmarc@yourdomain.com
    Проверка: mxtoolbox.com/dmarc

[ ] mail-tester.com — оценка ≥ 8/10 (обязательно, не опционально)
    Тест: отправить письмо на адрес теста, проверить отчёт

[ ] Заголовки List-Unsubscribe и List-Unsubscribe-Post добавлены в sender.py
    (Gmail требует для bulk-отправителей с 2024 года)

[ ] Cloudflare Tunnel запущен, BASE_URL в .env указывает на постоянный домен
    Проверка: открыть {BASE_URL}/health — должен вернуть {"status": "ok"}

[ ] Unsubscribe-эндпоинт работает:
    GET {BASE_URL}/api/v1/unsubscribe/{token} → 200, stop_automation=1
```

### 3.2 График прогрева (первые 10 дней)

Резкий рост объёма — главная причина попадания в спам у Яндекс и mail.ru.

| День | Лимит писем | Статус |
|------|-------------|--------|
| 1 | 0 — только чеклист и инфра | Подготовка |
| 2 | 10 | Старт Фазы 0 |
| 3 | 20 | Фаза 0 продолжение |
| 4 | 20 | Фаза 0 окончание |
| 5–6 | 0 — мониторинг ответов | Пауза |
| 7 | 30 | Старт Волны 1 |
| 8 | 30 | |
| 9 | 50 | |
| 10+ | 50 (global daily limit) | Рабочий режим |

> Итого Фаза 0: 50 писем за 3 дня (10+20+20). Паузы — не потеря времени, а наблюдение за bounce rate. Если bounce > 5% → стоп, разбираемся с базой.

### 3.3 Метрика здоровья

| Метрика | Норма | Стоп-сигнал |
|---------|-------|-------------|
| Bounce rate (hard) | < 2% | ≥ 5% → стоп |
| Spam complaints | < 0.1% | ≥ 0.5% → стоп |
| Open rate (mail.ru/Яндекс) | 10–20% | < 5% → проверить DKIM |
| Reply rate | цель ≥ 3% | < 1% → пересмотреть шаблон |

**Где смотреть bounce:** SMTP-сервер пишет уведомления на адрес отправителя. Настроить парсинг (Задача 6).

---

## 4. Шаблоны писем

### 4.1 `cold_email_v1` — основной (Фаза 0, Волны 2–4)

```
Имя в БД: cold_email_v1
Канал: email
body_type: plain

─── ТЕМА A ───
Подготовка фото под гравировку — пришлите самый сложный случай

─── ТЕМА B ───
Ретушь под памятник: старые и плохие фото — в день заказа

─── ТЕЛО ───
Здравствуйте.

Меня зовут Александр. Занимаюсь подготовкой портретов для гравировки
на памятниках — беру сложные случаи: старые фото, низкое разрешение,
повреждённые снимки.

Нейросети + ручная доработка. Срок — 12–24 часа, срочно — 3–6 часов.
Цена — от 700 ₽.

Готов сделать 1–2 пробных бесплатно — на ваших реальных исходниках,
без обязательств.

Примеры работ: https://retouchgrav.netlify.app

Александр
Telegram: @ganjavagen · WhatsApp: +7 (494) 694-35-43

---
Если не актуально — ответьте «нет», больше не напишу.
Отписаться: {unsubscribe_url}
```

### 4.2 `cold_email_marquiz` — для Marquiz + TG (Волна 1)

> **Изменение относительно v5:** убрана фраза `"Вижу, что {company_name} развивается"` — 58% имён в базе SEO-мусор, фраза выглядела бы как плохой шаблон. Заменена на нейтральную конкретику.

```
Имя в БД: cold_email_marquiz
Канал: email
body_type: plain

─── ТЕМА A ───
Подготовка фото под гравировку — могу разгрузить вас на ретуши

─── ТЕМА B ───
Ретушь портретов для вашей мастерской — оплата после результата

─── ТЕЛО ───
Здравствуйте.

Меня зовут Александр. Занимаюсь подготовкой портретных фото для
гравировки на памятниках.

Беру всё что сложно: старые снимки 80-х, фото на документах,
групповые — когда нужно вырезать одного человека, низкое разрешение.

Нейросети + ручная доработка. 12–24 часа, срочно 3–6 часов.
Цена — от 700 ₽, оплата после результата для новых клиентов.

Начнём с бесплатной пробы: пришлите 1–2 ваших текущих исходника —
покажу результат.

Примеры работ: https://retouchgrav.netlify.app

Александр
Telegram: @ganjavagen · WhatsApp: +7 (494) 694-35-43

---
Отписаться: {unsubscribe_url}
```

### 4.3 `follow_up_email_v1` — follow-up (только email, через 7 дней)

```
Имя в БД: follow_up_email_v1
Канал: email
body_type: plain

─── ТЕМА ───
Re: подготовка фото под гравировку

─── ТЕЛО ───
Добрый день.

Писал на прошлой неделе про ретушь портретов.

Не хочу надоедать — просто оставлю ссылку на примеры:
https://retouchgrav.netlify.app

Первый портрет бесплатно — пришлите в ответ любой сложный исходник.

Александр · @ganjavagen
---
Отписаться: {unsubscribe_url}
```

### 4.4 Критерий выбора победителя A/B

**Метрика:** reply rate (ответы / отправленные)  
**Срок измерения:** 5 дней после отправки последнего письма фазы 0  
**Победитель:** тема с reply rate ≥ 3% и превышением альтернативы минимум на 50%

Если оба варианта ниже 1% reply rate — проблема в теле письма или в домене, не в теме. Пересматриваем письмо, не запускаем волны.

---

## 5. Технический план

### Задача 0: Инфраструктура (до всего остального)

#### 0.1 Cloudflare Tunnel

```bash
# Установка и настройка
cloudflared tunnel login
cloudflared tunnel create granite-crm
cloudflared tunnel route dns granite-crm crm.yourdomain.com
cloudflared tunnel run granite-crm

# Автозапуск при старте системы
cloudflared service install
```

В `.env`:
```
BASE_URL=https://crm.yourdomain.com
```

> Проверка: `curl https://crm.yourdomain.com/health` → `{"status": "ok", "db": true}`

#### 0.2 SPF / DKIM / DMARC

DKIM добавить в `sender.py`:
```python
import dkim

def _sign_message(self, msg: MIMEMultipart) -> MIMEMultipart:
    """Подписать письмо DKIM."""
    private_key_path = os.getenv("DKIM_PRIVATE_KEY_PATH")
    dkim_selector = os.getenv("DKIM_SELECTOR", "mail")
    domain = os.getenv("SMTP_FROM_DOMAIN")

    if not all([private_key_path, domain]):
        logger.warning("DKIM не настроен — письмо отправляется без подписи")
        return msg

    with open(private_key_path, "rb") as f:
        private_key = f.read()

    raw = msg.as_bytes()
    sig = dkim.sign(
        raw,
        selector=dkim_selector.encode(),
        domain=domain.encode(),
        privkey=private_key,
        include_headers=[b"From", b"To", b"Subject", b"Date"]
    )
    # Вставить подпись в заголовок
    msg["DKIM-Signature"] = sig[len("DKIM-Signature: "):].decode()
    return msg
```

Заголовки `List-Unsubscribe` добавить в `sender.py`:
```python
msg["List-Unsubscribe"] = f"<{unsubscribe_url}>, <mailto:unsubscribe@yourdomain.com>"
msg["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"
```

---

### Задача 1: Постоянный `unsubscribe_token` в `CrmContactRow`

**Проблема v5:** отписка через `tracking_id` письма — у каждого письма свой ID, при нескольких письмах нужно знать ID последнего. Хрупко.

**Решение:** постоянный токен на уровне контакта.

#### 1.1 Миграция Alembic

```python
# alembic/versions/xxxx_add_unsubscribe_token.py
import uuid

def upgrade():
    op.add_column(
        "crm_contacts",
        sa.Column("unsubscribe_token", sa.String, nullable=True, unique=True)
    )
    # Заполнить существующие записи
    op.execute("""
        UPDATE crm_contacts
        SET unsubscribe_token = lower(hex(randomblob(16)))
        WHERE unsubscribe_token IS NULL
    """)
    op.alter_column("crm_contacts", "unsubscribe_token", nullable=False)
    op.create_index("ix_crm_contacts_unsubscribe_token", "crm_contacts", ["unsubscribe_token"])

def downgrade():
    op.drop_index("ix_crm_contacts_unsubscribe_token")
    op.drop_column("crm_contacts", "unsubscribe_token")
```

#### 1.2 Генерация токена при создании контакта

```python
# granite/database.py — в CrmContactRow.__init__ или seed-скрипте
import secrets

class CrmContactRow(Base):
    # ...
    unsubscribe_token = Column(
        String,
        nullable=False,
        default=lambda: secrets.token_hex(16),
        unique=True
    )
```

#### 1.3 Эндпоинт отписки

Файл `granite/api/unsubscribe.py`:

```python
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from granite.api.deps import get_db
from granite.database import CrmContactRow, CrmTouchRow
from datetime import datetime, timezone

router = APIRouter()

@router.get("/unsubscribe/{token}", response_class=HTMLResponse)
def unsubscribe(token: str, db: Session = Depends(get_db)):
    contact = db.query(CrmContactRow).filter_by(
        unsubscribe_token=token
    ).first()

    if not contact:
        raise HTTPException(404, "Ссылка недействительна")

    if contact.stop_automation:
        # Уже отписан — показать страницу без ошибки
        return _unsubscribe_page(already=True)

    contact.stop_automation = True
    contact.funnel_stage = "not_interested"
    contact.updated_at = datetime.now(timezone.utc)

    # Лог в touches
    db.add(CrmTouchRow(
        company_id=contact.company_id,
        channel="email",
        direction="incoming",
        subject="Отписка",
        note="unsubscribe_link",
    ))
    db.commit()

    return _unsubscribe_page(already=False)


def _unsubscribe_page(already: bool) -> str:
    msg = "Вы уже были отписаны ранее." if already else "Вы успешно отписаны. Больше писем не будет."
    return f"""
    <!DOCTYPE html><html><body style="font-family:sans-serif;max-width:500px;margin:60px auto;text-align:center">
    <h2>RetouchGrav</h2>
    <p>{msg}</p>
    </body></html>
    """
```

#### 1.4 Плейсхолдер `{unsubscribe_url}` в рендере шаблона

```python
# granite/database.py — метод CrmTemplateRow.render()
def render(self, **kwargs) -> str:
    body = self.body
    for key, value in kwargs.items():
        body = body.replace(f"{{{key}}}", html.escape(str(value)) if self.body_type == "html" else str(value))
    return body

# Использование в sender.py:
unsubscribe_url = f"{os.getenv('BASE_URL')}/api/v1/unsubscribe/{contact.unsubscribe_token}"
rendered = template.render(
    company_name=company.name_best,
    city=company.city,
    from_name=os.getenv("FROM_NAME", "Александр"),
    unsubscribe_url=unsubscribe_url,
)
```

---

### Задача 2: Архитектура отправки — Background Tasks с защитой

#### 2.1 Recovery при старте сервера

```python
# granite/api/app.py

@app.on_event("startup")
async def recover_stuck_campaigns():
    """При рестарте вернуть 'running' кампании в 'paused'.
    
    Background Tasks живут в памяти процесса — при рестарте они теряются.
    Кампания зависает в running навсегда без этого recovery.
    """
    db = Database()
    with db.session_scope() as session:
        stuck = session.query(CrmEmailCampaignRow).filter_by(
            status="running"
        ).all()
        for campaign in stuck:
            campaign.status = "paused"
            logger.warning(
                f"RECOVERY: кампания {campaign.id} '{campaign.name}' "
                f"переведена из running → paused (рестарт сервера)"
            )
        if stuck:
            logger.info(f"RECOVERY: восстановлено {len(stuck)} кампаний")
    db.engine.dispose()
```

#### 2.2 Атомарная блокировка перед стартом

```python
# granite/api/campaigns.py

@router.post("/campaigns/{campaign_id}/run")
async def run_campaign(
    campaign_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    # 1. Проверить что нет уже запущенной кампании (глобально)
    running = db.query(CrmEmailCampaignRow).filter_by(status="running").first()
    if running:
        raise HTTPException(
            409,
            f"Уже запущена кампания #{running.id} '{running.name}'. "
            f"Дождитесь завершения или поставьте её на паузу."
        )

    # 2. Получить и проверить целевую кампанию
    campaign = db.get(CrmEmailCampaignRow, campaign_id)
    if not campaign:
        raise HTTPException(404, "Кампания не найдена")
    if campaign.status not in ("draft", "paused"):
        raise HTTPException(
            400,
            f"Нельзя запустить кампанию со статусом '{campaign.status}'"
        )

    # 3. Атомарно сменить статус
    campaign.status = "running"
    campaign.started_at = campaign.started_at or datetime.now(timezone.utc)
    db.commit()

    # 4. Запустить фоновую задачу
    background_tasks.add_task(run_campaign_background, campaign_id)
    return {"status": "started", "campaign_id": campaign_id}
```

#### 2.3 Фоновая задача отправки

```python
# granite/api/campaigns.py

EMAIL_DELAY_MIN = int(os.getenv("EMAIL_DELAY_MIN", "45"))   # секунд
EMAIL_DELAY_MAX = int(os.getenv("EMAIL_DELAY_MAX", "120"))  # секунд
EMAIL_DAILY_LIMIT = int(os.getenv("EMAIL_DAILY_LIMIT", "50"))


def run_campaign_background(campaign_id: int) -> None:
    """Фоновая отправка. Работает в отдельном потоке, создаёт свою сессию БД."""
    import time, random
    from granite.database import Database
    from granite.email.sender import EmailSender

    db = Database()
    sender = EmailSender()

    try:
        with db.session_scope() as session:
            campaign = session.get(CrmEmailCampaignRow, campaign_id)
            if not campaign or campaign.status != "running":
                return

            recipients = _get_campaign_recipients(session, campaign)
            # Отфильтровать уже получивших письмо в этой кампании
            already_sent = {
                log.company_id
                for log in session.query(CrmEmailLogRow.company_id)
                .filter_by(campaign_id=campaign_id)
                .all()
            }
            recipients = [r for r in recipients if r.company_id not in already_sent]

            for company, enriched, contact in recipients:
                # Проверить паузу/отмену перед каждым письмом
                session.refresh(campaign)
                if campaign.status != "running":
                    logger.info(f"Кампания {campaign_id}: статус '{campaign.status}', выход")
                    return

                # Глобальный лимит — БЕЗ фильтра по campaign_id
                last_24h = datetime.now(timezone.utc) - timedelta(hours=24)
                sent_today = (
                    session.query(func.count(CrmEmailLogRow.id))
                    .filter(CrmEmailLogRow.sent_at >= last_24h)
                    .scalar()
                )
                if sent_today >= EMAIL_DAILY_LIMIT:
                    campaign.status = "paused_daily_limit"
                    logger.info(
                        f"Кампания {campaign_id}: достигнут дневной лимит "
                        f"({EMAIL_DAILY_LIMIT} писем). Кампания на паузе до завтра."
                    )
                    break

                # Отправка
                try:
                    result = sender.send(company, enriched, contact, campaign)
                    campaign.total_sent = (campaign.total_sent or 0) + 1
                    session.flush()
                except Exception as e:
                    logger.error(f"Ошибка отправки company_id={company.id}: {e}")
                    campaign.total_errors = (campaign.total_errors or 0) + 1

                # Задержка между письмами
                delay = random.randint(EMAIL_DELAY_MIN, EMAIL_DELAY_MAX)
                time.sleep(delay)

            else:
                # Цикл завершился без break — все письма отправлены
                campaign.status = "completed"
                campaign.completed_at = datetime.now(timezone.utc)
                logger.info(f"Кампания {campaign_id} завершена")

    except Exception as e:
        logger.exception(f"Критическая ошибка в кампании {campaign_id}: {e}")
        with db.session_scope() as session:
            campaign = session.get(CrmEmailCampaignRow, campaign_id)
            if campaign:
                campaign.status = "error"
    finally:
        db.engine.dispose()
```

#### 2.4 SSE-эндпоинт: только поллинг БД

```python
# granite/api/campaigns.py

@router.get("/campaigns/{campaign_id}/progress")
async def campaign_progress_sse(campaign_id: int, db: Session = Depends(get_db)):
    """SSE: отдаёт прогресс из БД каждые 3 секунды. Не занимается отправкой."""

    async def generate():
        while True:
            campaign = db.get(CrmEmailCampaignRow, campaign_id)
            if not campaign:
                yield f"data: {json.dumps({'error': 'not_found'})}\n\n"
                return

            payload = {
                "type": "progress",
                "data": {
                    "status": campaign.status,
                    "sent": campaign.total_sent or 0,
                    "errors": getattr(campaign, "total_errors", 0) or 0,
                    "completed_at": campaign.completed_at.isoformat() if campaign.completed_at else None,
                }
            }
            yield f"data: {json.dumps(payload)}\n\n"

            if campaign.status in ("completed", "error", "paused", "paused_daily_limit"):
                # Терминальный статус — закрыть SSE
                return

            await asyncio.sleep(3)

    return StreamingResponse(generate(), media_type="text/event-stream")
```

---

### Задача 3: A/B тест — детерминированное распределение

#### 3.1 Новые поля в `CrmEmailCampaignRow`

```python
# granite/database.py
class CrmEmailCampaignRow(Base):
    # ... существующие поля ...
    subject_a = Column(String, nullable=True)   # Тема A
    subject_b = Column(String, nullable=True)   # Тема B (None = не A/B тест)
    total_errors = Column(Integer, default=0)   # Счётчик ошибок отправки
```

Миграция:
```bash
uv run cli.py db migrate "add subject_ab and total_errors to campaigns"
uv run cli.py db upgrade head
```

#### 3.2 Хеш-распределение в sender.py

```python
# granite/email/sender.py
import hashlib

def get_ab_subject(company_id: int, subject_a: str, subject_b: str | None) -> str:
    """Детерминированное A/B распределение по company_id через MD5.

    %2 косит на малых выборках (чётные/нечётные ID).
    MD5-хеш даёт равномерное распределение независимо от диапазона ID.
    """
    if not subject_b:
        return subject_a  # Нет B — всем A

    hash_val = int(hashlib.md5(str(company_id).encode()).hexdigest(), 16)
    return subject_a if hash_val % 2 == 0 else subject_b
```

---

### Задача 4: Валидатор получателей

Файл `granite/email/validator.py`:

```python
# Домены агрегаторов — не мастерские, письмо уйдёт в никуда
AGGREGATOR_DOMAINS = frozenset({
    "memorial.ru", "vsepamyatniki.ru", "obeliski.ru",
    "mipomnim.ru", "uznm.ru", "monuments.su",
    "tsargranit.ru", "alshei.ru",
})

def validate_recipients(
    recipients: list[tuple]
) -> tuple[list[tuple], list[dict]]:
    """
    Возвращает (valid, warnings).
    warnings — список словарей с причиной пропуска для UI.
    """
    valid = []
    warnings = []

    for company, enriched, contact in recipients:
        reason = _check_recipient(company, contact)
        if reason:
            warnings.append({
                "company_id": company.id,
                "name": company.name_best,
                "reason": reason
            })
        else:
            valid.append((company, enriched, contact))

    return valid, warnings


def _check_recipient(company, contact) -> str | None:
    """None = валиден, строка = причина пропуска."""

    # Нет email
    emails = company.emails or []
    if not emails:
        return "нет email"

    email = emails[0] if isinstance(emails, list) else emails
    domain = email.split("@")[-1].lower() if "@" in str(email) else ""

    # Агрегатор
    if domain in AGGREGATOR_DOMAINS:
        return f"агрегатор ({domain})"

    # Отписан
    if contact and contact.stop_automation:
        return "отписан"

    # Нет имени или имя — явный SEO-мусор (> 60 символов)
    name = (company.name_best or "").strip()
    if not name:
        return "пустое название"
    if len(name) > 80:
        return "название слишком длинное (SEO?)"

    return None
```

Интеграция в `run_campaign` — перед стартом фоновой задачи:
```python
recipients = _get_campaign_recipients(db, campaign)
valid, warnings = validate_recipients(recipients)

if warnings:
    logger.warning(
        f"Кампания {campaign_id}: пропущено {len(warnings)} получателей — "
        + ", ".join(w["reason"] for w in warnings[:5])
    )
# Передаём только valid в фоновую задачу
```

---

### Задача 5: Воронка ответов и авто-отмена follow-up

#### 5.1 Авто-отмена при смене стадии

```python
# granite/api/companies.py — в update_company()

CANCEL_FOLLOWUP_ON_STAGES = {"replied", "interested", "not_interested", "unreachable"}

def update_company(company_id: int, data: UpdateCompanyRequest, db: Session = Depends(get_db)):
    # ... существующий код обновления ...

    if data.funnel_stage in CANCEL_FOLLOWUP_ON_STAGES:
        cancelled = (
            db.query(CrmTaskRow)
            .filter(
                CrmTaskRow.company_id == company_id,
                CrmTaskRow.status == "pending",
                CrmTaskRow.task_type == "follow_up",
            )
            .update(
                {"status": "cancelled", "completed_at": datetime.now(timezone.utc)},
                synchronize_session=False,
            )
        )
        if cancelled:
            logger.info(
                f"company_id={company_id}: отменено {cancelled} follow-up задач "
                f"(смена стадии → {data.funnel_stage})"
            )

    db.commit()
    return {"ok": True}
```

#### 5.2 Создание follow-up задачи при открытии письма

```python
# granite/api/tracking.py — в обработчике tracking pixel

def _maybe_create_followup_task(company_id: int, db: Session) -> None:
    """Создать follow-up задачу через 7 дней после открытия письма.
    Только если задачи ещё нет и контакт ещё не ответил.
    """
    contact = db.query(CrmContactRow).filter_by(company_id=company_id).first()
    if not contact:
        return

    # Не создавать если уже есть активная задача
    existing = db.query(CrmTaskRow).filter(
        CrmTaskRow.company_id == company_id,
        CrmTaskRow.task_type == "follow_up",
        CrmTaskRow.status == "pending",
    ).first()
    if existing:
        return

    # Не создавать если уже есть ответ
    if contact.funnel_stage in ("replied", "interested", "not_interested"):
        return

    db.add(CrmTaskRow(
        company_id=company_id,
        title="Follow-up (открыл письмо)",
        task_type="follow_up",
        priority="normal",
        status="pending",
        due_date=datetime.now(timezone.utc) + timedelta(days=7),
        description="Автоматически создано при открытии письма",
    ))
    db.flush()
```

#### 5.3 Воронка после ответа

Переходы после `replied` — только вручную через UI:

```
replied → interested  (обсуждаем условия)
replied → not_interested  (отказ)
interested → [ручная работа вне CRM]
```

Никаких автоматических действий при `interested` — это уже живое общение, не автоматизация.

---

### Задача 6: Парсинг bounce-уведомлений

Простой вариант без отдельного IMAP-демона — периодический скрипт.

Файл `scripts/process_bounces.py`:

```python
"""
Читает IMAP-ящик отправителя, ищет bounce-уведомления,
помечает компании как unreachable.

Запускать вручную или через cron: 
  uv run python -m scripts.process_bounces
"""
import imaplib, email, re
from granite.database import Database, CrmEmailLogRow, CrmContactRow

IMAP_HOST = os.getenv("IMAP_HOST")
IMAP_USER = os.getenv("SMTP_USER")
IMAP_PASS = os.getenv("SMTP_PASS")

# Паттерны для определения hard bounce
HARD_BOUNCE_PATTERNS = [
    r"550",  # User does not exist
    r"551",  # User not local
    r"553",  # Mailbox name not allowed
    r"unknown user",
    r"no such user",
    r"user unknown",
    r"mailbox not found",
    r"address rejected",
    r"does not exist",
]

def process_bounces():
    db = Database()
    processed = 0

    with imaplib.IMAP4_SSL(IMAP_HOST) as imap:
        imap.login(IMAP_USER, IMAP_PASS)
        imap.select("INBOX")

        # Искать письма от MAILER-DAEMON и Mail Delivery
        _, uids = imap.search(None, '(FROM "MAILER-DAEMON" UNSEEN)')
        if not uids[0]:
            _, uids = imap.search(None, '(SUBJECT "Delivery Status" UNSEEN)')

        for uid in uids[0].split():
            _, data = imap.fetch(uid, "(RFC822)")
            raw = data[0][1]
            msg = email.message_from_bytes(raw)

            bounce_email = _extract_bounced_email(msg)
            if not bounce_email:
                continue

            if not _is_hard_bounce(msg):
                continue  # Soft bounce — игнорируем

            with db.session_scope() as session:
                log = (
                    session.query(CrmEmailLogRow)
                    .filter_by(email_to=bounce_email)
                    .order_by(CrmEmailLogRow.sent_at.desc())
                    .first()
                )
                if log:
                    log.status = "bounced"
                    log.bounced_at = datetime.now(timezone.utc)

                    contact = session.query(CrmContactRow).filter_by(
                        company_id=log.company_id
                    ).first()
                    if contact:
                        contact.funnel_stage = "unreachable"
                        contact.stop_automation = True

                    processed += 1
                    logger.info(f"Bounce: {bounce_email} → company #{log.company_id}")

            # Пометить письмо как прочитанное
            imap.store(uid, "+FLAGS", "\\Seen")

    db.engine.dispose()
    logger.info(f"Обработано bounce: {processed}")
    return processed


def _extract_bounced_email(msg) -> str | None:
    """Извлечь email адрес получателя из bounce-уведомления."""
    for part in msg.walk():
        if part.get_content_type() in ("message/delivery-status", "text/plain"):
            content = part.get_payload(decode=True)
            if content:
                text = content.decode("utf-8", errors="ignore")
                match = re.search(r"Final-Recipient:.*?<?([\w._%+-]+@[\w.-]+\.\w+)>?", text)
                if match:
                    return match.group(1).lower()
    return None


def _is_hard_bounce(msg) -> bool:
    """Определить hard bounce по коду ответа."""
    text = msg.as_string().lower()
    return any(pattern.lower() in text for pattern in HARD_BOUNCE_PATTERNS)


if __name__ == "__main__":
    process_bounces()
```

---

### Задача 7: Фронтенд — обновления

#### 7.1 Wizard создания кампании

```tsx
// Шаг 2 — Шаблон
<FormField name="subject_a" label="Тема письма" required />

// Опциональный A/B блок
<Collapsible>
  <CollapsibleTrigger>
    <Button variant="ghost" size="sm">+ Добавить вариант темы B (A/B тест)</Button>
  </CollapsibleTrigger>
  <CollapsibleContent>
    <FormField name="subject_b" label="Тема B" />
    <p className="text-xs text-muted">
      Компании будут равномерно разделены между темой A и B.
      Победитель определяется по reply rate через 5 дней.
    </p>
  </CollapsibleContent>
</Collapsible>
```

#### 7.2 Карточка кампании — прогресс и A/B статистика

```tsx
// CampaignCard / CampaignDetailPage

// Прогресс отправки (поллинг SSE)
<ProgressBar value={campaign.total_sent} max={campaign.total_recipients} />
<p>{campaign.total_sent} из {campaign.total_recipients} · {campaign.status}</p>

// A/B статистика (только если есть subject_b)
{campaign.subject_b && (
  <ABStats>
    <ABVariant label="Тема A" subject={campaign.subject_a} stats={abStats.a} />
    <ABVariant label="Тема B" subject={campaign.subject_b} stats={abStats.b} />
    <p className="text-xs text-muted">
      Победитель: тема с reply rate ≥ 3% и превышением на 50%+
    </p>
  </ABStats>
)}

// Предупреждения валидатора
{campaign.warnings?.length > 0 && (
  <Collapsible>
    <CollapsibleTrigger>
      ⚠️ Пропущено {campaign.warnings.length} получателей
    </CollapsibleTrigger>
    <CollapsibleContent>
      {campaign.warnings.map(w => (
        <div key={w.company_id}>{w.name}: {w.reason}</div>
      ))}
    </CollapsibleContent>
  </Collapsible>
)}
```

#### 7.3 Recovery-уведомление

```tsx
// При загрузке списка кампаний — проверить наличие paused кампаний
// с причиной рестарта и показать баннер:
{recoveredCampaigns.length > 0 && (
  <Alert variant="warning">
    <AlertTitle>Кампании восстановлены после рестарта</AlertTitle>
    <AlertDescription>
      {recoveredCampaigns.map(c => c.name).join(", ")} — переведены в «пауза».
      Запустите их вручную когда будете готовы.
    </AlertDescription>
  </Alert>
)}
```

---

## 6. Roadmap по дням

### День 1 — Инфраструктура (только подготовка, 0 писем)

```
[ ] Cloudflare Tunnel настроен, постоянный домен работает
[ ] SPF + DKIM + DMARC настроены
[ ] mail-tester.com: оценка ≥ 8/10
[ ] Задача 0.2: DKIM-подпись в sender.py
[ ] Задача 0.2: List-Unsubscribe заголовки в sender.py
[ ] Задача 1: миграция unsubscribe_token, эндпоинт /unsubscribe/{token}
[ ] Задача 2.1: recovery при старте сервера
[ ] Задача 2.2: атомарная блокировка перед стартом кампании
[ ] Тест сквозной: отправить письмо на свой ящик, проверить:
    - DKIM-подпись в заголовках
    - Ссылка отписки работает
    - Tracking pixel фиксирует открытие
```

### День 2 — Фаза 0, первые 10 писем

```
[ ] Задача 2.3: Background Task отправки (рефакторинг)
[ ] Задача 2.4: SSE-поллинг из БД
[ ] Задача 3: A/B поля в БД + хеш-распределение
[ ] Задача 4: validator.py, интеграция перед стартом
[ ] Создать кампанию: 10 получателей, сегмент A, тема A vs B
[ ] Запустить, проверить логи
[ ] Проверить bounce rate к концу дня
```

### День 3–4 — Фаза 0, ещё 40 писем

```
[ ] 20 писем / день
[ ] Задача 5: авто-отмена follow-up + создание задачи при открытии
[ ] Задача 6: скрипт process_bounces.py
[ ] Мониторинг bounce rate — если > 5% → стоп
```

### День 5–6 — Пауза, мониторинг

```
[ ] 0 писем
[ ] Ответить всем кто написал (moved to: replied → interested)
[ ] Считать reply rate по теме A vs B
[ ] Если есть победитель (≥ 3% и 50%+ разрыв) — зафиксировать
[ ] Задача 7: обновления фронтенда
```

### День 7–9 — Волна 1: Marquiz + Bitrix

```
[ ] Вручную проверить список Marquiz (22 компании) — убрать SEO-имена
[ ] Создать кампанию Marquiz: шаблон cold_email_marquiz, 22 получателя
[ ] 30 писем / день
[ ] Создать кампанию Bitrix: шаблон cold_email_v1 (победитель), 41 получатель
[ ] Мониторинг ответов, обработка ручного этапа воронки
```

### День 10+ — Волны 2–4, масштаб

```
[ ] 50 писем / день (рабочий режим)
[ ] Волна 2: остаток A (60–80 компаний)
[ ] Волна 3: сегмент B (259 компаний)
[ ] Follow-up через 7 дней для тех кто открыл но не ответил
[ ] process_bounces.py — запускать каждые 2–3 дня
```

---

## Приложение: переменные окружения

```bash
# .env — полный список

# SMTP
SMTP_HOST=smtp.yourdomain.com
SMTP_PORT=465
SMTP_USER=alexander@yourdomain.com
SMTP_PASS=your_password
SMTP_FROM_DOMAIN=yourdomain.com

# DKIM
DKIM_PRIVATE_KEY_PATH=/home/user/.dkim/private.key
DKIM_SELECTOR=mail

# Отправка
FROM_NAME=Александр
BASE_URL=https://crm.yourdomain.com
EMAIL_DELAY_MIN=45
EMAIL_DELAY_MAX=120
EMAIL_DAILY_LIMIT=50

# IMAP (для bounce)
IMAP_HOST=imap.yourdomain.com

# CRM
GRANITE_API_KEY=             # опционально
```

---

*v6 · 2026-04-26 · Закрывает все проблемы v5: recovery кампаний, постоянный unsubscribe_token, прогрев домена, защищённый A/B тест, bounce-парсинг*
