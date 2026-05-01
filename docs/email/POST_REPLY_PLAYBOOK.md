# Post-Reply Playbook: Granite CRM

> Заполняется ИИ-агентом на основе документации проекта.
> Александр анализирует и правит.

---

## 1. Назначение документа

Полное руководство для оператора CRM при работе с ответами на email-рассылки. Содержит:

- Все сценарии реакций после отправки писем
- Ссылки на шаблоны ответов (тексты — в [EMAIL_TEMPLATES.md](./EMAIL_TEMPLATES.md))
- Инструкции по применению шаблонов
- Точную структуру фильтрации кампаний (на основе текущей ORM)
- Как сохраняется и доступна статистика кампаний

---

## 2. Сценарии post-reply

### 2.1 Сводная таблица реакций

| # | Реакция | Тип | Действие | Шаблон ответа | Статус в CRM |
|---|---------|-----|----------|---------------|-------------|
| 1 | «Интересно, расскажите подробнее» | auto/manual | Отправить детали + предложить пробный заказ | `reply_interested` | `interested` |
| 2 | «Сколько стоит?» | manual | Прайс + «оплата после результата» | `reply_price_question` | `interested` |
| 3 | «Пришлите примеры» | manual | Ссылка на портфолио + «пришлите свой исходник» | `reply_send_examples` | `interested` |
| 4 | «Подскажите по срокам» | manual | 12–24 часа стандарт, 3–6 срочно | `reply_timing` | `interested` |
| 5 | «Нам уже кто-то делает» | manual | «Ок, если что-то не устроит — я рядом» | `reply_has_vendor` | `replied` |
| 6 | «Нет, не актуально» / «Отпишите» | auto | Перевести в not_interested, никаких действий | — | `not_interested` |
| 7 | «Отпишите» / «Удалите мои данные» | auto | stop_automation=1, не писать больше | — | `not_interested` + `stop_automation=1` |
| 8 | Жалоба на спам | auto | Сразу stop_automation=1 | — | `not_interested` + `stop_automation=1` |
| 9 | Автоответчик (OOO) | auto | Проигнорировать, не менять стадию | — | без изменений |
| 10 | Bounce (email не существует) | auto | Отметить bounced | — | `unreachable` |
| 11 | Молчание после открытия | auto | follow-up через 7 дней | `follow_up_email_v1` | `email_opened` |
| 12 | Молчание без открытия | auto | Одно напоминание через 14 дней | `follow_up_email_v1` | `email_sent` |
| 13 | Молчание после 2 писем | auto | Стоп, больше не писать | — | `unreachable` |

### 2.2 Детали сценариев

#### Сценарий 1: «Интересно, расскажите подробнее»

**Контекст:** Владелец мастерской прочитал письмо и хочет узнать больше. Это горячий лид — он уже проявил интерес.

**Действия оператора:**
1. Открыть карточку компании в CRM
2. Убедиться, что входящий ответ распознан как «interested»
3. Нажать кнопку «Playbook» → выбрать сценарий «Заинтересован»
4. Шаблон `reply_interested` автоматически подставит `{city_locative}`, `{company_name}`
5. Предпросмотр — проверить текст, при необходимости дописать конкретику
6. Отправить → `CrmTouchRow(direction="outgoing")` + `funnel_stage = "interested"`

**Дополнительные возможности:**
- Если у компании есть WhatsApp/TG — продублировать ссылку на портфолио
- Если город Волгоград/Саратов/Астрахань — предложить личную встречу

**Переход к следующему шагу:** Ждём ответа. Если клиент прислал фото → `test_requested`. Если не ответил 3 дня → ручной follow-up.

---

#### Сценарий 2: «Сколько стоит?»

**Контекст:** Клиент прямо спрашивает цену. Это хороший сигнал — ему нужен сервис, но он не знает цен.

**Ключевой принцип:** НЕ называть точную цену в первом ответе. Вместо этого — рамка + «оплата после результата».

**Действия оператора:**
1. Открыть карточку → кнопка «Цена»
2. Шаблон `reply_price_question` — рамка цен + бесплатный тест
3. Отправить → `funnel_stage = "interested"`

**Типовой ответ:**
> Портретная ретушь — от 500₽/портрет при объёме, разовая — 1000₽. Но давайте так: пришлите фото, я покажу результат, и если устроит — оплатите. Если нет — никаких обязательств.

