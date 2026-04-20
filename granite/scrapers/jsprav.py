# scrapers/jsprav.py — рефакторинг scripts/scrape_fast.py (JSON-LD, быстрая версия)
import re
import base64
import random
import requests
import json
import time
from urllib.parse import urlparse, urlunparse
from bs4 import BeautifulSoup
from granite.scrapers.jsprav_base import JspravBaseScraper, JSPRAV_CATEGORY
from granite.models import RawCompany, Source
from granite.utils import normalize_phone, normalize_phones, extract_domain, extract_emails, slugify, get_random_ua, adaptive_delay, _sanitize_url_for_log, classify_messenger
from loguru import logger


class JspravScraper(JspravBaseScraper):
    """Скрепер jsprav.ru через JSON-LD — быстрый, не требует Playwright."""

    _source = Source.JSPRAV

    def _get_next_page_url(self, soup, base_dir: str, page_num: int) -> str | None:
        """Ищет кнопку 'Показать ещё' и берёт URL из data-url.

        Если кнопка не найдена — возвращает fallback URL через ?page=N.
        """
        btn = soup.find("a", class_="company-list-next-link")
        if btn:
            data_url = btn.get("data-url")
            if data_url:
                return data_url

        # Fallback: пробуем ?page=N (jsprav иногда не генерирует /page-N/ после 5-й)
        # Guard against infinite pagination — stop after 50 pages
        if page_num >= 50:
            return None
        parsed = urlparse(base_dir)
        fallback = urlunparse(
            (parsed.scheme, parsed.netloc, parsed.path, "", f"page={page_num + 1}", "")
        )
        return fallback

    def scrape(self) -> list[RawCompany]:
        companies = []
        subdomain = self._get_subdomain()
        if not re.match(r'^[a-z0-9][a-z0-9-]*$', subdomain):
            logger.warning(f"Invalid subdomain '{subdomain}' for city '{self.city}'")
            return []
        ua = {
            "User-Agent": get_random_ua()
        }

        seen_urls = set()
        for category in self.categories:
            companies_before = len(companies)
            declared_total = None
            url = f"https://{subdomain}.jsprav.ru/{category}/"
            empty_streak = 0
            last_page_num = 1
            max_pages = 5  # статическая пагинация jsprav отдаёт max ~5 страниц

            while url:
                page_num = self._extract_page_num(url)
                last_page_num = page_num
                logger.info(f"  JSprav: {_sanitize_url_for_log(url)}")

                # Ретраи при таймауте/ошибках сети + 429/503 backoff (P-6)
                r = None
                rate_retry = 0
                for attempt in range(10):  # увеличено: 3 retries + backoff
                    try:
                        r = requests.get(url, timeout=60, headers=ua)
                        if r.status_code in (429, 503):
                            rate_retry += 1
                            backoff_base = self.source_config.get("backoff_base", 5)
                            backoff_max = self.source_config.get("backoff_max", 60)
                            wait = min(backoff_max, backoff_base * (2 ** rate_retry)) + random.uniform(0, 5)
                            logger.warning(
                                f"  JSprav: HTTP {r.status_code}, backoff {wait:.0f}с "
                                f"(попытка {rate_retry})"
                            )
                            time.sleep(wait)
                            r = None  # retry
                            continue
                        # Успешный запрос — сбрасываем счётчик
                        rate_retry = 0
                        break
                    except (requests.Timeout, requests.ConnectionError) as e:
                        logger.warning(
                            f"  JSprav: попытка {attempt + 1}/3 не удалась: {e}"
                        )
                        time.sleep(3)
                        break  # после timeout/connection error — не retry бесконечно

                try:
                    if r is None:
                        logger.error(
                            f"  JSprav: не удалось загрузить {url} за 3 попытки"
                        )
                        continue

                    if r.status_code == 404:
                        logger.warning(
                            f"  JSprav: 404 для /page-{page_num}/ — пробуем fallback ?page="
                        )
                        # Fallback: если /page-N/ = 404, пробуем ?page=N
                        base_parsed = urlparse(
                            f"https://{subdomain}.jsprav.ru/{category}/"
                        )
                        fallback_url = urlunparse(
                            (
                                base_parsed.scheme,
                                base_parsed.netloc,
                                base_parsed.path,
                                "",
                                f"page={page_num}",
                                "",
                            )
                        )
                        r_fb = requests.get(fallback_url, timeout=30, headers=ua)
                        if r_fb.status_code == 200 and "LocalBusiness" in r_fb.text:
                            r = r_fb
                            url = fallback_url
                            logger.info(f"  JSprav: fallback ?page={page_num} успешен")
                        else:
                            logger.info(f"  JSprav: fallback тоже пуст — стоп")
                            break

                    soup = BeautifulSoup(r.text, "html.parser")

                    # На первой странице берём total из саммари
                    if declared_total is None:
                        declared_total = self._parse_total_from_summary(soup)
                        if declared_total is not None:
                            self._declared_total = declared_total
                            logger.info(
                                f"  JSprav: саммари — {declared_total} компаний в {self.city}"
                            )

                    page_companies = self._parse_companies_from_soup(soup, seen_urls)
                    # source_url уже заполнен URL detail-страницы в _parse_companies_from_soup
                    companies.extend(page_companies)
                    logger.info(
                        f"  JSprav: +{len(page_companies)} компаний (всего {len(companies)})"
                    )

                    # Набрали declared total — стоп
                    if declared_total is not None and (len(companies) - companies_before) >= declared_total:
                        logger.info(
                            f"  Jsprav: набрано {len(companies) - companies_before} из {declared_total} для категории {category} — стоп"
                        )
                        break

                    # Нет новых компаний — считаем пустую страницу
                    if len(page_companies) == 0:
                        empty_streak += 1
                        if empty_streak >= 2:
                            logger.info(
                                f"  JSprav: {empty_streak} пустых страниц подряд — стоп"
                            )
                            break
                    else:
                        empty_streak = 0

                    # Стоп после max_pages статической пагинации
                    if page_num >= max_pages:
                        logger.info(
                            f"  JSprav: достигнут лимит статической пагинации ({max_pages} стр.)"
                        )
                        break

                    # Ищем ссылку на следующую страницу через кнопку "Показать ещё"
                    next_url = self._get_next_page_url(soup, url, page_num)
                    if not next_url:
                        break

                    # Не зацикливаемся на одном и том же URL
                    if next_url == url:
                        break

                    url = next_url
                    adaptive_delay(0.8, 1.5)

                except Exception as e:
                    logger.error(f"  JSprav error ({_sanitize_url_for_log(url)}): {e}")
                    continue  # не теряем набранные компании при ошибке страницы

            # Playwright fallback: запускается только если ИЗВЕСТНО что недобрали.
            # Порог: <90% от declared_total. Если declared_total неизвестен —
            # НЕ запускаем PW автоматически (jsprav JSON-LD обычно собирает всё).
            cat_count = len(companies) - companies_before
            threshold = self.source_config.get("playwright_threshold", 0.9)
            if declared_total is not None and cat_count < declared_total * threshold:
                self._needs_playwright = True
                logger.warning(
                    f"  JSprav: получено {cat_count} из {declared_total} "
                    f"({cat_count * 100 // declared_total}%) для {self.city}/{category}. "
                    f"Порог <{threshold * 100:.0f}%, нужен Playwright fallback."
                )
            # declared_total неизвестен — НЕ запускаем PW автоматически
            # (JSON-LD собрал что мог, PW fallback — только при явном недоборе)

        # ═══════════════════════════════════════════════════════════════
        #  Второй проход: enrichment detail-страниц — мессенджеры, сайт, email
        # ═══════════════════════════════════════════════════════════════
        companies = self._enrich_from_detail_pages(companies)

        logger.info(f"  JSprav: итого {len(companies)} компаний для {self.city}")
        return companies

    def _enrich_from_detail_pages(self, companies: list[RawCompany]) -> list[RawCompany]:
        """Второй проход: обходит detail-страницы компаний и извлекает
        мессенджеры (TG, VK, WA, Viber), сайт и email из base64 data-link.
        """
        # Карта detail URL → company для быстрого поиска
        url_to_company: dict[str, RawCompany] = {}
        for c in companies:
            if c.source_url and c.source_url.startswith("http"):
                url_to_company[c.source_url] = c

        if not url_to_company:
            logger.debug("  JSprav: нет detail URL для enrichment — пропуск")
            return companies

        total = len(url_to_company)
        enriched = 0
        logger.info(f"  JSprav: enrichment {total} detail-страниц...")

        for i, (detail_url, company) in enumerate(url_to_company.items()):
            if i > 0 and i % 50 == 0:
                logger.info(
                    f"  JSprav: enrichment {i}/{total} "
                    f"(messengers: {enriched})"
                )

            try:
                detail = self._fetch_detail_page(detail_url)
                if detail["messengers"]:
                    company.messengers = detail["messengers"]
                    enriched += 1
                if detail["website"] and not company.website:
                    company.website = detail["website"]
                if detail["emails"] and not company.emails:
                    company.emails = detail["emails"]
                if detail["phones"] and not company.phones:
                    company.phones = detail["phones"]
            except Exception as e:
                logger.debug(f"  JSprav: enrichment error for {detail_url}: {e}")

            # Задержка между запросами к detail-страницам
            if i < total - 1:
                adaptive_delay(0.3, 0.7)

        logger.info(
            f"  JSprav: enrichment завершён — {enriched}/{total} "
            f"с мессенджерами"
        )
        return companies

    def _fetch_detail_page(self, detail_url: str) -> dict:
        """Загружает detail-страницу компании и извлекает:
        - messengers из base64 data-link (TG, VK, WA, Viber)
        - website из base64 data-link (org-link)
        - phones из data-props JSON
        - emails из HTML regex
        """
        result = {
            "messengers": {},
            "website": None,
            "emails": [],
            "phones": [],
        }

        r = None
        for attempt in range(3):
            try:
                r = requests.get(
                    detail_url,
                    timeout=20,
                    headers={"User-Agent": get_random_ua()},
                )
                if r.status_code == 200:
                    break
                elif r.status_code in (403, 404):
                    return result
            except (requests.Timeout, requests.ConnectionError):
                time.sleep(2)

        if r is None or r.status_code != 200:
            return result

        soup = BeautifulSoup(r.text, "html.parser")

        # ── Мессенджеры и сайт из base64 data-link ──
        for a in soup.find_all("a", attrs={"data-link": True}):
            try:
                decoded = base64.b64decode(a["data-link"]).decode("utf-8")
                dtype = a.get("data-type", "")
                if dtype == "org-link":
                    result["website"] = decoded
                elif dtype == "org-social-link":
                    self._classify_messenger(decoded, result["messengers"])
            except Exception:
                pass

        # ── Полные телефоны из data-props JSON ──
        for el in soup.find_all(attrs={"data-props": True}):
            try:
                props = json.loads(el.get("data-props", "{}"))
                if "phones" in props:
                    result["phones"] = normalize_phones(props["phones"])
            except Exception:
                pass

        # ── Email из HTML (бонус — jsprav обычно не показывает email) ──
        result["emails"] = extract_emails(r.text)

        return result
