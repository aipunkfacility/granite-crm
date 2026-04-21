# Granite Scrapers — Аудит качества данных и план рефакторинга

> Дата: 2026-04-21  
> База: `granite.db` — 1719 raw_companies, 1209 companies, 1209 enriched_companies  
> Источники: `jsprav` (545 записей), `web_search` (1174 записей)

---

## 1. Диагноз: что реально происходит с данными

### 1.1. Сводная статистика

| Показатель | Значение | Комментарий |
|-----------|---------|------------|
| raw_companies | 1 719 | Из них полезных — значительно меньше |
| Записи без телефона И email | **434 (25%)** | Полностью пустые контакты |
| web_search без контактов | **273 / 1174 (23%)** | Сайт есть, контактов нет |
| jsprav без контактов | **161 / 545 (30%)** | Компании с нулём телефонов |
| Generic/SEO названия в enriched | **700 / 1209 (58%)** | Не являются настоящим именем компании |
| Сегмент D (мало данных) | **513 / 1209 (42%)** | Почти половина базы бесполезна для аутрича |

---

### 1.2. Проблема 1 (Критическая): Агрегаторы-каталоги составляют 56% web_search

**Симптом:** Из 1174 записей от web_search — **660 (56%)** приходят с доменов, которые появляются в 5+ разных городах одновременно. Это не локальные компании, а агрегаторские сайты с каталогами по городам.

**Топ-агрегаторы в базе:**

| Домен | Городов | Записей |
|------|--------|--------|
| tsargranit.ru | 48 | 48 |
| alshei.ru | 42 | 42 |
| mipomnim.ru | 39 | 39 |
| uznm.ru | 30 | 30 |
| monuments.su | 27 | 27 |
| masterskay-granit.ru | 24 | 24 |
| gr-anit.ru | 22 | 22 |
| v-granit.ru | 21 | 21 |
| nbs-granit.ru | 20 | 20 |
| granit-pamiatnik.ru | 17 | 17 |
| postament.ru | 16 | 16 |
| uslugio.com | 14 | 14 |

**Что происходит:** DDG возвращает URL вида `alshei.ru/abaza.html`, `tsargranit.ru/abakan.html` — это страницы-каталоги с фотографиями памятников от одного федерального поставщика, представленного во всех городах. Scraper берёт заголовок страницы как имя компании ("Памятники на кладбищев Абазе"), контакты — централизованный колл-центр поставщика.

**Ошибочная логика в `_is_relevant_url()`:** Функция блокирует зарубежные домены и проверяет `.ru` TLD, но не имеет защиты от паттерна "один домен → много городов". Агрегатор на `.ru` проходит все проверки как "доверенный" источник.

**Дополнительная проблема:** `danila-master.ru` появляется в 52 городах с субдоменами (`abaza.danila-master.ru`, `abdulino.danila-master.ru`). Это реальная федеральная сеть-франшиза, но каждый субдомен регистрируется как отдельная "компания". В итоге в базе 58 записей с именем "Данила-Мастер" от одного юридического лица.

---

### 1.3. Проблема 2 (Критическая): jsprav собирает ритуальные услуги, а не мастерские памятников

**Симптом:** Из 545 записей jsprav — **279 (51%)** приходят из категории `ritualnyie-prinadlezhnosti-i-izgotovlenie-venkov` (ритуальные принадлежности и венки), а не из целевой `izgotovlenie-i-ustanovka-pamyatnikov-i-nadgrobij`.

**Что происходит:** `category_finder` по API `/api/cities/` находит категорию `ritualnyie-prinadlezhnosti-i-izgotovlenie-venkov` как "смежную" и добавляет её в список для парсинга. Либо парсер scrape'ит subpage компаний, у которых основная рубрика — ритуальные услуги, а не изготовление памятников. В результате в базе оказываются похоронные бюро, магазины венков и салоны ритуальных изделий — не целевая аудитория.

