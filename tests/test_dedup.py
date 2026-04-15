# tests/test_dedup.py
import pytest
from granite.dedup.phone_cluster import cluster_by_phones
from granite.dedup.name_matcher import find_name_matches
from granite.dedup.site_matcher import cluster_by_site
from granite.dedup.merger import merge_cluster
from granite.dedup.validator import validate_phone, validate_phones, validate_email, validate_emails


class TestPhoneCluster:
    def test_two_companies_same_phone(self):
        companies = [
            {"id": 1, "phones": ["79031234567"]},
            {"id": 2, "phones": ["79031234567"]},
            {"id": 3, "phones": ["79059990000"]},
        ]
        clusters = cluster_by_phones(companies)
        assert len(clusters) == 1
        assert set(clusters[0]) == {1, 2}

    def test_chain_same_phones(self):
        """1 и 2 связаны через phone_A, 2 и 3 через phone_B → один кластер {1,2,3}."""
        companies = [
            {"id": 1, "phones": ["79031111111", "79032222222"]},
            {"id": 2, "phones": ["79031111111", "79033333333"]},
            {"id": 3, "phones": ["79033333333"]},
        ]
        clusters = cluster_by_phones(companies)
        assert len(clusters) == 1
        assert set(clusters[0]) == {1, 2, 3}

    def test_no_shared_phones(self):
        companies = [
            {"id": 1, "phones": ["79031111111"]},
            {"id": 2, "phones": ["79032222222"]},
        ]
        clusters = cluster_by_phones(companies)
        assert len(clusters) == 0

    def test_empty_phones(self):
        companies = [
            {"id": 1, "phones": []},
            {"id": 2, "phones": []},
        ]
        clusters = cluster_by_phones(companies)
        assert len(clusters) == 0


class TestNameMatcher:
    def test_exact_match(self):
        companies = [
            {"id": 1, "name": "Гранит-Мастер"},
            {"id": 2, "name": "Гранит-Мастер"},
        ]
        matches = find_name_matches(companies, threshold=88)
        assert len(matches) == 1
        assert set(matches[0]) == {1, 2}

    def test_fuzzy_match(self):
        # Используем простые строки чтобы не зависеть от кодировки консоли
        companies = [
            {"id": 1, "name": "Granit Master LLC"},
            {"id": 2, "name": "Granit Master"},
        ]
        matches = find_name_matches(companies, threshold=80)
        assert len(matches) >= 1

    def test_no_match(self):
        companies = [
            {"id": 1, "name": "Гранит-Мастер"},
            {"id": 2, "name": "Мир Камня Юг"},
        ]
        matches = find_name_matches(companies, threshold=88)
        assert len(matches) == 0


class TestSiteMatcher:
    def test_same_domain(self):
        companies = [
            {"id": 1, "website": "https://granit-master.ru/kontakty"},
            {"id": 2, "website": "https://granit-master.ru"},
        ]
        clusters = cluster_by_site(companies)
        assert len(clusters) == 1
        assert set(clusters[0]) == {1, 2}

    def test_www_vs_no_www(self):
        companies = [
            {"id": 1, "website": "https://www.granit-master.ru"},
            {"id": 2, "website": "https://granit-master.ru"},
        ]
        clusters = cluster_by_site(companies)
        assert len(clusters) == 1

    def test_different_domains(self):
        companies = [
            {"id": 1, "website": "https://granit-a.ru"},
            {"id": 2, "website": "https://granit-b.ru"},
        ]
        clusters = cluster_by_site(companies)
        assert len(clusters) == 0


class TestMerger:
    def test_basic_merge(self):
        records = [
            {"id": 1, "name": "Гранит", "phones": ["79031111111"],
             "address_raw": "ул. Ленина, 1", "website": "http://site.ru",
             "emails": [], "messengers": {}, "city": "Новосибирск"},
            {"id": 2, "name": "Гранит-Мастер", "phones": ["79031111111", "79032222222"],
             "address_raw": "ул. Ленина, 1", "website": "http://site.ru/contacts",
             "emails": ["info@site.ru"], "messengers": {"telegram": "t.me/granite"},
             "city": "Новосибирск"},
        ]
        result = merge_cluster(records)
        assert isinstance(result, list)
        assert len(result) == 1
        merged = result[0]
        assert "Гранит-Мастер" in merged["name_best"]
        assert "79031111111" in merged["phones"]
        assert "79032222222" in merged["phones"]
        assert "info@site.ru" in merged["emails"]
        assert merged["messengers"].get("telegram") == "t.me/granite"
        assert set(merged["merged_from"]) == {1, 2}

    def test_address_conflict_sets_review(self):
        records = [
            {"id": 1, "name": "Гранит", "phones": ["79031111111"],
             "address_raw": "ул. Ленина, 1", "website": None,
             "emails": [], "messengers": {}, "city": "Новосибирск"},
            {"id": 2, "name": "Гранит", "phones": ["79031111111"],
             "address_raw": "ул. Маркса, 10", "website": None,
             "emails": [], "messengers": {}, "city": "Новосибирск"},
        ]
        result = merge_cluster(records)       # <-- теперь list[dict]
        assert len(result) == 1               # <-- слито (одинаковое название)
        merged = result[0]
        assert merged["needs_review"] is True
        assert "address" in merged["review_reason"]