---

#### Сценарий 3: «Пришлите примеры»

**Контекст:** Клиент хочет увидеть качество работ до принятия решения.

**Действия оператора:**
1. Открыть карточку → кнопка «Примеры»
2. Шаблон `reply_send_examples` — ссылка на портфолио + CTA «пришлите свой сложный случай»
3. Отправить → `funnel_stage = "interested"`

**Важно:** Не просто прислать примеры, а предложить конкретный тест с ИХ фото. Это сдвигает клиента от пассивного просмотра к действию.

---

#### Сценарий 4: «Подскажите по срокам»

**Контекст:** Клиент оценивает логистику — ему важно, насколько быстро он получит результат.

**Действия оператора:**
1. Открыть карточку → кнопка «Сроки»
2. Шаблон `reply_timing` — конкретные сроки
3. Отправить → `funnel_stage = "interested"`

**Типовой ответ:**
> Стандарт — 12–24 часа. Срочные заказы — 3–6 часов (доплата 50%). Если вам нужно быстрее — пишите, обсудим.

---

#### Сценарий 5: «Нам уже кто-то делает»

**Контекст:** У мастерской уже есть подрядчик по ретуши. Не давим — оставляем дверь открытой.

**Действия оператора:**
1. Открыть карточку → кнопка «Есть подрядчик»
2. Шаблон `reply_has_vendor` — мягкий ответ без давления
3. Отправить → `funnel_stage = "replied"` (не interested — не переводим)

**Важно:** Не спорить, не убеждать. Просто дать знать, что альтернатива есть. Когда текущий подрядчик подведёт (а в этой нише это часто), мастерская вспомнит.

---

#### Сценарий 6: «Нет, не актуально»

**Контекст:** Чёткий отказ. Уважаем решение, не навязываемся.

**Действия оператора:**
1. Система автоматически распознает отказ по ключевым словам: «не актуально», «не интересно», «нет», «не нужно», «отказ»
2. `funnel_stage = "not_interested"` — автоматический перевод
3. Никаких дополнительных писем

---

#### Сценарий 7: «Отпишите» / «Удалите мои данные»

**Контекст:** Требование удалить данные. Юридически обязателен — ФЗ-152.

**Действия оператора (автоматически):**
1. `stop_automation = 1` — система больше не отправляет письма
2. `funnel_stage = "not_interested"`
3. При необходимости — удалить данные из CRM по запросу (ручная операция)

---

#### Сценарий 8: Жалоба на спам

**Контекст:** Кто-то пометил письмо как спам или написал «это спам».

**Действия (автоматически):**
1. `stop_automation = 1` — немедленно
2. `funnel_stage = "not_interested"`
3. Логировать в `CrmTouchRow(note="spam complaint")` для анализа

**Важно:** Если спам-жалоб > 5% кампании — остановить кампанию, пересмотреть текст/тему.

---

#### Сценарий 9: Автоответчик (OOO)

**Контекст:** Получили автоматический ответ «в отпуске», «вне офиса» и т.д.

**Действия (автоматически):**
1. Распознать по паттернам: «out of office», «в отпуске», «автоответ», «auto-reply», «OOO»
2. НЕ менять `funnel_stage` — компания остаётся на текущей стадии
3. НЕ отправлять повторное письмо автоматически
4. Логировать в `CrmTouchRow(note="OOO auto-reply")` для информации

**Дальнейшие действия:** При следующем запуске follow-up (если срок прошёл) — письмо отправится повторно. Если OOO с датой возврата — отложить до этой даты.

---

#### Сценарий 10: Bounce

**Контекст:** Email не существует, ящик переполнен, домен не принимает почту.

**Действия (автоматически):**
1. IMAP-парсер распознает bounce по типам:
   - `5.1.1` — User unknown → `unreachable`
   - `5.2.2` — Mailbox full → оставить `email_sent`, повторить через 7 дней
   - `5.7.1` — Blocked / spam → `stop_automation = 1`
2. Обновить `CrmEmailLogRow.status = "bounced"`, `bounced_at = now()`
3. Обновить `funnel_stage = "unreachable"` (для User unknown / Blocked)

---

#### Сценарий 11: Молчание после открытия

**Контекст:** Клиент открыл письмо (tracking pixel сработал), но не ответил.