**Пример:** `Ритуальные услуги`, `Салон ритуальных изделий`, `Эдем`, `Истэлек`, `Мир камня` — все из категории `ritualnyie-prinadlezhnosti`.

---

### 1.4. Проблема 3 (Серьёзная): Извлечение имени компании из web_search полностью сломано

**Симптом:** 700 из 1209 записей в `enriched_companies` (58%) имеют generic или SEO-заголовок вместо реального имени.

**Причины:**

1. **Агрегаторы с URL-специфичными заголовками.** `alshei.ru/abaza.html` даёт title "Памятники на кладбищев Абазе". `_extract_contacts()` извлекает `company_name` из `og:site_name` или `<h1>`, но у агрегаторов эти поля содержат SEO-текст.

2. **Слияние страниц без имени.** Многие local-страницы на крупных сайтах (mipomnim.ru, uznm.ru) не имеют `og:site_name` — тогда берётся `<h1>` или `<title>`, которые всегда содержат ключевые слова вроде "Памятники из гранита в Абакане".

3. **`is_seo_title()` недостаточно строгий.** Паттерн не покрывает формулировки типа "Памятники в Абазе", "Изготовление памятников Абакан", "Памятники из гранита".

**Конкретный пример:** Запись `[Советск] Памятники из гранитаАбакан, score=0` — это страница компании из **Абакана**, которая была найдена по запросу для **Советска** через DDG. Название — буквально склейка SEO-текста.

---

### 1.5. Проблема 4 (Серьёзная): Отсутствует фильтр по географическому соответствию в web_search

**Симптом:** URL из DDG поиска "гранитная мастерская памятники Абаза" может вернуть страницу федерального агрегатора `tsargranit.ru/abaza.html` или `mipomnim.ru/pamyatniki-i-nadgrobiya/abaza/`. Эти страницы содержат **московские или федеральные контакты**, но записываются как компания города Абаза.

**Почему `_title_mentions_foreign_city()` не помогает:** Функция проверяет упоминание **другого** города в тексте. Но если title содержит "Абаза" (целевой город), фильтр пропускает запись, даже если контакты принадлежат Москве.

---

### 1.6. Проблема 5 (Серьёзная): Агрегаторы получают Telegram и email, создавая ложно-богатые записи

**Симптом:** `PQD.ru` с сегментом B (score=35) — это агрегатор, но `MessengerScanner` нашёл на его страницах Telegram и email. В итоге в базе появляется запись с хорошим скором, которая при аутриче даст нулевой результат (отвечает колл-центр агрегатора, а не местный мастер).

---

### 1.7. Проблема 6 (Умеренная): jsprav enrich дополняет ритуальные категории телефонами похоронных бюро

`_enrich_from_detail_pages()` обогащает все компании из jsprav, включая из неправильных категорий. Так в базе появляются номера телефонов похоронных агентств под видом мастерских памятников.

---

### 1.8. Проблема 7 (Умеренная): Дедупликация не устраняет агрегаторские сети

`cluster_by_site()` группирует по домену. Но `tsargranit.ru/abaza.html` и `tsargranit.ru/abakan.html` — разные URL, хотя один домен. После нормализации домена (`tsargranit.ru`) они попадут в один кластер — но только если оба оказались в raw_companies для **одного** города. Между городами кластеризация по домену не работает (она scoped по городу).

---

## 2. Корневые причины

```
DDG возвращает агрегатор → 
  _is_relevant_url() пропускает (.ru домен) → 
    _scrape_details() скрейпит страницу-каталог → 
      company_name = SEO-заголовок страницы →
        phones = федеральный колл-центр OR пусто →
          MessengerScanner находит TG агрегатора →
            enriched запись выглядит валидной (score B/C) →
              аутрич идёт не туда
```

