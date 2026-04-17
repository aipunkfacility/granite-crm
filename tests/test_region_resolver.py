# tests/test_region_resolver.py
"""Тесты для region_resolver: build_city_lookup, detect_city, lookup_region, seed_cities_table."""
import pytest

from unittest.mock import patch, MagicMock


# ── Mock regions.yaml ─────────────────────────────────────────────────────
MOCK_REGIONS = {
    "Республика Хакасия": ["Абаза", "Абакан", "Саяногорск"],
    "Краснодарский край": ["Краснодар", "Сочи"],
    "Московская область": ["Химки"],
    # Двойники — город в двух регионах
    "Кемеровская область": ["Кировск"],
    "Мурманская область": ["Кировск"],
}


@pytest.fixture(autouse=True)
def _mock_regions_cache():
    """Автоматически подменяет кэш regions.yaml для всех тестов."""
    import granite.pipeline.region_resolver as rr
    rr._REGIONS_CACHE = MOCK_REGIONS
    rr._CITY_LOOKUP_CACHE = None  # сбрасываем кэш lookup
    rr._CITY_TO_REGION_CACHE = None  # сбрасываем кэш обратного индекса
    yield
    rr._REGIONS_CACHE = None
    rr._CITY_LOOKUP_CACHE = None
    rr._CITY_TO_REGION_CACHE = None


# ── _match_score ──────────────────────────────────────────────────────────

class TestMatchScore:
    """Тесты для _match_score()."""

    def test_preposition_score(self):
        from granite.pipeline.region_resolver import _match_score
        # "в абакан" → pos of 'а' in 'абакан' = 2 (after "в ")
        assert _match_score("в абакан", 2) == 3  # после "в "

    def test_from_preposition(self):
        from granite.pipeline.region_resolver import _match_score
        assert _match_score("из москвы", 3) == 3

    def test_comma_score(self):
        from granite.pipeline.region_resolver import _match_score
        # "памятники, абакан" → ", " then space, "абакан" at pos 11
        # prefix="памятники, " → stripped="памятники," → last=','
        assert _match_score("памятники, абакан", 11) == 2

    def test_dash_score(self):
        from granite.pipeline.region_resolver import _match_score
        # "памятники — абакан" → " —" then space, "абакан" at pos 12
        # prefix="памятники — " → stripped="памятники —" → last='—'
        assert _match_score("памятники — абакан", 12) == 2

    def test_start_of_string(self):
        from granite.pipeline.region_resolver import _match_score
        assert _match_score("абакан гранит", 0) == 1

    def test_inside_word(self):
        from granite.pipeline.region_resolver import _match_score
        # "сабакан" — "абакан" внутри другого слова
        assert _match_score("сабакан", 1) == 0

    def test_after_space(self):
        from granite.pipeline.region_resolver import _match_score
        assert _match_score("фирма абакан", 6) == 1


# ── build_city_lookup ────────────────────────────────────────────────────

class TestBuildCityLookup:
    """Тесты для build_city_lookup()."""

    def test_basic(self):
        from granite.pipeline.region_resolver import build_city_lookup
        lookup, roots = build_city_lookup()
        # "абакан" → canonical "Абакан"
        assert lookup["абакан"] == "Абакан"
        assert "абакан" in roots

    def test_doppelganger_is_none(self):
        from granite.pipeline.region_resolver import build_city_lookup
        lookup, roots = build_city_lookup()
        # Кировск — в 2 регионах, должен быть None (неоднозначно)
        assert lookup["кировск"] is None

    def test_declension_variant(self):
        from granite.pipeline.region_resolver import build_city_lookup
        lookup, roots = build_city_lookup()
        # "абакан" (len=6), prefix_len=max(5,5)=5, prefix="абака"
        assert lookup["абака"] == "Абакан"

    def test_stop_words_excluded(self):
        from granite.pipeline.region_resolver import build_city_lookup, _STOP_WORDS
        lookup, roots = build_city_lookup()
        for sw in _STOP_WORDS:
            assert sw not in roots, f"Stop-word '{sw}' should not be in roots"

    def test_sorted_by_length_desc(self):
        from granite.pipeline.region_resolver import build_city_lookup
        _, roots = build_city_lookup()
        assert roots == sorted(roots, key=len, reverse=True)

    def test_cached(self):
        from granite.pipeline.region_resolver import build_city_lookup
        r1 = build_city_lookup()
        r2 = build_city_lookup()
        assert r1 is r2  # один и тот же объект


# ── detect_city ──────────────────────────────────────────────────────────

