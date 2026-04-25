# RetouchGrav — Email Campaign Dev Plan v3
### Холодная B2B рассылка гранитным мастерским

> **Сервис:** Ретушь портретов под лазерную / ударную гравировку на памятниках  
> **Автор:** Александр, самозанятый  
> **Telegram:** @ganjavagen · **WhatsApp:** +7 (494) 694-35-43  
> **Сайт:** https://aipunkfacility.github.io/monument-web/  
> **База:** ~6 000 компаний → **434 реальных цели** (A+B, не-сеть, валидный email)

---

## Что уже есть в проекте (не строить заново)

Прежде чем планировать разработку — зафиксируем, что уже реализовано в `granite-crm`.

### Бэкенд — готово

| Компонент | Файл | Статус |
|-----------|------|--------|
| Email отправка | `granite/email/sender.py` | ✅ Работает (SMTP, plain/HTML, tracking pixel) |
| Трекинг-пиксель | `granite/api/tracking.py` | ✅ `GET /api/v1/track/open/{id}.png` |
| Кампании API | `granite/api/campaigns.py` | ✅ 7 эндпоинтов, SSE прогресс |
| Воронка | `granite/api/stage_transitions.py` | ✅ Автоматические переходы при отправке/открытии |
| Шаблоны | `granite/api/templates.py` | ✅ CRUD, plain + HTML, плейсхолдеры |
| Задачи | `granite/api/tasks.py` | ✅ task_type: follow_up / send_test_offer / check_response |
| crm_email_logs | `granite/database.py` | ✅ Таблица с tracking_id, campaign_id, status, opened_at |
| crm_email_campaigns | `granite/database.py` | ✅ Таблица с filters, status, sent/open статистикой |

### Фронтенд — готово

| Страница | Путь | Статус |
|----------|------|--------|
| Список кампаний | `/campaigns` | ✅ Карточки, статус, open_rate |
| Создание кампании | `/campaigns` → диалог | ✅ Форма с шаблоном и фильтрами |
| Прогресс кампании | SSE в UI | ✅ Прогресс-бар с обновлением в реальном времени |
| Шаблоны | `/templates` | ✅ CRUD, загрузка HTML-файлов |
| Follow-up очередь | `/followup` | ✅ Список с рекомендованным каналом |
| Задачи | `/tasks` | ✅ Список с фильтрами |

### Что **не** реализовано и нужно добавить

1. **A/B тест тем** — поля `subject_a` / `subject_b` в схеме, логика разбивки и отдельный компонент статистики
2. **Валидатор получателей** — чистка мусорных названий, `.by`-доменов, дублей перед отправкой
3. **Отписка** — эндпоинт `GET /unsubscribe/{tracking_id}` + `List-Unsubscribe` заголовок
4. **Случайные задержки** — текущий `SEND_DELAY=3` фиксирован, нужен `random.uniform(45, 120)`
5. **Автоматика follow-up задач** — создание crm_task при тишине после открытия/отправки
6. **Cloudflare Tunnel** — для трекинг-пикселя через публичный URL

---

## Реальная картина базы

### Что надёжно есть в базе

`название, город, сайт, телефоны, email, мессенджеры, CMS, crm_score, сегмент, is_network, has_marquiz, tg_trust`

### Чего нет

Тип станка (лазер / ударный / шарошка) и объём заказов. `tech_keywords` из конфига в базу не попали — сайты мастерских редко пишут об оборудовании в явном виде.

### Главный фильтр — is_network

Из 578 компаний сегмента A с email — 403 помечены как сети. Это агрегаторы (`danila-master.ru`, `memorial.ru`, `vsepamyatniki.ru`), представленные в десятках городов. После фильтрации:

```
Сегмент A, не-сеть, валидный email:  175 компаний
Сегмент B, не-сеть, валидный email:  259 компаний
─────────────────────────────────────────────────
Итого приоритетная база:              434 компании
```

При 50 письмах в день — **8–9 рабочих дней** на первый полный прогон.

**Крупные сети — отдельный разговор.** `pamyatniki.moscow` (9 городов), `ritualgranit.ru` (7 городов), `ramgranit.ru` (7 городов) — им пишем **один раз** в головной офис, вручную. Потенциальный оптовый клиент с 10+ заказами в неделю.

---

## Сегментация волн рассылки

Рассылаем последовательными волнами — от самых горячих к тёплым. Каждая волна — отдельная кампания в CRM со своей темой письма.