```
category_finder добавляет ритуальную категорию → 
  jsprav scraper парсит не тех компаний (50%) →
    в базе похоронные бюро и магазины венков →
      не реагируют на предложение о сайте для мастерской
```

---

## 3. Детальный план рефакторинга

### Приоритеты

| Приоритет | ID | Проблема | Эффект |
|-----------|----|---------|----|
| **P0** | A-1 | Blacklist агрегаторов в web_search | Убирает 56% мусора из web_search |
| **P0** | A-2 | Фильтр jsprav только по целевой категории | Убирает 51% нерелевантных из jsprav |
| **P1** | A-3 | Детектор агрегаторов по паттерну "один домен — много городов" | Автоматическая защита от новых агрегаторов |
| **P1** | A-4 | Улучшение извлечения имени компании | 58% записей получат правильное имя |
| **P1** | A-5 | Фильтр по контактному городу в web_search | Отсекает федеральные номера в локальных записях |
| **P2** | A-6 | Дедупликация агрегаторских сетей между городами | Убирает франшизные дубликаты |
| **P2** | A-7 | Расширение `is_seo_title()` | Больше SEO-имён уходит на этапе merger |
| **P3** | A-8 | Кросс-городская детекция сетей в NetworkDetector | Правильная пометка is_network для сетей |

---

### A-1 (P0): Статический blacklist агрегаторов в SKIP_DOMAINS

**Файл:** `granite/scrapers/web_search.py`

**Что добавить в `SKIP_DOMAINS`:**

```python
# ── Агрегаторы памятников (один сайт → страницы по всем городам России) ──
"tsargranit.ru",          # 48 городов в базе
"alshei.ru",              # 42 города
"mipomnim.ru",            # 39 городов
"uznm.ru",                # 30 городов
"monuments.su",           # 27 городов
"masterskay-granit.ru",   # 24 города
"gr-anit.ru",             # 22 города
"v-granit.ru",            # 21 город
"nbs-granit.ru",          # 20 городов
"granit-pamiatnik.ru",    # 17 городов
"postament.ru",           # 16 городов
"monuments39.ru",         # 15 городов
"asgranit.ru",            # 15 городов
"uslugio.com",            # 14 городов
"pamiatnikiizgranita.ru", # 14 городов
"izgotovleniepamyatnikov.ru", # 14 городов
"pamatniki.ru",           # 10 городов
"pqd.ru",                 # 9 городов (агрегатор-справочник)
"spravker.ru",            # справочник
"mapage.ru",              # справочник
"orgpage.ru",             # справочник
"totadres.ru",            # справочник
"kamelotstone.ru",        # сеть с city-страницами
"diabazstone.ru",         # 13 городов — проверить, возможно реальная сеть
"danila-master.ru",       # 52 города — федеральная франшиза (обрабатывать отдельно)
"zoon.ru",                # справочник
"izgotovleniepamyatnikov.ru",
"uslugio.com",
"absopac.ru",
"pomnivsegda.ru",
"pamyatnik-russia.ru",
```

**Важно:** `danila-master.ru` — реальная сеть, не агрегатор. Её субдомены (`abaza.danila-master.ru`) представляют разные физические точки. Решение — добавить `danila-master.ru` в SKIP_DOMAINS (блокирует только корневой домен), но **не** блокировать субдомены. Проверить через `_is_skip_domain()`: `endswith("danila-master.ru")` заблокирует и `abaza.danila-master.ru`. Для франшиз — отдельная логика (см. A-6).

**Тест-критерий:** После добавления в тестовой прогон для 10 городов записи с этими доменами не появляются в `raw_companies`.

---

### A-2 (P0): Строгий фильтр категорий jsprav — только целевая рубрика

**Файл:** `granite/scrapers/jsprav.py`, `granite/category_finder.py`

**Проблема:** В `categories` попадает `ritualnyie-prinadlezhnosti-i-izgotovlenie-venkov` наряду с `izgotovlenie-i-ustanovka-pamyatnikov-i-nadgrobij`. Нужно жёстко ограничить.

