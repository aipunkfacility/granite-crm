# RetouchGrav — Email Campaign Dev Plan v4
### Критика v2/v3 + мой план

> Александр · @ganjavagen · +7 (494) 694-35-43  
> База: ~6 000 компаний → **434 приоритетных цели** (A+B, не-сеть, валидный email)

---

## Часть 1. Что не так в v2 и v3

Прежде чем строить — разобраться, где предыдущие планы ошибаются или умалчивают.

### 1.1 Математика задержек никто не посчитал

v2 предлагает `EMAIL_DELAY_MIN=45, EMAIL_DELAY_MAX=120`. Звучит профессионально. Но:

```
50 писем × random(45..120) сек = 50 × ~82 сек среднее = 4 100 сек = 68 минут
```

Это одна сессия. Пока компьютер работает, SSE держит соединение. Разумно — браузерная вкладка висит час, это нормально.

Но 434 письма при 50 в день = 9 дней. При задержке 82 сек в среднее — каждый день открываем браузер, запускаем кампанию, ждём 68 минут не закрывая вкладку. **Это работает, но надо понимать заранее, а не удивляться в процессе.**

Реальная проблема в другом: текущий `SEND_DELAY=3` в коде означает, что если кто-то уже запустил кампанию через UI — 50 писем уйдут за 3 минуты. Gmail заблокирует аккаунт на следующий день. **Это нужно исправить до первой отправки — это не "приятная доработка", это блокер.**

### 1.2 A/B тест на 22 компаниях статистически бесполезен

Волна 1 — 22 компании. A/B делим 50/50 → 11 получают тему A, 11 — тему B. При open rate 20% это 2–3 открытия на каждый вариант.

**Разница между 2 и 3 открытиями — это не A/B тест, это шум.** Статистической значимости нет ни при каком пороге.

Предложения обоих планов использовать победителя волны 1 для волны 2 — неверно. Нужно накапливать результаты A/B **по всем волнам** как единый эксперимент, а не делать выводы после 22 писем.

### 1.3 Сегментация волн логически противоречива

Волны 1–4 предполагают разные шаблоны для разных сегментов. Но если открываемость у Bitrix выше, чем у Tilda — это может быть из-за темы, а может из-за самих мастерских. **Нельзя менять и аудиторию, и текст одновременно** — это ломает любой A/B тест.

Правильный порядок: сначала найти лучшую тему (фиксируем сегмент, меняем тему), потом тестировать разные сегменты с лучшей темой.

### 1.4 "Follow-up через Telegram" — плохой совет для 2026 года

marketing-strategy.md прямо указывает: Telegram почти полностью заблокирован с февраля 2026 (~100% блокировка медиа/голос, текст через прокси у единиц). Оба плана тем не менее советуют follow-up через TG как основной канал после email.

**Реальная ситуация:** если мастерская открыла письмо и не ответила — следующий шаг это второе email (другой угол), а не TG. TG работает только если клиент сам написал первым.

### 1.5 Воронка после ответа — полностью отсутствует

Оба плана заканчиваются на «получили ответ». Но именно здесь начинается настоящая работа: что говорить, как вести к первому заказу, как перейти от "интересно" к "вот фото". В базе CRM это отражается как переход `replied → interested → client`. Плана действий для этих стадий нет ни в v2, ни в v3.

### 1.6 Слабые темы писем — конкретные примеры

**"Свободная минута? Сделаю пробную ретушь"** — плохо. Звучит неуверенно, как просьба об одолжении. Владелец мастерской ценит время, а "свободная минута" предполагает, что он должен что-то для тебя сделать.

**"Коллеги из {company_name}"** в начале письма — раздражает. В B2B холодной рассылке "коллеги" звучит как попытка создать ложную близость. Лучше просто "Здравствуйте" или конкретное обращение к ситуации.

**"Алексей Финаев, ИНН 775170718553"** — ИНН в подписи письма выглядит странно и не повышает доверие так, как кажется. Самозанятость лучше упомянуть текстом ("оформляю чек через приложение"), чем вставлять ИНН в письмо.

**"20 лет практики"** — если это AI-пайплайн, то "20 лет практики" вводит в заблуждение. Честнее: "специализируюсь на подготовке портретов под гравировку".

### 1.7 `{unsubscribe_url}` — плейсхолдер которого не существует в CRM

Текущие плейсхолдеры в `CrmTemplateRow.render()`: `{from_name}`, `{city}`, `{company_name}`, `{website}`. Нет `{unsubscribe_url}`. Если вставить его в шаблон — в письмо уйдёт буквально строка `{unsubscribe_url}`. Это нужно добавить в рендер перед использованием.