**Действия (автоматически):**
1. Через 7 дней после `opened_at` — отправить `follow_up_email_v1`
2. `funnel_stage` остаётся `email_opened` (не откатывать)
3. Если после follow-up ещё 7 дней молчания → переход к сценарию 12

---

#### Сценарий 12: Молчание без открытия

**Контекст:** Письмо доставлено, но не открыто. Возможные причины: попало в спам, клиент удаляет не читая, письмо затерялось.

**Действия (автоматически):**
1. Через 14 дней — одно напоминание `follow_up_email_v1` с другой темой
2. Если и после этого нет открытия → сценарий 13

---

#### Сценарий 13: Молчание после 2 писем

**Контекст:** Отправлено 2 письма, ни одного ответа/открытия.

**Действия (автоматически):**
1. `funnel_stage = "unreachable"`
2. Больше не отправлять автоматически
3. Через 90 дней — возможен повторный контакт с новой кампанией (если `stop_automation = 0`)

---

## 3. Точная структура фильтрации кампаний

### 3.1 Где хранятся фильтры

Фильтры кампании хранятся в колонке `filters` (JSON) таблицы `crm_email_campaigns`. ORM: `CrmEmailCampaignRow.filters`.

### 3.2 Допустимые поля фильтра

```json
{
  "cities": ["Волгоград", "Саратов"],
  "regions": ["Волгоградская область"],
  "segments": ["A", "B"],
  "min_score": 25,
  "max_score": 100,
  "has_email": true,
  "has_website": true,
  "cms": ["bitrix", "wordpress"],
  "has_telegram": true,
  "has_whatsapp": true,
  "has_marquiz": true,
  "is_network": false,
  "funnel_stages": ["new"],
  "exclude_companies": [123, 456],
  "max_per_domain": 2,
  "min_email_sent_count": 0,
  "max_email_sent_count": 0
}
```

### 3.3 Описание полей фильтра

| Поле | Тип | ORM-источник | Описание |
|------|-----|-------------|----------|
| `cities` | `list[str]` | `CompanyRow.city` | Фильтр по городам (индекс `ix_companies_city`) |
| `regions` | `list[str]` | `CompanyRow.region` | Фильтр по регионам (индекс на `region`) |
| `segments` | `list[str]` | `EnrichedCompanyRow.segment` | A/B/C/D сегмент (индекс `ix_enriched_companies_segment`) |
| `min_score` | `int` | `EnrichedCompanyRow.crm_score` | Минимальный скор (индекс `ix_enriched_companies_crm_score`) |
| `max_score` | `int` | `EnrichedCompanyRow.crm_score` | Максимальный скор |
| `has_email` | `bool` | `CompanyRow.emails` (JSON) | Только компании с email-адресами |
| `has_website` | `bool` | `CompanyRow.website` | Только компании с сайтом |
| `cms` | `list[str]` | `EnrichedCompanyRow.cms` | Фильтр по CMS: `bitrix`, `wordpress`, `tilda`, `unknown` (индекс `ix_enriched_cms`) |
| `has_telegram` | `bool` | `EnrichedCompanyRow.messengers` | Проверка `json_extract(messengers, '$.telegram') IS NOT NULL` |
| `has_whatsapp` | `bool` | `EnrichedCompanyRow.messengers` | Проверка `json_extract(messengers, '$.whatsapp') IS NOT NULL` |
| `has_marquiz` | `bool` | `EnrichedCompanyRow.has_marquiz` | Наличие виджета Marquiz (индекс `ix_enriched_marquiz`) |
| `is_network` | `bool` | `EnrichedCompanyRow.is_network` | Филиальная сеть |
| `funnel_stages` | `list[str]` | `CrmContactRow.funnel_stage` | Стадия воронки (индекс `ix_crm_contacts_funnel_stage`) |
| `exclude_companies` | `list[int]` | `CompanyRow.id` | Исключить конкретные компании по ID |
| `max_per_domain` | `int` | `CompanyRow.website` | Не более N компаний на один домен (дедупликация по домену) |
| `min_email_sent_count` | `int` | `CrmContactRow.email_sent_count` | Минимум отправленных email |
| `max_email_sent_count` | `int` | `CrmContactRow.email_sent_count` | Максимум отправленных email |

### 3.4 Логика наложения фильтров

Все фильтры — **конъюнкция** (AND). Внутри списков — **дизъюнкция** (OR).

