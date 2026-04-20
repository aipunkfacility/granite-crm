# tests/test_jsprav_base.py — Тесты JspravBaseScraper (P-1, P-5)
import pytest
from unittest.mock import MagicMock, patch
from granite.scrapers.jsprav_base import JspravBaseScraper
from granite.scrapers.jsprav import JspravScraper
from granite.scrapers.jsprav_playwright import JspravPlaywrightScraper
from granite.models import Source, RawCompany


class TestJspravBaseScraper:
    """P-1: Общий базовый класс — тесты наследования и общей логики."""

    @pytest.fixture
    def config(self):
        return {
            "cities": [{"name": "Астрахань", "population": 468000}],
            "sources": {
                "jsprav": {
                    "enabled": True,
                    "subdomain_map": {"астрахань": "astrahan"}
                }
            }
        }

    # ── _get_subdomain ──

    def test_get_subdomain_from_map(self, config):
        scraper = JspravScraper(config, "Астрахань")
        assert scraper._get_subdomain() == "astrahan"

    def test_get_subdomain_slugify_fallback(self, config):
        scraper = JspravScraper(config, "Новый Город")
        assert scraper._get_subdomain() == "novyy-gorod"

    def test_get_subdomain_cached(self, config):
        scraper = JspravScraper(config, "Астрахань", subdomain="custom")
        assert scraper._get_subdomain() == "custom"

    # ── _is_local (FIX 4.2 — единая реализация) ──

    def test_is_local_exact_match(self, config):
        scraper = JspravScraper(config, "Астрахань")
        assert scraper._is_local({"addressLocality": "Астрахань"}) is True

    def test_is_local_prefix_match(self, config):
        """Астрахани → Астрахань (stem-сравнение)."""
        scraper = JspravScraper(config, "Астрахань")
        assert scraper._is_local({"addressLocality": "Астрахани"}) is True

    def test_is_local_short_stem_rejected(self, config):
        """Короткая основа (<5 символов) → False. Регрессия на PW-баг >=3.

        PW-версия раньше использовала len(loc_lower) >= 3 без проверки len(stem),
        что приводило к ложным совпадениям: «Тар» совпадал с «Тара»/«Тараз».
        JspravBaseScraper использует FIX 4.2: len(loc_lower) >= 5 и len(stem) >= 5.
        """
        scraper = JspravScraper(config, "Астрахань")
        # "Тар" — 3 символа, основа "Т" — не должна совпадать
        assert scraper._is_local({"addressLocality": "Тар"}) is False

    def test_is_local_different_city(self, config):
        scraper = JspravScraper(config, "Астрахань")
        assert scraper._is_local({"addressLocality": "Москва"}) is False

    def test_is_local_no_locality(self, config):
        """Нет addressLocality → True (по умолчанию локальный)."""
        scraper = JspravScraper(config, "Астрахань")
        assert scraper._is_local({}) is True

    # ── _extract_page_num ──

    def test_extract_page_num(self):
        assert JspravBaseScraper._extract_page_num("https://site.ru/category/page-3/") == 3
        assert JspravBaseScraper._extract_page_num("https://site.ru/category/?page=5") == 5
        assert JspravBaseScraper._extract_page_num("https://site.ru/category/") == 1

    # ── Наследование ──

    def test_jsprav_inherits_base(self, config):
        """JspravScraper наследует JspravBaseScraper."""
        scraper = JspravScraper(config, "Астрахань")
        assert isinstance(scraper, JspravBaseScraper)

    def test_pw_inherits_base(self, config):
        """JspravPlaywrightScraper наследует JspravBaseScraper."""
        scraper = JspravPlaywrightScraper(config, "Астрахань")
        assert isinstance(scraper, JspravBaseScraper)

    def test_jsprav_source(self, config):
        """JspravScraper._source = Source.JSPRAV."""
        scraper = JspravScraper(config, "Астрахань")
        assert scraper._source == Source.JSPRAV

    def test_pw_source(self, config):
        """JspravPlaywrightScraper._source = Source.JSPRAV_PW."""
        scraper = JspravPlaywrightScraper(config, "Астрахань")
        assert scraper._source == Source.JSPRAV_PW

    def test_pw_is_local_uses_fix_42(self, config):
        """PW-скрепер теперь использует FIX 4.2 версию _is_local."""
        scraper = JspravPlaywrightScraper(config, "Астрахань")
        # Короткая основа — должна быть отклонена (PW-баг >= 3 исправлен)
        assert scraper._is_local({"addressLocality": "Тар"}) is False
        # Нормальная основа — должна совпадать
        assert scraper._is_local({"addressLocality": "Астрахани"}) is True

    # ── _parse_jsonld_item (новый общий метод) ──

    def test_parse_jsonld_item_basic(self, config):
        """_parse_jsonld_item парсит LocalBusiness в RawCompany."""
        scraper = JspravScraper(config, "Астрахань")
        c = {
            "@type": "LocalBusiness",
            "name": "Гранит-Мастер",
            "telephone": ["+7 (903) 123-45-67"],
            "address": {
                "@type": "PostalAddress",
                "streetAddress": "ул. Ленина, 10",
                "addressLocality": "Астрахань"
            },
            "url": "https://abakan.jsprav.ru/company/granit-master/",
            "sameAs": ["https://granit-master.ru"],
            "geo": {"latitude": "46.35", "longitude": "48.03"},
        }
        seen = set()
        company = scraper._parse_jsonld_item(c, seen)
        assert company is not None
        assert company.name == "Гранит-Мастер"
        assert company.source == Source.JSPRAV
        assert "79031234567" in company.phones
        assert company.source_url == "https://abakan.jsprav.ru/company/granit-master/"

    def test_parse_jsonld_item_skips_non_localbusiness(self, config):
        """_parse_jsonld_item пропускает не-LocalBusiness."""
        scraper = JspravScraper(config, "Астрахань")
        c = {"@type": "Product", "name": "Памятник"}
        assert scraper._parse_jsonld_item(c, set()) is None

    def test_parse_jsonld_item_skips_foreign_city(self, config):
        """_parse_jsonld_item фильтрует чужой город."""
        scraper = JspravScraper(config, "Астрахань")
        c = {
            "@type": "LocalBusiness",
            "name": "Moscow Granite",
            "address": {"addressLocality": "Москва"},
            "url": "https://moscow-granit.ru"
        }
        assert scraper._parse_jsonld_item(c, set()) is None

    def test_parse_jsonld_item_dedup_by_url(self, config):
        """_parse_jsonld_item дедуплицирует по URL."""
        scraper = JspravScraper(config, "Астрахань")
        c = {
            "@type": "LocalBusiness",
            "name": "Тест",
            "address": {"addressLocality": "Астрахань"},
            "url": "https://test.ru"
        }
        seen = set()
        result1 = scraper._parse_jsonld_item(c, seen)
        result2 = scraper._parse_jsonld_item(c, seen)
        assert result1 is not None
        assert result2 is None  # дубль отклонён

    def test_parse_jsonld_item_pw_no_emails(self, config):
        """PW-версия: extract_emails=False → emails=[]."""
        scraper = JspravPlaywrightScraper(config, "Астрахань")
        c = {
            "@type": "LocalBusiness",
            "name": "Тест",
            "address": {"addressLocality": "Астрахань"},
            "url": "https://test.ru",
            "email": "test@test.ru",
        }
        company = scraper._parse_jsonld_item(c, set(), extract_emails=False)
        assert company is not None
        assert company.emails == []  # PW не извлекает email из JSON-LD
        assert company.source == Source.JSPRAV_PW

    def test_parse_jsonld_item_jsprav_extracts_emails(self, config):
        """Jsprav-версия: extract_emails=True → email извлекается."""
        scraper = JspravScraper(config, "Астрахань")
        c = {
            "@type": "LocalBusiness",
            "name": "Тест",
            "address": {"addressLocality": "Астрахань"},
            "url": "https://test.ru",
            "email": "test@test.ru",
        }
        company = scraper._parse_jsonld_item(c, set(), extract_emails=True)
        assert company is not None
        assert "test@test.ru" in company.emails