### 1.8 Cloudflare Tunnel — не единственный вариант и не самый простой

Tunnel требует аккаунт Cloudflare, DNS-запись, свой домен. Для старта это лишняя зависимость. Более быстрый вариант: `ngrok` — бесплатно, запускается одной командой, домен фиксируется в платном плане ($8/мес). Для тестирования первых 22–63 писем хватит бесплатного ngrok с временным URL.

### 1.9 В v3 исчезла секция про `EMAIL_SESSION_GAP_HRS`

v2 предлагал минимум 2 часа между сессиями. v3 это убрал без объяснений. Это важный параметр — Gmail смотрит не только на задержки между письмами, но и на паттерн активности аккаунта.

---

## Часть 2. Мой план

### 2.1 Реальное состояние базы (уточнение)

```
Всего в базе:                        ~6 000 компаний
Обработанные города:                 29 из 46
Сегмент A, не-сеть, валидный email:  175
Сегмент B, не-сеть, валидный email:  259
─────────────────────────────────────────────────────
Приоритетная база:                   434 компании
Крупные сети (ручная работа):        8 компаний
```

**База будет расти.** 17 городов ещё не обработаны. После их обработки добавится ещё 100–200+ приоритетных контактов. Планировать рассылку нужно с запасом — архитектура должна легко принимать новые порции компаний в уже идущие кампании или добавлять новые волны.

### 2.2 Пересмотр стратегии волн

Проблема оригинальных волн: они смешивают две разные переменные — **аудиторию** (marquiz, bitrix, tilda) и **текст** (разные темы). Я предлагаю разделить это.

**Фаза 0 — Калибровка (50 писем, 1 волна, 1 неделя)**

Единственная цель: найти лучшую тему письма. Для этого нужна однородная аудитория и только переменная темы.

```
Аудитория: сегмент A, не-сеть, email, любой CMS
Размер: 50 компаний (25 получают тему A, 25 — тему B)
```

50 писем — минимально достаточная выборка для предварительного вывода. При open rate 20% это 5 открытий на вариант — мало, но уже что-то. Главное — это даст первые реальные данные, которых сейчас нет вообще.

Результат фазы 0: понимаем, какое направление темы работает лучше, смотрим первые ответы, корректируем текст.

**Фаза 1 — Основная рассылка (волны по аудитории)**

После калибровки запускаем волны с **фиксированной темой-победителем** и тестируем только текст тела (если хотим).

| Волна | Аудитория | Размер | Особенность |
|-------|-----------|--------|-------------|
| 1 | Marquiz + tg_trust≥2, A+B | 22 | Самые прогретые, отдельный шаблон |
| 2 | Bitrix, A+B | 41 | Деловой тон, {company_name} в теме |
| 3 | Tilda + WordPress, A | 60–80 | Основная масса A |
| 4 | Остаток A + B | 259+ | С победившей темой из фазы 0 |

Волна с Marquiz/tg_trust идёт **отдельно**, потому что там уместен принципиально другой подход — не "я ретушёр", а "вижу, что вы активно развиваете мастерскую". Это не A/B тест с другими волнами — это отдельная стратегия.

**Крупные сети — вручную, вне CRM-кампаний**

Для 8 крупных сетей (danila-master, ritualgranit и др.) — писать от первого лица в головной офис, без трекинга, без CRM-логики. Это переговоры об оптовом контракте, а не холодная рассылка.

### 2.3 Переработанные шаблоны писем

#### Принципы, которые я добавляю

**Не "я занимаюсь X", а "у вас есть проблема Y"** — письмо начинается с ситуации получателя, а не с самопрезентации.

**Конкретная проблема, конкретное решение** — не "ретушь для гравировки вообще", а "фото плохое, семья других не принесёт, я сделаю за сегодня".

**Без ИНН в письме** — это не налоговая декларация. Самозанятость упоминается как "работаю официально, чек через приложение", если спросят.

**"20 лет практики" → конкретнее** — если это AI+ручная, пишем "нейросети + ручная доводка". Честность важнее звучного опыта.

---

#### Шаблон A — Основной (фаза 0, волны 3–4)

Имя в CRM: `cold_email_v1`