**Решение — три уровня защиты:**

**Уровень 1: Константа разрешённых категорий**

```python
# granite/scrapers/jsprav_base.py
JSPRAV_ALLOWED_CATEGORIES = frozenset({
    "izgotovlenie-i-ustanovka-pamyatnikov-i-nadgrobij",
})

# В JspravBaseScraper.__init__():
if categories is not None:
    # Фильтруем только разрешённые категории
    self.categories = [c for c in categories if c in JSPRAV_ALLOWED_CATEGORIES]
    if not self.categories:
        logger.warning(f"JSprav: все переданные категории не разрешены, использую дефолт")
        self.categories = [self.JSPRAV_CATEGORY]
else:
    self.categories = [self.JSPRAV_CATEGORY]
```

**Уровень 2: Фильтр source_url при парсинге**

```python
# В _parse_jsonld_item() в JspravBaseScraper:
def _parse_jsonld_item(self, c, seen_urls, *, extract_emails=True):
    org_url = c.get("url", "")
    # Фильтруем компании из нецелевых категорий по source_url
    if org_url and not any(cat in org_url for cat in JSPRAV_ALLOWED_CATEGORIES):
        # Компания может быть в правильной категории даже если URL другой
        # (detail-страница компании не содержит категорию в URL)
        # Поэтому этот фильтр применяем только к самим URL категорий, не detail-страниц
        pass
    ...
```

**Уровень 3: Фильтр в `discover_categories()`**

```python
# granite/category_finder.py
# При сохранении в кэш — только если категория разрешена
if result.get("categories"):
    # Оставляем только разрешённые категории
    allowed = [c for c in result["categories"] if c in JSPRAV_ALLOWED_CATEGORIES]
    if allowed:
        cache.setdefault("jsprav", {})[city] = allowed
    else:
        # Нашли только нецелевые категории — записываем как "нет категории"
        cache.setdefault("jsprav", {})[city] = []
```

**Расширение `JSPRAV_ALLOWED_CATEGORIES`:** При необходимости можно добавить смежные категории, но каждая должна быть явно одобрена:

```python
# Возможные будущие добавления:
# "izgotovlenie-izdelij-iz-kamnya" — изделия из камня (шире, может быть релевантно)
```

---

### A-3 (P1): Автодетектор агрегаторов — "один домен → много городов"

**Файл:** `granite/scrapers/web_search.py`

**Идея:** Во время scraping одного прогона отслеживать домены, которые встречаются для множества разных городов. Если домен появился уже для 3+ городов — добавить в runtime blacklist.

```python
# В WebSearchScraper — добавить class-level кэш (разделяется между экземплярами)
import threading

_MULTI_CITY_DOMAIN_CACHE: dict[str, set[str]] = {}  # domain -> set of cities
_MULTI_CITY_LOCK = threading.Lock()
_MULTI_CITY_THRESHOLD = 3  # домен в 3+ городах = агрегатор

def _register_domain_city(domain: str, city: str) -> bool:
    """Зарегистрировать пару домен+город. 
    Возвращает True если домен превысил порог (агрегатор).
    """
    with _MULTI_CITY_LOCK:
        cities = _MULTI_CITY_DOMAIN_CACHE.setdefault(domain, set())
        cities.add(city)
        is_aggregator = len(cities) >= _MULTI_CITY_THRESHOLD
    if is_aggregator and len(cities) == _MULTI_CITY_THRESHOLD:
        logger.warning(f"  WebSearch: автоблокировка агрегатора {domain} ({_MULTI_CITY_THRESHOLD}+ городов)")
    return is_aggregator
```

**Интеграция в `scrape()`:**