Пример: `cities: ["Волгоград", "Саратов"], segments: ["A"]` → города Волгоград ИЛИ Саратов, И сегмент A.

### 3.5 Автоматические фильтры (всегда применяются)

Независимо от `filters` JSON, кампания **всегда** исключает:

1. `CrmContactRow.stop_automation = 1` — отписавшиеся
2. `CompanyRow.deleted_at IS NOT NULL` — удалённые компании
3. `CompanyRow.emails = []` или `CompanyRow.emails IS NULL` — нет email
4. `CrmContactRow.funnel_stage IN ("unreachable")` — недостижимые (если не указано иное в `funnel_stages`)

### 3.6 SQL-запрос фильтрации (псевдокод)

```sql
SELECT c.id, c.name_best, c.emails, c.city, ec.crm_score, ec.segment, cc.funnel_stage
FROM companies c
JOIN enriched_companies ec ON ec.id = c.id
JOIN crm_contacts cc ON cc.company_id = c.id
WHERE c.deleted_at IS NULL
  AND cc.stop_automation = 0
  AND c.emails IS NOT NULL AND c.emails != '[]'
  -- Пользовательские фильтры:
  AND c.city IN (:cities)            -- если задано
  AND ec.segment IN (:segments)      -- если задано
  AND ec.crm_score >= :min_score     -- если задано
  AND json_extract(ec.messengers, '$.telegram') IS NOT NULL  -- если has_telegram
  AND cc.funnel_stage IN (:stages)   -- если задано
ORDER BY ec.crm_score DESC
```

### 3.7 max_per_domain: дедупликация по домену

Когда `max_per_domain = 2`:
1. Извлечь домен из `CompanyRow.website` (нормализованный)
2. Сгруппировать компании по домену
3. Оставить не более N компаний с наибольшим `crm_score` в каждой группе
4. Компании без сайта — не группируются (каждая уникальна)

---

## 4. Статистика кампаний рассылки

### 4.1 Три уровня хранения статистики

Статистика хранится на **трёх уровнях** в текущей ORM. Данные обновляются автоматически при отправке, открытии и ответе.

#### Уровень 1: Агрегат кампании (`CrmEmailCampaignRow`)

| Поле | Тип | Описание |
|------|-----|----------|
| `total_sent` | INTEGER | Всего отправлено писем в рамках кампании |
| `total_opened` | INTEGER | Всего открытий (tracking pixel) |
| `total_replied` | INTEGER | Всего ответов (IMAP parser) |
| `started_at` | DATETIME | Время запуска кампании |
| `completed_at` | DATETIME | Время завершения |

**Формулы:**
- Open Rate = `total_opened / total_sent * 100`
- Reply Rate = `total_replied / total_sent * 100`

**Что добавляется в v11 (через миграции):**

| Поле | Зачем | Задача |
|------|-------|--------|
| `total_errors` | Считать ошибки отправки | 3.3 |
| `subject_a` / `subject_b` | A/B тест тем | уже есть |

#### Уровень 2: Каждое письмо (`CrmEmailLogRow`)

| Поле | Тип | Описание |
|------|-----|----------|
| `company_id` | INTEGER FK | Кому отправлено |
| `email_to` | VARCHAR | Адрес получателя |
| `campaign_id` | INTEGER FK | Какая кампания |
| `template_name` | VARCHAR | Какой шаблон использован |
| `status` | VARCHAR | `pending` → `sent` → `opened` → `replied` / `bounced` / `error` |
| `sent_at` | DATETIME | Когда отправлено |
| `opened_at` | DATETIME | Когда открыто |
| `replied_at` | DATETIME | Когда получен ответ |
| `bounced_at` | DATETIME | Когда был bounce |
| `tracking_id` | VARCHAR (UUID) | Для tracking pixel |
| `error_message` | TEXT | Текст ошибки (если есть) |

**Что добавляется в v11:**

| Поле | Зачем | Задача |
|------|-------|--------|
| `ab_variant` | "A" / "B" для разрезания статистики | 3.4 |

#### Уровень 3: Каждый контакт (`CrmContactRow`)