```
Тема A: Подготовка фото под гравировку — пришлите самый сложный случай
Тема B: Ретушь под памятник: старые и плохие фото — в день заказа

Здравствуйте.

Меня зовут Александр. Занимаюсь подготовкой портретов для гравировки
на памятниках — нейросети и ручная доводка.

Наверняка бывает: семья приносит единственное старое фото — размытое,
повреждённое, сделанное на кнопочный телефон. И нужно сделать из этого 
что-то, что будет хорошо читаться на камне.

Именно под такие случаи я и работаю.

Для мастерских:
- срок — в день обращения, без выходных
- оплата после того, как увидите результат
- от 10 заказов в неделю — специальные цены

Готов сделать 1–2 пробных бесплатно — на ваших реальных исходниках,
под ваш конкретный станок.

Примеры работ: https://aipunkfacility.github.io/monument-web/

Пришлите фото в ответ или напишите:
Telegram: https://t.me/ganjavagen
WhatsApp: +7 (494) 694-35-43

Александр
ganjavagen@gmail.com

---
Если не актуально — ответьте «нет», больше не напишу.
Отписаться: {unsubscribe_url}
```

---

#### Шаблон B — Для Marquiz/TG (волна 1)

Имя в CRM: `cold_email_marquiz`

Эти мастерские думают о маркетинге — им интересен не просто аутсорс, а партнёр. Письмо должно отражать это.

```
Тема A: Подготовка фото под гравировку — можем разгрузить вас на ретуши
Тема B: Ретушь портретов для вашей мастерской — оплата после результата

Здравствуйте.

Меня зовут Александр. Вижу, что {company_name} развивается — 
это заметно по сайту.

Занимаюсь подготовкой портретных фото для гравировки на памятниках.
Нейросети + ручная доводка. Работаю с мастерскими по всей России.

Если у вас есть поток заказов и ретушь занимает время — готов взять
это на себя. Сроки в день, оплата после результата.

Начнём с бесплатной пробы: пришлите 1–2 ваших текущих исходника,
покажу что получится.

https://aipunkfacility.github.io/monument-web/

Telegram: https://t.me/ganjavagen  
WhatsApp: +7 (494) 694-35-43

Александр

---
Не актуально — напишите «нет».
Отписаться: {unsubscribe_url}
```

---

#### Шаблон C — Для Bitrix (волна 2)

Имя в CRM: `cold_email_bitrix`

Bitrix-мастерские — часто с менеджером или офис-менеджером. Письмо может читать не владелец. Поэтому чуть более формальный тон и чёткая структура.

```
Тема A: {company_name}: аутсорс ретуши под гравировку — в день заказа
Тема B: Подготовка фото для гравировки на памятниках — без предоплаты

Здравствуйте.

Меня зовут Александр. Предлагаю сотрудничество по ретуши портретов
для гравировки на памятниках.

Что делаю:
— восстановление сложных исходников (старые, размытые, повреждённые)
— ретушь под конкретный станок и технологию (лазер / ударный)
— замена фона, одежды, монтаж, сборка в полный рост
— срок в день обращения, оплата после одобрения результата

Для партнёрских мастерских с постоянным потоком — индивидуальные 
условия и выделенный приоритет.

Предлагаю начать с бесплатной пробы: пришлите 1–2 реальных исходника —
покажу результат на вашем материале.

Примеры: https://aipunkfacility.github.io/monument-web/

Telegram: https://t.me/ganjavagen  
WhatsApp: +7 (494) 694-35-43  
Email: ganjavagen@gmail.com

Александр

---
Отписаться: {unsubscribe_url}
```

> ⚠️ `{company_name}` в теме письма C — только после прогона валидатора. Названия-агрегаторы и SEO-заголовки должны быть исключены.

---

#### Follow-up письмо (7 дней без ответа)

Имя в CRM: `follow_up_email_v1`

Важное решение: follow-up — **только email**, потому что TG заблокирован, WA нестабилен. Второе письмо должно быть заметно короче первого и менять угол подачи.

```
Тема: Re: подготовка фото под гравировку

Добрый день.

Писал на прошлой неделе про ретушь портретов для гравировки.

Не хочу надоедать — просто оставлю ссылку на примеры работ,
если будет удобный момент посмотреть:
https://aipunkfacility.github.io/monument-web/

Первый портрет — бесплатно, пришлите в ответ.

Александр · @ganjavagen

---
Отписаться: {unsubscribe_url}
```

Короткость — намеренная. Человек уже видел длинное письмо. Второй раз нужен короткий сигнал, а не повторение первого.

---

### 2.4 Что реально строить — технический план

#### Блокер 0: Случайные задержки (15 минут, до первой отправки)

В `granite/api/campaigns.py` найти `SEND_DELAY` и заменить:

```python
# Было:
import time
time.sleep(SEND_DELAY)  # SEND_DELAY = 3

# Стало:
import asyncio
import random

EMAIL_DELAY_MIN = int(os.getenv("EMAIL_DELAY_MIN", "45"))
EMAIL_DELAY_MAX = int(os.getenv("EMAIL_DELAY_MAX", "120"))

await asyncio.sleep(random.uniform(EMAIL_DELAY_MIN, EMAIL_DELAY_MAX))
```

