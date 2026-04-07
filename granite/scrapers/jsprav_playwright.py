# scrapers/jsprav_playwright.py — Playwright-версия JSprav (глубокий сбор)
# Рефакторинг функции scrape_jsprav() из scripts/scrape_city.py
from granite.scrapers.base import BaseScraper
from granite.models import RawCompany, Source
from granite.utils import normalize_phones, extract_emails, adaptive_delay
from loguru import logger


class JspravPlaywrightScraper(BaseScraper):
    """Playwright-версия JSprav: обходит страницы компаний, собирает детальную информацию.

    Медленнее JSON-LD версии (JspravScraper), но собирает больше данных.
    Используется когда JSON-LD не содержит нужной информации.
    """

    def __init__(self, config: dict, city: str, playwright_page=None):
        super().__init__(config, city)
        self.page = playwright_page
        self.source_config = config.get("sources", {}).get("jsprav", {})
        self.subdomain_map = self.source_config.get("subdomain_map", {})
        self.categories = self.source_config.get(
            "categories",
            [
                "izgotovlenie-pamyatnikov",
                "pamyatniki-i-nadgrobiya",
            ],
        )

    def _get_subdomain(self) -> str:
        city_lower = self.city.lower()
        if city_lower in self.subdomain_map:
            return self.subdomain_map[city_lower]

        from granite.utils import slugify

        return slugify(self.city)

    def scrape(self) -> list[RawCompany]:
        if not self.page:
            logger.warning("  JSprav PW: Playwright page не передан, пропуск")
            return []

        companies = []
        subdomain = self._get_subdomain()

        for category in self.categories:
            base_url = f"https://{subdomain}.jsprav.ru/{category}/"
            logger.info(f"  JSprav PW: {base_url}")

            try:
                self.page.goto(base_url, timeout=60000)
                adaptive_delay(2.0, 3.0)
                self.page.wait_for_load_state("domcontentloaded", timeout=30000)

                for _ in range(5):
                    self.page.evaluate("window.scrollBy(0, 1000)")
                    adaptive_delay(0.5, 1.0)

                # Собираем ссылки на компании
                company_links = self.page.query_selector_all(f"a[href*='/{category}/']")
                seen_urls: set = set()
                hrefs = []
                for link in company_links:
                    href = link.get_attribute("href")
                    if not href or href in seen_urls:
                        continue
                    # Пропускаем саму страницу категории
                    if href.rstrip("/").endswith(category):
                        continue
                    seen_urls.add(href)
                    hrefs.append(href)

                logger.info(f"  JSprav PW: найдено {len(hrefs)} ссылок")

                for href in hrefs:
                    try:
                        company_url = (
                            f"https://{subdomain}.jsprav.ru{href}"
                            if href.startswith("/")
                            else href
                        )
                        self.page.goto(company_url, timeout=20000)
                        self.page.wait_for_load_state("domcontentloaded", timeout=15000)

                        title = self.page.query_selector("h1")
                        name = title.inner_text().strip() if title else ""
                        if not name:
                            continue

                        phone_elems = self.page.query_selector_all("a[href^='tel:']")
                        phones_raw = [pe.inner_text() for pe in phone_elems]
                        phones = normalize_phones(phones_raw)

                        addr_elem = self.page.query_selector("address")
                        address = addr_elem.inner_text().strip() if addr_elem else ""

                        site_elem = self.page.query_selector(
                            f"a[href*='http']:not([href*='jsprav'])"
                        )
                        website = site_elem.get_attribute("href") if site_elem else None

                        page_content = self.page.content()
                        emails = extract_emails(page_content)

                        # Мессенджеры
                        messengers: dict = {}
                        for a_tag in self.page.query_selector_all(
                            "a[href*='t.me'], a[href*='vk.com']"
                        ):
                            a_href = a_tag.get_attribute("href") or ""
                            if "t.me" in a_href:
                                messengers["telegram"] = a_href
                            elif "vk.com" in a_href:
                                messengers["vk"] = a_href

                        companies.append(
                            RawCompany(
                                source=Source.JSPRAV_PW,
                                source_url=company_url,
                                name=name,
                                phones=phones,
                                address_raw=address,
                                website=website,
                                emails=emails,
                                city=self.city,
                                messengers=messengers,
                            )
                        )

                        # Возвращаемся к списку
                        self.page.goto(base_url, timeout=20000)
                        self.page.wait_for_load_state("domcontentloaded", timeout=15000)

                    except Exception as e:
                        logger.warning(f"  JSprav PW: ошибка для {href}: {e}")
                        continue

            except Exception as e:
                logger.error(f"  JSprav PW error ({category}): {e}")

        return companies