| Поле | Тип | Описание |
|------|-----|----------|
| `funnel_stage` | VARCHAR | Текущая стадия: `new`, `email_sent`, `email_opened`, `replied`, `interested`, `not_interested`, `unreachable` |
| `email_sent_count` | INTEGER | Сколько писем отправлено этому контакту |
| `email_opened_count` | INTEGER | Сколько открыто |
| `email_replied_count` | INTEGER | Сколько ответов |
| `last_email_sent_at` | DATETIME | Дата последней отправки |
| `last_email_opened_at` | DATETIME | Дата последнего открытия |
| `stop_automation` | INTEGER | 1 = отписка, не слать больше |
| `contact_count` | INTEGER | Общее кол-во касаний (email + tg + wa) |
| `last_contact_at` | DATETIME | Время последнего касания |
| `last_contact_channel` | VARCHAR | Канал: `email`, `tg`, `wa`, `manual` |

### 4.2 A/B статистика

Для кампаний с A/B тестированием тем:

**Запрос A/B stats** (задача 3.4):

```sql
SELECT
  ab_variant,
  COUNT(*) as total,
  SUM(CASE WHEN opened_at IS NOT NULL THEN 1 ELSE 0 END) as opened,
  SUM(CASE WHEN replied_at IS NOT NULL THEN 1 ELSE 0 END) as replied
FROM crm_email_logs
WHERE campaign_id = :campaign_id AND ab_variant IN ('A', 'B')
GROUP BY ab_variant
```

**API endpoint:** `GET /api/v1/campaigns/{id}/ab-stats`

**Ответ:**
```json
{
  "variants": {
    "A": {"subject": "...", "sent": 45, "opened": 12, "replied": 3, "reply_rate": 6.7},
    "B": {"subject": "...", "sent": 47, "opened": 18, "replied": 7, "reply_rate": 14.9}
  },
  "winner": null,
  "note": "Победитель — по количеству ответов"
}
```

### 4.3 Чего сейчас НЕТ (и когда добавлять)

| Метрика | Статус | Когда добавлять |
|---------|--------|----------------|
| Исторические снапшоты (sent/opened/replied по дням) | Не реализовано | Когда данных станет достаточно для графиков. Таблица `crm_campaign_daily_stats` |
| A/B по телу письма | Не реализовано | Добавить `template_b_name` в `CrmEmailCampaignRow` + миграция |
| Warm-up статистика (репутация домена) | Не реализовано | После настройки DKIM/SPF/DMARC |
| Bounce rate по причинам | Частично (только статус) | Добавить `bounce_reason` в `CrmEmailLogRow` |

---

## 5. Инструкция по применению шаблонов

### 5.1 Где хранятся шаблоны

| Хранилище | Назначение | Формат |
|-----------|-----------|--------|
| `docs/EMAIL_TEMPLATES.md` | **Спецификация** — человекочитаемый каталог, который правит Александр | Markdown + YAML-блоки |
| `crm_templates` (таблица БД) | **Рабочие шаблоны** — используются при отправке | ORM: `CrmTemplateRow` |

### 5.2 Путь от спецификации к отправке

```
docs/EMAIL_TEMPLATES.md  (человек правит тексты)
         │
         ▼  cli.py db seed-templates
crm_templates (CrmTemplateRow в БД)
         │
         ├──▶ Кампания: template_name → body + subject_a/subject_b
         │
         └──▶ Post-reply: кнопка сценария → шаблон → render() → отправка
```

### 5.3 Команды для работы с шаблонами

```bash
# Загрузить все шаблоны из EMAIL_TEMPLATES.md в БД
uv run cli.py db seed-templates

# Обновить конкретный шаблон (по имени)
uv run cli.py db seed-templates --only reply_interested

# Посмотреть все шаблоны в БД
uv run cli.py db list-templates

# Обновить HTML-шаблон через API
PUT /api/v1/templates/{name}
Content-Type: application/json
{"body": "<html>...", "subject": "...", "body_type": "html"}
```

### 5.4 Как работает рендеринг шаблонов

1. `CrmTemplateRow.render(**kwargs)` — подставляет плейсхолдеры через `str.replace()`
2. Для `body_type="html"` — значения экранируются через `html.escape()`
3. Для `body_type="plain"` — подстановка как есть
`city_locative` вычисляется из `city` автоматически через `get_locative()` из модуля `granite/city_declensions.py` — оператору не нужно заполнять отдельно. Данные: `data/city_declensions.json` (1093 города).

**Доступные плейсхолдеры:**

