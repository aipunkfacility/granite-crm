"""Tests for NetworkDetector domain filtering."""

import pytest
from unittest.mock import MagicMock, PropertyMock
from granite.enrichers.network_detector import NetworkDetector


def test_scan_filters_non_network_domains():
    """NON_NETWORK_DOMAINS should not be counted as network signals."""
    db = MagicMock()
    session = MagicMock()
    db.session_scope.return_value.__enter__.return_value = session

    mock_rows = [
        (1, "https://company1.clients.site/", ["79001112233"], ["a@mail.ru"]),
        (2, "https://company2.clients.site/", ["79004445566"], ["b@mail.ru"]),
        (3, "https://company3.clients.site/", ["79007778899"], ["c@mail.ru"]),
        (4, "https://real-company.ru/", ["79009990011"], ["d@mail.ru"]),
        (5, "https://real-company2.ru/", ["79009990011"], ["e@mail.ru"]),
    ]

    # Mock the detection query that loads rows - no filter_by when city=None
    Q = session.query
    Q.return_value.all.return_value = mock_rows
    Q.return_value.filter.return_value.all.return_value = mock_rows

    detector = NetworkDetector(db, {"enrichment": {"network_threshold": 2}})
    detector.scan_for_networks()

    # Shared phone signal (79009990011 appears twice) should trigger network
    # clients.site should NOT contribute to domain_count
    update_called = Q.return_value.filter.return_value.update.called
    assert update_called, "Network should be detected via phone signal"


def test_scan_filters_spam_domains():
    """SPAM_DOMAINS should not be counted as network signals."""
    db = MagicMock()
    session = MagicMock()
    db.session_scope.return_value.__enter__.return_value = session

    mock_rows = [
        (1, "https://www.zoon.ru/company1/", ["79001112233"], []),
        (2, "https://www.zoon.ru/company2/", ["79004445566"], []),
    ]

    Q = session.query
    Q.return_value.all.return_value = mock_rows
    Q.return_value.filter.return_value.all.return_value = mock_rows

    detector = NetworkDetector(db, {"enrichment": {"network_threshold": 2}})
    detector.scan_for_networks()

    # Only zoon.ru domain signal (domain count = 2) - should be filtered
    # No shared phones or email domains
    update_called = Q.return_value.filter.return_value.update.called
    assert not update_called, "zoon.ru should not trigger network"


def test_scan_keeps_real_phone_network():
    """Real networks by shared phone should still work after fix."""
    db = MagicMock()
    session = MagicMock()
    db.session_scope.return_value.__enter__.return_value = session

    mock_rows = [
        (1, "https://danila-master.ru/", ["79022202052"], []),
        (2, "https://spb.danila-master.ru/", ["79022202052"], []),
        (3, "https://msk.danila-master.ru/", ["79022202052"], []),
        (4, "https://independent.ru/", ["79009990011"], []),
    ]

    Q = session.query
    Q.return_value.all.return_value = mock_rows
    Q.return_value.filter.return_value.all.return_value = mock_rows

    detector = NetworkDetector(db, {"enrichment": {"network_threshold": 2}})
    detector.scan_for_networks()

    # Shared phone 79022202052 across 3 companies = network
    update_called = Q.return_value.filter.return_value.update.called
    assert update_called, "Real phone-based network should still be caught"


def test_scan_keeps_real_base_domain_network():
    """Real networks by shared base domain should still work."""
    db = MagicMock()
    session = MagicMock()
    db.session_scope.return_value.__enter__.return_value = session

    mock_rows = [
        (1, "https://spb.danila-master.ru/", ["79001112233"], []),
        (2, "https://msk.danila-master.ru/", ["79004445566"], []),
        (3, "https://nsk.danila-master.ru/", ["79007778899"], []),
    ]

    Q = session.query
    Q.return_value.all.return_value = mock_rows
    Q.return_value.filter.return_value.all.return_value = mock_rows

    detector = NetworkDetector(db, {"enrichment": {"network_threshold": 2}})
    detector.scan_for_networks()

    # Base domain danila-master.ru appears 3 times = network
    update_called = Q.return_value.filter.return_value.update.called
    assert update_called, "Base domain network should be caught"
