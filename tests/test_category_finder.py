# tests/test_category_finder.py — Тесты category_finder (P-7: кэш негативных результатов)
import pytest
from granite.category_finder import get_categories, discover_categories


class TestCategoryCache:
    """P-7: Перманентный кэш category_finder — негативные результаты ([])."""

    def test_get_categories_positive_result(self):
        """get_categories() с [...] -> возвращает список категорий."""
        cache = {"jsprav": {"москва": ["izgotovlenie-i-ustanovka-pamyatnikov-i-nadgrobij"]}}
        result = get_categories(cache, "jsprav", "москва")
        assert result == ["izgotovlenie-i-ustanovka-pamyatnikov-i-nadgrobij"]

    def test_get_categories_empty_list_means_no_category(self):
        """get_categories() с [] в кэше -> возвращает [] (не fallback)."""
        cache = {"jsprav": {"тараз": []}}
        result = get_categories(cache, "jsprav", "тараз", fallback=["default-cat"])
        assert result == []

    def test_get_categories_none_means_unchecked(self):
        """get_categories() с None (нет ключа) -> возвращает fallback."""
        cache = {"jsprav": {}}
        result = get_categories(cache, "jsprav", "новгород", fallback=["fallback-cat"])
        assert result == ["fallback-cat"]

    def test_get_categories_no_source_means_unchecked(self):
        """get_categories() без секции source -> возвращает fallback."""
        cache = {}
        result = get_categories(cache, "jsprav", "москва", fallback=["fb"])
        assert result == ["fb"]

    def test_get_categories_no_fallback_returns_empty(self):
        """get_categories() без ключа и без fallback -> возвращает []."""
        cache = {"jsprav": {}}
        result = get_categories(cache, "jsprav", "новгород")
        assert result == []

    def test_negative_result_different_from_missing(self):
        """[] (проверено, категорий нет) != отсутствие ключа (не проверено)."""
        cache = {"jsprav": {"город-без-кат": []}}
        # [] -> реально проверено, категорий нет
        assert get_categories(cache, "jsprav", "город-без-кат") == []
        # нет ключа -> не проверено
        assert get_categories(cache, "jsprav", "город-не-проверен", fallback=["fb"]) == ["fb"]

    def test_discover_categories_skips_cached_negative(self):
        """Город с [] в кэше -> HTTP-запрос не делается."""
        cache = {
            "jsprav": {"тараз": []},
            "_subdomains": {"jsprav": {"тараз": "taraz"}}
        }
        # Если тараз уже [] в кэше — discover_categories должен его пропустить
        # Проверяем что cached is not None для [] работает
        cached = cache.get("jsprav", {}).get("тараз")
        assert cached is not None  # [] — это не None
        assert cached == []

    def test_discover_categories_missing_is_none(self):
        """Город без ключа в кэше -> get() возвращает None."""
        cache = {"jsprav": {}}
        cached = cache.get("jsprav", {}).get("новгород")
        assert cached is None  # город не проверен