| Плейсхолдер | Источник | Пример |
|-------------|----------|--------|
| `{city}` | `CompanyRow.city` | Волгоград |
| `{company_name}` | `CompanyRow.name_best` | Гранит-М |
| `{website}` | `CompanyRow.website` | granit-m.ru |
| `{from_name}` | config.yaml | Александр |
| `{contact_name}` | Ручной ввод | Иван |
| `{phone}` | `CompanyRow.phones[0]` | 79001234567 |
| `{unsubscribe_url}` | Автогенерация | `https://.../unsubscribe?...` |
| `{city_locative}` | Город в предложном падеже (авто из словаря) | Москве |
| `{original_subject}` | Из предыдущего письма | Помощь с подготовкой фото |

### 5.5 A/B тестирование и шаблоны

**Текущая реализация:** A/B тестирование работает **только по темам** писем.

- `CrmEmailCampaignRow.subject_a` — тема варианта A
- `CrmEmailCampaignRow.subject_b` — тема варианта B
- Тело письма (`CrmTemplateRow.body`) — одинаковое для обоих вариантов
- `CrmEmailLogRow.ab_variant` — помечает, какую тему получил получатель

**Расширение для A/B по телу (будущее):**

Если потребуется A/B тестировать разные тексты письма:
1. Добавить `template_b_name` в `CrmEmailCampaignRow` (миграция)
2. При отправке: вариант A → `template_name`, вариант B → `template_b_name`
3. Статистика по `ab_variant` уже работает

---

## 6. Рабочий процесс оператора

### 6.1 Обработка входящего ответа

```
Входящий email (IMAP)
    │
    ▼  process_replies.py
Классификация ответа
    │
    ├── Автоматические (не требуют оператора):
    │   ├── OOO → проигнорировать
    │   ├── Bounce → unreachable
    │   ├── Отписка → stop_automation=1
    │   └── Спам-жалоба → stop_automation=1
    │
    └── Требуют оператора:
        │
        ▼  UI: карточка компании
        Показать текст ответа
        Кнопки быстрых сценариев:
        ├── «Заинтересован» → reply_interested
        ├── «Цена» → reply_price_question
        ├── «Примеры» → reply_send_examples
        ├── «Сроки» → reply_timing
        ├── «Есть подрядчик» → reply_has_vendor
        └── «Отказ» → not_interested
            │
            ▼  Выбор сценария
        Предпросмотр шаблона с плейсхолдерами
            │
            ▼  Отправка
        CrmTouchRow(direction="outgoing")
        CrmContactRow.funnel_stage обновлён
        CrmEmailLogRow создан
```

### 6.2 Создание новой кампании

```
1. Выбрать шаблон из crm_templates (по имени)
2. Задать фильтры (JSON в CrmEmailCampaignRow.filters)
3. Задать A/B темы (subject_a, subject_b)
4. Предпросмотр: сколько получателей подходит под фильтры
5. Запуск → SSE-прогресс в реальном времени
6. Статистика: total_sent, total_opened, total_replied
```

### 6.3 Анализ результатов кампании

```
1. Открыть кампанию → общая статистика (sent/opened/replied)
2. A/B stats: сравнить open_rate и reply_rate вариантов
3. Фильтр по результату: кто открыл, кто ответил, кто отписался
4. Перевести ответивших → post-reply сценарии (раздел 2)
5. Остановить кампанию если bounce_rate > 10% или spam_complaints > 5%
```

---

## 7. Сводка по файлам

| Файл | Назначение |
|------|-----------|
| `docs/POST_REPLY_PLAYBOOK.md` | Этот документ — сценарии, инструкции, структура фильтрации |
| `docs/EMAIL_TEMPLATES.md` | Каталог шаблонов писем — тексты, которые правит Александр |
| `granite/database.py` → `CrmTemplateRow` | ORM шаблонов (name, body, subject, body_type) |
| `granite/database.py` → `CrmEmailCampaignRow` | ORM кампаний (filters, stats, subject_a/b) |
| `granite/database.py` → `CrmEmailLogRow` | ORM логов писем (status, tracking, ab_variant) |
| `granite/database.py` → `CrmContactRow` | ORM контактов (funnel_stage, email counters) |
| `granite/api/campaigns.py` | API для кампаний + A/B stats endpoint |
| `granite/api/unsubscribe.py` | API отписки |
| `granite/email/sender.py` | Отправка писем |
| `granite/email/validator.py` | Валидация + дедупликация получателей |
| `granite/email/process_replies.py` | Классификация входящих ответов (будущее) |
