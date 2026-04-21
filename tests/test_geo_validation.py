# tests/test_geo_validation.py — Тесты A-5: географическая валидация
import pytest
from granite.utils import is_non_local_phone
from granite.scrapers.web_search import WebSearchScraper


# ── is_non_local_phone (utils.py) ──────────────────────────────────────────


class TestIsNonLocalPhone:
    """A-5: Общая функция валидации DEF-кода — is_non_local_phone()."""

    # ── Московские DEF-кода ──

    def test_moscow_def_for_moscow_not_nonlocal(self):
        """495 для Москвы → False (не не-локальный)."""
        assert is_non_local_phone("74951234567", "Москва") is False

    def test_moscow_def_499_for_moscow_not_nonlocal(self):
        """499 для Москвы → False."""
        assert is_non_local_phone("74991234567", "Москва") is False

    def test_moscow_def_498_for_moscow_not_nonlocal(self):
        """498 для Москвы → False."""
        assert is_non_local_phone("74981234567", "Москва") is False

    def test_moscow_def_for_abaza_is_nonlocal(self):
        """495 для Абазы → True (не-локальный)."""
        assert is_non_local_phone("74951234567", "Абаза") is True

    def test_moscow_def_499_for_abaza_is_nonlocal(self):
        """499 для Абазы → True."""
        assert is_non_local_phone("74991234567", "Абаза") is True

    # ── Питерские DEF-кода ──

    def test_spb_def_for_spb_not_nonlocal(self):
        """812 для СПб → False."""
        assert is_non_local_phone("78121234567", "Санкт-Петербург") is False

    def test_spb_def_for_abaza_is_nonlocal(self):
        """812 для Абазы → True (не-локальный)."""
        assert is_non_local_phone("78121234567", "Абаза") is True

    # ── Федеральные номера ──

    def test_8800_not_nonlocal_for_any(self):
        """8-800 для любого города → False (не не-локальный)."""
        assert is_non_local_phone("78001234567", "Абаза") is False
        assert is_non_local_phone("78001234567", "Москва") is False

    # ── Мобильные DEF-кода ──

    def test_mobile_def_not_nonlocal(self):
        """903 для Абазы → False (мобильный = не подозрительный)."""
        assert is_non_local_phone("79031234567", "Абаза") is False

    def test_mobile_def_not_nonlocal_moscow(self):
        """916 для Москвы → False."""
        assert is_non_local_phone("79161234567", "Москва") is False

    # ── Граничные случаи ──

    def test_empty_phone_not_nonlocal(self):
        """Пустой телефон → False (не помечаем)."""
        assert is_non_local_phone("", "Абаза") is False

    def test_none_phone_not_nonlocal(self):
        """None → False."""
        assert is_non_local_phone(None, "Абаза") is False

    def test_short_phone_not_nonlocal(self):
        """Короткий номер → False."""
        assert is_non_local_phone("7903", "Абаза") is False

    def test_non_russian_phone_not_nonlocal(self):
        """Не-российский формат → False."""
        assert is_non_local_phone("39031234567", "Абаза") is False

    def test_empty_city_moscow_def_nonlocal(self):
        """Пустой город + московский DEF → True (нельзя подтвердить что Москва)."""
        assert is_non_local_phone("74951234567", "") is True

    def test_none_city_moscow_def_nonlocal(self):
        """None город + московский DEF → True."""
        assert is_non_local_phone("74951234567", None) is True


# ── _is_local_phone (WebSearchScraper — обратная обёртка) ──────────────────


