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
        merged = merge_cluster(records)
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
        merged = merge_cluster(records)
        assert merged["needs_review"] is True
        assert "address" in merged["review_reason"]


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
