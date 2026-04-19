# scrapers/web_search.py — поиск компаний через duckduckgo-search + Yandex + Bing
#
# ТРЕБОВАНИЕ: pip install duckduckgo-search
import json
import re
import threading
import time
import warnings
from urllib.parse import urlparse

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

# ── Кэш недоступных доменов (таймаут/403) — не ретраить в рамках сессии ──
_FAILED_DOMAINS: dict[str, float] = {}  # domain -> timestamp
_FAILED_DOMAINS_LOCK = threading.Lock()
_FAILED_DOMAINS_TTL_DEFAULT = 600  # 10 минут


def get_failed_domain_ttl(config: dict) -> int:
    """Извлечь TTL кэша недоступных доменов из конфига."""
    return config.get("scraping", {}).get("failed_domain_cache_ttl", _FAILED_DOMAINS_TTL_DEFAULT)


def is_domain_failed(domain: str, ttl: int = _FAILED_DOMAINS_TTL_DEFAULT) -> bool:
    """Проверить, был ли домен недавно недоступен."""
    with _FAILED_DOMAINS_LOCK:
        ts = _FAILED_DOMAINS.get(domain)
        if ts and (time.time() - ts) < ttl:
            return True
        return False


def mark_domain_failed(domain: str):
    """Запомнить домен как недоступный.

    FIX 4.9: Lazy cleanup при превышении лимита.
    Удаляет expired-записи вместо бесконечного роста словаря.
    """
    _MAX_FAILED_DOMAINS = 5000
    with _FAILED_DOMAINS_LOCK:
        _FAILED_DOMAINS[domain] = time.time()
        if len(_FAILED_DOMAINS) > _MAX_FAILED_DOMAINS:
            now = time.time()
            expired = [d for d, ts in _FAILED_DOMAINS.items()
                       if (now - ts) >= _FAILED_DOMAINS_TTL_DEFAULT]
            for d in expired:
                del _FAILED_DOMAINS[d]

# ── Русские TLD, которым доверяем без дополнительных проверок ──────────
_TRUSTED_TLDS = {".ru", ".su"}

# ── Зарубежные TLD — блокируем результаты с этих доменов ───────────────
_BLOCKED_TLDS = {".ee", ".lv", ".lt", ".ge", ".md", ".am", ".az", ".tm",
                 ".tr", ".cn", ".il", ".pl", ".fi", ".cz", ".it", ".es",
                 ".de", ".fr", ".uk", ".us", ".jp",
                 ".kz", ".by", ".kg", ".uz"}

# ── Зарубежные страны — блокируем результаты с упоминанием этих стран ──
_FOREIGN_COUNTRIES = re.compile(
    r"(?:Эстон[ияию]|Латв[ияию]|Литв[аеы]|Груз[ияию]|Казахстан|Беларус[ьюи]|"
    r"Украин[аеыу]|Молдов[аеы]|Армен[ияию]|Азербайджан|Узбекистан|Туркменистан|"
    r"Кыргызстан|Таджикистан|Турци[еяю]|Китай|Израил[ьюь]|США|Герман[ияиюю]|"
    r"Польш[аеы]|Финлянд[ияиюю]|Чех[ияиюю]|Итали[еяю]|Испан[ияиюю]|"
    r"Каркси-Нуйа|Tallinn|Riga|Vilnius|Baltic)",
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
from granite.utils import is_seo_title


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
        companies = []
        seen_urls = set()

        for query in self.queries:
            search_query = f"{query} {self.city}"
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

                companies.append(
                    RawCompany(
                        source=Source.WEB_SEARCH,
                        source_url=url,
                        name=title,
                        phones=[],
                        address_raw="",
                        website=url,
                        emails=[],
                        city=self.city,
                        region=self.city_config.get("region", ""),
                    )
                )

            adaptive_delay(min_sec=2.0, max_sec=5.0)

        logger.info(f"  WebSearch: найдено {len(companies)} компаний (поиск)")

        # Детальный сбор со всех уникальных сайтов
        seen_domains = set()
        enriched = 0
        for company in companies:
            if not company.website:
                continue
            domain = extract_domain(company.website)
            if not domain or domain in seen_domains:
                continue
            seen_domains.add(domain)

            logger.info(f"  Scrape: {company.website}")
            details = self._scrape_details(company.website)
            if details:
                company.phones = normalize_phones(
                    company.phones + details.get("phones", [])
                )
                company.emails = list(set(company.emails + details.get("emails", [])))
                if not company.address_raw and details.get("addresses"):
                    company.address_raw = details["addresses"][0]
                # Обновляем имя если текущее — SEO-заголовок, а из страницы извлечено реальное название
                if details.get("company_name") and is_seo_title(company.name):
                    company.name = details["company_name"]
                enriched += 1

            adaptive_delay(min_sec=1.0, max_sec=2.5)

        logger.info(f"  WebSearch: обогащено {enriched}/{len(seen_domains)} сайтов")

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

    def _extract_contacts(self, html: str) -> dict | None:
        """Извлечение контактов из HTML."""
        soup = BeautifulSoup(html, "html.parser")

        data_out: dict = {"phones": [], "emails": [], "addresses": [], "company_name": None}

        # 0. Извлечение названия компании (приоритет: JSON-LD > og:site_name > h1)
        _seo_words = ("купить", "цен", "недорог", "заказать", "от производителя",
                      "с установк", "на могил", "доставк", "скидк")

        # JSON-LD: Organization / LocalBusiness
        for script in soup.select("script[type='application/ld+json']"):
            try:
                data = json.loads(script.string)
                items = data if isinstance(data, list) else [data]
                for item in items:
                    if isinstance(item, dict) and item.get("@type") in ("Organization", "LocalBusiness", "Brand"):
                        name = item.get("name") or item.get("legalName")
                        if name and 3 < len(name.strip()) < 80:
                            data_out["company_name"] = name.strip()
                            break
                if data_out["company_name"]:
                    break
            except (json.JSONDecodeError, TypeError, AttributeError):
                pass

        # og:site_name
        if not data_out["company_name"]:
            og = soup.find("meta", attrs={"property": "og:site_name"})
            if og and og.get("content"):
                name = og["content"].strip()
                if 3 < len(name) < 80 and not any(w in name.lower() for w in _seo_words):
                    data_out["company_name"] = name

        # <h1> — короткий, без SEO-паттернов
        if not data_out["company_name"]:
            h1 = soup.find("h1")
            if h1:
                name = h1.get_text(strip=True)
                if (3 < len(name) < 60
                        and not any(w in name.lower() for w in _seo_words)):
                    data_out["company_name"] = name

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