Добавить в `.env`:
```
EMAIL_DELAY_MIN=45
EMAIL_DELAY_MAX=120
EMAIL_DAILY_LIMIT=50
```

**Это не опциональная улучшайзинг — это обязательное условие перед запуском.** Gmail банит аккаунты за паттерн отправки с постоянным интервалом.

---

#### Блокер 1: Трекинг-пиксель через публичный URL

Без публичного URL трекинг не работает — пиксель грузится только внутри локальной сети.

**Вариант А — ngrok (быстрее для старта):**
```bash
# Установка
brew install ngrok  # macOS
# или https://ngrok.com/download

# Запуск
ngrok http 8000

# Получаем URL вида: https://abc123.ngrok.io
# Добавить в .env:
TRACKING_BASE_URL=https://abc123.ngrok.io
```

Минус: URL меняется при каждом перезапуске (в бесплатном плане). Для первых тестов — нормально. Для продакшна — платный ngrok ($8/мес фиксированный домен) или Cloudflare Tunnel.

**Вариант Б — Cloudflare Tunnel (стабильнее, нужен домен):**
```bash
cloudflared tunnel login
cloudflared tunnel create granite-crm
cloudflared tunnel route dns granite-crm track.yourdomain.com
# В config.yml туннеля:
# ingress:
#   - hostname: track.yourdomain.com
#     service: http://localhost:8000
cloudflared tunnel run granite-crm
```

Рекомендую: ngrok для фазы 0 (22–50 писем), Cloudflare Tunnel при переходе к регулярным рассылкам.

---

#### Задача 1: Плейсхолдер `{unsubscribe_url}` и эндпоинт отписки

**Шаг 1.** Новый роутер `granite/api/unsubscribe.py`:

```python
from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from granite.api.deps import get_db
from granite.database import CrmEmailLogRow, CrmContactRow

router = APIRouter()

UNSUB_PAGE = """
<!DOCTYPE html>
<html lang="ru">
<head><meta charset="utf-8"><title>Отписка</title></head>
<body style="font-family:sans-serif;max-width:500px;margin:80px auto;text-align:center">
  <h2>Готово</h2>
  <p>Вы отписались. Больше писем от нас не будет.</p>
  <p style="color:#999;font-size:13px">
    RetouchGrav — <a href="https://aipunkfacility.github.io/monument-web/">сайт</a>
  </p>
</body>
</html>
"""

ALREADY_PAGE = """
<!DOCTYPE html>
<html lang="ru">
<head><meta charset="utf-8"><title>Отписка</title></head>
<body style="font-family:sans-serif;max-width:500px;margin:80px auto;text-align:center">
  <h2>Вы уже отписаны</h2>
  <p style="color:#999;font-size:13px">RetouchGrav</p>
</body>
</html>
"""

@router.get("/unsubscribe/{tracking_id}", include_in_schema=False)
async def unsubscribe(tracking_id: str, db: Session = Depends(get_db)):
    log = db.query(CrmEmailLogRow).filter_by(tracking_id=tracking_id).first()
    if not log:
        return HTMLResponse("<p>Ссылка недействительна или устарела.</p>", status_code=404)

    contact = db.query(CrmContactRow).filter_by(company_id=log.company_id).first()
    if not contact:
        return HTMLResponse(UNSUB_PAGE)

    if contact.stop_automation:
        return HTMLResponse(ALREADY_PAGE)

    contact.stop_automation = True
    contact.updated_at = datetime.now(timezone.utc)
    db.commit()

    return HTMLResponse(UNSUB_PAGE)
```

**Шаг 2.** Зарегистрировать роутер в `granite/api/app.py`:
```python
from granite.api import unsubscribe
app.include_router(unsubscribe.router)
```

**Шаг 3.** Добавить `List-Unsubscribe` заголовок в `granite/email/sender.py`:
```python
TRACKING_BASE_URL = os.getenv("TRACKING_BASE_URL", "http://localhost:8000")

# В методе send():
msg['List-Unsubscribe'] = f'<{TRACKING_BASE_URL}/unsubscribe/{tracking_id}>'
msg['List-Unsubscribe-Post'] = 'List-Unsubscribe=One-Click'
```

**Шаг 4.** Добавить `{unsubscribe_url}` в рендер шаблона в `sender.py`:
```python
unsubscribe_url = f"{TRACKING_BASE_URL}/unsubscribe/{tracking_id}"
rendered_body = template.render(
    company_name=company.name or "",
    city=company.city or "",
    from_name=FROM_NAME,
    website=company.website or "",
    unsubscribe_url=unsubscribe_url,
)
```