```python
# В проходе 2 (скрейпинг сайтов):
domain = extract_domain(item["url"])
if domain:
    is_aggregator = _register_domain_city(domain, self.city)
    if is_aggregator:
        logger.debug(f"  WebSearch: пропуск агрегатора {domain}")
        skipped_aggregator += 1
        continue
    if domain in seen_domains:
        continue
```

**Дополнительно:** По завершению прогона сохранять обнаруженные агрегаторы в YAML-файл для последующего ручного переноса в SKIP_DOMAINS:

```python
# После завершения run all — сохранить новые агрегаторы
def save_detected_aggregators(path="data/detected_aggregators.yaml"):
    with _MULTI_CITY_LOCK:
        candidates = {d: list(cities) for d, cities in _MULTI_CITY_DOMAIN_CACHE.items()
                      if len(cities) >= _MULTI_CITY_THRESHOLD}
    if candidates:
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(candidates, f, allow_unicode=True)
```

---

### A-4 (P1): Переписать извлечение имени компании в `_extract_contacts()`

**Файл:** `granite/scrapers/web_search.py`, метод `_extract_contacts()`

**Текущая логика (проблема):** Берёт `og:site_name` или `<h1>`. У агрегаторов `og:site_name` — название сайта ("TsarGranit"), `<h1>` — SEO-заголовок ("Памятники в Абазе").

**Новая приоритетная цепочка:**

```python
def _extract_company_name(self, soup, url: str) -> str | None:
    """Извлечь реальное название компании. Приоритет от самого надёжного."""
    
    # 1. JSON-LD Organization/LocalBusiness — самый надёжный источник
    for script in soup.select("script[type='application/ld+json']"):
        try:
            data = json.loads(script.string or "")
            items = data if isinstance(data, list) else [data]
            for item in items:
                if not isinstance(item, dict):
                    continue
                if item.get("@type") in ("Organization", "LocalBusiness", "Brand"):
                    name = item.get("name") or item.get("legalName")
                    if name and 3 < len(name.strip()) < 60:
                        if not is_seo_title(name) and not self._is_city_page_name(name):
                            return name.strip()
        except Exception:
            pass
    
    # 2. og:site_name — название сайта (не SEO-текст страницы)
    og = soup.find("meta", attrs={"property": "og:site_name"})
    if og and og.get("content"):
        name = og["content"].strip()
        if 3 < len(name) < 60 and not is_seo_title(name) and not self._is_city_page_name(name):
            return name
    
    # 3. <title> до первого разделителя (|, —, -, •)
    title_tag = soup.find("title")
    if title_tag:
        title = title_tag.get_text(strip=True)
        # Берём часть до разделителя: "Гранит-Мастер | Памятники в Абакане" → "Гранит-Мастер"
        for sep in (" | ", " — ", " - ", " • ", " · "):
            if sep in title:
                parts = title.split(sep, 1)
                candidate = parts[0].strip()
                if 3 < len(candidate) < 50 and not is_seo_title(candidate) and not self._is_city_page_name(candidate):
                    return candidate
    
    # 4. <h1> — только короткие, без SEO-паттернов и упоминания целевого города
    h1 = soup.find("h1")
    if h1:
        name = h1.get_text(strip=True)
        if 3 < len(name) < 50 and not is_seo_title(name) and not self._is_city_page_name(name):
            return name
    
    # Не нашли реального имени
    return None

def _is_city_page_name(self, name: str) -> bool:
    """Проверяет, является ли имя страницей-каталогом для города."""
    city_lower = self.city.lower()
    name_lower = name.lower()
    # "Памятники в Абазе", "Изготовление памятников Абакан", "Гранитные мастерские в Ачинске"
    if city_lower in name_lower:
        return True
    # Падежные формы города (первые 4 буквы города достаточно для большинства случаев)
    if len(city_lower) >= 4 and city_lower[:4] in name_lower:
        return True
    return False
```

**Расширение `is_seo_title()` в `utils.py`:**

