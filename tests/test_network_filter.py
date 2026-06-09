"""Tests for A-6 network filter domain filtering."""

import pytest
from unittest.mock import MagicMock
from granite.dedup.network_filter import detect_and_mark_aggregators


def test_a6_filters_non_network_domains():
    """NON_NETWORK_DOMAINS in 3+ cities should NOT trigger network."""
    db = MagicMock()
    session = MagicMock()
    db.session_scope.return_value.__enter__.return_value = session

    mock_records = [
        (1, "https://clients.site/company1", "City1"),
        (2, "https://clients.site/company2", "City2"),
        (3, "https://clients.site/company3", "City3"),
    ]
    session.query.return_value.filter.return_value.all.return_value = mock_records

    mock_company = MagicMock()
    mock_company.id = 1
    mock_company.needs_review = False
    mock_company.review_reason = ""
    session.query.return_value.get.return_value = mock_company

    result = detect_and_mark_aggregators(db)

    assert result == 0, "NON_NETWORK_DOMAINS should not trigger A-6"
    assert not mock_company.needs_review, "Company should not be marked"


def test_a6_still_catches_real_networks():
    """Real networks in 3+ cities should still be caught."""
    db = MagicMock()
    session = MagicMock()
    db.session_scope.return_value.__enter__.return_value = session

    mock_records = [
        (1, "https://vmkros.ru/", "Москва"),
        (2, "https://vmkros.ru/", "СПб"),
        (3, "https://vmkros.ru/", "Казань"),
    ]
    session.query.return_value.filter.return_value.all.return_value = mock_records

    mock_company = MagicMock()
    mock_company.id = 1
    mock_company.needs_review = False
    mock_company.review_reason = ""
    session.query.return_value.get.return_value = mock_company

    result = detect_and_mark_aggregators(db)

    assert result > 0, "Real network should still be detected"
    assert mock_company.needs_review, "Real network company should be marked"


def test_a6_spam_domains_become_spam():
    """SPAM_DOMAINS in 3+ cities should become segment=spam."""
    db = MagicMock()
    session = MagicMock()
    db.session_scope.return_value.__enter__.return_value = session

    mock_records = [
        (1, "https://www.zoon.ru/company1/", "City1"),
        (2, "https://www.zoon.ru/company2/", "City2"),
        (3, "https://www.zoon.ru/company3/", "City3"),
    ]
    session.query.return_value.filter.return_value.all.return_value = mock_records

    mock_company = MagicMock()
    mock_company.id = 1
    mock_company.needs_review = False
    mock_company.review_reason = ""
    mock_company.segment = "A"
    session.query.return_value.get.return_value = mock_company

    result = detect_and_mark_aggregators(db)

    assert result > 0, "SPAM_DOMAINS should still be marked"
    assert mock_company.needs_review, "Spam domain company should be marked"
    assert mock_company.segment == "spam", "Spam domain should become segment=spam"
