# scrapers/web_search.py — поиск компаний через duckduckgo-search + Yandex + Bing
#
# ТРЕБОВАНИЕ: pip install duckduckgo-search
import json
import re
import threading
import time
import warnings
from pathlib import Path
from urllib.parse import urlparse

import yaml

from bs4 import BeautifulSoup

from granite.scrapers.base import BaseScraper
from granite.models import RawCompany, Source
from granite.utils import (
    normalize_phones,
    extract_phones,
    extract_emails,
    extract_domain,
    is_safe_url,
    fetch_page,
    adaptive_delay,
    get_random_ua,
    is_non_local_phone,
)
from loguru import logger

import requests

# ── Проверка зависимости ──────────────────────────────────────────────
try:
    from ddgs import DDGS
    _HAS_DDGS = True
    logger.debug("  ddgs: используется пакет 'ddgs'")
except ImportError:
    _HAS_DDGS = False
    logger.warning(
        "  ⚠ Пакет ddgs НЕ установлен! "
        "Запустите: pip install ddgs"
    )

# Глобальный lock для сериализации поисковых запросов (DDG rate-limit)
_search_lock = threading.Lock()

# ── A-3: Runtime-детектор агрегаторов (домен в N+ городах) ──
_MULTI_CITY_DOMAIN_CACHE: dict[str, set[str]] = {}  # domain → set of cities
_MULTI_CITY_LOCK = threading.Lock()
_MULTI_CITY_THRESHOLD_DEFAULT = 3  # домен в 3+ городах = агрегатор


def _register_domain_city(domain: str, city: str, threshold: int = _MULTI_CITY_THRESHOLD_DEFAULT) -> bool:
    """Регистрирует пару домен-город. Возвращает True если домен превысил порог (агрегатор)."""
    if not domain:
        return False
    with _MULTI_CITY_LOCK:
        if domain not in _MULTI_CITY_DOMAIN_CACHE:
            _MULTI_CITY_DOMAIN_CACHE[domain] = set()
        _MULTI_CITY_DOMAIN_CACHE[domain].add(city.lower())
        count = len(_MULTI_CITY_DOMAIN_CACHE[domain])
        if count >= threshold and count == threshold:
            logger.warning(
                f"  A-3: Автодетектор: домен {domain} найден в {count} городах — агрегатор!"
            )
            return True
        return count >= threshold


def _get_multi_city_domains() -> dict[str, set[str]]:
    """Возвращает копию кэша обнаруженных агрегаторов."""
    with _MULTI_CITY_LOCK:
        return {d: set(cities) for d, cities in _MULTI_CITY_DOMAIN_CACHE.items()
                if len(cities) >= _MULTI_CITY_THRESHOLD_DEFAULT}


def _clear_multi_city_cache():
    """Очищает кэш (для тестов)."""
    with _MULTI_CITY_LOCK:
        _MULTI_CITY_DOMAIN_CACHE.clear()


def _load_detected_aggregators() -> None:
    """A-3: Загружает ранее обнаруженные агрегаторы из data/detected_aggregators.yaml.

    Без этого кэш пуст после каждого перезапуска процесса, и агрегаторы,
    уже обнаруженные в предыдущих запусках, снова проходят через фильтр,
    пока не наберут threshold городов заново.
    """
    path = Path(__file__).parent.parent / "data" / "detected_aggregators.yaml"
    if not path.exists():
        return
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        if not isinstance(data, dict):
            return
        loaded = 0
        with _MULTI_CITY_LOCK:
            for domain, cities in data.items():
                if not isinstance(cities, list):
                    continue
                city_set = {c.lower() for c in cities if isinstance(c, str)}
                if len(city_set) >= _MULTI_CITY_THRESHOLD_DEFAULT:
                    _MULTI_CITY_DOMAIN_CACHE[domain] = city_set
                    loaded += 1
        if loaded:
            logger.info(f"  A-3: Загружено {loaded} агрегаторов из {path}")
    except Exception as e:
        logger.warning(f"  A-3: Не удалось загрузить агрегаторы из {path}: {e}")


# Загружаем ранее обнаруженные агрегаторы при импорте модуля
_load_detected_aggregators()

# ── Кэш недоступных доменов (таймаут/403) — не ретраить в рамках сессии ──
_FAILED_DOMAINS_TTL_DEFAULT = 600  # 10 минут


class FailedDomainCache:
    """Потокобезопасный кэш недоступных доменов с TTL и ограничением размера (P-8).

    Инкапсулирует _FAILED_DOMAINS dict + lock в класс для:
    - Подготовки к multiprocessing ( singleton → DI в будущем)
    - Явного управления TTL и max_size
    - Обратной совместимости через module-level функции
    """

    def __init__(self, ttl: int = _FAILED_DOMAINS_TTL_DEFAULT, max_size: int = 5000):
        self._cache: dict[str, float] = {}
        self._lock = threading.Lock()
        self.ttl = ttl
        self.max_size = max_size

    def is_failed(self, domain: str) -> bool:
        """Проверить, был ли домен недавно недоступен."""
        with self._lock:
            ts = self._cache.get(domain)
            return bool(ts and (time.time() - ts) < self.ttl)

    def mark_failed(self, domain: str) -> None:
        """Запомнить домен как недоступный.

        FIX 4.9: Lazy cleanup при превышении лимита.
        Удаляет expired-записи вместо бесконечного роста словаря.
        """
        with self._lock:
            self._cache[domain] = time.time()
            if len(self._cache) > self.max_size:
                now = time.time()
                expired = [d for d, ts in self._cache.items()
                           if (now - ts) >= self.ttl]
                for d in expired:
                    del self._cache[d]

    def clear(self) -> None:
        """Очистить кэш (для тестов)."""
        with self._lock:
            self._cache.clear()


