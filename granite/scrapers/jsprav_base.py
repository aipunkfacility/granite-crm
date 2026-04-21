# scrapers/jsprav_base.py — Общий базовый класс для JspravScraper и JspravPlaywrightScraper
import re
import json
from granite.scrapers.base import BaseScraper
from granite.models import RawCompany, Source
from granite.utils import normalize_phones, slugify, classify_messenger


JSPRAV_CATEGORY = "izgotovlenie-i-ustanovka-pamyatnikov-i-nadgrobij"

# ── A-2: Разрешённые категории jsprav — только изготовление памятников ──
# Ритуальные агентства (ritualnye-uslugi) отсекаются — они не ЦА.
# 38% jsprav-записей были ритуальными агентствами без изготовления памятников.
JSPRAV_ALLOWED_CATEGORIES = frozenset({
    JSPRAV_CATEGORY,
})


class JspravBaseScraper(BaseScraper):
    """Общий базовый класс для JspravScraper и JspravPlaywrightScraper.

    Содержит: _get_subdomain, _is_local (FIX 4.2 версия), _parse_total_from_summary,
    _extract_page_num, _parse_companies_from_soup, _parse_jsonld_item,
    _classify_messenger (алиас на utils.classify_messenger).
    """

    JSPRAV_CATEGORY = JSPRAV_CATEGORY

    # Переопределяется в наследниках: Source.JSPRAV или Source.JSPRAV_PW
    _source: str = Source.JSPRAV

    def __init__(
        self,
        config: dict,
        city: str,
        categories: list[str] | None = None,
        subdomain: str | None = None,
    ):
        super().__init__(config, city)
        self.source_config = config.get("sources", {}).get("jsprav", {})
        self.subdomain_map = self.source_config.get("subdomain_map", {})
        self._cached_subdomain = subdomain
        if categories is not None:
            # A-2: Фильтруем категории, оставляя только разрешённые
            filtered = [c for c in categories if c in JSPRAV_ALLOWED_CATEGORIES]
            if filtered:
                self.categories = filtered
            else:
                from loguru import logger as _logger
                _logger.warning(
                    f"JSprav {city}: все переданные категории не в JSPRAV_ALLOWED_CATEGORIES, "
                    f"используем дефолт: {self.JSPRAV_CATEGORY}"
                )
                self.categories = [self.JSPRAV_CATEGORY]
        else:
            self.categories = [self.JSPRAV_CATEGORY]

        self._city_lower = city.lower().strip()
        self._declared_total = None  # для Playwright fallback: сколько всего компаний
        self._needs_playwright = False  # устанавливается в scrape() если нужно добрать через PW

    def _get_subdomain(self) -> str:
        if self._cached_subdomain:
            return self._cached_subdomain
        city_lower = self._city_lower
        if city_lower in self.subdomain_map:
            return self.subdomain_map[city_lower]
        base = slugify(self.city)
        if base.endswith("iy"):
            base = base[:-2] + "ij"
        return base

    def _is_local(self, address: dict) -> bool:
        """Проверяет, относится ли компания к искомому городу.

        FIX 4.2: минимальная длина loc_lower >= 5 и stem >= 5 для stem-сравнения.
        Короткие основы типа «Тар» (3 символа) ложно совпадают с «Тара» и «Тараз».
        """
        locality = address.get("addressLocality", "")
        if not locality:
            return True
        loc_lower = locality.lower().strip()
        if loc_lower == self._city_lower:
            return True
        if self._city_lower.startswith(loc_lower) or loc_lower.startswith(
            self._city_lower
        ):
            shorter = min(len(self._city_lower), len(loc_lower))
            longer = max(len(self._city_lower), len(loc_lower))
            if shorter * 100 / longer >= 70:
                return True
        if len(loc_lower) >= 5:  # FIX 4.2: минимальная длина для stem-сравнения
            stem = loc_lower.rstrip("аеоуияью")
            if stem and len(stem) >= 5 and stem == self._city_lower.rstrip("аеоуияью"):
                return True
        return False

    def _parse_total_from_summary(self, soup) -> int | None:
        """Ищет в саммари количество компаний для города."""
        benefits = soup.find("div", class_="cat-benefits")
        if not benefits:
            return None
        for li in benefits.find_all("li"):
            text = li.get_text(strip=True)
            m = re.search(r"(\d+)\s+компани", text)
            if m:
                return int(m.group(1))
        return None

    @staticmethod
    def _extract_page_num(url: str) -> int:
        """Извлекает номер страницы из URL."""
        m = re.search(r"page-?(\d+)", url) or re.search(r"page=(\d+)", url)
        return int(m.group(1)) if m else 1

    def _parse_companies_from_soup(self, soup, seen_urls: set) -> list[RawCompany]:
        """Парсит JSON-LD из soup, фильтрует дубли (по URL) и чужой город."""
        companies = []
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                raw = script.string
                if not raw:
                    continue
                data = json.loads(raw)
                if data.get("@type") != "ItemList":
                    continue
                for item in data.get("itemListElement", []):
                    c = item.get("item", {})
                    company = self._parse_jsonld_item(c, seen_urls)
                    if company is not None:
                        companies.append(company)
            except (json.JSONDecodeError, KeyError, AttributeError):
                continue
        return companies

    def _parse_jsonld_item(
        self, c: dict, seen_urls: set, *, extract_emails: bool = True
    ) -> RawCompany | None:
        """Парсит один JSON-LD LocalBusiness item в RawCompany.

        Args:
            c: JSON-LD item dict (значение "item" в itemListElement)
            seen_urls: множество уже обработанных URL для дедупликации
            extract_emails: извлекать ли email из JSON-LD (True для requests,
                False для PW — PW извлекает email позже из page content)

        Returns:
            RawCompany или None если компания не подходит
        """
        if c.get("@type") != "LocalBusiness":
            return None
        name = c.get("name", "")
        if not name:
            return None

        addr = c.get("address", {})

        # Дубль по URL организации
        org_url = c.get("url", "")
        if org_url and org_url in seen_urls:
            return None

        # Фильтр по городу
        if not self._is_local(addr):
            return None

        if org_url:
            seen_urls.add(org_url)

        same = c.get("sameAs", [])
        tel = c.get("telephone", [])
        if isinstance(tel, str):
            tel = [tel]
        phones = normalize_phones(tel)
        if isinstance(same, str):
            website = same if same else None
        else:
            website = same[0] if same else None

        geo = None
        if c.get("geo"):
            try:
                lat_raw = c["geo"].get("latitude")
                lon_raw = c["geo"].get("longitude")
                if lat_raw is not None and lon_raw is not None:
                    geo = [float(lat_raw), float(lon_raw)]
            except (ValueError, TypeError):
                pass

        # Email из JSON-LD (опционально — PW извлекает позже из page content)
        if extract_emails:
            item_emails = c.get("email", [])
            if isinstance(item_emails, str):
                item_emails = [item_emails]
            elif not isinstance(item_emails, list):
                item_emails = []
        else:
            item_emails = []

        return RawCompany(
            source=self._source,
            source_url=org_url,  # URL detail-страницы компании
            name=name,
            phones=phones,
            address_raw=f"{addr.get('streetAddress', '')}, "
            f"{addr.get('addressLocality', '')}".strip(", "),
            website=website,
            emails=item_emails,
            city=self.city,
            geo=geo,
        )

    # LOW-7: _classify_messenger вынесен в granite.utils.classify_messenger.
    # Оставляем alias для обратной совместимости внутренних вызовов.
    _classify_messenger = staticmethod(classify_messenger)
