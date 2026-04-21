# tests/test_jsprav_category_filter.py — Тесты A-2: фильтр jsprav категорий
import pytest
from granite.scrapers.jsprav_base import (
    JspravBaseScraper,
    JSPRAV_CATEGORY,
    JSPRAV_ALLOWED_CATEGORIES,
)
from granite.scrapers.jsprav import JspravScraper
from granite.scrapers.jsprav_playwright import JspravPlaywrightScraper


# ── Константа для тестирования ритуальной категории ──
_RITUAL_CATEGORY = "ritualnye-uslugi"


class TestJspravAllowedCategories:
    """A-2: Фильтрация категорий jsprav — только целевые."""

    @pytest.fixture
    def config(self):
        return {
            "cities": [{"name": "Астрахань", "population": 468000}],
            "sources": {
                "jsprav": {
                    "enabled": True,
                    "subdomain_map": {"астрахань": "astrahan"},
                }
            },
        }

    # ── JSPRAV_ALLOWED_CATEGORIES frozenset ──

    def test_allowed_categories_contains_target(self):
        """Целевая категория есть в JSPRAV_ALLOWED_CATEGORIES."""
        assert JSPRAV_CATEGORY in JSPRAV_ALLOWED_CATEGORIES

    def test_allowed_categories_is_frozenset(self):
        """JSPRAV_ALLOWED_CATEGORIES — frozenset (иммутабельный)."""
        assert isinstance(JSPRAV_ALLOWED_CATEGORIES, frozenset)

    # ── Фильтрация в __init__: только целевая категория проходит ──

    def test_allowed_category_passes(self, config):
        """Целевая категория проходит фильтр."""
        scraper = JspravScraper(config, "Астрахань", categories=[JSPRAV_CATEGORY])
        assert scraper.categories == [JSPRAV_CATEGORY]

    def test_ritual_category_filtered_out(self, config):
        """Ритуальная категория отсекается фильтром."""
        scraper = JspravScraper(config, "Астрахань", categories=[_RITUAL_CATEGORY])
        # Ритуальная категория не в ALLOWED → fallback на дефолт
        assert scraper.categories == [JSPRAV_CATEGORY]

    def test_mixed_categories_filters_ritual(self, config):
        """Смешанный список → только целевая категория остаётся."""
        scraper = JspravScraper(
            config, "Астрахань",
            categories=[_RITUAL_CATEGORY, JSPRAV_CATEGORY],
        )
        assert scraper.categories == [JSPRAV_CATEGORY]
        assert _RITUAL_CATEGORY not in scraper.categories

    def test_empty_categories_uses_default(self, config):
        """Пустой список категорий → fallback на дефолт."""
        scraper = JspravScraper(config, "Астрахань", categories=[])
        # Пустой список — filtered пустой → fallback
        assert scraper.categories == [JSPRAV_CATEGORY]

    def test_none_categories_uses_default(self, config):
        """categories=None → дефолтная категория."""
        scraper = JspravScraper(config, "Астрахань", categories=None)
        assert scraper.categories == [JSPRAV_CATEGORY]

    def test_no_categories_argument_uses_default(self, config):
        """Без аргумента categories → дефолтная категория."""
        scraper = JspravScraper(config, "Астрахань")
        assert scraper.categories == [JSPRAV_CATEGORY]

    # ── PW-скрейпер тоже использует фильтр ──

    def test_pw_ritual_category_filtered(self, config):
        """PW-скрейпер тоже фильтрует ритуальные категории."""
        mock_page = None  # PW создаётся лениво
        scraper = JspravPlaywrightScraper(
            config, "Астрахань",
            categories=[_RITUAL_CATEGORY],
            playwright_page=mock_page,
        )
        assert scraper.categories == [JSPRAV_CATEGORY]

    def test_pw_mixed_categories_filtered(self, config):
        """PW-скрейпер фильтрует смешанный список."""
        mock_page = None
        scraper = JspravPlaywrightScraper(
            config, "Астрахань",
            categories=[_RITUAL_CATEGORY, JSPRAV_CATEGORY],
            playwright_page=mock_page,
        )
        assert scraper.categories == [JSPRAV_CATEGORY]
        assert _RITUAL_CATEGORY not in scraper.categories


class TestCategoryFinderFilter:
    """A-2: Фильтрация категорий в category_finder.discover_categories()."""

    def test_category_finder_caches_only_allowed(self):
        """discover_categories() сохраняет в кэш только разрешённые категории."""
        from granite.category_finder import discover_categories

        # Мокаем _load_cache и _save_cache
        cache = {"jsprav": {}}

        # Мокаем find_jsprav — возвращает и ритуальную и целевую
        with pytest.MonkeyPatch.context() as m:
            m.setattr(
                "granite.category_finder._load_cache",
                lambda: cache,
            )
            m.setattr(
                "granite.category_finder._save_cache",
                lambda c: None,
            )
            m.setattr(
                "granite.category_finder.find_jsprav",
                lambda city, config, region=None: {
                    "subdomain": "test",
                    "categories": [JSPRAV_CATEGORY, _RITUAL_CATEGORY],
                },
            )

            result = discover_categories(["ТестГород"], {})

            # В кэше должна быть только целевая категория
            cached = result.get("jsprav", {}).get("ТестГород", [])
            assert JSPRAV_CATEGORY in cached
            assert _RITUAL_CATEGORY not in cached

    def test_category_finder_caches_empty_when_only_ritual(self):
        """Если find_jsprav вернула только ритуальную категорию →
        в кэше пустой список (город без нужной категории)."""
        from granite.category_finder import discover_categories

        cache = {"jsprav": {}}

        with pytest.MonkeyPatch.context() as m:
            m.setattr(
                "granite.category_finder._load_cache",
                lambda: cache,
            )
            m.setattr(
                "granite.category_finder._save_cache",
                lambda c: None,
            )
            m.setattr(
                "granite.category_finder.find_jsprav",
                lambda city, config, region=None: {
                    "subdomain": "test",
                    "categories": [_RITUAL_CATEGORY],
                },
            )

            result = discover_categories(["ТестГород"], {})

            # Только ритуальная → отфильтрована → пустой список
            cached = result.get("jsprav", {}).get("ТестГород", [])
            assert cached == []