# Модульный singleton для обратной совместимости
_failed_domain_cache = FailedDomainCache()


def get_failed_domain_ttl(config: dict) -> int:
    """Извлечь TTL кэша недоступных доменов из конфига."""
    return config.get("scraping", {}).get("failed_domain_cache_ttl", _FAILED_DOMAINS_TTL_DEFAULT)


def is_domain_failed(domain: str, ttl: int = _FAILED_DOMAINS_TTL_DEFAULT) -> bool:
    """Проверить, был ли домен недавно недоступен (backward-compat)."""
    return _failed_domain_cache.is_failed(domain)


def mark_domain_failed(domain: str) -> None:
    """Запомнить домен как недоступный (backward-compat)."""
    _failed_domain_cache.mark_failed(domain)

# ── Русские TLD, которым доверяем без дополнительных проверок ──────────
_TRUSTED_TLDS = {".ru", ".su"}

# ── Зарубежные TLD — блокируем результаты с этих доменов ───────────────
_BLOCKED_TLDS = {".ee", ".lv", ".lt", ".ge", ".md", ".am", ".az", ".tm",
                 ".tr", ".cn", ".il", ".pl", ".fi", ".cz", ".it", ".es",
                 ".de", ".fr", ".uk", ".us", ".jp",
                 ".kz", ".by", ".kg", ".uz"}

# ── Стоп-слова (Зарубежные страны и крупные города РФ) ──────────────────
_FOREIGN_COUNTRIES = re.compile(
    r"(?:Эстон[ияию]|Латв[ияию]|Литв[аеы]|Груз[ияию]|Казахстан|Беларус[ьюи]|"
    r"Украин[аеыу]|Молдов[аеы]|Армен[ияию]|Азербайджан|Узбекистан|Туркменистан|"
    r"Кыргызстан|Таджикистан|Турци[еяю]|Китай|Израил[ьюь]|США|Герман[ияиюю]|"
    r"Польш[аеы]|Финлянд[ияиюю]|Чех[ияиюю]|Итали[еяю]|Испан[ияиюю]|"
    r"Tallinn|Riga|Vilnius|Baltic|"
    r"Москв[аеыу]|Петербург[аеуя]|Питер[аеу]|Екатеринбург[аеу]|Казан[ьию]|"
    r"Новосибирск[аеу]|Краснодар[аеу]|Ростов[аеу]|Воронеж[аеу])",
    re.IGNORECASE,
)

# ── Русские ключевые слова для проверки релевантности ──────────────────
_RU_KEYWORDS = re.compile(
    r"(?:памятник|гранит|надгробие|ритуал|мемориал|захоронен|"
    r"могил|камень|плита|монумент|склеп|крематорий|кладбищ|мастерск|"
    r"изготовлен|установк|ритуаль|похорон|гробов|венки|крест|обелиск)",
    re.IGNORECASE,
)

# ── SEO-title детектор: импортируем из utils.py (общий с merger.py) ──
from granite.utils import is_seo_title, is_aggregator_name


# ── Негатив-фильтр: мусорные темы в title ────────────────────────────────
_JUNK_KEYWORDS = re.compile(
    r"(?:прогноз|ставк|букмекер|казино|азарт|спорт|футбол|хоккей|"
    r"бонус|бесплатн.*скачат|кино|фильм|сериал|аниме|игра|игрушк|"
    r"порн|эрот|дать объявлен|авито|доска объявлен|новости|"
    r"погода|курс.*валют|обмен.*крипт|майнинг)",
    re.IGNORECASE,
)