> Текущий `CrmTemplateRow.render()` делает `str.replace`. Это безопасно — `unsubscribe_url` будет plain URL без HTML, XSS-атаки через этот плейсхолдер невозможны.

---

#### Задача 2: Валидатор получателей

Новый файл `granite/email/validator.py`:

```python
"""
Валидатор списка получателей перед отправкой кампании.
Возвращает чистый список и список предупреждений для UI.
"""
import re
from typing import NamedTuple

# Домены-агрегаторы из аудита скраперов — уже помечены is_network,
# но дополнительная проверка по домену email не помешает
_AGGREGATOR_EMAIL_DOMAINS = frozenset({
    "danila-master.ru", "vsepamyatniki.ru", "memorial.ru",
    "tsargranit.ru", "alshei.ru", "mipomnim.ru",
})

# Паттерн мусорного названия: нет пробела при длине > 10, или длина > 80
_RE_NO_SPACE = re.compile(r"^\S{11,}$")


class ValidationResult(NamedTuple):
    clean: list[dict]
    warnings: list[str]
    excluded_count: int


def validate_batch(recipients: list[dict]) -> ValidationResult:
    """
    Принимает список dict с ключами: company_id, name, email,
    stop_automation, already_sent.
    Возвращает ValidationResult.
    """
    warnings: list[str] = []
    clean: list[dict] = []
    seen_emails: set[str] = set()
    excluded = 0

    for r in recipients:
        email = (r.get("email") or "").lower().strip()
        name = (r.get("name") or "").strip()

        # Нет email — пропускаем молча
        if not email or "@" not in email:
            excluded += 1
            continue

        # Дубль email в этой волне
        if email in seen_emails:
            excluded += 1
            continue
        seen_emails.add(email)

        # stop_automation — оператор вручную остановил автоматизацию
        if r.get("stop_automation"):
            excluded += 1
            continue

        # Уже получали письмо в рамках этой кампании
        if r.get("already_sent"):
            excluded += 1
            continue

        # Зарубежные домены в email (не российские мастерские)
        email_domain = email.split("@")[-1]
        if email_domain.endswith(".by") or email_domain.endswith(".kz"):
            warnings.append(f"Зарубежный email пропущен: {email}")
            excluded += 1
            continue

        # Известные агрегаторы по домену email
        if email_domain in _AGGREGATOR_EMAIL_DOMAINS:
            warnings.append(f"Email агрегатора пропущен: {email}")
            excluded += 1
            continue

        # Мусорное название: слитное слово длиннее 10 символов или общая длина > 80
        if _RE_NO_SPACE.match(name) or len(name) > 80:
            warnings.append(f"Подозрительное название пропущено: {name[:50]!r}")
            excluded += 1
            continue

        # Пустое название (письмо с {company_name}="" будет выглядеть плохо)
        if not name:
            warnings.append(f"Нет названия для email {email} — пропущен")
            excluded += 1
            continue

        clean.append(r)

    return ValidationResult(clean=clean, warnings=warnings, excluded_count=excluded)
```

**Интеграция в campaigns.py** — вызывать перед началом отправки:
```python
from granite.email.validator import validate_batch

recipients_raw = _get_campaign_recipients(db, campaign)
result = validate_batch([r.to_dict() for r in recipients_raw])

if result.warnings:
    # Отдать предупреждения через SSE в начале потока
    yield f"data: {json.dumps({'type': 'warnings', 'data': {'warnings': result.warnings, 'excluded': result.excluded_count}})}\n\n"

recipients = result.clean
```

---

#### Задача 3: A/B тест тем

**Миграция.** Создать через CLI:
```bash
uv run cli.py db migrate "add_ab_test_to_campaigns"
```

```python
# В файле миграции alembic/versions/..._add_ab_test_to_campaigns.py
def upgrade() -> None:
    with op.batch_alter_table("crm_email_campaigns") as batch_op:
        batch_op.add_column(sa.Column("subject_a", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("subject_b", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("sent_count_a", sa.Integer(), server_default="0"))
        batch_op.add_column(sa.Column("sent_count_b", sa.Integer(), server_default="0"))
        batch_op.add_column(sa.Column("open_count_a", sa.Integer(), server_default="0"))
        batch_op.add_column(sa.Column("open_count_b", sa.Integer(), server_default="0"))

    with op.batch_alter_table("crm_email_logs") as batch_op:
        # ab_variant уже может существовать — проверить через db check
        batch_op.add_column(sa.Column("ab_variant", sa.String(1), nullable=True))

def downgrade() -> None:
    with op.batch_alter_table("crm_email_campaigns") as batch_op:
        for col in ["subject_a", "subject_b", "sent_count_a", "sent_count_b",
                    "open_count_a", "open_count_b"]:
            batch_op.drop_column(col)
    with op.batch_alter_table("crm_email_logs") as batch_op:
        batch_op.drop_column("ab_variant")
```