### Волна 1 — Сигнальные (22 компании)

**Фильтр CRM:**
```
has_marquiz=1 OR tg_trust>=2
AND is_network=0
AND segment IN (A, B)
AND email IS NOT NULL
```

Мастерские, которые уже думают о маркетинге: поставили квиз на сайт или ведут живой Telegram-канал (аватар + описание, tg_trust ≥ 2). Они понимают ценность аутсорса — объяснять меньше.

**Тема A:** `Ретушь для гравировки — в день обращения, оплата после`  
**Тема B:** `Для вашей мастерской: подготовка фото под гравировку без предоплаты`

---

### Волна 2 — Bitrix-мастерские (41 компания)

**Фильтр CRM:**
```
cms=bitrix
AND is_network=0
AND segment IN (A, B)
AND email IS NOT NULL
```

Bitrix — признак профессионального бизнеса, часто с менеджером. Привыкли работать с подрядчиками и принимают решения быстрее. Самый конвертируемый сегмент после волны 1.

Примеры из базы: Гранит-Мастер (Белгород, score 63), Небеса (Брянск, score 57), Кинель-Гранит (Кинель, score 57).

**Тема A:** `{company_name}: готовим фото под гравировку — в день заказа`  
**Тема B:** `Аутсорс ретуши для гранитных мастерских — без предоплаты`

> ⚠️ `{company_name}` в теме — только после прогона валидатора. Часть названий в базе — SEO-заголовки страниц (без пробелов, длиннее 80 символов). Такие исключаются автоматически.

---

### Волна 3 — Tilda-сайты (25 компаний)

**Фильтр CRM:**
```
cms=tilda
AND is_network=0
AND segment IN (A, B)
AND email IS NOT NULL
```

Tilda — владелец сам делал сайт, думает о подаче. Маркетингово восприимчив.

**Тема A:** `Фото на памятник: ретушь под ваш станок — смотрите примеры`  
**Тема B:** `Свободная минута? Сделаю пробную ретушь для вашей мастерской`

---

### Волна 4 — Остальной сегмент A (121 компания)

**Фильтр CRM:**
```
segment=A
AND is_network=0
AND cms NOT IN (bitrix, tilda)
AND email IS NOT NULL
```

WordPress, Joomla, OpenCart, unknown CMS. Хороший скор, реальный бизнес — просто меньше сигналов о маркетинговой зрелости.

**Тема A:** `Ретушь портретов для гравировки — бесплатная проба`  
**Тема B:** `Первое фото — бесплатно. Оцените качество без обязательств`

---

### Волна 5 — Сегмент B (259 компаний)

**Фильтр CRM:**
```
segment=B
AND is_network=0
AND email IS NOT NULL
```

Чуть ниже скор, но 259 компаний — существенный объём. Запускать после анализа результатов волн 1–4, с победившей темой A/B.

---

## Шаблоны писем

### Принципы

Мастерская получает фото от родственников и должна сама их подготовить — это реальная регулярная боль. Письмо не должно звучать как реклама. Тон — коллега из смежной ниши, который предлагает снять конкретную задачу.

**Не использовать:** «Предлагаем сотрудничество», «Наша компания», «Коммерческое предложение» — это спам-фразы и по тону, и по фильтрам.