class TestIsLocalPhone:
    """A-5: Валидация DEF-кода телефона — _is_local_phone()."""

    @pytest.fixture
    def scraper_abaza(self):
        """Абаза — небольшой город, не Москва и не СПб."""
        config = {
            "cities": [{"name": "Абаза", "region": "Республика Хакасия"}],
            "sources": {"web_search": {"enabled": True}},
        }
        return WebSearchScraper(config, "Абаза")

    @pytest.fixture
    def scraper_moscow(self):
        """Москва — московские DEF-коды ок."""
        config = {
            "cities": [{"name": "Москва", "region": "Москва"}],
            "sources": {"web_search": {"enabled": True}},
        }
        return WebSearchScraper(config, "Москва")

    @pytest.fixture
    def scraper_spb(self):
        """Санкт-Петербург — питерские DEF-коды ок."""
        config = {
            "cities": [{"name": "Санкт-Петербург", "region": "Санкт-Петербург"}],
            "sources": {"web_search": {"enabled": True}},
        }
        return WebSearchScraper(config, "Санкт-Петербург")

    # ── Федеральные номера ──

    def test_8800_always_ok_abaza(self, scraper_abaza):
        """8-800 для Абазы → True (федеральный номер)."""
        assert scraper_abaza._is_local_phone("78001234567") is True

    def test_8800_always_ok_moscow(self, scraper_moscow):
        """8-800 для Москвы → True."""
        assert scraper_moscow._is_local_phone("78001234567") is True

    # ── Московские DEF-кода ──

    def test_moscow_def_for_moscow(self, scraper_moscow):
        """495 для Москвы → True."""
        assert scraper_moscow._is_local_phone("74951234567") is True

    def test_moscow_def_499_for_moscow(self, scraper_moscow):
        """499 для Москвы → True."""
        assert scraper_moscow._is_local_phone("74991234567") is True

    def test_moscow_def_498_for_moscow(self, scraper_moscow):
        """498 для Москвы → True."""
        assert scraper_moscow._is_local_phone("74981234567") is True

    def test_moscow_def_for_abaza(self, scraper_abaza):
        """495 для Абазы → False (московский номер в провинции = агрегатор)."""
        assert scraper_abaza._is_local_phone("74951234567") is False

    def test_moscow_def_499_for_abaza(self, scraper_abaza):
        """499 для Абазы → False."""
        assert scraper_abaza._is_local_phone("74991234567") is False

    # ── Питерские DEF-кода ──

    def test_spb_def_for_spb(self, scraper_spb):
        """812 для СПб → True."""
        assert scraper_spb._is_local_phone("78121234567") is True

    def test_spb_def_for_abaza(self, scraper_abaza):
        """812 для Абазы → False (питерский код в провинции = не-локальный)."""
        # Теперь 812 тоже считается не-локальным для не-СПб (A-5 расширено)
        assert scraper_abaza._is_local_phone("78121234567") is False

    # ── Мобильные DEF-кода (903, 916 и т.д.) ──

    def test_mobile_def_for_abaza(self, scraper_abaza):
        """903 для Абазы → True (мобильный, локальный)."""
        assert scraper_abaza._is_local_phone("79031234567") is True

    def test_mobile_def_for_moscow(self, scraper_moscow):
        """916 для Москвы → True (мобильный)."""
        assert scraper_moscow._is_local_phone("79161234567") is True

    # ── Граничные случаи ──

    def test_empty_phone(self, scraper_abaza):
        """Пустой телефон → True (не помечаем)."""
        assert scraper_abaza._is_local_phone("") is True

    def test_none_phone(self, scraper_abaza):
        """None → True (не помечаем)."""
        assert scraper_abaza._is_local_phone(None) is True

    def test_short_phone(self, scraper_abaza):
        """Короткий номер → True (неизвестный формат)."""
        assert scraper_abaza._is_local_phone("7903") is True

    def test_non_russian_phone(self, scraper_abaza):
        """Не-российский формат (не начинается с 7, 11 цифр) → True."""
        assert scraper_abaza._is_local_phone("39031234567") is True


# ── _title_mentions_foreign_city ──────────────────────────────────────────