**Логика распределения A/B** в sender:
```python
def get_ab_variant(company_id: int) -> str:
    """Детерминированное распределение: одна компания всегда в одном варианте."""
    return "A" if company_id % 2 == 0 else "B"
```

**Новый эндпоинт** `GET /api/v1/campaigns/{id}/ab-stats`:
```python
@router.get("/{campaign_id}/ab-stats")
def get_ab_stats(campaign_id: int, db: Session = Depends(get_db)):
    campaign = db.get(CrmEmailCampaignRow, campaign_id)
    if not campaign:
        raise HTTPException(404, "Campaign not found")

    from sqlalchemy import text
    rows = db.execute(text("""
        SELECT ab_variant,
               COUNT(*) as sent,
               SUM(CASE WHEN status IN ('opened', 'replied') THEN 1 ELSE 0 END) as opened
        FROM crm_email_logs
        WHERE campaign_id = :cid AND ab_variant IS NOT NULL
        GROUP BY ab_variant
    """), {"cid": campaign_id}).fetchall()

    def rate(opened, sent):
        return round(opened / sent * 100, 1) if sent else 0

    result = {}
    for row in rows:
        v = row.ab_variant
        result[v] = {
            "subject": campaign.subject_a if v == "A" else campaign.subject_b,
            "sent": row.sent,
            "opened": row.opened,
            "open_rate": rate(row.opened, row.sent),
        }

    # Вывод о победителе только при достаточной выборке
    winner = None
    if "A" in result and "B" in result:
        a, b = result["A"], result["B"]
        if a["sent"] >= 20 and b["sent"] >= 20:
            diff = abs(a["open_rate"] - b["open_rate"])
            if diff >= 5:
                winner = "A" if a["open_rate"] > b["open_rate"] else "B"

    return {"variants": result, "winner": winner,
            "note": "Победитель определяется при ≥20 отправках на вариант и разнице ≥5%"}
```

---

#### Задача 4: Автоматика follow-up задач

Это важная часть воронки, которой нет ни в одном из предыдущих планов в виде работающего кода.

**Логика:**
- Компания открыла письмо, но не ответила 3 дня → задача "написать повторно по email"
- Компания получила письмо, не открыла 7 дней → задача "проверить, дошло ли"

**Место реализации:** `granite/api/tracking.py` (при фиксации открытия) и фоновая проверка через существующий follow-up механизм.

В `tracking.py`, после обновления статуса на `opened`:

```python
from granite.database import CrmTaskRow
from datetime import datetime, timezone, timedelta

def _schedule_followup_task(company_id: int, db: Session) -> None:
    """Создать задачу follow-up если её ещё нет."""
    existing = db.query(CrmTaskRow).filter(
        CrmTaskRow.company_id == company_id,
        CrmTaskRow.task_type == "follow_up",
        CrmTaskRow.status == "pending",
    ).first()

    if existing:
        return  # уже есть активная задача

    due = datetime.now(timezone.utc) + timedelta(days=3)
    db.add(CrmTaskRow(
        company_id=company_id,
        title="Follow-up: открыли письмо, не ответили",
        task_type="follow_up",
        priority="high",
        status="pending",
        due_date=due,
        description=(
            "Компания открыла письмо 3+ дня назад и не ответила.\n"
            "Отправить короткое follow-up email (шаблон follow_up_email_v1).\n"
            "TG заблокирован — только email."
        ),
    ))
```

Для 7-дневного кейса (не открыли) — добавить в `granite/api/followup.py` в формирование очереди:

```python
# В запросе get_followup_queue — добавить условие:
# Если email_sent_count > 0, email_opened_count = 0,
# и last_email_sent_at < now() - 7 дней → task_type = check_response
```

---

#### Задача 5: Обновление схем Pydantic для A/B

В `granite/api/schemas.py`:

```python
class CreateCampaignRequest(BaseModel):
    name: str
    template_name: str
    subject_a: str = Field(..., min_length=1, max_length=100, description="Тема письма (вариант A)")
    subject_b: Optional[str] = Field(None, max_length=100, description="Тема письма B для A/B теста")
    filters: Optional[dict] = None
    daily_limit: int = Field(50, ge=10, le=200)
    # ... остальные поля

class CampaignABStatsResponse(BaseModel):
    variants: dict[str, dict]  # "A": {...}, "B": {...}
    winner: Optional[str]      # "A", "B" или None
    note: str
```