```python
_SEO_TITLE_PATTERN = re.compile(
    r"(?:купить|цен[аыуе]|недорог|заказать|от производитель|"
    r"с установк|на могил|доставк|скидк|каталог|"
    r"памятник[аиы]?\s+(?:из|в|на|от)|"
    r"изготовлен.*(?:памятник|надгробие|гранит)|"
    r"гранитн[ые]+\s+мастерск|"         # ← ДОБАВИТЬ
    r"памятники\s+(?:в|из|на|и)\s+|"   # ← ДОБАВИТЬ: "Памятники в", "Памятники из"
    r"памятники\s+(?:на\s+кладбищ)|"   # ← ДОБАВИТЬ
    r"изготовление\s+памятников|"       # ← ДОБАВИТЬ
    r"памятники\s+и\s+надгробия)",      # ← ДОБАВИТЬ
    re.IGNORECASE,
)
```

---

### A-5 (P1): Валидация географического соответствия контактов

**Файл:** `granite/scrapers/web_search.py`

**Проблема:** Страница `tsargranit.ru/abaza.html` содержит московский телефон `+7 (495) xxx-xxxx`. Эта запись попадает в базу города Абаза с московским номером.

**Решение — проверка DEF-кода телефона:**

```python
# Региональные DEF-коды, доступные для определения региона
_MOSCOW_DEF_CODES = frozenset({
    "495", "499", "925", "926", "916", "903", "905", "906",  # Москва
    # Не блокировать: 800 (федеральные бесплатные), 903 (Москва, но и другие)
})

def _is_local_phone(self, phone: str) -> bool:
    """Проверяет, может ли телефон принадлежать местной компании.
    
    Грубая эвристика: московские DEF-коды для нестоличных городов — подозрительно.
    Для столичных городов (Москва, СПб) — не применять.
    """
    if self.city in ("Москва", "Санкт-Петербург"):
        return True
    norm = normalize_phone(phone)
    if not norm or len(norm) != 11:
        return False
    def_code = norm[1:4]
    # Федеральный номер 8-800 — нормально, может быть у любой компании
    if def_code == "800":
        return True
    # Явно московский номер для не-московского города — подозрительно
    if def_code in {"495", "499"}:
        return False
    return True
```

**Интеграция в `scrape()`:** Если у записи **все** телефоны не соответствуют региону — помечать `needs_review=True` или снижать приоритет, но не удалять (телефон может быть правильным, просто с московской регистрацией).

**Более надёжный вариант:** Проверять адрес на сайте. Если на странице `alshei.ru/abaza.html` в блоке контактов написан адрес Москвы — это агрегатор.

```python
def _extract_contact_city(self, html: str) -> str | None:
    """Пытается найти город в контактной информации страницы."""
    # Ищем паттерны адреса в HTML
    from granite.pipeline.region_resolver import detect_city
    # Ищем в тексте контактного блока
    soup = BeautifulSoup(html, "html.parser")
    for block in soup.select("[class*='contact'], [class*='address'], address, footer"):
        text = block.get_text(separator=" ", strip=True)
        if text and len(text) > 10:
            found = detect_city(text)
            if found:
                return found
    return None
```

---

### A-6 (P2): Дедупликация агрегаторских сетей между городами

**Файл:** `granite/pipeline/dedup_phase.py`, новый модуль `granite/dedup/network_filter.py`

**Проблема:** Текущая кластеризация работает в рамках одного города. Агрегатор `tsargranit.ru` создаёт 48 отдельных "компаний" в разных городах с одним доменом.

**Решение — пост-обработка после дедупликации:**