**Проверить на [mail-tester.com](https://mail-tester.com) перед стартом — цель 8+/10.**

---

### Основной шаблон (волны 1, 3, 4)

Имя шаблона в CRM: `cold_email_main`  
Channel: `email` · Body type: `plain`

```
Тема: [вариант A или B из таблицы волны]

Здравствуйте.

Меня зовут Александр, занимаюсь ретушью фотографий специально для гравировки
на памятниках — нейросети и ручная обработка, работаю с мастерскими по всей России.

Часто бывает: фото плохое, размытое, старое, скриншот с телефона — 
а семья других не принесёт. Именно под такие случаи и работаю. 
Восстанавливаю детали, делаю нужный контраст, готовлю файл под станок.

Условия для мастерских:
• Выполнение в день обращения, без выходных
• Оплата только после получения и одобрения результата
• От 10 заказов в неделю — специальные цены и приоритет

Готов сделать 1–2 пробных фото бесплатно, чтобы вы оценили качество
на своём оборудовании.

Примеры работ: https://aipunkfacility.github.io/monument-web/

Если интересно — пришлите фото в ответ или напишите в Telegram:
https://t.me/ganjavagen
WhatsApp: +7 (494) 694-35-43

Александр
ganjavagen@gmail.com

---
Если не актуально — напишите «нет», больше не побеспокою.
{unsubscribe_url}
```

---

### Вариант для Bitrix (волна 2) — деловой тон

Имя шаблона в CRM: `cold_email_bitrix`  
Channel: `email` · Body type: `plain`

```
Тема: [вариант A или B из таблицы волны 2]

Здравствуйте, {company_name}.

Работаю с гранитными мастерскими: подготавливаю фотографии для лазерной
и ударной гравировки на памятниках. Нейросети + ручная обработка,
сотрудничаю с мастерскими по всей России.

Что делаю:
— Ретушь под конкретный станок и технологию гравировки
— Восстановление сложных исходников (старые, размытые, повреждённые, скриншоты)
— Монтаж, замена одежды, фона, сборка в полный рост
— Срок — в день обращения, оплата после результата

Предлагаю начать с бесплатной пробы на 1–2 ваших реальных заказа.
Пришлите фото — покажу результат на вашем материале.

Примеры работ: https://aipunkfacility.github.io/monument-web/

Telegram: https://t.me/ganjavagen
WhatsApp: +7 (494) 694-35-43
Email: ganjavagen@gmail.com

Александр

---
{unsubscribe_url}
```

---

### Плейсхолдеры

| Плейсхолдер | Значение | Источник в БД |
|---|---|---|
| `{company_name}` | Название компании | `enriched_companies.name` |
| `{city}` | Город | `enriched_companies.city` |
| `{from_name}` | Имя отправителя (из `.env` → `FROM_NAME`) | ENV |
| `{unsubscribe_url}` | Ссылка отписки | генерируется по `tracking_id` |

> ⚠️ Не использовать `{city}` и `{company_name}` в теме без предварительного прогона валидатора. Часть названий в базе — title страниц-агрегаторов.

---

## Технический план — что строить

### Параметры безопасной рассылки

Изменить в `granite/api/campaigns.py` (сейчас `SEND_DELAY=3`):

```python
import random

EMAIL_DELAY_MIN       = 45    # сек между письмами (минимум)
EMAIL_DELAY_MAX       = 120   # сек между письмами (максимум)
EMAIL_BATCH_PER_DAY   = 50    # старт; поднять до 80–100 после первой недели
MAX_PER_DOMAIN        = 2     # писем на один домен-получатель за 24 часа

# Вместо time.sleep(SEND_DELAY):
await asyncio.sleep(random.uniform(EMAIL_DELAY_MIN, EMAIL_DELAY_MAX))
```

Случайная задержка — критично. Паттерн «каждые 3 секунды» распознаётся провайдером и приводит к бану аккаунта.

---

### Задача 1: Валидатор получателей (новый файл)

**Файл:** `granite/email/validator.py`

```python
def validate_batch(recipients: list) -> tuple[list, list[str]]:
    """Возвращает (чистый список, список предупреждений)."""
    warnings = []
    clean = []
    seen_emails = set()

    for r in recipients:
        email = (r.get('email') or '').lower().strip()
        name = (r.get('name') or '').strip()

        # Дубль email в пределах одной волны
        if email in seen_emails:
            continue
        seen_emails.add(email)

        # Мусорное название: без пробелов или длиннее 80 символов
        if len(name) > 80 or (len(name) > 5 and ' ' not in name):
            warnings.append(f"Подозрительное название пропущено: {name[:50]}")
            continue

        # .by домены (Беларусь — другая ниша, другой рынок)
        if email.endswith('.by'):
            warnings.append(f"Зарубежный email пропущен: {email}")
            continue

        # Уже получали письмо в этой кампании
        if r.get('already_sent'):
            continue

        # stop_automation — оператор вручную остановил
        if r.get('stop_automation'):
            continue

        clean.append(r)

    return clean, warnings
```

---

### Задача 2: Отписка

**Новый эндпоинт** в `granite/api/tracking.py` (рядом с пикселем):

```python
@router.get("/unsubscribe/{tracking_id}")
async def unsubscribe(tracking_id: str, db: Session = Depends(get_db)):
    """Страница отписки по tracking_id письма."""
    log = db.query(CrmEmailLogRow).filter_by(tracking_id=tracking_id).first()
    if not log:
        return HTMLResponse("<p>Ссылка недействительна.</p>")
    
    # Ставим stop_automation = True
    contact = db.query(CrmContactRow).filter_by(company_id=log.company_id).first()
    if contact:
        contact.stop_automation = True
        contact.updated_at = datetime.now(timezone.utc)
    
    db.commit()
    return HTMLResponse(
        "<p>Вы отписались. Больше писем не будет.</p>"
        "<p style='color:#888;font-size:12px'>RetouchGrav · "
        "<a href='https://aipunkfacility.github.io/monument-web/'>Сайт</a></p>"
    )
```

**Добавить `List-Unsubscribe` заголовок** в `granite/email/sender.py`:

```python
msg['List-Unsubscribe'] = f'<{TRACKING_BASE_URL}/unsubscribe/{tracking_id}>'
msg['List-Unsubscribe-Post'] = 'List-Unsubscribe=One-Click'
```

**Генерация `{unsubscribe_url}`** в рендере шаблона:
```python
unsubscribe_url = f"{TRACKING_BASE_URL}/unsubscribe/{tracking_id}"
body = template.render(
    company_name=company.name,
    city=company.city,
    from_name=FROM_NAME,
    unsubscribe_url=f"Отписаться: {unsubscribe_url}"
)
```

---

### Задача 3: A/B тест тем

**Миграция Alembic** — добавить поля в `crm_email_campaigns`:

```bash
uv run cli.py db migrate "add_ab_test_fields_to_campaigns"
```

```python
# В файле миграции:
def upgrade():
    with op.batch_alter_table("crm_email_campaigns") as batch_op:
        batch_op.add_column(sa.Column("subject_a", sa.Text, nullable=True))
        batch_op.add_column(sa.Column("subject_b", sa.Text, nullable=True))
        batch_op.add_column(sa.Column("open_count_a", sa.Integer, default=0, server_default="0"))
        batch_op.add_column(sa.Column("open_count_b", sa.Integer, default=0, server_default="0"))
        batch_op.add_column(sa.Column("sent_count_a", sa.Integer, default=0, server_default="0"))
        batch_op.add_column(sa.Column("sent_count_b", sa.Integer, default=0, server_default="0"))
```

**Добавить поле `ab_variant` в `crm_email_logs`** (уже есть в схеме таблицы — проверить миграцией):

```python
# В sender.py — выбор варианта:
ab_variant = "A" if company_id % 2 == 0 else "B"
subject = campaign.subject_a if ab_variant == "A" else (campaign.subject_b or campaign.subject_a)
```

**Новый эндпоинт статистики A/B:**

```python
# GET /api/v1/campaigns/{id}/ab-stats
@router.get("/{campaign_id}/ab-stats")
def get_ab_stats(campaign_id: int, db: Session = Depends(get_db)):
    campaign = db.get(CrmEmailCampaignRow, campaign_id)
    if not campaign:
        raise HTTPException(404)
    
    # Агрегируем из crm_email_logs
    stats = db.execute(text("""
        SELECT ab_variant,
               COUNT(*) as sent,
               SUM(CASE WHEN status='opened' THEN 1 ELSE 0 END) as opened
        FROM crm_email_logs
        WHERE campaign_id = :cid AND ab_variant IS NOT NULL
        GROUP BY ab_variant
    """), {"cid": campaign_id}).fetchall()
    
    return {
        "A": next(({"sent": r.sent, "opened": r.opened, "subject": campaign.subject_a}
                   for r in stats if r.ab_variant == "A"), None),
        "B": next(({"sent": r.sent, "opened": r.opened, "subject": campaign.subject_b}
                   for r in stats if r.ab_variant == "B"), None),
    }
```

---

### Задача 4: Автоматика follow-up задач

Добавить в `granite/api/tracking.py` после фиксации открытия:

```python
# При открытии — создать задачу follow-up через 3 дня, если нет ответа
def _maybe_create_followup_task(company_id: int, db: Session):
    existing = db.query(CrmTaskRow).filter_by(
        company_id=company_id,
        task_type="follow_up",
        status="pending"
    ).first()
    if not existing:
        due = datetime.now(timezone.utc) + timedelta(days=3)
        db.add(CrmTaskRow(
            company_id=company_id,
            title="Follow-up: открыли письмо — написать в Telegram",
            task_type="follow_up",
            priority="high",
            status="pending",
            due_date=due,
            description="Компания открыла письмо, но не ответила. "
                        "Попробовать Telegram: https://t.me/ganjavagen"
        ))
```

Для 7-дневного follow-up (не открыли) — добавить в `granite/api/followup.py` в логику формирования очереди: если `email_sent_count > 0` и `email_opened_count == 0` и прошло 7+ дней с `last_email_sent_at` — добавлять задачу `check_response`.

---

### Задача 5: Cloudflare Tunnel (для трекинг-пикселя)

Трекинг-пиксель требует публичный URL (`TRACKING_BASE_URL`). Без него пиксель загружается только локально и открытия не фиксируются.

```bash
# Установка
brew install cloudflare/cloudflare/cloudflared  # macOS
# или скачать с https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/install-and-setup/

# Создание туннеля (нужен аккаунт Cloudflare, бесплатный)
cloudflared tunnel login
cloudflared tunnel create granite-crm
cloudflared tunnel route dns granite-crm track.YOURDOMAIN.com

# Запуск (добавить в автозапуск)
cloudflared tunnel run granite-crm
```

**В `.env`:**
```
TRACKING_BASE_URL=https://track.YOURDOMAIN.com
```

> Если нет своего домена — `cloudflared tunnel --url http://localhost:8000` создаёт временный публичный URL вида `https://random-name.trycloudflare.com`. Подходит для теста.

---

### Обновление .env

```env
# SMTP
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your@gmail.com
SMTP_PASS=xxxx-xxxx-xxxx-xxxx   # App Password, НЕ основной пароль
SMTP_FROM=your@gmail.com

# Трекинг
TRACKING_BASE_URL=https://track.YOURDOMAIN.com

# Рассылка
FROM_NAME=Александр
EMAIL_DAILY_LIMIT=50
EMAIL_DELAY_MIN=45
EMAIL_DELAY_MAX=120

# API
GRANITE_API_KEY=   # оставить пустым для локальной работы
```

**Gmail App Password:**
`Google Account → Security → 2-Step Verification → App Passwords → Other (granite-crm)`

---

### Фронтенд — что добавить к существующему

Существующая страница `/campaigns` уже работает. Нужно дополнить:

#### 1. CampaignWizard — добавить шаг A/B тем

В существующий диалог создания кампании добавить поле для второй темы:

```tsx
// В форме создания кампании:
<div className="space-y-2">
  <Label>Тема письма A <span className="text-red-500">*</span></Label>
  <Input placeholder="Ретушь для гравировки — в день обращения, оплата после" />
</div>
<div className="space-y-2">
  <Label>Тема письма B <span className="text-slate-400">(опционально, для A/B)</span></Label>
  <Input placeholder="Оставить пустым если A/B тест не нужен" />
  {subjectB && (
    <p className="text-xs text-slate-500">
      50% получат тему A, 50% — тему B
    </p>
  )}
</div>
```

#### 2. ABResultCard — новый компонент

```tsx
// src/components/campaigns/ABResultCard.tsx
interface ABStats {
  A: { sent: number; opened: number; subject: string } | null;
  B: { sent: number; opened: number; subject: string } | null;
}

export function ABResultCard({ stats }: { stats: ABStats }) {
  const rateA = stats.A ? (stats.A.opened / stats.A.sent * 100).toFixed(0) : 0;
  const rateB = stats.B ? (stats.B.opened / stats.B.sent * 100).toFixed(0) : 0;
  const winner = Number(rateA) > Number(rateB) ? "A" : "B";
  const diff = Math.abs(Number(rateA) - Number(rateB));
  const significant = diff >= 5 && (stats.A?.sent ?? 0) >= 20 && (stats.B?.sent ?? 0) >= 20;

  return (
    <Card>
      <CardHeader><CardTitle>A/B тест — Открываемость</CardTitle></CardHeader>
      <CardContent>
        <div className="grid grid-cols-2 gap-4">
          {(["A", "B"] as const).map(variant => {
            const s = stats[variant];
            const rate = s ? (s.opened / s.sent * 100).toFixed(0) : "—";
            const isWinner = significant && variant === winner;
            return (
              <div key={variant} className={cn(
                "rounded-lg border p-4",
                isWinner && "border-emerald-500 bg-emerald-50"
              )}>
                <div className="text-xs text-slate-500 mb-1">Тема {variant}</div>
                <div className="text-sm font-medium mb-3 line-clamp-2">
                  {s?.subject ?? "—"}
                </div>
                <div className="text-2xl font-bold">{rate}%</div>
                <div className="text-xs text-slate-500">
                  {s?.opened ?? 0} из {s?.sent ?? 0} открыли
                </div>
                {isWinner && (
                  <Badge className="mt-2 bg-emerald-500">Победитель ★</Badge>
                )}
              </div>
            );
          })}
        </div>
        {significant && (
          <p className="text-sm text-slate-600 mt-3">
            Разница {diff}% — достаточно для вывода. Использовать тему {winner} в следующей волне.
          </p>
        )}
        {!significant && (
          <p className="text-sm text-slate-400 mt-3">
            Для вывода нужно ≥20 отправок на каждый вариант и разница ≥5%.
          </p>
        )}
      </CardContent>
    </Card>
  );
}
```

#### 3. Превью получателей с предупреждениями

Добавить в `RecipientPreview` вывод из `/campaigns/{id}/preview`:

```tsx
{warnings.length > 0 && (
  <Alert variant="warning">
    <AlertTitle>{warnings.length} компаний исключено валидатором</AlertTitle>
    <AlertDescription>
      <ul className="text-xs mt-1 space-y-1">
        {warnings.slice(0, 5).map((w, i) => <li key={i}>⚠ {w}</li>)}
        {warnings.length > 5 && <li>...ещё {warnings.length - 5}</li>}
      </ul>
    </AlertDescription>
  </Alert>
)}
```

---

## Автоматика воронки (уже реализована, проверить)

В `granite/api/stage_transitions.py` уже есть логика переходов при отправке и открытии. **Проверить:**

```
Отправка письма  → funnel_stage: new → email_sent         ✅ (через campaigns.py)
Открытие пикселя → funnel_stage: email_sent → email_opened ✅ (через tracking.py)
3 дня тишины     → crm_task: follow_up (написать в TG)    ❌ НУЖНО ДОБАВИТЬ
7 дней без откр. → crm_task: check_response               ❌ НУЖНО ДОБАВИТЬ
Ответил          → воронка: replied                        ✅ (вручную через UI)
```

---

## Порядок реализации

### Неделя 1 — Инфраструктура

| День | Задача | Файл |
|------|--------|------|
| Пн | Cloudflare Tunnel + `.env` + проверить трекинг-пиксель | infra |
| Вт | Валидатор получателей | `granite/email/validator.py` |
| Вт | Отписка: эндпоинт + `List-Unsubscribe` заголовок | `granite/api/tracking.py`, `sender.py` |
| Ср | Случайные задержки (45–120 сек) вместо `SEND_DELAY=3` | `granite/api/campaigns.py` |
| Ср | Миграция A/B полей + эндпоинт `/ab-stats` | `granite/api/campaigns.py` |
| Чт | ABResultCard на фронтенде, поле subject_b в форме создания | `granite-web/` |
| Чт | Тест на 3–5 своих адресах: Gmail, Яндекс, корпоративный | — |
| Пт | **Волна 1: 22 письма** (marquiz + tg_trust≥2). Тема A vs B | CRM UI |

### Неделя 2 — Первый анализ + масштабирование

| День | Задача |
|------|--------|
| Пн | Смотрим открытия волны 1 (подождать 3 рабочих дня). Определяем победителя A/B |
| Вт | **Волна 2: 41 письмо** (Bitrix). Победившая тема + новый вариант B |
| Ср–Чт | Наблюдение, ответы обрабатываем вручную через Telegram |
| Пт | Автоматика follow-up задач (если тишина 3 дня после открытия) |
| Пт | **Волна 3: 25 писем** (Tilda) |

### Неделя 3 — Полный прогон

| День | Задача |
|------|--------|
| Пн–Ср | **Волна 4**: остальной сегмент A (121 компания, по 50/день) |
| Чт–Пт | **Волна 5**: начало сегмента B (259 компаний, несколько дней) |
| Любой момент | Ручные письма крупным сетям (8 компаний) |

---

## Чеклист перед первой отправкой

### Технический
- [ ] App Password создан (НЕ основной пароль Gmail)
- [ ] Cloudflare Tunnel запущен, трекинг-пиксель отдаёт 1×1 PNG
- [ ] Отписка работает: ссылка → страница → `stop_automation=True` в БД
- [ ] Случайная задержка 45–120 сек вместо `SEND_DELAY=3`
- [ ] Alembic миграция применена: `uv run cli.py db upgrade head`
- [ ] `.env` заполнен (SMTP_*, TRACKING_BASE_URL, FROM_NAME)
- [ ] Тест на своих адресах: Gmail, Яндекс, ещё один

### Контентный
- [ ] Нет спам-слов в теме (акция, скидка, бесплатно в нерелевантном контексте, срочно, гарантия)
- [ ] Нет КАПСА в теме
- [ ] Длина темы ≤ 50 символов
- [ ] Есть ссылка отписки в теле письма
- [ ] Проверка на [mail-tester.com](https://mail-tester.com) — цель 8+/10
- [ ] Контакты в подписи: Telegram, WhatsApp, email

### Данные
- [ ] Фильтр `is_network=0` включён в кампании
- [ ] Фильтр `stop_automation=0` включён
- [ ] Нет дублей email в пределах одной волны (валидатор)
- [ ] `.by` домены исключены (валидатор)
- [ ] Мусорные названия исключены (валидатор)

---

## Целевые показатели

| Метрика | Реалистично | Хорошо | Отлично |
|---|---|---|---|
| Open rate (пиксель) | 15–20% | 25–30% | 35%+ |
| Реальные открытия (~2× пикселя) | 30–40% | 50–60% | 70%+ |
| Reply rate | 1–2% | 3–5% | 7%+ |
| Писем в день | 50 | 80 | 100 |
| Ответов за первые 2 недели | 2–4 | 5–10 | 15+ |

> Пиксель блокируется Gmail / Яндексом в ~40–60% случаев — это норма. Используем как **относительный** показатель для A/B, не как абсолютный. Реальный open rate вдвое выше.

**Расчёт по базе (434 × reply rate 3%):** ~13 потенциальных клиентов из первого прогона. При 5+ заказах в неделю от каждого — хорошая стартовая точка для постоянных партнёров.

---

## Риски и митигация

| Риск | Митигация |
|---|---|
| Gmail блокирует аккаунт | Случайные задержки 45–120 сек, не более 50/день в старте, не слать всё за 2 часа |
| Письма в спам | mail-tester.com перед стартом, нет спам-слов, подпись, `List-Unsubscribe` заголовок |
| Трекинг не работает | Норма — 40–60% блокируют. Используем как относительный показатель A/B |
| Мусорные названия в теле | Валидатор исключает имена без пробелов и длиннее 80 символов |
| .by адреса | Автофильтр в валидаторе |
| Компьютер офлайн во время рассылки | Кампания получит статус `paused`, перезапустить вручную — продолжит со следующего получателя |
| Крупные сети — дубли | `is_network=0` в основных волнах; сети — отдельно, вручную |
| TG/WA заблокированы РКН | Email — основной канал. TG/WA — только если клиент сам пишет |

---

## Что НЕ строить (отложить)

- **Автоматическая отправка в TG/WA** — каналы заблокированы РКН, mock-режим оставить как есть
- **WebSocket для прогресса** — SSE уже работает, этого достаточно
- **Собственный email-сервер** — Gmail/Яндекс личный аккаунт полностью подходит для 50–100 писем в день
- **Сложный WYSIWYG редактор шаблонов** — textarea + плейсхолдеры закрывают задачу
- **Мобильная версия CRM** — один пользователь за ноутбуком

---

## Итого: дельта от текущего состояния

| Задача | Объём | Приоритет |
|--------|-------|-----------|
| Случайные задержки (1 строка) | 15 мин | 🔴 Критично перед стартом |
| `List-Unsubscribe` заголовок | 30 мин | 🔴 Критично |
| Эндпоинт отписки | 1 час | 🔴 Критично |
| Валидатор получателей | 1 час | 🔴 Критично |
| Cloudflare Tunnel + `.env` | 1 час | 🔴 Критично |
| Миграция A/B полей | 30 мин | 🟡 До волны 1 |
| Эндпоинт `/ab-stats` | 1 час | 🟡 До волны 1 |
| ABResultCard (фронтенд) | 2 часа | 🟡 До волны 1 |
| Поле subject_b в форме создания | 30 мин | 🟡 До волны 1 |
| Автоматика follow-up задач | 2 часа | 🟢 До волны 2 |

**Итого до первой отправки: ~4–5 часов работы.**