class TestTitleMentionsForeignCity:
    """A-5: Фильтр чужого города в title — _title_mentions_foreign_city()."""

    @pytest.fixture
    def scraper_abaza(self):
        """Абаза (Хакасия) — _foreign_city_roots мокается вручную."""
        config = {
            "cities": [{"name": "Абаза", "region": "Республика Хакасия"}],
            "sources": {"web_search": {"enabled": True}},
        }
        s = WebSearchScraper(config, "Абаза")
        # Мокаем foreign_city_roots напрямую, т.к. regions.yaml может отсутствовать
        s._foreign_city_roots = ["москв", "петербург", "новосибирск", "казан"]
        return s

    @pytest.fixture
    def scraper_moscow(self):
        """Москва — _foreign_city_roots мокается вручную."""
        config = {
            "cities": [{"name": "Москва", "region": "Москва"}],
            "sources": {"web_search": {"enabled": True}},
        }
        s = WebSearchScraper(config, "Москва")
        # Москва — чужие города: Абаза, Абакан, Новосибирск и т.д.
        s._foreign_city_roots = ["абаз", "абакан", "новосибирск", "казан"]
        return s

    def test_moscow_title_for_abaza(self, scraper_abaza):
        """'Гранитная мастерская в Москве' при скрейпинге Абазы → True."""
        assert scraper_abaza._title_mentions_foreign_city("Гранитная мастерская в Москве") is True

    def test_same_region_city(self, scraper_abaza):
        """'Гранитная мастерская в Абакане' при скрейпинге Абазы → False (тот же регион)."""
        assert scraper_abaza._title_mentions_foreign_city("Гранитная мастерская в Абакане") is False

    def test_no_city_in_title(self, scraper_abaza):
        """'Памятники из гранита' → False (нет города)."""
        assert scraper_abaza._title_mentions_foreign_city("Памятники из гранита") is False

    def test_empty_title(self, scraper_abaza):
        """Пустой title → False."""
        assert scraper_abaza._title_mentions_foreign_city("") is False

    def test_none_title(self, scraper_abaza):
        """None → False."""
        assert scraper_abaza._title_mentions_foreign_city(None) is False

    def test_case_insensitive(self, scraper_abaza):
        """'москв' в нижнем регистре → True."""
        assert scraper_abaza._title_mentions_foreign_city("гранитная мастерская в москве") is True

    def test_city_inside_word_not_matched(self, scraper_abaza):
        """'замоскворецкий' → False (город внутри другого слова)."""
        # 'москв' появляется внутри 'замоскворецкий' — 'з' перед 'москв' = буква → не граница слова
        result = scraper_abaza._title_mentions_foreign_city("Замоскворецкий район")
        # Это зависит от того, есть ли 'москв' в foreign_city_roots
        # Если Москва — чужой город для Абазы, 'москв' в roots
        # но 'з' перед 'москв' — буква → before_ok = False → не совпадение
        assert result is False

    def test_abaza_title_for_moscow(self, scraper_moscow):
        """'Памятники в Абазе' при скрейпинге Москвы → True (Абаза не в Московском регионе)."""
        assert scraper_moscow._title_mentions_foreign_city("Памятники в Абазе") is True

    def test_moscow_city_for_moscow(self, scraper_moscow):
        """'Гранитная мастерская в Москве' при скрейпинге Москвы → False (свой город)."""
        # Москва — в регионе Москвы, поэтому не в foreign_city_roots
        assert scraper_moscow._title_mentions_foreign_city("Гранитная мастерская в Москве") is False


# ── _is_relevant_url — интеграционный тест A-5 через foreign city ────────


class TestIsRelevantUrlForeignCity:
    """A-5: _is_relevant_url() отсекает чужой город в title."""

    @pytest.fixture
    def scraper_abaza(self):
        config = {
            "cities": [{"name": "Абаза", "region": "Республика Хакасия"}],
            "sources": {"web_search": {"enabled": True}},
        }
        s = WebSearchScraper(config, "Абаза")
        s._foreign_city_roots = ["москв", "петербург", "новосибирск", "казан"]
        return s

    def test_ru_domain_foreign_city_blocked(self, scraper_abaza):
        """.ru домен с чужим городом в title → заблокирован."""
        assert scraper_abaza._is_relevant_url("https://example.ru/page", "Гранитная мастерская в Москве") is False

    def test_ru_domain_same_region_ok(self, scraper_abaza):
        """.ru домен с городом того же региона → OK."""
        assert scraper_abaza._is_relevant_url("https://example.ru/page", "Гранитная мастерская в Абакане") is True

    def test_ru_domain_no_city_ok(self, scraper_abaza):
        """.ru домен без города в title → OK."""
        assert scraper_abaza._is_relevant_url("https://example.ru/page", "Памятники из гранита") is True