```python
# granite/dedup/network_filter.py

AGGREGATOR_THRESHOLD = 3  # домен у 3+ компаний из разных городов = агрегатор

def detect_and_mark_aggregators(db: Database) -> int:
    """Находит компании с одним доменом в 3+ городах и помечает их.
    
    Франшизы (danila-master.ru) помечаются как is_network=True.
    Агрегаторы-каталоги (alshei.ru) помечаются как needs_review=True + segment='spam'.
    
    Returns:
        Количество помеченных компаний.
    """
    with db.session_scope() as session:
        # Найти домены, встречающиеся в 3+ разных городах
        from sqlalchemy import func, text
        domain_cities = session.execute(text("""
            SELECT 
                SUBSTR(website, INSTR(website,'://')+3, 
                       CASE WHEN INSTR(SUBSTR(website,INSTR(website,'://')+3),'/') > 0 
                            THEN INSTR(SUBSTR(website,INSTR(website,'://')+3),'/')-1 
                            ELSE 100 END) as domain,
                COUNT(DISTINCT city) as city_count,
                COUNT(*) as total
            FROM companies 
            WHERE website IS NOT NULL AND deleted_at IS NULL
            GROUP BY domain
            HAVING city_count >= :threshold
        """), {"threshold": AGGREGATOR_THRESHOLD}).fetchall()
        
        marked = 0
        for domain, city_count, total in domain_cities:
            if not domain or len(domain) < 4:
                continue
            
            # Получаем все компании с этим доменом
            companies = session.query(CompanyRow).filter(
                CompanyRow.website.like(f"%{domain}%"),
                CompanyRow.deleted_at.is_(None)
            ).all()
            
            for c in companies:
                c.needs_review = True
                c.review_reason = f"aggregator_domain_{domain}_{city_count}_cities"
                
                # Обновляем enriched
                erow = session.get(EnrichedCompanyRow, c.id)
                if erow:
                    erow.is_network = True  # сеть (для franshises)
                    # Если это известный агрегатор — спам
                    if domain in KNOWN_AGGREGATOR_DOMAINS:
                        erow.segment = "spam"
                        erow.crm_score = 0
                
                marked += 1
        
        return marked
```

**Интеграция в пайплайн:** Вызывать после `DedupPhase.run()`, до `EnrichmentPhase.run()`.

---

### A-7 (P2): Расширение `is_seo_title()` и добавление `is_aggregator_name()`

**Файл:** `granite/utils.py`

```python
# Известные названия-заглушки агрегаторов
_AGGREGATOR_NAMES = frozenset({
    "pqd.ru", "pqd", "uslugio", "uslugio.com", "orgpage", "orgpage.ru",
    "spravker", "totadres", "zoon.ru", "zoon", "mapage", "mapage.ru",
    "my site",  # wix дефолт
    "наши услуги",  # Generic page title
    "каталог памятников",
    "памятники",  # Слишком общее
})

def is_aggregator_name(name: str) -> bool:
    """Проверяет, является ли имя агрегатором или заглушкой."""
    if not name:
        return True
    name_lower = name.strip().lower()
    return name_lower in _AGGREGATOR_NAMES or len(name.strip()) <= 2
```

**Использование в `merge_cluster()`:** Приоритет имён: не-SEO + не-агрегатор → SEO → агрегатор.

---

### A-8 (P3): Кросс-городская детекция сетей в NetworkDetector

**Файл:** `granite/enrichers/network_detector.py`

**Текущее поведение:** `scan_for_networks()` принимает параметр `city` и ищет сети **только внутри одного города**. Это правильно для паттерна "один телефон у двух точек в городе", но не для агрегаторов.

**Дополнение — глобальный скан при `run all`:**

```python
def scan_for_networks_global(self, threshold: int = 3) -> int:
    """Пересчитывает is_network для компаний с одним доменом в 3+ РАЗНЫХ городах.
    
    Отличие от scan_for_networks(): работает кросс-городски.
    Предназначен для запуска один раз после завершения всего прогона.
    """
    with self.db.session_scope() as session:
        # ... аналогично A-6
        pass
```

**Интеграция:** Добавить команду CLI `granite scan-networks` для ручного запуска.

---