---

### 2.5 Фронтенд — минимальные изменения к существующему

Существующая страница `/campaigns` уже работает. Список изменений:

**1. Поле subject_b в форме создания** — добавить второй input под subject_a с пометкой "опционально, для A/B". Если заполнено — показать `"50% получат тему A · 50% получат тему B"`.

**2. Блок A/B статистики на странице кампании** — новый компонент `ABResultCard`:

```tsx
// src/components/campaigns/ABResultCard.tsx
interface ABVariant {
  subject: string;
  sent: number;
  opened: number;
  open_rate: number;
}

interface ABStats {
  variants: Record<string, ABVariant>;
  winner: string | null;
  note: string;
}

export function ABResultCard({ campaignId }: { campaignId: number }) {
  const { data } = useQuery<ABStats>({
    queryKey: ["campaign-ab-stats", campaignId],
    queryFn: () => apiClient.get(`/campaigns/${campaignId}/ab-stats`).then(r => r.data),
    refetchInterval: 30_000,
  });

  if (!data?.variants || Object.keys(data.variants).length === 0) return null;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">A/B тест тем</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-2 gap-3">
          {(["A", "B"] as const).map(v => {
            const s = data.variants[v];
            if (!s) return null;
            const isWinner = data.winner === v;
            return (
              <div key={v} className={cn(
                "rounded-md border p-3 text-sm",
                isWinner ? "border-emerald-400 bg-emerald-50" : "border-slate-200"
              )}>
                <div className="flex items-center justify-between mb-2">
                  <span className="font-medium text-xs text-slate-500">Тема {v}</span>
                  {isWinner && <Badge className="bg-emerald-500 text-xs">Победитель</Badge>}
                </div>
                <p className="text-slate-700 mb-3 line-clamp-2 text-xs">{s.subject}</p>
                <div className="text-2xl font-bold text-slate-900">{s.open_rate}%</div>
                <div className="text-xs text-slate-400">{s.opened} из {s.sent} открыли</div>
              </div>
            );
          })}
        </div>
        {!data.winner && (
          <p className="text-xs text-slate-400 mt-3">{data.note}</p>
        )}
        {data.winner && (
          <p className="text-xs text-slate-600 mt-3">
            Используй тему {data.winner} в следующей волне.
          </p>
        )}
      </CardContent>
    </Card>
  );
}
```

**3. Предупреждения валидатора в прогрессе** — когда SSE шлёт событие `type: "warnings"`, показать коллапсируемый блок с предупреждениями перед началом отправки.

**4. Ничего больше** — не переписывать wizard, не добавлять сложные фильтры, не делать превью с live-данными. Существующего UI достаточно для первых 9 рабочих дней рассылки.

---

### 2.6 Что делать с ответами (воронка после ответа)

Этого нет ни в одном предыдущем плане, а это самое важное.

**Когда мастерская ответила на письмо:**

1. Перевести в CRM: `email_sent/email_opened → replied` (вручную через UI)
2. Ответить в течение **2 часов** — скорость ответа критична в B2B
3. Стандартный ответ на "интересно, расскажите подробнее":

```
Отлично! Для начала просто пришлите фото — я покажу результат 
прямо на нём. Это быстрее любых объяснений.

Форматы: JPG, PNG, PDF, RAW, скан — любое качество.
Срок: сегодня/завтра.

Александр
```

4. Если прислали фото → делаем бесплатно → отправляем результат → переходим к обсуждению условий
5. Переводить в CRM: `replied → interested` после того как одобрили результат
6. Стандартные условия для постоянных партнёров:
   - 1–9 портретов: 1 000 ₽ ретушь, до 2 000 ₽ монтаж
   - 10+ в неделю: договорная цена, приоритет в очереди

**Перевод в `client` в CRM — только после первого оплаченного заказа.**

---

### 2.7 SMTP и прогрев — практические детали

**Gmail App Password:**
```
myaccount.google.com → Безопасность → Двухэтапная аутентификация → Пароли приложений
→ "Другое приложение" → "granite-crm"
```

**Прогрев нового аккаунта (если email свежий):**

| Неделя | Писем в день | Интервал |
|--------|-------------|----------|
| 1 | 10–20 | 90–180 сек |
| 2 | 30–40 | 60–120 сек |
| 3+ | 50 | 45–120 сек |

Если `ganjavagen@gmail.com` уже активно используется для переписки — прогрев не нужен, можно начинать с 50.

