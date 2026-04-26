# tests/test_seo_name_extraction.py — Тесты A-4: извлечение имени компании + SEO-детектор
import pytest
from unittest.mock import MagicMock
from bs4 import BeautifulSoup

from granite.utils import is_seo_title
from granite.scrapers.web_search import WebSearchScraper


# ── is_seo_title (utils.py) ──────────────────────────────────────────────


class TestIsSeoTitle:
    """A-4: SEO-title детектор — is_seo_title() из utils.py."""

    def test_seo_title_купить(self):
        """'купить памятники' → SEO."""
        assert is_seo_title("купить памятники в Москве недорого") is True

    def test_seo_title_цены(self):
        """'цены на памятники' → SEO."""
        assert is_seo_title("цены на гранитные памятники") is True

    def test_seo_title_изготовление(self):
        """'изготовление памятников' → SEO."""
        assert is_seo_title("изготовление памятников на заказ") is True

    def test_seo_title_памятники_в(self):
        """'Памятники в Абакане' → SEO."""
        assert is_seo_title("Памятники в Абакане из гранита") is True

    def test_seo_title_памятники_и_надгробия(self):
        """'Памятники и надгробия' → SEO."""
        assert is_seo_title("Памятники и надгробия от производителя") is True

    def test_seo_title_производство(self):
        """'производство памятников' → SEO."""
        assert is_seo_title("производство памятников из гранита") is True

    def test_real_company_name_not_seo(self):
        """'Гранит-Мастер' → не SEO."""
        assert is_seo_title("Гранит-Мастер") is False

    def test_short_real_name(self):
        """'ИП Смирнов' → не SEO."""
        assert is_seo_title("ИП Смирнов") is False

    def test_very_long_name_seo(self):
        """Строка > 80 символов → SEO (слишком длинное для названия компании)."""
        long_name = "А" * 81
        assert is_seo_title(long_name) is True

    def test_empty_is_seo(self):
        """Пустая строка → SEO (недопустимое имя)."""
        assert is_seo_title("") is True

    def test_none_is_seo(self):
        """None → SEO (недопустимое имя)."""
        assert is_seo_title(None) is True

    def test_гранитные_мастерские(self):
        """'Гранитные мастерские' → НЕ SEO (v13: реальное название в нише, как «Гранит-Мастер»)."""
        assert is_seo_title("Гранитные мастерские России") is False

    def test_normal_name_with_granit(self):
        """'Гранит-Мастер ООО' → не SEO (реальное название)."""
        assert is_seo_title("Гранит-Мастер ООО") is False


# ── _is_city_page_name ────────────────────────────────────────────────────


class TestIsCityPageName:
    """A-4: Проверка наличия города в названии — _is_city_page_name()."""

    @pytest.fixture
    def scraper_abaza(self):
        config = {
            "cities": [{"name": "Абаза", "region": "Республика Хакасия"}],
            "sources": {"web_search": {"enabled": True}},
        }
        return WebSearchScraper(config, "Абаза")

    @pytest.fixture
    def scraper_moscow(self):
        config = {
            "cities": [{"name": "Москва", "region": "Москва"}],
            "sources": {"web_search": {"enabled": True}},
        }
        return WebSearchScraper(config, "Москва")

    def test_city_in_name(self, scraper_abaza):
        """'Памятники в Абазе' → True (город в названии)."""
        assert scraper_abaza._is_city_page_name("Памятники в Абазе") is True

    def test_city_stem_in_name(self, scraper_abaza):
        """'Памятники Абаз' → True (корень города)."""
        assert scraper_abaza._is_city_page_name("Памятники Абаз") is True

    def test_no_city_in_name(self, scraper_abaza):
        """'Гранит-Мастер' → False (нет города)."""
        assert scraper_abaza._is_city_page_name("Гранит-Мастер") is False

    def test_moscow_in_name(self, scraper_moscow):
        """'Памятники в Москве' → True."""
        assert scraper_moscow._is_city_page_name("Памятники в Москве") is True

    def test_moscow_stem(self, scraper_moscow):
        """'Москв' → True (корень 'москв' в 'москве')."""
        assert scraper_moscow._is_city_page_name("москве") is True

    def test_empty_name(self, scraper_abaza):
        """Пустое имя → False."""
        assert scraper_abaza._is_city_page_name("") is False

    def test_none_name(self, scraper_abaza):
        """None → False."""
        assert scraper_abaza._is_city_page_name(None) is False


# ── _extract_company_name ─────────────────────────────────────────────────


