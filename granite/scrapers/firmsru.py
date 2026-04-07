# scrapers/firmsru.py — рефакторинг части Firmsru из scripts/scrape_city.py
from granite.scrapers.base import BaseScraper
from granite.models import RawCompany, Source
from granite.utils import normalize_phones, extract_emails, adaptive_delay, slugify
from loguru import logger


class FirmsruScraper(BaseScraper):
    """Скрепер firmsru.ru через Playwright. Страница передаётся извне."""

    def __init__(self, config: dict, city: str, playwright_page=None, categories: list[str] = None):
        super().__init__(config, city)
        self.page = playwright_page
        self.source_config = config.get("sources", {}).get("firmsru", {})
        self.categories = categories  # от category_finder
        self.base_path = self.source_config.get("base_path", None)

    def _build_urls(self) -> list[str]:
        """Список URL для парсинга."""
        urls = []
        city_slug = slugify(self.city)
        if self.categories:
            for cat in self.categories:
                url = f"https://firmsru.ru{cat}/".rstrip("/")
                urls.append(url)
        elif self.base_path:
            path = self.base_path.replace("{city}", city_slug)
            urls.append(f"https://firmsru.ru{path}")
        return urls

    def scrape(self) -> list[RawCompany]:
        if not self.page:
            logger.warning("  Firmsru: Playwright page не передан, пропуск")
            return []

        urls = self._build_urls()
        if not urls:
            logger.warning("  Firmsru: нет категорий и фоллбэка, пропуск")
            return []

        companies = []
        for url in urls:
            logger.info(f"  Firmsru: {url}")
            try:
                self.page.goto(url, timeout=30000, wait_until="domcontentloaded")
                self.page.wait_for_load_state("domcontentloaded", timeout=20000)

                for _ in range(5):
                    self.page.evaluate("window.scrollBy(0, 1000)")
                    adaptive_delay(0.5, 1.0)

                cards = self.page.query_selector_all(
                    "div.company, div.firm-item, a[href*='/firm/']"
                )

                page_count = 0
                for card in cards:
                    try:
                        name_elem = card.query_selector("h3 a, h2 a, a.name, span.name")
                        if not name_elem:
                            continue
                        name = name_elem.inner_text().strip()
                        if not name or len(name) < 3:
                            continue

                        addr_elem = card.query_selector("address, div.address, span.address")
                        address = addr_elem.inner_text().strip() if addr_elem else ""

                        phone_elems = card.query_selector_all(
                            "span.phone, div.phone, a[href^='tel:']"
                        )
                        phones_raw = [pe.inner_text() for pe in phone_elems]
                        phones = normalize_phones(phones_raw)

                        site_elem = card.query_selector(
                            "a[href*='http']:not([href*='firmsru'])"
                        )
                        website = site_elem.get_attribute("href") if site_elem else None

                        page_content = card.inner_html()
                        emails = extract_emails(page_content)

                        messengers: dict = {}
                        for a_tag in card.query_selector_all("a[href*='t.me'], a[href*='vk.com']"):
                            href = a_tag.get_attribute("href") or ""
                            if "t.me" in href:
                                messengers["telegram"] = href
                            elif "vk.com" in href:
                                messengers["vk"] = href

                        companies.append(RawCompany(
                            source=Source.FIRMSRU,
                            source_url=url,
                            name=name,
                            phones=phones,
                            address_raw=address,
                            website=website,
                            emails=emails,
                            city=self.city,
                            messengers=messengers,
                        ))
                        page_count += 1
                    except (KeyError, AttributeError, ValueError) as e:
                        logger.warning(f"  Firmsru: ошибка обработки карточки: {e}")
                        continue

                logger.info(f"  Firmsru: {page_count} компаний на странице {url}")

            except Exception as e:
                logger.error(f"  Firmsru error ({url}): {e}")

        return companies
