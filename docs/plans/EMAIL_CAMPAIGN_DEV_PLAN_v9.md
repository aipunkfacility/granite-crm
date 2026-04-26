# RetouchGrav — Email Campaign Dev Plan v9

> Александр · @ganjavagen · +84 946 943 543
> База: ~6 000 компаний → **434 приоритетных цели** (A+B, не-сеть, валидный email)
> SMTP: ai.punk.facility@gmail.com (личный аккаунт, App Password)
> v9 · 2026-04-26 · v8 + аудит: SMTP_SSL, SEO-pattern fix, reply detection

---

## Содержание

1. [Что изменилось относительно v8](#1-что-изменилось-относительно-v8)
2. [Стратегия и волны](#2-стратегия-и-волны)
3. [Прогрев домена](#3-прогрев-домена)
4. [Шаблоны писем](#4-шаблоны-писем)
5. [Технический план](#5-технический-план)
6. [Roadmap по дням](#6-roadmap-по-дням)

---

## 1. Что изменилось относительно v8

| В v8 | В v9 | Почему |
|------|------|--------|
| `smtplib.SMTP` + `starttls()` для порта 465 | ✅ `smtplib.SMTP_SSL` для 465 | Порту 465 нужен implicit TLS (`SMTP_SSL`), а не STARTTLS. Текущий код в sender.py использует `SMTP(port=587)+starttls()` — при `SMTP_PORT=465` из .env отправка упадёт |
| `памятник[аиы]?\s*(?:из\|в\|на\|от\|и)?\s*` флагает «Гранит-Мастер ООО Памятники» | ✅ Паттерн переписан | «Памятники» в конце названия компании — не SEO. Добавлен негативный lookahead: совпадение только если после «памятник[аиы]?» идёт SEO-слово, а не конец строки |
| Нет механизма обнаружения ответов | ✅ Добавлен IMAP reply parser | Воронка упоминает `replied`, но некому перевести в этот статус. Добавлен скрипт `process_replies.py` |
| `process_bounces.py` создаёт `Database()` напрямую | ✅ Использует `get_engine()` из app | Разные пути к БД — риск записать не в ту базу |
| Background task: commit каждые 10 писем | ✅ Commit после каждого письма | При краше между 10-ками теряются данные об отправке. 1 лишний commit/письмо — незаметно на SQLite |
| Задача 8 (SEO) стоит перед Задачей 7 (Frontend) | ✅ Переnumerировано | SEO-фикс = Задача 7, Frontend = Задача 8 |

<details>
<summary>Разница v7 → v8 (для справки)</summary>

| В v7 | В v8 | Почему |
|------|------|--------|
| SEO-regex содержит «гранит» в 4 паттернах | ✅ Убрано | «Гранит» в названии — норма для ниши |

</details>

<details>
<summary>Разница v6 → v7 (для справки)</summary>

| В v6 | В v7 | Почему |
|------|------|--------|
| SPF/DKIM/DMARC настраиваются на своём домене | ❌ Убрано — отправка через Gmail | Google управляет SPF/DKIM/DMARC для gmail.com |
| DKIM-подпись в sender.py | ❌ Убрано | Невозможно через Gmail SMTP |
| Заголовки List-Unsubscribe | ❌ Убрано | Gmail фильтрует произвольные заголовки |
| `SELECT FOR UPDATE` | ❌ Исправлено | SQLite не поддерживает |
| Recovery через `on_event` | ❌ Исправлено | Депрекейтнут, используем `lifespan()` |
| A/B тест: «≥ 3% + 50%» | ⚠️ Упрощено | На 25/25 — шум, не статистика |
| Авто-resume при `paused_daily_limit` | ❌ Не нужен | Ручной перезапуск — нормально |
| `{company_name}` убрано | ✅ Добавлен `{city}` | Персонализация без SEO-мусора |
| Bounce: паттерн `"550"` | ❌ Исправлено | Ложные срабатывания, теперь regex по SMTP-кодам |
| Валидатор email | ✅ Добавлено | Минимальная проверка формата |
| GET /unsubscribe отписывает | ⚠️ Добавлена защита | Префетч почтовых клиентов |

</details>

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

Принцип: **тестируем только одну переменную за раз**.

| Фаза | Волна | Аудитория | Размер | Шаблон | Цель |
|------|-------|-----------|--------|--------|------|
| **0** | Калибровка | Сегмент A, email, случайные 50 | 50 | `cold_email_v1`, тема A vs B | Найти лучшую тему |
| **1** | Marquiz | Marquiz=1, tg_trust≥2, A+B | ~22 | `cold_email_marquiz` | Тёплая аудитория |
| **1** | Bitrix | CMS=bitrix, A+B | ~41 | `cold_email_v1` (победитель) | Деловой тон |
| **2** | Остаток A | Tilda+WP, A | ~60–80 | `cold_email_v1` (победитель) | Основной сегмент |
| **2** | Остаток B | B | ~259 | `cold_email_v1` (победитель) | Масштаб |

> **Важно по волне 1 / Marquiz:** После фикса SEO-regex (задача 7) «Гранитные мастерские» и «Гранит-Мастер» больше не флагаются как SEO. Но остаются другие SEO-паттерны (купить/цены/изготовление + город). Перед запуском проверить список — 22 компании, 10 минут.

---

## 3. Прогрев домена

### 3.1 Обязательный чеклист до первой отправки

Поскольку отправка через Gmail — SPF/DKIM/DMARC настраивать не нужно (Google управляет ими). Но нужно другое:

```
[ ] Gmail: включить 2FA на ai.punk.facility@gmail.com
[ ] Gmail: создать App Password (https://myaccount.google.com/apppasswords)
[ ] .env: SMTP_HOST=smtp.gmail.com, SMTP_PORT=465, SMTP_PASS=<app-password>
[ ] .env: IMAP_HOST=imap.gmail.com (для bounce + reply)
[ ] Проверка: отправить тестовое письмо себе через sender.py
[ ] Проверить заголовки полученного письма (Show Original в Gmail):
    - SPF: pass (google.com)
    - DKIM: pass (google.com) — подпись Google, не ваша
[ ] Cloudflare Tunnel запущен, BASE_URL в .env указывает на постоянный домен
    Проверка: curl {BASE_URL}/health → {"status": "ok"}
[ ] Unsubscribe-эндпоинт работает:
    GET {BASE_URL}/api/v1/unsubscribe/{token} → страница подтверждения
[ ] Tracking pixel работает:
    открыть {BASE_URL}/api/v1/track/open/test1234.png → 200, прозрачный PNG
```

### 3.2 График прогрева (первые 10 дней)

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

> Итого Фаза 0: 50 писем за 3 дня (10+20+20). Паузы — наблюдение за bounce rate. Если bounce > 5% → стоп, разбираемся с базой.

### 3.3 Метрики здоровья

| Метрика | Норма | Стоп-сигнал |
|---------|-------|-------------|
| Bounce rate (hard) | < 2% | ≥ 5% → стоп |
| Spam complaints | < 0.1% | ≥ 0.5% → стоп |
| Open rate (mail.ru/Яндекс) | 10–20% | < 5% → проверить что Gmail не в спаме |
| Reply rate | цель ≥ 3% | < 1% → пересмотреть шаблон |

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

Ищу контакты мастерских в {city} и области, которым нужна
качественная ретушь портретов для гравировки на памятниках.

Беру сложные случаи: старые фото, низкое разрешение,
повреждённые снимки. Нейросети + ручная доработка.
Срок — 12–24 часа, срочно — 3–6 часов. Цена — от 700 ₽.

Готов сделать 1–2 пробных бесплатно — на ваших реальных
исходниках, без обязательств.

Примеры работ: https://retouchgrav.netlify.app

Александр
Telegram: @ganjavagen · WhatsApp: +84 946 943 543

---
Если не актуально — ответьте «нет», больше не напишу.
Отписаться: {unsubscribe_url}
```

### 4.2 `cold_email_marquiz` — для Marquiz + TG (Волна 1)

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

Ищу контакты мастерских в {city} и области, которым нужна
качественная ретушь портретных фото для гравировки на памятниках.

Беру всё что сложно: старые снимки 80-х, фото на документах,
групповые — когда нужно вырезать одного человека, низкое разрешение.

Нейросети + ручная доработка. 12–24 часа, срочно 3–6 часов.
Цена — от 700 ₽, оплата после результата для новых клиентов.

Начнём с бесплатной пробы: пришлите 1–2 ваших текущих исходника —
покажу результат.

Примеры работ: https://retouchgrav.netlify.app

Александр
Telegram: @ganjavagen · WhatsApp: +84 946 943 543

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

**Реальность:** при 25/25 писем на каждую тему статистическая значимость минимальна. 1 ответ = 4% — это шум.

**Практический критерий:**

- Если одна тема набрала **≥ 2 ответа**, а другая **0** — используем первую
- Если обе темы дали **0 ответов** за 5 дней — проблема в теле письма или домене, не в теме. Пересматриваем письмо, не запускаем волны
- Если обе дали **1 ответ** — **ничья**, используем тему A (по умолчанию)

Никаких процентов и «превышение на 50%» на выборке из 25 — это иллюзия точности.

---

## 5. Технический план

### Текущее состояние кода (что уже есть)

| Компонент | Статус |
|-----------|--------|
| `CrmEmailCampaignRow.subject_a` / `subject_b` | ✅ В ORM + миграция |
| `CrmTemplateRow.render()` + `render_subject()` | ✅ Полная реализация |
| Campaign lock (Python `threading.Lock()`) | ✅ Потокобезопасный |
| Атомарный `UPDATE ... WHERE status NOT IN (...)` | ✅ |
| Tracking pixel + bot-фильтрация | ✅ |
| SMTP retry на `SMTPTemporaryError` | ✅ |
| Stale campaign watchdog (`POST /campaigns/stale`) | ✅ Ручной |
| `EmailSender._smtp_send` | ⚠️ Использует `SMTP+starttls()` — не работает с портом 465 |

### Что нужно реализовать

---

### Задача 1: Unsubscribe — токен + эндпоинт

**Проблема v6:** отписка через `tracking_id` письма — хрупко при нескольких письмах.
**Решение:** постоянный `unsubscribe_token` в `CrmContactRow`.

#### 1.1 Миграция Alembic

```python
# alembic/versions/xxxx_add_unsubscribe_token.py

def upgrade():
    op.add_column(
        "crm_contacts",
        sa.Column("unsubscribe_token", sa.String, nullable=True, unique=True)
    )
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

#### 1.2 ORM

```python
# granite/database.py — CrmContactRow
import secrets

class CrmContactRow(Base):
    # ... существующие поля ...
    unsubscribe_token = Column(
        String,
        nullable=False,
        default=lambda: secrets.token_hex(16),
        unique=True,
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

_UNSUBSCRIBE_PAGE = """<!DOCTYPE html>
<html><body style="font-family:sans-serif;max-width:500px;margin:60px auto;text-align:center">
<h2>RetouchGrav</h2>
<p>{msg}</p>
{extra}
</body></html>"""

@router.get("/unsubscribe/{token}", response_class=HTMLResponse)
def unsubscribe_page(token: str, db: Session = Depends(get_db)):
    """Страница подтверждения отписки. НЕ отписывает при GET —
    защита от префетча почтовыми клиентами."""
    contact = db.query(CrmContactRow).filter_by(unsubscribe_token=token).first()
    if not contact:
        raise HTTPException(404, "Ссылка недействительна")

    if contact.stop_automation:
        return _UNSUBSCRIBE_PAGE.format(
            msg="Вы уже отписаны. Писем больше не будет.",
            extra="",
        )

    # Показать кнопку подтверждения
    return _UNSUBSCRIBE_PAGE.format(
        msg="Подтвердите отписку от рассылки RetouchGrav.",
        extra=f'''
        <form method="POST" action="/api/v1/unsubscribe/{token}">
          <button type="submit" style="padding:10px 24px;font-size:16px;cursor:pointer">
            Отписаться
          </button>
        </form>''',
    )


@router.post("/unsubscribe/{token}", response_class=HTMLResponse)
def unsubscribe_confirm(token: str, db: Session = Depends(get_db)):
    """Собственно отписка — только POST."""
    contact = db.query(CrmContactRow).filter_by(unsubscribe_token=token).first()
    if not contact:
        raise HTTPException(404, "Ссылка недействительна")

    if contact.stop_automation:
        return _UNSUBSCRIBE_PAGE.format(msg="Вы уже отписаны.", extra="")

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

    return _UNSUBSCRIBE_PAGE.format(
        msg="Вы успешно отписаны. Больше писем не будет.",
        extra="",
    )
```

**Регистрация маршрута** — в `app.py` добавить:
```python
from granite.api import unsubscribe
app.include_router(unsubscribe.router, prefix="/api/v1", tags=["unsubscribe"])
```

**Auth bypass** — в `api_key_auth_middleware` добавить:
```python
# Отписка доступна без API-ключа (клики из email)
or request.url.path.startswith("/api/v1/unsubscribe/")
```

#### 1.4 Плейсхолдер `{unsubscribe_url}` в sender.py

```python
# В методе send() — перед рендером шаблона:
if contact:
    unsubscribe_url = f"{self.base_url}/api/v1/unsubscribe/{contact.unsubscribe_token}"
else:
    unsubscribe_url = ""
render_kwargs["unsubscribe_url"] = unsubscribe_url
```

`CrmTemplateRow.render()` уже поддерживает произвольные плейсхолдеры — достаточно передать `unsubscribe_url` в kwargs.

---

### Задача 2: Recovery + архитектура отправки

#### 2.1 Recovery при старте сервера

Добавить в `lifespan()` в `app.py` — **не** через `on_event` (депрекейтнут):

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # ... существующая инициализация ...

    # RECOVERY: при рестарте вернуть running → paused
    with db.session_scope() as session:
        stuck = session.query(CrmEmailCampaignRow).filter_by(status="running").all()
        for campaign in stuck:
            campaign.status = "paused"
            logger.warning(
                f"RECOVERY: кампания {campaign.id} '{campaign.name}' "
                f"переведена из running → paused (рестарт сервера)"
            )
        if stuck:
            logger.info(f"RECOVERY: восстановлено {len(stuck)} кампаний")

    yield
    # ... существующая очистка ...
```

#### 2.2 Рефакторинг: BackgroundTask + SSE-поллинг

**Проблема текущей архитектуры:** отправка происходит внутри SSE-генератора. Если клиент закрывает вкладку — SSE-соединение рвётся, отправка останавливается через `GeneratorExit`. Это работает, но хрупко: при проблемах с сетью на клиенте кампания зависает.

**Решение:** отделить отправку (BackgroundTask) от прогресса (SSE-поллинг БД).

**Новый endpoint запуска:**

```python
@router.post("/campaigns/{campaign_id}/run")
async def run_campaign(campaign_id: int, background_tasks: BackgroundTasks, request: Request):
    """Запустить кампанию. Отправка — в BackgroundTask, прогресс — через SSE."""
    SessionFactory = request.app.state.Session

    # 1. Проверить что нет уже запущенной кампании
    check_session = SessionFactory()
    try:
        running = check_session.query(CrmEmailCampaignRow).filter_by(status="running").first()
        if running and running.id != campaign_id:
            raise HTTPException(409, f"Уже запущена кампания #{running.id} '{running.name}'")
    finally:
        check_session.close()

    # 2. Атомарно сменить статус
    pre_session = SessionFactory()
    try:
        result = pre_session.execute(
            sa_text(
                "UPDATE crm_email_campaigns SET status='running', "
                "started_at=COALESCE(started_at, :now), updated_at=:now "
                "WHERE id=:id AND status NOT IN ('running', 'completed')"
            ),
            {"id": campaign_id, "now": datetime.now(timezone.utc)},
        )
        pre_session.commit()
        if result.rowcount == 0:
            raise HTTPException(400, "Кампания не может быть запущена")
    finally:
        pre_session.close()

    # 3. Запустить фоновую задачу
    background_tasks.add_task(_run_campaign_background, campaign_id, SessionFactory)
    return {"status": "started", "campaign_id": campaign_id}
```

**Фоновая задача отправки:**

```python
def _run_campaign_background(campaign_id: int, SessionFactory) -> None:
    """Фоновая отправка писем. Создаёт свою сессию БД."""
    import time, random
    from granite.email.sender import EmailSender
    from granite.email.validator import validate_recipients

    EMAIL_DELAY_MIN = int(os.environ.get("EMAIL_DELAY_MIN", "45"))
    EMAIL_DELAY_MAX = int(os.environ.get("EMAIL_DELAY_MAX", "120"))
    EMAIL_DAILY_LIMIT = int(os.environ.get("EMAIL_DAILY_LIMIT", "50"))

    session = SessionFactory()
    sender = EmailSender()

    try:
        campaign = session.get(CrmEmailCampaignRow, campaign_id)
        if not campaign or campaign.status != "running":
            return

        template = session.query(CrmTemplateRow).filter_by(name=campaign.template_name).first()
        if not template:
            campaign.status = "error"
            session.commit()
            return

        recipients = _get_campaign_recipients(campaign, session)

        # Валидация получателей
        valid, warnings = validate_recipients(recipients)
        if warnings:
            logger.warning(
                f"Кампания {campaign_id}: пропущено {len(warnings)} получателей — "
                + ", ".join(w["reason"] for w in warnings[:5])
            )

        from_name = os.environ.get("FROM_NAME", "")
        sent = campaign.total_sent or 0

        for company, enriched, contact, email_to in valid:
            # Проверить паузу/отмену
            session.refresh(campaign)
            if campaign.status != "running":
                logger.info(f"Кампания {campaign_id}: статус '{campaign.status}', выход")
                return

            # Глобальный дневной лимит
            last_24h = datetime.now(timezone.utc) - timedelta(hours=24)
            sent_today = (
                session.query(func.count(CrmEmailLogRow.id))
                .filter(CrmEmailLogRow.sent_at >= last_24h)
                .scalar()
            )
            if sent_today >= EMAIL_DAILY_LIMIT:
                campaign.status = "paused_daily_limit"
                campaign.updated_at = datetime.now(timezone.utc)
                session.commit()
                logger.info(f"Кампания {campaign_id}: дневной лимит ({EMAIL_DAILY_LIMIT})")
                return

            # Рендер шаблона
            city = company.city or ""
            render_kwargs = {
                "from_name": from_name,
                "city": city,
                "company_name": company.name_best or "",
                "website": company.website or "",
                "unsubscribe_url": f"{sender.base_url}/api/v1/unsubscribe/{contact.unsubscribe_token}" if contact else "",
            }

            # A/B тема
            subject = get_ab_subject(company.id, campaign.subject_a, campaign.subject_b, template, render_kwargs)

            rendered = template.render(**render_kwargs)

            # Отправка
            try:
                if template.body_type == "html":
                    from granite.utils import html_to_plain_text
                    body_text = html_to_plain_text(rendered)
                    tracking_id = sender.send(
                        company_id=company.id, email_to=email_to,
                        subject=subject, body_text=body_text, body_html=rendered,
                        template_name=template.name, db_session=session,
                        campaign_id=campaign.id,
                    )
                else:
                    tracking_id = sender.send(
                        company_id=company.id, email_to=email_to,
                        subject=subject, body_text=rendered,
                        template_name=template.name, db_session=session,
                        campaign_id=campaign.id,
                    )

                if tracking_id:
                    sent += 1
                    campaign.total_sent = sent
                    session.add(CrmTouchRow(
                        company_id=company.id, channel="email",
                        direction="outgoing", subject=subject,
                        body=f"[tracking_id={tracking_id}]",
                    ))
                    if contact:
                        from granite.api.stage_transitions import apply_outgoing_touch
                        apply_outgoing_touch(contact, "email")
                    # v9: commit после КАЖДОГО письма — не теряем данные при краше
                    campaign.updated_at = datetime.now(timezone.utc)
                    session.commit()
                else:
                    campaign.total_errors = (campaign.total_errors or 0) + 1
                    session.commit()

            except Exception as e:
                logger.error(f"Ошибка отправки company_id={company.id}: {e}")
                campaign.total_errors = (campaign.total_errors or 0) + 1
                session.commit()

            # Задержка
            delay = random.randint(EMAIL_DELAY_MIN, EMAIL_DELAY_MAX)
            time.sleep(delay)

        # Цикл завершён
        campaign.status = "completed"
        campaign.completed_at = datetime.now(timezone.utc)
        session.commit()

    except Exception as e:
        logger.exception(f"Критическая ошибка в кампании {campaign_id}: {e}")
        try:
            campaign = session.get(CrmEmailCampaignRow, campaign_id)
            if campaign:
                campaign.status = "error"
                session.commit()
        except Exception:
            pass
    finally:
        session.close()
```

**SSE-поллинг прогресса (читает только БД):**

```python
@router.get("/campaigns/{campaign_id}/progress")
async def campaign_progress(campaign_id: int, request: Request):
    """SSE: прогресс из БД каждые 3 секунды."""
    SessionFactory = request.app.state.Session

    async def generate():
        while True:
            session = SessionFactory()
            try:
                campaign = session.get(CrmEmailCampaignRow, campaign_id)
                if not campaign:
                    yield f"data: {json.dumps({'error': 'not_found'})}\n\n"
                    return

                yield f"data: {json.dumps({
                    'status': campaign.status,
                    'sent': campaign.total_sent or 0,
                    'errors': campaign.total_errors or 0,
                    'opened': campaign.total_opened or 0,
                    'replied': campaign.total_replied or 0,
                })}\n\n"

                if campaign.status in ("completed", "error", "paused", "paused_daily_limit"):
                    return
            finally:
                session.close()

            await asyncio.sleep(3)

    return StreamingResponse(generate(), media_type="text/event-stream")
```

#### 2.3 Статус `paused_daily_limit`

Кампания переходит в `paused_daily_limit` при достижении дневного лимита. Ручной перезапуск на следующий день — достаточно. В UI: показать причину паузы и кнопку «Продолжить».

Статус `paused_daily_limit` входит в группу `paused`-подобных — разрешён перезапуск:

```python
if campaign.status not in ("draft", "paused", "paused_daily_limit"):
    raise HTTPException(400, "Кампания не может быть запущена")
```

---

### Задача 3: A/B — детерминированное распределение

#### 3.1 Колонка `total_errors`

```python
# granite/database.py — CrmEmailCampaignRow
total_errors = Column(Integer, default=0)
```

Миграция:
```bash
uv run cli.py db migrate "add total_errors to campaigns"
uv run cli.py db upgrade head
```

#### 3.2 Функция A/B-распределения

`subject_a` и `subject_b` уже есть в ORM. Если `subject_b` задан — кампания A/B-тест.

```python
# granite/api/campaigns.py (или granite/email/sender.py)

def get_ab_subject(
    company_id: int,
    subject_a: str | None,
    subject_b: str | None,
    template: CrmTemplateRow,
    render_kwargs: dict,
) -> str:
    """Детерминированное A/B распределение по company_id.

    Если у кампании задан subject_b — делим 50/50 через MD5-хеш.
    Если subject_b нет — используем тему из шаблона.
    """
    # Приоритет: subject_a/b из кампании > тема из шаблона
    a = subject_a or template.render_subject(**render_kwargs)

    if not subject_b:
        return a

    import hashlib
    hash_val = int(hashlib.md5(str(company_id).encode()).hexdigest(), 16)
    return a if hash_val % 2 == 0 else subject_b
```

---

### Задача 4: Валидатор получателей

Файл `granite/email/validator.py`:

```python
"""Валидация получателей перед отправкой."""
import re

# Домены агрегаторов — не мастерские
AGGREGATOR_DOMAINS = frozenset({
    "memorial.ru", "vsepamyatniki.ru", "obeliski.ru",
    "mipomnim.ru", "uznm.ru", "monuments.su",
    "tsargranit.ru", "alshei.ru",
})

_EMAIL_RE = re.compile(r"^[\w.+-]+@[\w.-]+\.\w{2,}$")


def validate_recipients(
    recipients: list[tuple],
) -> tuple[list[tuple], list[dict]]:
    """Возвращает (valid, warnings)."""
    valid = []
    warnings = []

    for company, enriched, contact, email_to in recipients:
        reason = _check_recipient(company, contact, email_to)
        if reason:
            warnings.append({
                "company_id": company.id,
                "name": company.name_best,
                "reason": reason,
            })
        else:
            valid.append((company, enriched, contact, email_to))

    return valid, warnings


def _check_recipient(company, contact, email_to: str) -> str | None:
    """None = валиден, строка = причина пропуска."""

    # Формат email
    if not email_to or not _EMAIL_RE.match(email_to):
        return f"невалидный email ({email_to})"

    # Агрегатор
    domain = email_to.split("@")[-1].lower()
    if domain in AGGREGATOR_DOMAINS:
        return f"агрегатор ({domain})"

    # Отписан
    if contact and contact.stop_automation:
        return "отписан"

    # Пустое название
    name = (company.name_best or "").strip()
    if not name:
        return "пустое название"
    if len(name) > 80:
        return "название слишком длинное (SEO?)"

    return None
```

---

### Задача 5: Воронка — follow-up + авто-отмена

#### 5.1 Создание follow-up задачи при открытии письма

Добавить в `granite/api/tracking.py` — после обновления `contact.funnel_stage`:

```python
# После: if contact.funnel_stage == "email_sent": contact.funnel_stage = "email_opened"

_maybe_create_followup_task(contact.company_id, db)


def _maybe_create_followup_task(company_id: int, db: Session) -> None:
    """Создать follow-up задачу через 7 дней после открытия письма."""
    from granite.database import CrmTaskRow

    contact = db.get(CrmContactRow, company_id)
    if not contact:
        return

    # Не создавать если уже есть активная follow-up задача
    existing = db.query(CrmTaskRow).filter(
        CrmTaskRow.company_id == company_id,
        CrmTaskRow.task_type == "follow_up",
        CrmTaskRow.status == "pending",
    ).first()
    if existing:
        return

    # Не создавать если уже ответил
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

**Примечание:** follow-up создаётся только при открытии. Получатели, которые не открыли письмо, follow-up не получают. Это осознанное решение — не дублируем тем, кто проигнорировал.

#### 5.2 Авто-отмена follow-up при смене стадии

Добавить в `granite/api/stage_transitions.py` (или `companies.py`):

```python
CANCEL_FOLLOWUP_ON_STAGES = {"replied", "interested", "not_interested", "unreachable"}

# В apply_incoming_touch() — после установки funnel_stage:
if new_stage in CANCEL_FOLLOWUP_ON_STAGES:
    cancelled = (
        db.query(CrmTaskRow)
        .filter(
            CrmTaskRow.company_id == company_id,
            CrmTaskRow.status == "pending",
            CrmTaskRow.task_type == "follow_up",
        )
        .update({"status": "cancelled", "completed_at": datetime.now(timezone.utc)})
    )
    if cancelled:
        logger.info(f"company_id={company_id}: отменено {cancelled} follow-up (→ {new_stage})")
```

#### 5.3 Воронка после ответа

```
replied → interested  (обсуждаем условия)
replied → not_interested  (отказ)
interested → [ручная работа вне CRM]
```

Никаких автоматических действий при `interested`.

---

### Задача 6: Парсинг bounce-уведомлений

Файл `scripts/process_bounces.py`:

```python
"""
Читает IMAP-ящик (Gmail), ищет bounce-уведомления,
помечает компании как unreachable.

Запуск:
  uv run python -m scripts.process_bounces
"""
import email
import imaplib
import os
import re
from datetime import datetime, timezone
from loguru import logger


IMAP_HOST = os.getenv("IMAP_HOST", "imap.gmail.com")
IMAP_USER = os.getenv("SMTP_USER")
IMAP_PASS = os.getenv("SMTP_PASS")

# SMTP-коды hard bounce — ищем как отдельные числа, не подстроки
_HARD_BOUNCE_CODES = re.compile(
    r"\b550\b|\b551\b|\b553\b",
)
_HARD_BOUNCE_PHRASES = [
    "user unknown",
    "no such user",
    "unknown user",
    "mailbox not found",
    "address rejected",
    "recipient invalid",
    "recipient not found",
    "no such recipient",
]


def process_bounces() -> int:
    if not all([IMAP_HOST, IMAP_USER, IMAP_PASS]):
        logger.error("IMAP_HOST / SMTP_USER / SMTP_PASS не заданы")
        return 0

    # v9: Используем get_engine() из app, а не Database() напрямую
    from granite.database import get_engine, CrmEmailLogRow, CrmContactRow
    from sqlalchemy.orm import Session

    engine = get_engine()
    processed = 0

    with imaplib.IMAP4_SSL(IMAP_HOST) as imap:
        imap.login(IMAP_USER, IMAP_PASS)
        imap.select("INBOX")

        # Искать bounce: MAILER-DAEMON + Delivery Status + Gmail NDR
        uid_list = []
        for criteria in [
            '(FROM "MAILER-DAEMON" UNSEEN)',
            '(SUBJECT "Delivery Status Notification" UNSEEN)',
            '(FROM "mailer-daemon@googlemail.com" UNSEEN)',
            '(SUBJECT "Undelivered" UNSEEN)',
        ]:
            _, uids = imap.search(None, criteria)
            if uids[0]:
                uid_list.extend(uids[0].split())

        # Дедупликация UID
        seen_uids = set()
        for uid in uid_list:
            if uid in seen_uids:
                continue
            seen_uids.add(uid)

            _, data = imap.fetch(uid, "(RFC822)")
            if not data or not data[0]:
                continue
            raw = data[0][1]
            msg = email.message_from_bytes(raw)

            bounce_email = _extract_bounced_email(msg)
            if not bounce_email:
                continue

            if not _is_hard_bounce(msg):
                continue

            with Session(engine) as session:
                log = (
                    session.query(CrmEmailLogRow)
                    .filter_by(email_to=bounce_email)
                    .order_by(CrmEmailLogRow.sent_at.desc())
                    .first()
                )
                if log and log.status != "bounced":
                    log.status = "bounced"
                    log.bounced_at = datetime.now(timezone.utc)

                    contact = session.query(CrmContactRow).filter_by(
                        company_id=log.company_id
                    ).first()
                    if contact:
                        contact.funnel_stage = "unreachable"
                        contact.stop_automation = True

                    session.commit()
                    processed += 1
                    logger.info(f"Bounce: {bounce_email} → company #{log.company_id}")

            imap.store(uid, "+FLAGS", "\\Seen")

    engine.dispose()
    logger.info(f"Обработано bounce: {processed}")
    return processed


def _extract_bounced_email(msg) -> str | None:
    """Извлечь email получателя из bounce-уведомления."""
    for part in msg.walk():
        if part.get_content_type() in ("message/delivery-status", "text/plain"):
            content = part.get_payload(decode=True)
            if content:
                text = content.decode("utf-8", errors="ignore")
                match = re.search(
                    r"Final-Recipient:.*?<?([\w._%+-]+@[\w.-]+\.\w+)>?", text
                )
                if match:
                    return match.group(1).lower()
    return None


def _is_hard_bounce(msg) -> bool:
    """Определить hard bounce по SMTP-коду или фразе."""
    text = msg.as_string().lower()
    # Коды — regex с границами слов, чтобы «550» не совпадало с IP
    if _HARD_BOUNCE_CODES.search(text):
        return True
    return any(phrase in text for phrase in _HARD_BOUNCE_PHRASES)


if __name__ == "__main__":
    process_bounces()
```

---

### Задача 7: Фикс SEO-regex — убрать «гранит» + починить `памятник[аиы]?`

**Проблема v8:** две проблемы в `_SEO_TITLE_PATTERN`:

1. «Гранит» в 4 паттернах — нормальная часть названия в нише
2. `памятник[аиы]?\s*(?:из|в|на|от|и)?\s*` флагает «Гранит-Мастер ООО Памятники» — слово «Памятники» в конце названия компании не SEO

**7.1 Убираем «гранит» из 4 паттернов:**

| # | Паттерн | Почему убрать | Покрытие сохранено |
|---|---------|---------------|-------------------|
| 1 | `изготовлен.*(?:памятник\|надгробие\|гранит)` | «гранит» как альтернатива избыточна — `изготовлен.*памятник` уже ловит | Основной паттерн `изготовлен.*памятник` остаётся |
| 2 | `гранитн[ые]+\s*мастерск` | «Гранитные мастерские» — реальное название в нише | Мн.ч. без «гранит» не покрывается, но это допустимо — «Мастерские памятников» ловится через `памятник` |
| 3 | `памятниковизгранита\|памятникиизгранита` | Слипшиеся слова с «гранит» | Детектор длинных слов (>15 символов) ловит всё равно |
| 4 | `гранитнаямастерская` | Слипшееся «гранитнаямастерская» | Аналогично — ловится детектором длинных слов |

**7.2 Фикс `памятник[аиы]?` — добавляем негативный lookahead:**

Проблема: `памятник[аиы]?\s*(?:из|в|на|от|и)?\s*` совпадает с «Памятники» в «Гранит-Мастер ООО Памятники». Это не SEO — обычное слово в названии.

Решение: паттерн должен совпадать только если после «памятник[аиы]?» идёт SEO-контекст (предлог + город, или глагол), а не конец строки или юридическая форма.

```python
# Было (v8):
r"памятник[аиы]?\s*(?:из|в|на|от|и)?\s*|"

# Стало (v9):
r"памятник[аиы]?\s*(?:из|в|на|от|и)\s+\S|"   # требует предлог + слово после
```

Ключевое изменение: `(?:из|в|на|от|и)?\s*` → `(?:из|в|на|от|и)\s+\S`
- Убран `?` после группы предлогов — предлог теперь обязателен
- Добавлен `\s+\S` — после предлога должно быть хотя бы одно слово
- Результат: «Памятники» без продолжения больше не флагается, но «Памятники в Москве» и «Памятники из гранита» ловятся

**Итоговый regex после фикса (v9):**

```python
_SEO_TITLE_PATTERN = re.compile(
    r"(?:купить|цен[аыуе]|недорог|заказать|от производитель|"
    r"с установк|на могил|доставк|скидк|каталог|"
    r"памятник[аиы]?\s*(?:из|в|на|от|и)\s+\S|"   # v9: предлог обязателен + слово после
    r"изготовлен.*(?:памятник|надгробие)|"         # без «гранит»
    r"памятники\s*(?:в|из|на|и)\s+\S|"            # v9: + слово после предлога
    r"памятники\s*(?:на\s*кладбищ)|"
    r"изготовление\s*памятников|"
    r"памятники\s*и\s*надгробия|"
    r"производство\s*памятников|"
    # Слипшиеся слова — «гранит» убрано, ловится детектором >15 символов
    r"изготовлениепамятников|установкапамятников|"
    r"памятникинамогилу|купитьпамятник|"
    r"заказатьпамятник)",
    re.IGNORECASE,
)
```

**Что НЕ трогаем:**
- `_RU_KEYWORDS` в `web_search.py` — проверка релевантности, «гранит» там правильный
- `config.yaml` queries — поисковые запросы
- `_AGGREGATOR_NAMES` — не связано

**Побочные эффекты и тесты:**

1. `is_seo_title("Гранитные мастерские России")` → было `True`, станет `False`. Ожидаемо
2. `is_seo_title("Гранит-Мастер")` → было `False`, остаётся `False` — не затронуто
3. `is_seo_title("Гранит-Мастер ООО Памятники")` → было `True` (из-за `памятник[аиы]?`), станет `False`. Ожидаемо — «Памятники» без предлога после = не SEO
4. `is_seo_title("Памятники в Екатеринбурге")` → `True` (предлог «в» + слово). Покрытие сохранено
5. `is_seo_title("Памятники из гранита дёшево")` → `True` (предлог «из» + слово). Покрытие сохранено
6. Слипшиеся «памятниковизгранита» всё ещё ловятся детектором длинных слов (>15 символов)
7. Тест `test_гранитные_мастерские` обновить: ожидаем `False`
8. Тест `test_longest_real_name_wins` обновить: «Гранит-Мастер ООО Памятники» → `name_best`, не SEO

---

### Задача 8: Фикс SMTP_SSL — порт 465

**Проблема v8:** sender.py использует `smtplib.SMTP(port=587) + starttls()`, а .env задаёт `SMTP_PORT=465`. Порт 465 — implicit TLS, для него нужен `smtplib.SMTP_SSL`, а не `SMTP` + `STARTTLS`.

Текущий код (`granite/email/sender.py`):
```python
# НЕПРАВИЛЬНО для порта 465:
with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
    server.ehlo()
    server.starttls()    # ← на порту 465 SSL уже установлен, starttls() упадёт
    server.login(...)
```

**Исправление:**

```python
# granite/email/sender.py — метод _smtp_send

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(min=2, max=30),
    retry=retry_if_exception(_is_temporary_smtp_error),
    reraise=True,
)
def _smtp_send(self, email_to: str, msg: MIMEMultipart) -> None:
    """SMTP-отправка с retry на временные ошибки.

    Поддерживает два режима:
    - Порт 465: SMTP_SSL (implicit TLS) — Gmail по умолчанию
    - Порт 587: SMTP + STARTTLS (explicit TLS)
    """
    if self.smtp_port == 465:
        with smtplib.SMTP_SSL(self.smtp_host, self.smtp_port) as server:
            server.login(self.smtp_user, self.smtp_pass)
            server.sendmail(self.smtp_user, [email_to], msg.as_bytes())
    else:
        with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(self.smtp_user, self.smtp_pass)
            server.sendmail(self.smtp_user, [email_to], msg.as_bytes())
```

**Также обновить дефолтный порт:**

```python
# Было:
self.smtp_port = int(os.environ.get("SMTP_PORT", "587"))
# Стало:
self.smtp_port = int(os.environ.get("SMTP_PORT", "465"))
```

---

### Задача 9: Обнаружение ответов — IMAP reply parser

**Проблема v8:** воронка упоминает стадии `replied` → `interested`/`not_interested`, но нет кода, который переводит контакт в `replied`. Следующие follow-up'ы не отменяются автоматически, потому что стадия никогда не переходит в `replied`.

**Решение:** скрипт `scripts/process_replies.py` — аналогичен `process_bounces.py`, но ищет ответы от людей.

Файл `scripts/process_replies.py`:

```python
"""
Читает IMAP-ящик (Gmail), ищет ответы на отправленные письма,
переводит контакты в replied.

Запуск:
  uv run python -m scripts.process_replies
"""
import email
import imaplib
import os
import re
from datetime import datetime, timezone
from loguru import logger


IMAP_HOST = os.getenv("IMAP_HOST", "imap.gmail.com")
IMAP_USER = os.getenv("SMTP_USER")
IMAP_PASS = os.getenv("SMTP_PASS")

# Предметы, которые точно не ответы от людей
_SKIP_SUBJECTS = re.compile(
    r"delivery status|undelivered|mailer-daemon|out of office|"
    r"автоответ|автоматическ|уведомлен",
    re.IGNORECASE,
)


def process_replies() -> int:
    if not all([IMAP_HOST, IMAP_USER, IMAP_PASS]):
        logger.error("IMAP_HOST / SMTP_USER / SMTP_PASS не заданы")
        return 0

    from granite.database import get_engine, CrmEmailLogRow, CrmContactRow, CrmTouchRow
    from sqlalchemy.orm import Session

    engine = get_engine()
    processed = 0

    with imaplib.IMAP4_SSL(IMAP_HOST) as imap:
        imap.login(IMAP_USER, IMAP_PASS)
        imap.select("INBOX")

        # Искать входящие письма, где мы не в копии и не от MAILER-DAEMON
        _, uids = imap.search(
            None,
            '(UNSEEN NOT FROM "mailer-daemon" NOT FROM "mailer-daemon@googlemail.com")',
        )
        if not uids[0]:
            logger.info("Нет новых входящих писем")
            engine.dispose()
            return 0

        for uid in uids[0].split():
            _, data = imap.fetch(uid, "(RFC822)")
            if not data or not data[0]:
                continue
            raw = data[0][1]
            msg = email.message_from_bytes(raw)

            # Проверяем что это ответ, а не bounce/OOO
            subject = msg.get("Subject", "")
            if _SKIP_SUBJECTS.search(subject):
                continue

            # Извлечь email отправителя
            from_header = msg.get("From", "")
            reply_email = _extract_email(from_header)
            if not reply_email:
                continue

            # Найти контакт по email
            with Session(engine) as session:
                log = (
                    session.query(CrmEmailLogRow)
                    .filter_by(email_to=reply_email)
                    .order_by(CrmEmailLogRow.sent_at.desc())
                    .first()
                )
                if not log:
                    continue

                contact = session.query(CrmContactRow).filter_by(
                    company_id=log.company_id
                ).first()
                if not contact:
                    continue

                if contact.funnel_stage in ("replied", "interested", "not_interested", "unreachable"):
                    continue

                # Тело ответа (для заметки)
                body_text = _get_text_body(msg)[:200] if _get_text_body(msg) else ""

                contact.funnel_stage = "replied"
                contact.updated_at = datetime.now(timezone.utc)

                # Обновить статус лога
                log.status = "replied"
                log.replied_at = datetime.now(timezone.utc)

                session.add(CrmTouchRow(
                    company_id=contact.company_id,
                    channel="email",
                    direction="incoming",
                    subject=subject[:200] if subject else "(без темы)",
                    body=body_text or "Ответ на email",
                ))
                session.commit()

                processed += 1
                logger.info(f"Reply: {reply_email} → company #{contact.company_id} → replied")

            imap.store(uid, "+FLAGS", "\\Seen")

    engine.dispose()
    logger.info(f"Обработано reply: {processed}")
    return processed


def _extract_email(header: str) -> str | None:
    """Извлечь email из заголовка From."""
    match = re.search(r'<([\w._%+-]+@[\w.-]+\.\w+)>', header)
    if match:
        return match.group(1).lower()
    match = re.search(r'([\w._%+-]+@[\w.-]+\.\w+)', header)
    if match:
        return match.group(1).lower()
    return None


def _get_text_body(msg) -> str | None:
    """Извлечь текстовое тело письма."""
    for part in msg.walk():
        if part.get_content_type() == "text/plain":
            payload = part.get_payload(decode=True)
            if payload:
                return payload.decode("utf-8", errors="ignore")
    return None


if __name__ == "__main__":
    process_replies()
```

**Cron-запуск (опционально):** `process_replies.py` запускать каждые 15–30 минут в рабочее время, или вручную при проверке почты.

**Ограничения:**
- Не отличает «нет, не интересно» от «да, давайте обсудим» — оба переводят в `replied`. Дальнейшая квалификация — вручную
- Если человек пишет с другого email — не найдём. Это нормально для cold outreach
- Не парсит цепочки (thread) — только первое письмо в inbox

---

### Задача 10: Фронтенд — обновления

#### 10.1 Wizard создания кампании

```tsx
// Шаг — Шаблон + A/B
<FormField name="subject_a" label="Тема письма" required />

<Collapsible>
  <CollapsibleTrigger>
    + Добавить вариант темы B (A/B тест)
  </CollapsibleTrigger>
  <CollapsibleContent>
    <FormField name="subject_b" label="Тема B" />
    <p className="text-xs text-muted">
      Компании делятся 50/50 между A и B. Победитель — по количеству ответов.
    </p>
  </CollapsibleContent>
</Collapsible>
```

#### 10.2 Карточка кампании

```tsx
// Прогресс — поллинг SSE
<ProgressBar value={campaign.total_sent} max={campaign.total_recipients} />

// Причина паузы
{campaign.status === "paused_daily_limit" && (
  <Alert>Достигнут дневной лимит. Продолжите завтра.</Alert>
)}

// Предупреждения валидатора
{campaign.warnings?.length > 0 && (
  <Collapsible>
    <CollapsibleTrigger>
      Пропущено {campaign.warnings.length} получателей
    </CollapsibleTrigger>
    <CollapsibleContent>
      {campaign.warnings.map(w => (
        <div key={w.company_id}>{w.name}: {w.reason}</div>
      ))}
    </CollapsibleContent>
  </Collapsible>
)}
```

---

## 6. Roadmap по дням

### День 1 — Инфраструктура + критические фиксы (0 писем)

```
[ ] Задача 8: фикс SMTP_SSL в sender.py (порт 465 + SMTP_SSL)
[ ] Задача 7: фикс SEO-regex (убрать «гранит» + починить памятник[аиы]?)
[ ] Обновить тесты: test_seo_name_extraction.py, test_merger.py
[ ] Запустить полный набор тестов
[ ] Gmail: 2FA + App Password
[ ] .env: SMTP + IMAP + BASE_URL
[ ] Тест: отправить письмо себе через sender.py (с портом 465)
[ ] Проверить заголовки: SPF pass, DKIM pass (google.com)
[ ] Задача 1: миграция unsubscribe_token, эндпоинт /unsubscribe/{token}
[ ] Задача 2.1: recovery в lifespan()
[ ] Cloudflare Tunnel: {BASE_URL}/health → ok
[ ] Сквозной тест: отправить → открыть → tracking → отписаться
```

### День 2 — Рефакторинг отправки + Фаза 0 старт (10 писем)

```
[ ] Задача 2.2: BackgroundTask + SSE-поллинг
[ ] Задача 3: total_errors + A/B-распределение
[ ] Задача 4: validator.py
[ ] Создать кампанию: 10 получателей, сегмент A, тема A vs B
[ ] Запустить, проверить логи
```

### День 3–4 — Фаза 0, ещё 40 писем

```
[ ] 20 писем / день
[ ] Задача 5: follow-up при открытии + авто-отмена
[ ] Задача 6: process_bounces.py
[ ] Задача 9: process_replies.py
[ ] Мониторинг bounce rate
```

### День 5–6 — Пауза, мониторинг

```
[ ] 0 писем
[ ] Ответить всем кто написал
[ ] process_replies.py — обработать ответы
[ ] Оценить тему A vs B (практический критерий из 4.4)
[ ] Задача 10: обновления фронтенда
```

### День 7–9 — Волна 1: Marquiz + Bitrix

```
[ ] Проверить список Marquiz (22 компании) — убрать SEO-имена
[ ] Кампания Marquiz: cold_email_marquiz, 22 получателя
[ ] 30 писем / день
[ ] Кампания Bitrix: cold_email_v1 (победитель), 41 получатель
```

### День 10+ — Волны 2–4, масштаб

```
[ ] 50 писем / день (рабочий режим)
[ ] Волна 2: остаток A (60–80 компаний)
[ ] Волна 3: сегмент B (259 компаний)
[ ] Follow-up через 7 дней
[ ] process_bounces.py — запускать каждые 2–3 дня
[ ] process_replies.py — запускать каждый день
```

---

## Приложение: переменные окружения

```bash
# .env

# SMTP (Gmail)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=465                        # v9: 465 = SMTP_SSL (implicit TLS)
SMTP_USER=ai.punk.facility@gmail.com
SMTP_PASS=xxxx xxxx xxxx xxxx    # App Password (16 символов)

# Отправка
FROM_NAME=Александр
BASE_URL=https://crm.yourdomain.com   # Cloudflare Tunnel
EMAIL_DELAY_MIN=45
EMAIL_DELAY_MAX=120
EMAIL_DAILY_LIMIT=50

# IMAP (для bounce + reply, Gmail)
IMAP_HOST=imap.gmail.com

# CRM
GRANITE_API_KEY=             # опционально
```

---

*v9 · 2026-04-26 · v8 + аудит: SMTP_SSL fix (критический), SEO-pattern `памятник[аиы]?` fix, reply detection, commit-per-email, process_bounces uses get_engine()*
