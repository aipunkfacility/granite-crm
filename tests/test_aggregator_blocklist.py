# tests/test_aggregator_blocklist.py — Тесты A-1: блокировка агрегаторских доменов в SKIP_DOMAINS
import pytest
from granite.scrapers.web_search import WebSearchScraper


# ── Список агрегаторских доменов, которые ДОЛЖНЫ быть в SKIP_DOMAINS ──
# Аудит A-1: эти домены создают страницы-каталоги для каждого города РФ
# с федеральными контактами (колл-центр), а не реальными местными мастерскими.
_AGGREGATOR_DOMAINS = [
    "tsargranit.ru",
    "alshei.ru",
    "mipomnim.ru",
    "uznm.ru",
    "v-granit.ru",
    "spravker.ru",
    "monuments.su",
    "masterskay-granit.ru",
    "gr-anit.ru",
    "nbs-granit.ru",
    "granit-pamiatnik.ru",
    "postament.ru",
    "uslugio.com",
    "pamiatnikiizgranita.ru",
    "monuments39.ru",
    "asgranit.ru",
    "zoon.ru",
    "pomnivsegda.ru",
    "izgotovleniepamyatnikov.ru",
    "seprava.ru",
    "pamatniki.ru",
    "pqd.ru",
    "artgranit33.ru",
    "granit33market.ru",
    "rosreestrr.ru",
    "granitunas.ru",
    "fabrika-vek.ru",
    "mapage.ru",
    "orgpage.ru",
    "totadres.ru",
    "kamelotstone.ru",
    "kamenpamyati.ru",
    "home-granit.ru",
    "ritualst.ru",
    "gidgranit.ru",
    "luxritual.ru",
    "granitreal.ru",
    "granit-art.ru",
    "vekgranit.ru",
    "artmemorials.ru",
    "dymovskiy.ru",
    "bizorg.su",
    "best-monuments.ru",
    "eurogranite.ru",
    "e-memorial.ru",
    "granitmasterplus.ru",
    "grad-ex.ru",
    "planetagranita.ru",
    "kamengorod.ru",
    "ritual-reestr.ru",
    "pamyatnik-online.ru",
    "pamiatniky.ru",
    "ritualsp.ru",
    "ritualagency.ru",
    "ripme.ru",
    "ratusha-pamyatniki.ru",
    "masternovikov.ru",
    "izgotovleniye-pamyatnikov.ru",
    "sitc.ru",
]


class TestAggregatorBlocklist:
    """A-1: Агрегаторские домены должны быть в SKIP_DOMAINS и блокироваться."""

    @pytest.fixture
    def scraper(self):
        config = {
            "cities": [{"name": "Абаза"}],
            "sources": {"web_search": {"enabled": True}},
        }
        return WebSearchScraper(config, "Абаза")

    # ── Проверка наличия всех агрегаторов в SKIP_DOMAINS ──

    def test_skip_domains_contains_all_aggregators(self, scraper):
        """Все агрегаторские домены из аудита должны быть в SKIP_DOMAINS."""
        for domain in _AGGREGATOR_DOMAINS:
            assert domain in scraper.SKIP_DOMAINS, (
                f"Агрегаторский домен '{domain}' отсутствует в SKIP_DOMAINS"
            )

    # ── Проверка блокировки агрегаторских URL ──

    def test_is_skip_domain_blocks_aggregator_direct(self, scraper):
        """Прямой URL агрегатора блокируется: tsargranit.ru/abaza.html → True."""
        assert scraper._is_skip_domain("https://tsargranit.ru/abaza.html") is True

    def test_is_skip_domain_blocks_aggregator_subdomain(self, scraper):
        """Субдомен агрегатора блокируется: abaza.tsargranit.ru → True."""
        assert scraper._is_skip_domain("https://abaza.tsargranit.ru/") is True

    def test_is_skip_domain_blocks_spravker(self, scraper):
        """Справочник spravker.ru блокируется."""
        assert scraper._is_skip_domain("https://spravker.ru/abaza/pamyatniki/") is True

    def test_is_skip_domain_blocks_pqd(self, scraper):
        """Агрегатор-справочник pqd.ru блокируется."""
        assert scraper._is_skip_domain("https://pqd.ru/abaza/pamyatniki") is True

    def test_is_skip_domain_blocks_uslugio(self, scraper):
        """Справочник uslugio.com блокируется."""
        assert scraper._is_skip_domain("https://uslugio.com/abaza/pamyatniki") is True

    # ── Проверка что реальные компании НЕ блокируются ──

    def test_is_skip_domain_allows_real_company(self, scraper):
        """Реальная компания проходит: some-real-stone.ru → False."""
        assert scraper._is_skip_domain("https://some-real-stone.ru/") is False

    def test_is_skip_domain_allows_local_workshop(self, scraper):
        """Локальная мастерская проходит: granit-master.ru → False."""
        assert scraper._is_skip_domain("https://granit-master.ru/") is False

    # ── Данила-Мастер — реальная франшиза, НЕ блокируется ──

    def test_danila_master_not_blocked(self, scraper):
        """Данила-Мастер (франшиза) НЕ блокируется: abaza.danila-master.ru → False."""
        assert scraper._is_skip_domain("https://abaza.danila-master.ru/") is False

    def test_danila_master_root_not_blocked(self, scraper):
        """Корневой домен Данила-Мастер НЕ блокируется."""
        assert scraper._is_skip_domain("https://danila-master.ru/") is False

    # ── Регистронезависимость ──

    def test_is_skip_domain_case_insensitive(self, scraper):
        """Блокировка агрегаторов регистронезависима."""
        assert scraper._is_skip_domain("https://TSARGRANIT.RU/abaza.html") is True
        assert scraper._is_skip_domain("https://Tsargranit.Ru/abaza.html") is True

    # ── URL с www ──

    def test_is_skip_domain_blocks_with_www(self, scraper):
        """URL с www. тоже блокируется: www.tsargranit.ru → True."""
        assert scraper._is_skip_domain("https://www.tsargranit.ru/abaza.html") is True

    # ── punycode домены ──

    def test_is_skip_domain_blocks_punycode(self, scraper):
        """punycode домен памятники.рф блокируется."""
        assert scraper._is_skip_domain("https://xn--d1aigketcf.xn--p1ai/") is True