class TestEnrichmentPhase:
    """P-5: Enrichment вызывается ОДИН РАЗ после сбора всех JSON-LD."""

    @pytest.fixture
    def config(self):
        return {
            "cities": [{"name": "Астрахань", "population": 468000}],
            "sources": {
                "jsprav": {
                    "enabled": True,
                    "subdomain_map": {"астрахань": "astrahan"}
                }
            }
        }

    def test_parse_jsonld_from_page_no_enrichment(self, config):
        """_parse_jsonld_from_page() НЕ вызывает enrichment (P-5)."""
        mock_page = MagicMock()
        mock_page.query_selector_all.return_value = []  # нет JSON-LD скриптов
        scraper = JspravPlaywrightScraper(config, "Астрахань", playwright_page=mock_page)

        # Мокаем enrichment чтобы отследить вызов
        scraper._enrich_from_detail_pages = MagicMock(return_value=[])

        scraper._parse_jsonld_from_page(seen_urls=set())

        # enrichment НЕ должен был вызваться из _parse_jsonld_from_page
        scraper._enrich_from_detail_pages.assert_not_called()

    def test_enrich_called_once_in_scrape_click_more(self, config):
        """enrich_from_detail_pages() вызывается ровно 1 раз в _scrape_click_more()."""
        mock_page = MagicMock()
        mock_page.goto = MagicMock()
        mock_page.wait_for_load_state = MagicMock()
        mock_page.query_selector.return_value = None  # нет кнопки "Показать ещё"

        scraper = JspravPlaywrightScraper(config, "Астрахань", playwright_page=mock_page)

        # Мокаем _parse_jsonld_from_page — возвращает 2 компании
        test_company = RawCompany(source=Source.JSPRAV_PW, name="Тест", source_url="https://test.ru")
        scraper._parse_jsonld_from_page = MagicMock(return_value=[test_company, test_company])
        scraper._enrich_from_detail_pages = MagicMock(return_value=[test_company, test_company])

        scraper._scrape_click_more()

        # enrichment вызывается ровно 1 раз (после сбора всех JSON-LD)
        scraper._enrich_from_detail_pages.assert_called_once()

    def test_enrich_not_called_when_no_companies(self, config):
        """Если компаний нет — enrichment не вызывается."""
        mock_page = MagicMock()
        mock_page.goto = MagicMock()
        mock_page.wait_for_load_state = MagicMock()
        mock_page.query_selector.return_value = None
        mock_page.query_selector_all.return_value = []

        scraper = JspravPlaywrightScraper(config, "Астрахань", playwright_page=mock_page)
        scraper._enrich_from_detail_pages = MagicMock(return_value=[])

        # Возвращаем пустой список из _parse_jsonld_from_page
        result = scraper._scrape_click_more()

        assert result == []
        # Нет компаний — enrichment не вызывается (guard: if companies)
        scraper._enrich_from_detail_pages.assert_not_called()