class TestExtractCompanyName:
    """A-4: Приоритетная цепочка извлечения имени — _extract_company_name()."""

    @pytest.fixture
    def scraper(self):
        config = {
            "cities": [{"name": "Абаза", "region": "Республика Хакасия"}],
            "sources": {"web_search": {"enabled": True}},
        }
        return WebSearchScraper(config, "Абаза")

    def test_json_ld_organization(self, scraper):
        """JSON-LD Organization → имя из структуры."""
        html = '''
        <html><head>
        <script type="application/ld+json">
        {"@type": "Organization", "name": "Гранит-Мастер"}
        </script>
        </head><body></body></html>
        '''
        soup = BeautifulSoup(html, "html.parser")
        assert scraper._extract_company_name(soup) == "Гранит-Мастер"

    def test_json_ld_local_business(self, scraper):
        """JSON-LD LocalBusiness → имя из структуры."""
        html = '''
        <html><head>
        <script type="application/ld+json">
        {"@type": "LocalBusiness", "name": "Мастерская Памяти"}
        </script>
        </head><body></body></html>
        '''
        soup = BeautifulSoup(html, "html.parser")
        assert scraper._extract_company_name(soup) == "Мастерская Памяти"

    def test_json_ld_seo_name_skipped(self, scraper):
        """JSON-LD с SEO-именем → пропускается, fallback на og:site_name."""
        html = '''
        <html><head>
        <script type="application/ld+json">
        {"@type": "Organization", "name": "купить памятники в Абакане недорого"}
        </script>
        <meta property="og:site_name" content="Гранит-Мастер">
        </head><body></body></html>
        '''
        soup = BeautifulSoup(html, "html.parser")
        assert scraper._extract_company_name(soup) == "Гранит-Мастер"

    def test_og_site_name(self, scraper):
        """og:site_name → имя из мета-тега."""
        html = '''
        <html><head>
        <meta property="og:site_name" content="Мемориал-Сервис">
        </head><body></body></html>
        '''
        soup = BeautifulSoup(html, "html.parser")
        assert scraper._extract_company_name(soup) == "Мемориал-Сервис"

    def test_title_with_separator(self, scraper):
        """Title с разделителем → часть до разделителя."""
        html = '''
        <html><head>
        <title>Гранит-Мастер | Памятники в Абазе</title>
        </head><body></body></html>
        '''
        soup = BeautifulSoup(html, "html.parser")
        assert scraper._extract_company_name(soup) == "Гранит-Мастер"

    def test_title_with_dash_separator(self, scraper):
        """Title с тире → часть до тире."""
        html = '''
        <html><head>
        <title>Мемориал-Сервис — изготовление памятников</title>
        </head><body></body></html>
        '''
        soup = BeautifulSoup(html, "html.parser")
        assert scraper._extract_company_name(soup) == "Мемориал-Сервис"

    def test_title_seo_skipped(self, scraper):
        """SEO-title → пропускается, fallback на h1."""
        html = '''
        <html><head>
        <title>купить памятники в Абакане недорого с установкой</title>
        </head><body>
        <h1>Гранит-Мастер</h1>
        </body></html>
        '''
        soup = BeautifulSoup(html, "html.parser")
        assert scraper._extract_company_name(soup) == "Гранит-Мастер"

    def test_h1_fallback(self, scraper):
        """h1 → fallback если всё остальное не подходит."""
        html = '''
        <html><head></head><body>
        <h1>ИП Смирнов</h1>
        </body></html>
        '''
        soup = BeautifulSoup(html, "html.parser")
        assert scraper._extract_company_name(soup) == "ИП Смирнов"

    def test_city_page_name_skipped(self, scraper):
        """Имя с городом → пропускается, берётся следующее."""
        html = '''
        <html><head>
        <meta property="og:site_name" content="Памятники в Абазе">
        <title>Гранит-Мастер | каталог</title>
        </head><body></body></html>
        '''
        soup = BeautifulSoup(html, "html.parser")
        # og:site_name = "Памятники в Абазе" → город в имени → skip
        # title = "Гранит-Мастер" → OK
        assert scraper._extract_company_name(soup) == "Гранит-Мастер"

    def test_all_seo_returns_none(self, scraper):
        """Все источники — SEO → None."""
        html = '''
        <html><head>
        <title>купить памятники недорого изготовление надгробий</title>
        </head><body>
        <h1>памятники и надгробия от производителя</h1>
        </body></html>
        '''
        soup = BeautifulSoup(html, "html.parser")
        assert scraper._extract_company_name(soup) is None

    def test_empty_html_returns_none(self, scraper):
        """Пустой HTML → None."""
        html = "<html><head></head><body></body></html>"
        soup = BeautifulSoup(html, "html.parser")
        assert scraper._extract_company_name(soup) is None

    def test_priority_json_ld_over_og(self, scraper):
        """JSON-LD имеет приоритет над og:site_name."""
        html = '''
        <html><head>
        <script type="application/ld+json">
        {"@type": "Organization", "name": "Первая Компания"}
        </script>
        <meta property="og:site_name" content="Вторая Компания">
        </head><body></body></html>
        '''
        soup = BeautifulSoup(html, "html.parser")
        assert scraper._extract_company_name(soup) == "Первая Компания"

    def test_json_ld_invalid_json_skipped(self, scraper):
        """Невалидный JSON-LD → пропускается, fallback на og:site_name."""
        html = '''
        <html><head>
        <script type="application/ld+json">{invalid json!!!</script>
        <meta property="og:site_name" content="Валидная Компания">
        </head><body></body></html>
        '''
        soup = BeautifulSoup(html, "html.parser")
        assert scraper._extract_company_name(soup) == "Валидная Компания"