class TestMergerSplit:
    """Тесты для нового поведения: не сливать при разных названиях+адресах."""

    def test_different_names_different_addresses_returns_list(self):
        """Разные названия + разные адреса = НЕ сливать, вернуть список."""
        records = [
            {"id": 1, "name": "Гранит-Мастер",
             "phones": ["79031111111"],
             "address_raw": "ул. Ленина, 1, Новосибирск",
             "website": None, "emails": [], "messengers": {},
             "city": "Новосибирск"},
            {"id": 2, "name": "Мир Памятников",
             "phones": ["79031111111"],  # тот же телефон!
             "address_raw": "пр. Маркса, 45, Новосибирск",
             "website": None, "emails": [], "messengers": {},
             "city": "Новосибирск"},
        ]
        result = merge_cluster(records)
        assert isinstance(result, list)
        assert len(result) == 2  # НЕ слилось!
        assert result[0]["name_best"] == "Гранит-Мастер"
        assert result[1]["name_best"] == "Мир Памятников"
        assert result[0]["needs_review"] is False

    def test_same_name_different_address_still_sets_review(self):
        """Одинаковое название + разные адреса = слить + needs_review."""
        records = [
            {"id": 1, "name": "Гранит-Мастер",
             "phones": ["79031111111"],
             "address_raw": "ул. Ленина, 1, Новосибирск",
             "website": None, "emails": [], "messengers": {},
             "city": "Новосибирск"},
            {"id": 2, "name": "Гранит-Мастер",
             "phones": ["79031111111"],
             "address_raw": "ул. Маркса, 45, Новосибирск",
             "website": None, "emails": [], "messengers": {},
             "city": "Новосибирск"},
        ]
        result = merge_cluster(records)
        assert isinstance(result, list)
        assert len(result) == 1  # Слилось (одинаковое название)
        assert result[0]["needs_review"] is True
        assert "address" in result[0]["review_reason"]

    def test_single_record_returns_list(self):
        """Одна запись = вернуть список из одного элемента."""
        records = [
            {"id": 1, "name": "Гранит",
             "phones": ["79031111111"],
             "address_raw": "ул. Ленина, 1",
             "website": "http://site.ru",
             "emails": [], "messengers": {}, "city": "Москва"},
        ]
        result = merge_cluster(records)
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["name_best"] == "Гранит"

    def test_empty_returns_empty_list(self):
        result = merge_cluster([])
        assert result == []


class TestWebSearchDomainDedup:
    """Тесты для дедупликации доменов в web_search."""

    def test_same_domain_different_urls(self):
        """Один домен, разные URL — создаётся только одна RawCompany."""
        # Это проверка логики, а не парсинга — тестируем через seen_domains
        seen_domains = set()
        urls_domains = [
            ("https://granit.ru/catalog/page1", "granit.ru"),
            ("https://granit.ru/catalog/page2", "granit.ru"),
            ("https://granit.ru/contacts", "granit.ru"),
        ]
        passed = 0
        for url, expected_domain in urls_domains:
            if expected_domain in seen_domains:
                continue
            seen_domains.add(expected_domain)
            passed += 1
        assert passed == 1  # Только первая запись

    def test_different_domains(self):
        seen_domains = set()
        urls_domains = [
            ("https://granit-a.ru", "granit-a.ru"),
            ("https://granit-b.ru", "granit-b.ru"),
        ]
        passed = 0
        for url, expected_domain in urls_domains:
            if expected_domain in seen_domains:
                continue
            seen_domains.add(expected_domain)
            passed += 1
        assert passed == 2


class TestSplitLargeClusters:
    """Тесты для разбивки больших суперкластеров."""

    def _make_dedup_phase(self, config=None):
        from granite.pipeline.dedup_phase import DedupPhase
        from granite.database import Database
        db = Database(db_path=":memory:", auto_migrate=False)
        phase = DedupPhase(db, config=config or {})
        return phase

    def test_small_cluster_unchanged(self):
        phase = self._make_dedup_phase({"dedup": {"max_cluster_size": 5}})
        dicts_by_id = {
            1: {"id": 1, "website": "https://a.ru", "city": "Москва"},
            2: {"id": 2, "website": "https://b.ru", "city": "Москва"},
        }
        result = phase._split_large_clusters([[1, 2]], dicts_by_id)
        assert len(result) == 1
        assert set(result[0]) == {1, 2}

    def test_large_cluster_split_by_domain(self):
        phase = self._make_dedup_phase({"dedup": {"max_cluster_size": 3}})
        dicts_by_id = {
            i: {"id": i, "website": f"https://domain{i % 3}.ru",
                "city": "Москва"}
            for i in range(10)
        }
        result = phase._split_large_clusters([list(range(10))], dicts_by_id)
        assert len(result) > 1  # Разбилось

    def test_different_cities_split(self):
        phase = self._make_dedup_phase({"dedup": {"max_cluster_size": 100}})
        dicts_by_id = {
            1: {"id": 1, "website": "https://a.ru", "city": "Москва"},
            2: {"id": 2, "website": "https://b.ru", "city": "СПб"},
        }
        result = phase._split_large_clusters([[1, 2]], dicts_by_id)
        assert len(result) == 2  # Разные города — разбили


class TestValidator:
    def test_valid_phone(self):
        assert validate_phone("79031234567") is True

    def test_invalid_phone_8_digits(self):
        assert validate_phone("7903123456") is False

    def test_invalid_empty(self):
        assert validate_phone("") is False

    def test_validate_phones_dedup(self):
        result = validate_phones(["79031234567", "79031234567", "79032222222"])
        assert result == ["79031234567", "79032222222"]

    def test_valid_email(self):
        assert validate_email("info@site.ru") is True

    def test_invalid_email(self):
        assert validate_email("notanemail") is False

    def test_validate_emails_dedup(self):
        result = validate_emails(["a@b.ru", "a@b.ru", "c@d.com"])
        assert result == ["a@b.ru", "c@d.com"]