class WebSearchScraper(BaseScraper):
    """Поиск и сбор контактов компаний через поисковики + парсинг сайтов.

    Работает без внешних CLI:
    1. Поиск запросов из конфигурации через duckduckgo-search / Yandex / Bing
    2. Парсит каждый найденный сайт через requests + BeautifulSoup
    3. Извлекает телефоны, email, адреса
    """

    # Домены, которые НЕ ведут на сайты компаний — пропускаем
    # Разделы: поисковики, соцсети, видео, музыка, стриминг, путешествия,
    # банкинг, словари, маркетплейсы, форумы, новости, IT-сервисы
    SKIP_DOMAINS = [
        # ── Поисковики ──
        "duckduckgo.com",
        "google.com",
        "google.co",
        "googleapis.com",
        "bing.com",
        "yandex.ru",
        "yandex.com",
        "baidu.com",
        "mojeek.com",
        "brave.com",
        "yahoo.com",
        "yahoo.co.jp",
        "search.yahoo.co.jp",
        "detail.chiebukuro.yahoo.co.jp",
        "yahoo-net.jp",
        "mail.yahoo.co.jp",
        "news.yahoo.co.jp",
        "weather.yahoo.co.jp",
        "yahoo.jp",
        # ── Соцсети / мессенджеры ──
        "vk.com",
        "telegram.org",
        "instagram.com",
        "facebook.com",
        "ok.ru",
        "twitter.com",
        "x.com",
        "tiktok.com",
        "reddit.com",
        "pinterest.com",
        "linkedin.com",
        "weibo.com",
        "douyin.com",
        # ── Видео / стриминг / музыка ──
        "youtube.com",
        "rutube.ru",
        "bilibili.com",
        "t.bilibili.com",
        "netflix.com",
        "spotify.com",
        "accounts.spotify.com",
        "webplayer.byspotify.com",
        "open.spotify.com",
        "music.youtube.com",
        "bandsintown.com",
        "ticketmaster.com",
        "tving.com",
        "coupangplay.com",
        "moviefone.com",
        "moviesanywhere.com",
        "tv.apple.com",
        "justwatch.com",
        "tvguide.com",
        "movies.fandom.com",
        "comingsoon.net",
        "imdb.com",
        "kinopoisk.ru",
        # ── Путешествия / отели / авиабилеты ──
        "trip.com",
        "tripadvisor.com",
        "tripadvisor.cn",
        "tripadvisor.com.vn",
        "klook.com",
        "agoda.com",
        "booking.com",
        "airbnb.com",
        "routard.com",
        "lonelyplanet.com",
        "travelandleisure.com",
        "cn.tripadvisor.com",
        "voilaquebec.com",
        "restgeo.com",
        "you.ctrip.com",
        "china-travelnote.com",
        "eastchinatrip.com",
        "th.trip.com",
        "vn.trip.com",
        "mia.vn",
        "saigontimestravel.com",
        "travelshelper.com",
        "travel.destinationcanada.cn",
        "destinationcanada.cn",
        # ── Банкинг / финансы ──
        "hdfcbank.com",
        "netbanking.hdfcbank.com",
        "hdfc.bank.in",
        "now.hdfc.bank.in",
        "v.hdfc.bank.in",
        "hdfcbankdifc.com",
        "hdfc.biz",
        "flexatuat.hdfcbank.com",
        "kiwoom.com",
        "i.kiwoom.com",
        "www1.kiwoom.com",
        "www3.kiwoom.com",
        "bankbazaar.com",
        "sberbank.ru",
        "tinkoff.ru",
        "alfabank.ru",
        "vtb.ru",
        # ── Словари / переводчики ──
        "spanishdict.com",
        "deepl.com",
        "collinsdictionary.com",
        "translate.com",
        "merriam-webster.com",
        "dictionary.cambridge.org",
        "reverso.net",
        "translate.google.com",
        # ── Маркетплейсы / магазины приложений ──
        "ozon.ru",
        "wildberries.ru",
        "market.yandex.ru",
        "apps.apple.com",
        "apps.microsoft.com",
        "play.google.com",
        "ssg.com",
        "yes24.com",
        "coupang.com",
        # ── Классифайды / справочники (не ритуальные) ──
        "avito.ru",
        "hh.ru",
        "gismeteo.ru",
        "2gis.ru",
        "2gis.com",
        "zhihu.com",
        "mail.ru",
        "rambler.ru",
        "aol.com",
        "login.aol.com",
        "mail.aol.com",
        "jsprav.ru",   # обрабатывается JspravScraper, поддомены блокируются через endswith()
        "yell.ru",     # disabled (enabled: false), дубли не нужны
        # ── Спорт / ставки / прогнозы ──
        "livesport.ru",
        "vprognoze.ru",
        "bombardir.ru",
        "soccer365.ru",
        "betzona.ru",
        "sportsdaily.ru",
        "ligastavok.ru",
        "winline.ru",
        "leonbets.com",
        "fonbet.ru",
        "1xbet.com",
        "marathonbet.ru",
        "olimp.kz",
        "bwin.com",
        "flashscore.com",
        "flashscore.ru",
        "scoreboard.com",
        "whoscored.com",
        "transfermarkt.com",
        # ── Случайный мусор из логов ──
        "slowroads.io",
        "old.slowroads.io",
        "driftmas24.slowroads.io",
        "driftmas.slowroads.io",
        "driftmas23.slowroads.io",
        "yuleleague24.slowroads.io",
        "baanmaha.com",
        "namu.wiki",
        "anibase.net",
        "doubao.com",
        "onthisday.com",
        "spigotmc.org",
        "worldometers.info",
        "worldpopulationreview.com",
        "countrymeters.info",
        "populationpyramids.org",
        "allevents.in",
        "localgo.by",
        "irr.by",
        "pdfcompressor.com",
        "support.microsoft.com",
        "elevenforum.com",
        "zoom.us",
        "forum.lowyat.net",
        "sante-medecine.journaldesfemmes.fr",
        "office54.net",
        "ryumasblog.com",
        "suisui-office.com",
        "jo-sys.net",
        "choge-blog.com",
        "pc-jiten.com",
        "it-tool-labo.top",
        "jbc-ltd.com",
        "m32006400n.xsrv.jp",
        "windows.point-b.jp",
        "investopedia.com",
        "legal.thomsonreuters.com",
        "wikipedia.org",
        "wikidata.org",
        "wikimedia.org",
        # ── Агрегаторы памятников (один сайт → страницы по всем городам РФ) ──
        # Аудит A-1: эти домены создают страницы-каталоги для каждого города
        # с федеральными контактами (колл-центр), а не реальными местными мастерскими.
        # Паттерн: tsargranit.ru/abaza.html, alshei.ru/abakan.html и т.д.
        "tsargranit.ru",              # 59 городов
        "alshei.ru",                  # 51 город
        "mipomnim.ru",                # 48 городов
        "uznm.ru",                    # 36 городов
        "v-granit.ru",                # 30 городов
        "spravker.ru",                # справочник, 46 записей
        "monuments.su",               # 33 города
        "masterskay-granit.ru",       # 26 городов
        "gr-anit.ru",                 # 26 городов
        "nbs-granit.ru",              # 24 города
        "xn--d1aigketcf.xn--p1ai",   # 23 города (памятники.рф)
        "granit-pamiatnik.ru",        # 19 городов
        "postament.ru",               # 18 городов
        "uslugio.com",                # справочник, 17 городов
        "pamiatnikiizgranita.ru",     # 17 городов
        "monuments39.ru",             # 17 городов
        "asgranit.ru",                # 16 городов
        "diabazstone.ru",             # 16 городов (проверить — возможно реальная сеть)
        "zoon.ru",                    # справочник, 16 городов
        "pomnivsegda.ru",             # 17 городов
        "izgotovleniepamyatnikov.ru", # 15 городов
        "seprava.ru",                 # 15 городов
        "pamatniki.ru",               # 13 городов
        "pqd.ru",                     # агрегатор-справочник, 13 городов
        "thezeitgeistmovement.ru",    # 13 городов
        "artgranit33.ru",             # 12 городов
        "granit33market.ru",          # 11 городов
        "rosreestrr.ru",              # 10 городов
        "granitunas.ru",              # 10 городов
        "fabrika-vek.ru",             # 10 городов
        "mapage.ru",                  # справочник
        "orgpage.ru",                 # справочник
        "totadres.ru",                # справочник
        "kamelotstone.ru",            # сеть с city-страницами
        "kamenpamyati.ru",            # 9 городов
        "home-granit.ru",             # 9 городов
        "ritualst.ru",                # 8 городов
        "gidgranit.ru",               # 8 городов
        "luxritual.ru",               # 8 городов
        "granitreal.ru",              # 8 городов
        "okultureno.ru",              # 8 городов
        "granit-art.ru",              # 7 городов
        "vekgranit.ru",               # 7 городов
        "artmemorials.ru",            # 7 городов
        "dymovskiy.ru",               # 7 городов
        "bizorg.su",                  # справочник, 5 городов
        "best-monuments.ru",          # 5 городов
        "eurogranite.ru",             # 5 городов
        "e-memorial.ru",              # 5 городов
        "granitmasterplus.ru",        # 5 городов
        "grad-ex.ru",                 # 5 городов
        "planetagranita.ru",          # 5 городов
        "kamengorod.ru",              # 5 городов
        "ritual-reestr.ru",           # 6 городов
        "pamyatnik-online.ru",        # 6 городов
        "pamiatniky.ru",              # 6 городов
        "ritualsp.ru",                # 5 городов
        "ritualagency.ru",            # 5 городов
        # ── B1: Новые агрегаторы из аудита БД ──
        "vmkros.ru",                  # 11 городов — агрегатор
        "exkluziv-granit.ru",         # 7 городов — city-страницы
        "gravestone.ru",              # 6 городов — агрегатор
        "katangranit.ru",             # 6 городов — агрегатор
        "granit-master.shop",         # 6 городов — агрегатор
        "monument-nd.ru",             # 6 городов — Подмосковье агрегатор
        "grandmonument.ru",           # 5 городов — агрегатор
        "rting.ru",                   # 5 городов — справочник-агрегатор
        "altai-offroad.ru",           # 5 городов — НЕРЕЛЕВАНТНЫЙ (внедорожники!)
        "steel-prof.ru",              # 4 города — агрегатор
        "rosbaltnord.ru",             # 4 города — агрегатор
        "urbanplaces.su",             # 4 города — агрегатор
        "stella-master.ru",           # 4 города — агрегатор
        "nikapamyatniki.ru",          # 7 городов — агрегатор
        "памятники-цены.рф",           # 6 городов — агрегатор (кириллический домен)
        "ripme.ru",                   # 5 городов
        "ratusha-pamyatniki.ru",      # 5 городов
        "masternovikov.ru",           # 5 городов
        "izgotovleniye-pamyatnikov.ru",  # 5 городов
        "sitc.ru",                    # 6 городов
        # ── Данила-Мастер — реальная франшиза, НЕ блокируем ──
        # Субдомены (abaza.danila-master.ru) — реальные локальные точки
        # с разными контактами. Обработка через is_network=True в A-6.
    ]

    def __init__(self, config: dict, city: str):
        super().__init__(config, city)
        self.source_config = config.get("sources", {}).get("web_search", {})
        self.queries = self.source_config.get("queries", [])
        self.search_limit = self.source_config.get("search_limit", 10)
        self._failed_domain_ttl = get_failed_domain_ttl(config)
        # FIX 4.8: Конфигурируемый timeout вместо захардкоженного 15
        self.timeout = self.source_config.get("timeout", 15)
        # HTTP сессия для Yandex / Bing
        self._session = requests.Session()
        self._session.headers.update(
            {
                "User-Agent": get_random_ua(),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
            }
        )
        # FIX 2.2: Нормализованный set для быстрого endswith-поиска
        self._SKIP_DOMAINS_SET = frozenset(
            d.lower()[4:] if d.lower().startswith("www.") else d.lower()
            for d in self.SKIP_DOMAINS
        )
        # Фильтр по чужому городу: корни названий городов из ДРУГИХ регионов.
        # Строится один раз при инициализации скрейпера.
        # Используется в _is_relevant_url() чтобы отсеивать результаты
        # вида "Гранитная мастерская в Москве" при скрапинге Абазы.
        self._foreign_city_roots = self._build_foreign_city_roots()
        # A-3: Порог детектора агрегаторов из конфига
        self._aggregator_threshold = self.source_config.get("aggregator_threshold", _MULTI_CITY_THRESHOLD_DEFAULT)

    # ── A-3: Сохранение обнаруженных агрегаторов ──

    def _save_detected_aggregators(self) -> None:
        """A-3: Сохраняет обнаруженные агрегаторы в data/detected_aggregators.yaml."""
        multi_city = _get_multi_city_domains()
        if not multi_city:
            return
        path = Path(__file__).parent.parent / "data" / "detected_aggregators.yaml"
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {domain: sorted(cities) for domain, cities in sorted(multi_city.items())}
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, allow_unicode=True, default_flow_style=False)
        logger.info(f"  A-3: Сохранено {len(multi_city)} обнаруженных агрегаторов в {path}")

    # ── A-4: Извлечение имени компании ──

    def _is_city_page_name(self, name: str) -> bool:
        """Проверяет, содержит ли имя целевой город (с падежами).

        "Памятники в Абазе" → True, "Гранит-Мастер" → False
        """
        if not name or not self.city:
            return False
        city_lower = self.city.lower()
        name_lower = name.lower()
        # Проверяем корень города (без окончания)
        city_stem = city_lower.rstrip("аеоуияью")
        if len(city_stem) >= 3 and city_stem in name_lower:
            return True
        if city_lower in name_lower:
            return True
        return False

    def _extract_company_name(self, soup) -> str | None:
        """A-4: Извлечение имени компании с приоритетной цепочкой.

        Приоритет: JSON-LD Organization → og:site_name → <title> до разделителя → <h1>
        Каждый уровень проверяется на is_seo_title() и _is_city_page_name().
        Возвращает None если реальное имя не найдено.
        """
        # 1. JSON-LD Organization / LocalBusiness / Brand
        for script in soup.select("script[type='application/ld+json']"):
            try:
                data = json.loads(script.string)
                items = data if isinstance(data, list) else [data]
                for item in items:
                    if isinstance(item, dict) and item.get("@type") in ("Organization", "LocalBusiness", "Brand"):
                        name = item.get("name") or item.get("legalName")
                        if name:
                            name = name.strip()
                            if (3 < len(name) < 80
                                    and not is_seo_title(name)
                                    and not is_aggregator_name(name)
                                    and not self._is_city_page_name(name)):
                                return name
            except (json.JSONDecodeError, TypeError, AttributeError):
                pass

        # 2. og:site_name
        og = soup.find("meta", attrs={"property": "og:site_name"})
        if og and og.get("content"):
            name = og["content"].strip()
            if (3 < len(name) < 80
                    and not is_seo_title(name)
                    and not is_aggregator_name(name)
                    and not self._is_city_page_name(name)):
                return name

        # 3. <title> до разделителя
        title_tag = soup.find("title")
        if title_tag:
            title_text = title_tag.get_text(strip=True)
            for sep in [" | ", " — ", " - ", "–", "·"]:
                if sep in title_text:
                    title_text = title_text.split(sep)[0].strip()
                    break
            if (3 < len(title_text) < 80
                    and not is_seo_title(title_text)
                    and not is_aggregator_name(title_text)
                    and not self._is_city_page_name(title_text)):
                return title_text

        # 4. <h1> — короткий, без SEO-паттернов
        h1 = soup.find("h1")
        if h1:
            name = h1.get_text(strip=True)
            if (3 < len(name) < 60
                    and not is_seo_title(name)
                    and not is_aggregator_name(name)
                    and not self._is_city_page_name(name)):
                return name

        return None

    # ── A-5: Географическая валидация телефонов ──

    def _is_local_phone(self, phone: str) -> bool:
        """A-5: Проверяет, является ли телефон локальным для скрапинга.

        Делегирует к is_non_local_phone() из utils.py.
        Возвращает True если телефон локальный (OK), False если не-локальный.
        """
        return not is_non_local_phone(phone, self.city)

    def _is_skip_domain(self, url: str) -> bool:
        """Проверяет, нужно ли пропустить URL (каталоги, соцсети, мусор).

        FIX 2.2: Используем hostname-сравнение через endswith вместо substring match.
        Раньше: '2gis.com' in 'my2gis.com' = True (ложное срабатывание).
        Теперь: точный match или endswith для субдоменов (detail.chiebukuro.yahoo.co.jp).
        """
        try:
            parsed = urlparse(url)
            hostname = (parsed.hostname or "").lower()
            if hostname.startswith("www."):
                hostname = hostname[4:]
            return any(
                hostname == d or hostname.endswith("." + d)
                for d in self._SKIP_DOMAINS_SET
            )
        except Exception:
            # Fallback для невалидных URL — оригинальный substring match
            return any(d in url for d in self.SKIP_DOMAINS)

    def _build_foreign_city_roots(self) -> list[str]:
        """Строит список корней городов из ДРУГИХ регионов.

        Использует build_city_lookup() из region_resolver
        вместо собственного кода генерации падежей.
        """
        from granite.pipeline.region_resolver import build_city_lookup, _load_regions
        target_region = self.city_config.get("region", "")
        if not target_region:
            return []

        regions = _load_regions()
        target_cities = set(regions.get(target_region, []) or [])

        city_lookup, sorted_roots = build_city_lookup()
        return [
            root for root in sorted_roots
            if city_lookup.get(root) and city_lookup[root] not in target_cities
        ]

    def _title_mentions_foreign_city(self, title: str) -> bool:
        """Проверяет, упоминает ли title город из другого региона.

        Примеры:
          "Гранитная мастерская в Москве" → True (Москва не в Хакасии)
          "Гранитная мастерская в Абакане" → False (Абакан в Хакасии)
          "Памятники из гранита" → False (нет упоминания города)
        """
        if not title or not self._foreign_city_roots:
            return False

        title_lower = title.lower()
        title_len = len(title_lower)

        for root in self._foreign_city_roots:
            pos = 0
            while True:
                pos = title_lower.find(root, pos)
                if pos == -1:
                    break
                # Проверяем только НАЧАЛЬНУЮ границу слова.
                # Конечную границу НЕ проверяем — нужно ловить
                # предложный падеж: "москв" в "в Москве" (е — буква, но это наш город).
                # Без after-check ложных срабатываний минимум:
                # "москв" не может появиться в середине другого слова
                # если проверена начальная граница.
                before_ok = (pos == 0 or not title_lower[pos - 1].isalpha())
                if before_ok:
                    return True
                pos += 1

        return False

    def _is_relevant_url(self, url: str, title: str = "") -> bool:
        """Фильтрация URL: оставляем только релевантные результаты.

        Стратегия:
        1. Блок-лист доменов (SKIP_DOMAINS)
        2. Блокируем зарубежные страны в title
        3. Для .ru/.su: проверяем, что title не упоминает чужой город
        4. Доверяем русским TLD (.by, .kz и т.д.) с проверкой ключевых слов
        5. Для остальных — требуем русские ключевые слова в title
        """
        if not url:
            return False

        # 1. Блок-лист
        if self._is_skip_domain(url):
            return False

        # 2. Блокируем зарубежные страны в title
        if title and _FOREIGN_COUNTRIES.search(title):
            logger.debug(f"  WebSearch: ФИЛЬТР (зарубежная страна): {title[:60]}")
            return False

        # 2.5 Блокируем зарубежные TLD (Estonia, Latvia, etc.)
        parsed = urlparse(url)
        domain = parsed.hostname or ""
        for tld in _BLOCKED_TLDS:
            if domain.endswith(tld):
                logger.debug(f"  WebSearch: ФИЛЬТР (зарубежный TLD {tld}): {url}")
                return False

        # 2.6 Негатив-фильтр: блокируем мусорные темы
        if title and _JUNK_KEYWORDS.search(title):
            logger.debug(f"  WebSearch: ФИЛЬТР (мусорная тема): {title[:60]}")
            return False

        # 3. Для .ru/.su — доверяем, но проверяем что title
        #    не упоминает город из ДРУГОГО региона.
        #    Без этой проверки "Гранитная мастерская в Москве" проходила
        #    бы как результат для Абазы.
        if domain.endswith((".ru", ".su")):
            if title and self._title_mentions_foreign_city(title):
                logger.debug(f"  WebSearch: ФИЛЬТР (чужой город): {title[:60]}")
                return False
            return True

        # 4. Для generic TLD (.com, .net, .org и т.д.) — требуем
        #    русские ключевые слова И явное упоминание искомого города
        if domain.endswith((".com", ".net", ".org", ".io", ".info", ".biz")):
            if title and _RU_KEYWORDS.search(title):
                city_mentioned = self.city.lower() in title.lower()
                if city_mentioned:
                    return True
            logger.debug(f"  WebSearch: ФИЛЬТР (generic TLD без города): {url}")
            return False

        # 5. Для остальных не-русских TLD: проверяем title на русские ключевые слова
        if title and _RU_KEYWORDS.search(title):
            return True

        # 5. Для не-русских TLD без релевантного title — фильтруем
        logger.debug(f"  WebSearch: ФИЛЬТР (не рус. домен, нет ключевых слов): {url}")
        return False

    # ═══════════════════════════════════════════════════════════════════
    #  ПОИСКОВИК 1: duckduckgo-search (DDGS API)
    #  НЕ использует lite.duckduckgo.com — использует внутренний API DDG
    #  Работает из любой точки мира, включая Вьетнам.
    # ═══════════════════════════════════════════════════════════════════

    def _search_ddgs(self, query: str) -> list[dict]:
        """Поиск через duckduckgo-search пакет (DDGS API).

        Использует API-эндпоинты DDG, а не lite.duckduckgo.com,
        поэтому работает из любой точки мира.
        """
        if not _HAS_DDGS:
            logger.warning(
                "  DDGS: пакет не установлен! pip install duckduckgo-search"
            )
            return []

        results = []
        filtered = 0
        with _search_lock:
            try:
                with DDGS() as ddgs:
                    # region="ru-ru" для русских результатов
                    for r in ddgs.text(
                        query, region="ru-ru", max_results=self.search_limit
                    ):
                        url = r.get("href", "")
                        title = r.get("title", "")
                        if url and title and self._is_relevant_url(url, title):
                            results.append({"url": url, "title": title})
                        else:
                            filtered += 1

                if filtered > 0:
                    logger.info(
                        f"  WebSearch: DDGS отфильтровано {filtered} нерелевантных"
                    )

                return results

            except Exception as e:
                logger.warning(f"  DDGS: ошибка — {e}")
                return []

    # ═══════════════════════════════════════════════════════════════════
    #  ПОИСКОВИК 2: Bing
    #  Фоллбэк с раскрыванием redirect URL (/ck/a?)
    # ═══════════════════════════════════════════════════════════════════

    def _search_bing(self, query: str) -> list[dict]:
        """Bing search — фоллбэк."""
        results = []
        search_url = "https://www.bing.com/search"
        params = {
            "q": query,
            "count": self.search_limit,
            "cc": "ru",
            "setmkt": "ru-RU",
        }

        # Anti-bot: set cookies that Bing expects
        self._session.cookies.set("_EDGE_S", "mkt=ru-ru")
        self._session.cookies.set("_EDGE_V", "1")

        try:
            resp = self._session.get(
                search_url,
                params=params,
                timeout=min(self.timeout, 30),
                allow_redirects=True,
                headers={
                    "User-Agent": self._session.headers.get("User-Agent", get_random_ua()),
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
                    "Accept-Encoding": "gzip, deflate, br",
                    "DNT": "1",
                    "Connection": "keep-alive",
                    "Upgrade-Insecure-Requests": "1",
                    "Referer": "https://www.bing.com/",
                },
            )

            if not resp.text or resp.status_code != 200:
                logger.warning(f"  Bing: status={resp.status_code}")
                return results

            html_len = len(resp.text)
            logger.debug(f"  Bing: HTML {html_len} байт")

            soup = BeautifulSoup(resp.text, "html.parser")

            # ── Стратегия 1: li.b_algo (стандартная разметка) ──
            for li in soup.select("li.b_algo"):
                anchor = li.find("a", href=True)
                if not anchor:
                    continue

                href = anchor.get("href", "")
                title = anchor.get_text(strip=True)

                if not href or not title:
                    continue
                if "bing.com" in href and "/ck/a" not in href:
                    continue
                if "microsoft.com" in href:
                    continue

                # Раскрываем Bing redirect URL
                if "bing.com/ck/a" in href:
                    try:
                        real = self._session.get(
                            href, timeout=8, allow_redirects=True
                        ).url
                        if real and "bing.com" not in real:
                            href = real
                        else:
                            continue
                    except Exception:
                        continue

                if not self._is_relevant_url(href, title):
                    continue

                results.append({"url": href, "title": title})

            # ── Стратегия 2: fallback — любые ссылки ──
            if not results:
                logger.warning("  Bing: b_algo не найден, пробуем fallback")
                for a in soup.find_all("a", href=True):
                    href = a.get("href", "")
                    title = a.get_text(strip=True)
                    if (
                        not title
                        or not href
                        or len(title) < 15
                        or not href.startswith(("http://", "https://"))
                        or not self._is_relevant_url(href, title)
                    ):
                        continue
                    results.append({"url": href, "title": title})
                    if len(results) >= self.search_limit:
                        break

            return results[: self.search_limit]

        except requests.Timeout:
            logger.warning("  Bing: timeout")
        except Exception as e:
            logger.warning(f"  Bing: ошибка — {e}")

        return results

    # ═══════════════════════════════════════════════════════════════════
    #  ОРКЕСТРАТОР ПОИСКА
    # ═══════════════════════════════════════════════════════════════════

    def _search(self, query: str) -> list[dict]:
        """Поиск: DDGS.

        Yandex отключён: всегда возвращает капчу.
        Bing отключён: всегда возвращает 0 (анти-бот блокировка).
        DDGS (ddgs пакет) — единственный рабочий поисковик.
        """

        results = self._search_ddgs(query)
        if results:
            logger.info(f"  WebSearch: DDGS — {len(results)} результатов")
        else:
            logger.info("  WebSearch: DDGS — 0 результатов")
        return results

    # ═══════════════════════════════════════════════════════════════════
    #  СБОР ДАННЫХ
    # ═══════════════════════════════════════════════════════════════════

    def scrape(self) -> list[RawCompany]:
        # ═══════════════════════════════════════════════════════════════
        #  Проход 1: сбор URL из поиска + дедупликация
        # ═══════════════════════════════════════════════════════════════
        search_results = []
        seen_urls = set()

        for query in self.queries:
            # A-1/A-3: Город в начале запроса для лучшей локализации DDG
            search_query = f"{self.city} {query}"
            logger.info(f"  WebSearch: {search_query}")

            web_results = self._search(search_query)
            if not web_results:
                continue

            for item in web_results:
                url = item["url"]
                title = item["title"]
                if not url or not title:
                    continue

                if url in seen_urls:
                    continue
                seen_urls.add(url)
                search_results.append(item)

            adaptive_delay(min_sec=2.0, max_sec=5.0)

        logger.info(f"  WebSearch: найдено {len(search_results)} URL (поиск)")

        # ═══════════════════════════════════════════════════════════════
        #  Проход 2: скрейпинг сайтов + мягкая фильтрация (P-3)
        # ═══════════════════════════════════════════════════════════════
        companies = []
        seen_domains = set()
        enriched = 0
        skipped_unavailable = 0

        for item in search_results:
            domain = extract_domain(item["url"])
            if domain and domain in seen_domains:
                continue

            # A-3: Регистрируем домен+город, пропускаем автодетектированных агрегаторов
            if domain and _register_domain_city(domain, self.city, self._aggregator_threshold):
                logger.debug(f"  A-3: пропуск {domain} (автодетектор: агрегатор)")
                skipped_unavailable += 1
                continue

            details = self._scrape_details(item["url"])
            adaptive_delay(min_sec=1.0, max_sec=2.5)

            # Мягкий фильтр (P-3): отсекаем только полностью недоступные ресурсы.
            # Сайты с website, но без контактов — СОХРАНЯЕМ для enrichment
            # (MessengerScanner и tg_finder найдут контакты позже).
            if not details:
                skipped_unavailable += 1
                continue

            if domain:
                seen_domains.add(domain)
            enriched += 1

            # B4: Имя компании — fallback-цепочка (site name → search title → domain)
            raw_name = details.get("company_name")
            search_title = item["title"]

            if raw_name and not is_seo_title(raw_name) and not is_aggregator_name(raw_name):
                company_name = raw_name
            elif not is_seo_title(search_title) and not is_aggregator_name(search_title):
                company_name = search_title
            else:
                # Всё плохо — берём домен как имя (лучше чем SEO-мусор)
                domain = extract_domain(item["url"]) or ""
                company_name = domain or search_title

            company = RawCompany(
                    source=Source.WEB_SEARCH,
                    source_url=item["url"],
                    name=company_name,
                    phones=normalize_phones(details.get("phones", [])),
                    address_raw=details.get("addresses", [""])[0] if details.get("addresses") else "",
                    website=item["url"],
                    emails=details.get("emails", []),
                    city=self.city,
                    region=self.city_config.get("region", ""),
                )

            # A-5: Географическая валидация телефонов
            # Если ВСЕ телефоны не-локальные — это признак агрегатора
            # (федеральный колл-центр с московским номером для провинциального города).
            if company.phones and all(is_non_local_phone(p, self.city) for p in company.phones):
                logger.info(
                    f"  A-5: Все телефоны не-локальные для {self.city}: {company.name[:50]}"
                )
                company.needs_review = True
                company.review_reason = "non_local_phones"

            # A-5: Валидация адресов (Address Detection)
            # Ищем упоминания ДРУГИХ городов в контактной зоне
            foreign_city = self._extract_contact_city(details.get("_raw_html", ""))
            if foreign_city:
                logger.info(
                    f"  A-5: Найден чужой город ({foreign_city}) на странице {company.name[:50]}"
                )
                company.needs_review = True
                reason = f"foreign_city_address({foreign_city})"
                company.review_reason = (company.review_reason + " " + reason).strip()

            companies.append(company)

        logger.info(
            f"  WebSearch: обогащено {enriched}, "
            f"недоступно {skipped_unavailable}, "
            f"итого {len(companies)} компаний"
        )

        # Фильтр по российскому телефону ВЫКЛЮЧЕН.
        # Раньше: компании без найденного телефона отбрасывались (30-50% потерь).
        # Теперь: все компании попадают в raw_companies, фильтрация на этапе дедупликации.
        # Если нужен — включить через config: sources.web_search.require_ru_phone: true
        require_ru_phone = self.source_config.get("require_ru_phone", False)
        if require_ru_phone and companies:
            before = len(companies)
            filtered = []
            for c in companies:
                has_ru_phone = any(
                    p.startswith("7") and len(p) == 11
                    for p in c.phones
                )
                if has_ru_phone:
                    filtered.append(c)
                else:
                    logger.debug(
                        f"  WebSearch: ФИЛЬТР (не российский телефон): {c.name[:50]}"
                    )
            companies = filtered
            if len(companies) < before:
                logger.info(
                    f"  WebSearch: отфильтровано {before - len(companies)} без российских телефонов"
                )

        # A-3: Удаляем компании, чьи домены оказались агрегаторами
        # (домены, которые появились в >=threshold городах за эту сессию)
        multi_city = _get_multi_city_domains()
        if multi_city:
            before_a3 = len(companies)
            companies = [c for c in companies
                        if extract_domain(c.website or c.source_url or "") not in multi_city]
            removed_a3 = before_a3 - len(companies)
            if removed_a3:
                logger.info(f"  A-3: Удалено {removed_a3} компаний-агрегаторов (мульти-город)")

        # A-3: Сохраняем обнаруженные агрегаторы
        self._save_detected_aggregators()

        return companies

    # ═══════════════════════════════════════════════════════════════════
    #  ДЕТАЛЬНЫЙ СКРАПИНГ САЙТОВ
    # ═══════════════════════════════════════════════════════════════════

    def _scrape_details(self, url: str) -> dict | None:
        """Детальный скрапинг сайта через requests + BeautifulSoup."""
        if not is_safe_url(url):
            return None

        domain = extract_domain(url)
        if domain and is_domain_failed(domain, self._failed_domain_ttl):
            logger.debug(f"  WebSearch: пропуск {domain} (ранее недоступен)")
            return None

        try:
            html = fetch_page(url, timeout=min(self.timeout, 30))
            if not html:
                # fetch_page вернул None — домен скорее всего мёртв
                if domain:
                    mark_domain_failed(domain)
                return None
            if len(html) < 100:
                return None
        except Exception as e:
            # Таймаут, Connection error, HTTP ошибки (4xx/5xx) — кэшируем домен
            err_str = str(e).lower()
            if any(kw in err_str for kw in ("timeout", "connection", "403", "429", "503", "502", "ssl", "resolve")):
                if domain:
                    mark_domain_failed(domain)
            logger.debug(f"  WebSearch: не удалось загрузить {url}: {e}")
            return None

        return self._extract_contacts(html)

    def _extract_contact_city(self, html: str) -> str | None:
        """A-5: Пытается найти город в контактной информации страницы.
        
        Использует self._foreign_city_roots для детекции упоминаний других городов.
        """
        if not html or not self._foreign_city_roots:
            return None
            
        # Ограничиваем поиск "контактной зоной" (футер или блок контактов)
        # Если не нашли явных блоков, берем весь текст
        soup = BeautifulSoup(html, "html.parser")
        contact_zone = soup.find(["footer", "address"]) or soup.find(id=re.compile(r"contact|footer", re.I)) or soup
        text = contact_zone.get_text(separator=" ").lower()
        
        for root in self._foreign_city_roots:
            pos = text.find(root)
            if pos != -1:
                # Простейшая проверка границ слова
                if pos == 0 or not text[pos - 1].isalpha():
                    # Проверяем, что это не наш город (на случай если корни похожи)
                    # Но foreign_city_roots уже отфильтрованы по региону.
                    from granite.pipeline.region_resolver import build_city_lookup
                    lookup, _ = build_city_lookup()
                    return lookup.get(root, root)
                    
        return None

    def _extract_contacts(self, html: str) -> dict | None:
        """Извлечение контактов из HTML."""
        soup = BeautifulSoup(html, "html.parser")

        data_out: dict = {"phones": [], "emails": [], "addresses": [], "company_name": None, "_raw_html": html}

        # A-4: Извлечение имени через приоритетную цепочку
        data_out["company_name"] = self._extract_company_name(soup)

        # 1. Телефоны из tel: ссылок
        for tel_link in soup.select('a[href^="tel:"]'):
            href = tel_link.get("href", "")
            phone = href.replace("tel:", "").strip()
            if phone:
                data_out["phones"].append(phone)

        # Также из текста страницы
        text = soup.get_text(separator=" ")
        for p in extract_phones(text):
            if p not in data_out["phones"]:
                data_out["phones"].append(p)

        # 2. Email из mailto: ссылок (приоритет — обычно реальные)
        for mailto in soup.select('a[href^="mailto:"]'):
            href = mailto.get("href", "")
            email = href.replace("mailto:", "").strip().split("?")[0]
            if email and email not in data_out["emails"]:
                data_out["emails"].append(email)

        # Email из текста HTML
        html_emails = extract_emails(html)
        for em in html_emails:
            if em not in data_out["emails"]:
                data_out["emails"].append(em)

        # 3. Адреса
        address_patterns = [
            r"г\.?\s+[А-Яа-яё]+\s*,?\s*ул\.?\s+[А-Яа-яё]+",
            r"г\.?\s+[А-Яа-яё]+\s*,?\s*[А-Яа-яё]+\s+\d+",
        ]
        for pattern in address_patterns:
            found = re.findall(pattern, text)
            for addr in found:
                if addr not in data_out["addresses"]:
                    data_out["addresses"].append(addr)

        has_data = data_out["phones"] or data_out["emails"] or data_out["addresses"]
        return data_out if has_data else None
