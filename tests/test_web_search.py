# tests/test_web_search.py — Тесты WebSearchScraper (P-2, P-3)
import pytest
from unittest.mock import MagicMock, patch
from granite.scrapers.web_search import WebSearchScraper
from granite.models import Source


class TestSkipDomains:
    """P-2: Фильтрация каталог-URL jsprav/yell через SKIP_DOMAINS."""

    @pytest.fixture
    def scraper(self):
        config = {
            "cities": [{"name": "Астрахань"}],
            "sources": {"web_search": {"enabled": True}},
        }
        return WebSearchScraper(config, "Астрахань")

    def test_jsprav_domain_blocked(self, scraper):
        """jsprav.ru -> заблокирован."""
        assert scraper._is_skip_domain("https://jsprav.ru/some-category/") is True

    def test_jsprav_subdomain_blocked(self, scraper):
        """abakan.jsprav.ru -> заблокирован (endswith)."""
        assert scraper._is_skip_domain("https://abakan.jsprav.ru/category/") is True

    def test_yell_domain_blocked(self, scraper):
        """yell.ru -> заблокирован."""
        assert scraper._is_skip_domain("https://yell.ru/some-page/") is True

    def test_yell_subdomain_blocked(self, scraper):
        """ekb.yell.ru -> заблокирован (endswith)."""
        assert scraper._is_skip_domain("https://ekb.yell.ru/category/") is True

    def test_normal_domain_passes(self, scraper):
        """granit-master.ru -> проходит."""
        assert scraper._is_skip_domain("https://granit-master.ru/") is False

    def test_2gis_still_blocked(self, scraper):
        """2gis.ru остаётся заблокированным (регрессионный тест)."""
        assert scraper._is_skip_domain("https://2gis.ru/astrahan") is True

    def test_2gis_subdomain_blocked(self, scraper):
        """api.2gis.ru -> заблокирован."""
        assert scraper._is_skip_domain("https://api.2gis.ru/") is True


class TestWebSearchTwoPass:
    """P-3: Двухпроходная модель WebSearch с мягким фильтром."""

    @pytest.fixture
    def scraper(self):
        config = {
            "cities": [{"name": "Астрахань"}],
            "sources": {
                "web_search": {
                    "enabled": True,
                    "queries": ["гранитная мастерская памятники"],
                }
            },
        }
        return WebSearchScraper(config, "Астрахань")

    def test_empty_details_no_raw_company(self, scraper):
        """_scrape_details вернул None → RawCompany не создаётся."""
        with patch.object(scraper, '_search', return_value=[{"url": "https://test.ru", "title": "Test"}]):
            with patch.object(scraper, '_scrape_details', return_value=None):
                result = scraper.scrape()
                assert len(result) == 0

    def test_no_contacts_but_has_content_creates_raw_company(self, scraper):
        """details без phones/emails, но сайт загрузился → RawCompany создаётся (мягкий фильтр P-3)."""
        details = {"phones": [], "emails": [], "addresses": []}
        with patch.object(scraper, '_search', return_value=[{"url": "https://test.ru", "title": "Test"}]):
            with patch.object(scraper, '_scrape_details', return_value=details):
                result = scraper.scrape()
                assert len(result) == 1
                assert result[0].source == Source.WEB_SEARCH
                assert result[0].phones == []
                assert result[0].emails == []

    def test_with_phone_creates_raw_company(self, scraper):
        """details с phones → RawCompany создаётся с телефонами."""
        details = {"phones": ["+7 (903) 123-45-67"], "emails": [], "addresses": []}
        with patch.object(scraper, '_search', return_value=[{"url": "https://test.ru", "title": "Test"}]):
            with patch.object(scraper, '_scrape_details', return_value=details):
                result = scraper.scrape()
                assert len(result) == 1
                assert len(result[0].phones) > 0

    def test_with_email_creates_raw_company(self, scraper):
        """details с emails → RawCompany создаётся с email."""
        details = {"phones": [], "emails": ["test@test.ru"], "addresses": []}
        with patch.object(scraper, '_search', return_value=[{"url": "https://test.ru", "title": "Test"}]):
            with patch.object(scraper, '_scrape_details', return_value=details):
                result = scraper.scrape()
                assert len(result) == 1
                assert "test@test.ru" in result[0].emails

    def test_url_dedup_before_scraping(self, scraper):
        """Дубли URL из поиска → скрейпится один раз."""
        search_items = [
            {"url": "https://test.ru", "title": "Test 1"},
            {"url": "https://test.ru", "title": "Test 2"},
        ]
        details = {"phones": [], "emails": [], "addresses": []}
        with patch.object(scraper, '_search', return_value=search_items):
            with patch.object(scraper, '_scrape_details', return_value=details) as mock_scrape:
                result = scraper.scrape()
                # URL дедуплицирован — _scrape_details вызывается 1 раз
                assert mock_scrape.call_count == 1
                assert len(result) == 1

    def test_domain_dedup_before_scraping(self, scraper):
        """Дубли домена → скрейпится один раз."""
        search_items = [
            {"url": "https://test.ru/page1", "title": "Test 1"},
            {"url": "https://test.ru/page2", "title": "Test 2"},
        ]
        details = {"phones": [], "emails": [], "addresses": []}
        with patch.object(scraper, '_search', return_value=search_items):
            with patch.object(scraper, '_scrape_details', return_value=details) as mock_scrape:
                result = scraper.scrape()
                # Домен дедуплицирован — _scrape_details вызывается 1 раз
                assert mock_scrape.call_count == 1
                assert len(result) == 1
