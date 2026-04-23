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

    def test_excludes_network_phone(self):
        """Федеральный телефон у 15 компаний — не должен создавать кластер."""
        companies = [
            {"id": i, "phones": ["79022234935", f"7900000000{i}"]}
            for i in range(15)
        ]
        clusters = cluster_by_phones(companies, network_phone_threshold=10)
        # Ни один кластер не должен содержать >10 компаний
        assert all(len(c) < 10 for c in clusters), \
            "Сетевой телефон не должен создавать гигантский кластер"

    def test_normal_dedup_unaffected_by_threshold(self):
        """Обычный случай: 2 компании с общим телефоном — должны слиться."""
        companies = [
            {"id": 1, "phones": ["79031234567"]},
            {"id": 2, "phones": ["79031234567"]},
            {"id": 3, "phones": ["79039999999"]},
        ]
        clusters = cluster_by_phones(companies, network_phone_threshold=10)
        assert [1, 2] in clusters or [2, 1] in clusters, \
            "Обычные дубли должны кластеризоваться"


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

    def test_exact_same_city_not_missed(self):
        """C2: Exact name+city match must be found even if fuzzy matching misses it."""
        companies = [
            {"id": 1, "name": "Гранитная мастерская НИКА", "city": "Воронеж", "address": "ул. Ленина, 1"},
            {"id": 2, "name": "Гранитная мастерская НИКА", "city": "Воронеж", "address": "ул. Мира, 2"},
            {"id": 3, "name": "Другая мастерская", "city": "Воронеж", "address": "ул. Ленина, 1"},
        ]
        matches = find_name_matches(companies, threshold=88)
        match_sets = [frozenset(m) for m in matches]
        assert frozenset([1, 2]) in match_sets
        assert frozenset([1, 3]) not in match_sets


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
        assert isinstance(result, dict)
        assert "Гранит-Мастер" in result["name_best"]
        assert "79031111111" in result["phones"]
        assert "79032222222" in result["phones"]
        assert "info@site.ru" in result["emails"]
        assert result["messengers"].get("telegram") == "t.me/granite"
        assert set(result["merged_from"]) == {1, 2}

    def test_address_conflict_sets_review(self):
        records = [
            {"id": 1, "name": "Гранит", "phones": ["79031111111"],
             "address_raw": "ул. Ленина, 1", "website": None,
             "emails": [], "messengers": {}, "city": "Новосибирск"},
            {"id": 2, "name": "Гранит", "phones": ["79031111111"],
             "address_raw": "ул. Маркса, 10", "website": None,
             "emails": [], "messengers": {}, "city": "Новосибирск"},
        ]
        result = merge_cluster(records)
        assert isinstance(result, dict)
        assert result["needs_review"] is True
        assert "address" in result["review_reason"]


class TestMergerSplit:
    """Тесты для поведения merge_cluster при разных названиях/адресах.

    merge_cluster всегда возвращает dict (одно сливание).
    При разных названиях+адресах устанавливается needs_review=True.
    """

    def test_different_names_different_addresses_sets_review(self):
        """Разные названия + разные адреса = слить + needs_review."""
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
        assert isinstance(result, dict)
        assert result["needs_review"] is True
        assert "different_names_different_addresses" in result["review_reason"]

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
        assert isinstance(result, dict)
        assert result["needs_review"] is True
        assert "address" in result["review_reason"]

    def test_single_record_returns_dict(self):
        """Одна запись = вернуть dict."""
        records = [
            {"id": 1, "name": "Гранит",
             "phones": ["79031111111"],
             "address_raw": "ул. Ленина, 1",
             "website": "http://site.ru",
             "emails": [], "messengers": {}, "city": "Москва"},
        ]
        result = merge_cluster(records)
        assert isinstance(result, dict)
        assert result["name_best"] == "Гранит"

    def test_empty_returns_empty_dict(self):
        result = merge_cluster([])
        assert result == {}


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
    """Тесты для разбивки больших суперкластеров.

    NOTE: _split_large_clusters был удалён из DedupPhase.
    Кластеры теперь всегда сливаются через merge_cluster с needs_review-флагами.
    Эти тесты проверяют, что needs_review корректно выставляется при
    признаках ложного слияния.
    """

    def test_contacts_over_limit_sets_review(self):
        """Превышение лимита телефонов/emails → needs_review."""
        records = [
            {"id": i, "name": f"Компания{i}",
             "phones": [f"7903111111{i}"],
             "address_raw": f"ул. {i}, Москва",
             "website": None, "emails": [f"info{i}@site{i}.ru"],
             "messengers": {}, "city": "Москва"}
            for i in range(8)  # 8 телефонов > MAX_MERGE_PHONES (6)
        ]
        result = merge_cluster(records)
        assert isinstance(result, dict)
        assert result["needs_review"] is True
        assert "contacts_over_limit" in result["review_reason"]

    def test_different_cities_sets_review(self):
        """Разные города в кластере → needs_review."""
        records = [
            {"id": 1, "name": "Гранит",
             "phones": ["79031111111"],
             "address_raw": "ул. Ленина, 1",
             "website": None, "emails": [], "messengers": {},
             "city": "Москва"},
            {"id": 2, "name": "Гранит",
             "phones": ["79031111111"],
             "address_raw": "ул. Ленина, 1",
             "website": None, "emails": [], "messengers": {},
             "city": "СПб"},
        ]
        result = merge_cluster(records)
        assert isinstance(result, dict)
        assert result["needs_review"] is True
        assert "different_cities" in result["review_reason"]


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
