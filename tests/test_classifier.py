# tests/test_classifier.py
import pytest
from granite.enrichers.classifier import Classifier


@pytest.fixture
def classifier():
    # FIX AUDIT-5 #9: Веса и пороги синхронизированы с config.yaml production.
    # Ранее 6 из 11 весов отличались от production — тесты проверяли другую формулу.
    config = {
        "scoring": {
            "weights": {
                "has_website": 5,
                "has_telegram": 15,
                "has_whatsapp": 10,
                "multiple_phones": 5,
                "has_email": 5,
                "cms_bitrix": 10,
                "cms_modern": 3,
                "has_marquiz": 8,
                "tg_trust_multiplier": 2,
                "is_network": 5
            },
            "levels": {
                "segment_A": 50,
                "segment_B": 30,
                "segment_C": 15
            }
        }
    }
    return Classifier(config)


def test_classifier_empty_company(classifier):
    company = {}
    score = classifier.calculate_score(company)
    segment = classifier.determine_segment(score)

    assert score == 0
    assert segment == "spam"  # score=0 → сегмент spam


def test_classifier_max_score(classifier):
    company = {
        "website": "http://granit-master.ru",
        "cms": "bitrix",
        "has_marquiz": True,
        "messengers": {"telegram": "t.me/granit", "whatsapp": "wa.me/79031234567"},
        "tg_trust": {"trust_score": 3},  # 3 * 2 = +6
        "phones": ["79031234567", "79032222222"],
        "emails": ["info@granit.ru"],
        "is_network": True
    }
    
    score = classifier.calculate_score(company)
    # 5(web) + 10(bitrix) + 8(marquiz) + 15(tg) + 6(tg_trust) + 10(wa) + 5(2_phones) + 5(email) + 5(network) = 69
    assert score == 69
    segment = classifier.determine_segment(score)
    assert segment == "A"


def test_classifier_segment_B(classifier):
    company = {
        "website": "http://granit-master.ru",
        "messengers": {"whatsapp": "wa.me/79031234567"},
        "phones": ["79031234567", "79032222222"]
    }
    
    score = classifier.calculate_score(company)
    # 5(web) + 10(wa) + 5(2_phones) = 20
    assert score == 20
    segment = classifier.determine_segment(score)
    assert segment == "C" # 20 is >= 15 -> C


def test_classifier_flexbe_gets_modern_cms_bonus(classifier):
    """Flexbe is classified as a modern CMS (same as WordPress/Tilda)."""
    company = {"website": "http://site.ru", "cms": "flexbe"}
    score = classifier.calculate_score(company)
    # 5 (has_website) + 3 (cms_modern) = 8
    assert score == 8
