"""Network type classification tests."""
import pytest
from granite.enrichers.network_detector import NetworkDetector
from granite.database import Database


def _make_detector():
    return NetworkDetector(Database())


class TestClassifyNetworkType:

    def test_local_all_same_city(self):
        det = _make_detector()
        companies = [
            {"id": 1, "city": "Москва", "emails": ["a@test.ru"], "website": "test.ru", "phones": ["+7111"]},
            {"id": 2, "city": "Москва", "emails": ["b@test.ru"], "website": "test.ru", "phones": ["+7222"]},
        ]
        result = det._classify_network_type(companies, "website")
        assert result == "local"

    def test_local_single_city_with_none(self):
        det = _make_detector()
        companies = [
            {"id": 1, "city": "Москва", "emails": ["a@test.ru"], "website": "test.ru", "phones": []},
            {"id": 2, "city": None, "emails": [], "website": "test.ru", "phones": []},
        ]
        result = det._classify_network_type(companies, "website")
        assert result == "local"

    def test_regional_shared_email(self):
        det = _make_detector()
        companies = [
            {"id": 1, "city": "Москва", "emails": ["info@nebo-odno.ru"], "website": "nebo-odno.ru", "phones": []},
            {"id": 2, "city": "Тула", "emails": ["info@nebo-odno.ru"], "website": "nebo-odno.ru", "phones": []},
        ]
        result = det._classify_network_type(companies, "website")
        assert result == "regional"

    def test_aggregator_phone_signal(self):
        det = _make_detector()
        companies = [
            {"id": 1, "city": "Москва", "emails": ["a@landing.ru"], "website": "moskva.landing.ru", "phones": ["+74951111111"]},
            {"id": 2, "city": "Тула", "emails": ["b@landing.ru"], "website": "tula.landing.ru", "phones": ["+74951111111"]},
        ]
        result = det._classify_network_type(companies, "phone")
        assert result == "aggregator"

    def test_franchise_website_diff_emails(self):
        det = _make_detector()
        companies = [
            {"id": 1, "city": "Абаза", "emails": ["abaza@danila-master.ru"], "website": "danila-master.ru", "phones": []},
            {"id": 2, "city": "Москва", "emails": ["msk@danila-master.ru"], "website": "danila-master.ru", "phones": []},
        ]
        result = det._classify_network_type(companies, "website")
        assert result == "franchise"

    def test_empty_companies(self):
        det = _make_detector()
        result = det._classify_network_type([], "website")
        assert result == "regional"

    def test_regional_threshold_below_70_percent(self):
        det = _make_detector()
        companies = [
            {"id": 1, "city": "Москва", "emails": ["info@nebo-odno.ru"], "website": "nebo-odno.ru", "phones": []},
            {"id": 2, "city": "Тула", "emails": ["info@nebo-odno.ru"], "website": "nebo-odno.ru", "phones": []},
            {"id": 3, "city": "Калуга", "emails": ["other@site.ru"], "website": "nebo-odno.ru", "phones": []},
        ]
        result = det._classify_network_type(companies, "website")
        # 2/3 share email = 66% < 70% threshold → fails regional, falls through to franchise
        assert result == "franchise"

    def test_aggregator_email_domain_signal(self):
        det = _make_detector()
        companies = [
            {"id": 1, "city": "Москва", "emails": ["a@yell.ru"], "website": "moskva.yell.ru", "phones": ["+7111"]},
            {"id": 2, "city": "Тула", "emails": ["b@yell.ru"], "website": "tula.yell.ru", "phones": ["+7222"]},
        ]
        result = det._classify_network_type(companies, "email_domain")
        assert result == "aggregator"