**Признаки что Gmail начинает блокировать:**
- Письма уходят в папку "Промоакции" вместо "Входящие" — это нормально, не блокировка
- SMTP ошибка 421/550 → снизить объём на 50% на 3 дня
- Письма вообще не уходят → проверить App Password, SMTP настройки

**Перед запуском — тест на mail-tester.com:**
```
1. Зайти на mail-tester.com
2. Скопировать адрес для теста
3. Отправить через CRM одно письмо на этот адрес
4. Получить оценку — цель 8+/10
5. Исправить что указано и повторить
```

---

## Часть 3. Итоговые приоритеты

### Что нужно до первой отправки (фаза 0, ~50 писем)

| # | Задача | Файл | Оценка |
|---|--------|------|--------|
| 1 | Случайные задержки 45–120 сек | `campaigns.py` | 15 мин |
| 2 | Трекинг через ngrok (пока без домена) | `.env` | 20 мин |
| 3 | Плейсхолдер `{unsubscribe_url}` в рендере | `sender.py` | 30 мин |
| 4 | Эндпоинт `/unsubscribe/{tracking_id}` | новый `unsubscribe.py` | 45 мин |
| 5 | `List-Unsubscribe` заголовок в письме | `sender.py` | 15 мин |
| 6 | Валидатор получателей | новый `validator.py` | 1 час |
| 7 | Добавить шаблоны в CRM через UI | — | 20 мин |
| 8 | Тест на mail-tester.com | — | 30 мин |
| **Итого** | | | **~3.5 часа** |

### Что делать после фазы 0 (перед основными волнами)

| # | Задача | Файл | Оценка |
|---|--------|------|--------|
| 9 | Миграция A/B полей | alembic | 30 мин |
| 10 | A/B логика в sender | `sender.py` | 45 мин |
| 11 | Эндпоинт `/ab-stats` | `campaigns.py` | 45 мин |
| 12 | ABResultCard на фронтенде | `granite-web` | 1.5 час |
| 13 | Поле subject_b в форме создания | `granite-web` | 30 мин |
| 14 | Автоматика follow-up задач при открытии | `tracking.py` | 1 час |
| 15 | Cloudflare Tunnel вместо ngrok | infra | 1 час |
| **Итого** | | | **~6 часов** |

### Что не делать

- Не менять `task_type` пока не применена миграция — сначала `uv run cli.py db upgrade head`
- Не запускать > 50 писем в день пока не подтверждена доставляемость
- Не делать follow-up через TG — канал заблокирован, только email
- Не добавлять ИНН в тело письма
- Не использовать слово "Предлагаем сотрудничество" — спам-триггер
- Не переписывать существующий CampaignWizard — работает, тратить время нет смысла

---

## Часть 4. График

```
День 1 (утро)   Блокеры 1–8: задержки, ngrok, отписка, валидатор, шаблоны
День 1 (вечер)  Тест на mail-tester.com, тест на 3–5 своих адресов
День 2          ФАЗА 0: 50 писем (сегмент A, смешанный CMS, тема A vs B)
День 3          Пауза — смотрим открытия, ждём ответы
День 4–5        Если есть ответы — обрабатываем. Задачи 9–15 (A/B, автоматика)
День 6          Волна 1: 22 письма (marquiz + tg_trust≥2), шаблон cold_email_marquiz
День 7          Пауза + анализ
День 8          Волна 2: 41 письмо (Bitrix), шаблон cold_email_bitrix
День 9–12       Волны 3–4: остаток A + B, 50 писем/день
День 13–17      Волна 5: сегмент B (259 компаний, 50/день = 5+ дней)
Параллельно     Ручные письма 8 крупным сетям (в любой день когда есть время)
```

---

## Часть 5. Метрики успеха

**Фаза 0 (50 писем) — что считаем:**
- Open rate (пиксель): цель ≥ 15%
- Reply rate: цель ≥ 1 ответа из 50 (2%)
- Технические: 0 SMTP ошибок, трекинг работает

**По окончании первого прогона (434 письма):**
- Ответов: 4–13 (1–3%)
- Из них дошли до бесплатного теста: 50–70%
- Из теста конвертировались в первый заказ: 50–70%
- Итого первых клиентов: 2–6

При 5+ заказах в неделю от одного клиента × 1 000 ₽ × 2–6 клиентов = 10 000–30 000 ₽/нед на старте. Это валидация модели, после которой можно обрабатывать следующие 17 городов.

**A/B тест — как интерпретировать:**
- До 20 писем на вариант: не делать выводов
- 20–50: ориентироваться на тренд, не на точные цифры
- 50+: статистически полезно, разница ≥5% — достаточный сигнал

---

*v4 · 2026-04-26 · RetouchGrav*