class TestDetectCity:
    """Тесты для detect_city()."""

    def test_basic_preposition(self):
        from granite.pipeline.region_resolver import detect_city
        assert detect_city("Гранитная мастерская в Абакане") == "Абакан"

    def test_comma(self):
        from granite.pipeline.region_resolver import detect_city
        assert detect_city("ул. Промышленная, 7Е, Абакан") == "Абакан"

    def test_address(self):
        from granite.pipeline.region_resolver import detect_city
        assert detect_city("г. Абакан, ул. Ленина 10") == "Абакан"

    def test_exclude_self(self):
        from granite.pipeline.region_resolver import detect_city
        assert detect_city("Памятники Абаза", exclude_city="Абаза") is None

    def test_doppelganger_returns_none(self):
        from granite.pipeline.region_resolver import detect_city
        # Кировск — двойник, detect_city не должен его возвращать
        assert detect_city("Памятники Кировск") is None

    def test_score_priority(self):
        from granite.pipeline.region_resolver import detect_city
        # "в Абакане" (score=3) > plain "Химки" (score=1)
        result = detect_city("Мастерская в Абакане и Химки")
        assert result == "Абакан"

    def test_longest_match(self):
        from granite.pipeline.region_resolver import detect_city
        # "Саяногорск" (len=11) > "Саян" не существует, но проверяем что
        # длинное совпадение найдено
        assert detect_city("Памятники Саяногорск") == "Саяногорск"

    def test_no_match(self):
        from granite.pipeline.region_resolver import detect_city
        assert detect_city("Ритуальные услуги") is None

    def test_empty_text(self):
        from granite.pipeline.region_resolver import detect_city
        assert detect_city("") is None
        assert detect_city(None) is None

    def test_word_boundary(self):
        from granite.pipeline.region_resolver import detect_city
        # "Абакана" — "абакан" внутри другого слова (АбаканА), не должно совпасть
        # Но "абакан" как корень может совпасть... это граничный случай.
        # Главное что внутри другого слова не ловит.
        from granite.pipeline.region_resolver import _match_score
        # Проверяем что _match_score даёт 0 для середины слова
        assert _match_score("сабаканский", 1) == 0

    def test_adjective_not_matched(self):
        """Прилагательное 'Абаканский' не должно совпадать с городом Абакан.

        Корень 'абака' (prefix_len=5 из 'абакан') может совпасть в 'Абаканский',
        но _match_score проверяет что после корня идёт не-буква (граница слова).
        """
        from granite.pipeline.region_resolver import detect_city
        # "Абаканский завод" — корень "абака" в слове "абаканский"
        # Проверяем что _match_score даёт 0 (внутри слова)
        from granite.pipeline.region_resolver import _match_score
        assert _match_score("абаканский", 0, 6) == 0  # начало слова, но после идёт буква
        assert detect_city("Абаканский завод") is None


# ── lookup_region ────────────────────────────────────────────────────────

class TestLookupRegion:
    """Тесты для lookup_region()."""

    def test_known_city(self):
        from granite.pipeline.region_resolver import lookup_region
        assert lookup_region("Абаза") == "Республика Хакасия"
        assert lookup_region("Сочи") == "Краснодарский край"

    def test_unknown_city(self):
        from granite.pipeline.region_resolver import lookup_region
        assert lookup_region("НесуществующийГород") == ""

    def test_doppelganger_returns_first(self):
        from granite.pipeline.region_resolver import lookup_region
        # Кировск есть в 2 регионах — lookup_region вернёт первый найденный
        result = lookup_region("Кировск")
        assert result in ("Кемеровская область", "Мурманская область")


# ── seed_cities_table ────────────────────────────────────────────────────

class TestSeedCitiesTable:
    """Тесты для seed_cities_table()."""

    def test_seed_populates(self, tmp_path):
        from granite.pipeline.region_resolver import seed_cities_table
        from granite.database import CityRefRow, Base, Database

        db_path = str(tmp_path / "test.db")
        db = Database(db_path=db_path, auto_migrate=False)
        Base.metadata.create_all(db.engine)

        count = seed_cities_table(db)
        assert count == 7  # 7 уникальных городов (Кировск double-skip)

        # Проверяем данные
        with db.session_scope() as session:
            cities = session.query(CityRefRow).all()
            names = {c.name for c in cities}
            assert "Абаза" in names
            assert "Абакан" in names
            assert "Кировск" in names  # один Кировск (двойник)

        db.engine.dispose()

    def test_seed_skip_if_filled(self, tmp_path):
        from granite.pipeline.region_resolver import seed_cities_table
        from granite.database import CityRefRow, Base, Database

        db_path = str(tmp_path / "test.db")
        db = Database(db_path=db_path, auto_migrate=False)
        Base.metadata.create_all(db.engine)

        count1 = seed_cities_table(db)
        count2 = seed_cities_table(db)
        assert count1 == 7
        assert count2 == 0  # skip

        db.engine.dispose()

    def test_doppelganger_flag(self, tmp_path):
        from granite.pipeline.region_resolver import seed_cities_table
        from granite.database import CityRefRow, Base, Database

        db_path = str(tmp_path / "test.db")
        db = Database(db_path=db_path, auto_migrate=False)
        Base.metadata.create_all(db.engine)

        seed_cities_table(db)

        with db.session_scope() as session:
            kirovsk = session.query(CityRefRow).filter_by(name="Кировск").first()
            assert kirovsk.is_doppelganger is True

            abaza = session.query(CityRefRow).filter_by(name="Абаза").first()
            assert abaza.is_doppelganger is False

        db.engine.dispose()