## 4. Порядок реализации

```
Этап 1 (P0, 1 день):
  ├── A-1: Добавить список агрегаторов в SKIP_DOMAINS — 30 мин
  └── A-2: Ограничить jsprav строго ALLOWED_CATEGORIES — 2 часа

Этап 2 (P1, 2-3 дня):
  ├── A-3: Автодетектор агрегаторов (runtime blacklist) — 1 день
  ├── A-4: Переписать извлечение имени компании — 1 день
  └── A-5: Географическая валидация контактов — 0.5 дня

Этап 3 (P2, 1-2 дня):
  ├── A-6: Пост-обработка агрегаторов в dedup — 1 день
  └── A-7: Расширить is_seo_title() и добавить is_aggregator_name() — 0.5 дня

Этап 4 (P3, 1 день):
  └── A-8: Глобальный scan_for_networks — [DONE] 2026-04-21
  └── A-5: Адресная гео-валидация и перенос флагов — [DONE] 2026-04-21
  └── Оптимизация поиска (City First) — [DONE] 2026-04-21
```

**Итого:** ~5-7 дней работы.

---

## 5. Быстрые победы без рефакторинга кода

Если нет времени на рефакторинг, можно немедленно улучшить качество базы SQL-скриптом очистки:

```sql
-- Пометить агрегаторы как spam
UPDATE enriched_companies SET segment = 'spam', crm_score = 0
WHERE website LIKE '%tsargranit.ru%'
   OR website LIKE '%alshei.ru%'
   OR website LIKE '%mipomnim.ru%'
   OR website LIKE '%uznm.ru%'
   OR website LIKE '%monuments.su%'
   OR website LIKE '%uslugio.com%'
   OR website LIKE '%pqd.ru%'
   OR website LIKE '%spravker.ru%'
   OR website LIKE '%orgpage.ru%'
   OR website LIKE '%totadres.ru%'
   OR website LIKE '%mapage.ru%';

-- Пометить jsprav ритуальные категории (не то что ищем)
UPDATE raw_companies SET name = name || ' [RITUAL]'
WHERE source = 'jsprav' 
AND source_url LIKE '%ritualnyie-prinadlezhnosti%';

-- Найти записи без реального имени (для ручной проверки)
SELECT id, name, city, website FROM enriched_companies
WHERE name LIKE 'Памятники%'
   OR name LIKE 'Изготовление памятников%'
   OR name LIKE '%Мастерские%в %'
   OR name LIKE 'Uslugio%'
   OR name LIKE 'PQD%'
ORDER BY crm_score DESC;
```

---

## 6. Ожидаемый результат после исправлений

| Показатель | До | После (оценка) |
|-----------|-----|--------------|
| Агрегаторы в raw_companies | 660 (56% web_search) | ~50 (<5%) |
| jsprav нецелевых категорий | 279 (51%) | ~0 |
| SEO-имена в enriched | 700 (58%) | ~150 (12%) |
| D-сегмент (мало данных) | 513 (42%) | ~250 (20%) |
| Полезных для аутрича (A+B) | 569 (47%) | ~700-800 (60-70%) |

---

## 7. Открытые вопросы

1. **Данила-Мастер как сеть vs агрегатор.** 52 субдомена — реальные локальные точки с разными контактами. Решение: не блокировать субдомены в SKIP_DOMAINS, но помечать is_network=True и не контактировать с ними (они не самостоятельные мастерские).

2. **Граница "агрегатор vs реальная сеть".** `diabazstone.ru` в 13 городах — возможно, реальная мастерская с филиалами. Нужно ручное решение: посмотреть страницы и телефоны.

3. **web_search queries слишком широкие.** Запросы "гранитная мастерская памятники" без указания города возвращают федеральных игроков. Рекомендуется добавить `{self.city}` в начало каждого запроса (вместо добавления в конец), что даст более локальные результаты в DDG.
