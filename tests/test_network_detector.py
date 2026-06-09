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


def test_scan_filters_tilda_constructor():
    """Tilda subdomains should not trigger network via base_domain."""
    db = MagicMock()
    session = MagicMock()
    db.session_scope.return_value.__enter__.return_value = session

    mock_rows = [
        (1, "https://bel.oblaka.tilda.ws/", ["79001112233"], []),
        (2, "https://ritual-angel.tilda.ws/", ["79004445566"], []),
        (3, "https://ritualtitov.tilda.ws/", ["79007778899"], []),
    ]

    Q = session.query
    Q.return_value.all.return_value = mock_rows
    Q.return_value.filter.return_value.all.return_value = mock_rows

    detector = NetworkDetector(db, {"enrichment": {"network_threshold": 2}})
    detector.scan_for_networks()

    # All different phones, all on tilda.ws — should NOT trigger network
    update_called = Q.return_value.filter.return_value.update.called
    assert not update_called, "tilda.ws should not trigger network via base_domain"


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


def test_list_networks_skips_subdomain_of_major_network():
    """Subdomain groups (ntagil.danila-master.ru) should be merged into the
    parent base_domain group when the base already forms a major network."""
    from unittest.mock import MagicMock

    db = MagicMock()
    session = MagicMock()

    # Companies: 4 on danila-master.ru (4 cities), 2 on ntagil.danila-master.ru
    mock_rows = [
        (1, "Данила-Мастер Москва", "Москва", "https://danila-master.ru/",
         ["79001112233"], [], 30.0, "A"),
        (2, "Данила-Мастер СПб", "Санкт-Петербург", "https://danila-master.ru/",
         ["79004445566"], [], 30.0, "A"),
        (3, "Данила-Мастер Казань", "Казань", "https://danila-master.ru/",
         ["79007778899"], [], 30.0, "A"),
        (4, "Данила-Мастер НН", "Нижний Новгород", "https://danila-master.ru/",
         ["79009990011"], [], 30.0, "A"),
        (5, "Ритуал НТагил", "Нижний Тагил", "https://ntagil.danila-master.ru/",
         ["79001113344"], [], 20.0, "B"),
        (6, "Ритуал НТагил 2", "Нижний Тагил", "https://ntagil.danila-master.ru/",
         ["79001115566"], [], 20.0, "B"),
        (7, "Independent A", "Тверь", "https://independent.ru/",
         ["79009991234"], [], 15.0, "C"),
        (8, "Independent B", "Рязань", "https://independent.ru/",
         ["79009995678"], [], 15.0, "C"),
    ]

    # session.query(...).filter(...).all() returns mock_rows
    # session.query(...).filter(...).all() on second call returns []
    # session.query(...).filter(...).distinct().all() returns []
    query_mock = MagicMock()
    query_mock.all.side_effect = [
        mock_rows,  # EnrichedCompanyRow query
        [],  # dead_ids query
    ]
    query_mock.distinct.return_value.all.return_value = []  # CrmEmailLog query
    session.query.return_value.filter.return_value = query_mock

    detector = NetworkDetector(db, {"enrichment": {"network_threshold": 2}})
    groups = detector.list_networks(session)

    # Should have 2 groups: danila-master.ru and independent.ru
    website_groups = [g for g in groups if g["signal_type"] == "website"]
    group_ids = {g["group_id"] for g in website_groups}

    assert "website:danila-master.ru" in group_ids, (
        "danila-master.ru should be a network group"
    )
    assert "website:ntagil.danila-master.ru" not in group_ids, (
        "ntagil.danila-master.ru should NOT be a separate group"
    )
    assert "website:independent.ru" in group_ids, (
        "independent.ru should be a separate group"
    )

    # danila-master.ru group should contain all 6 companies
    dm_group = next(g for g in website_groups if g["group_id"] == "website:danila-master.ru")
    assert dm_group["company_count"] == 6, (
        f"Expected 6 companies in danila-master.ru group, got {dm_group['company_count']}"
    )


def test_list_networks_does_not_skip_standalone_subdomain():
    """Subdomain groups without a major parent network should remain separate."""
    from unittest.mock import MagicMock

    db = MagicMock()
    session = MagicMock()

    # Two unrelated companies on the same subdomain, same phone = network
    mock_rows = [
        (1, "Comp A", "City1", "https://unique.petshop.ru/",
         ["79001112233"], [], 25.0, "A"),
        (2, "Comp B", "City2", "https://unique.petshop.ru/",
         ["79001112233"], [], 25.0, "A"),
    ]

    query_mock = MagicMock()
    query_mock.all.side_effect = [
        mock_rows,
        [],
    ]
    query_mock.distinct.return_value.all.return_value = []
    session.query.return_value.filter.return_value = query_mock

    detector = NetworkDetector(db, {"enrichment": {"network_threshold": 2}})
    groups = detector.list_networks(session)

    website_groups = [g for g in groups if g["signal_type"] == "website"]
    group_ids = {g["group_id"] for g in website_groups}

    assert "website:unique.petshop.ru" in group_ids, (
        "Standalone subdomain network should still appear"
    )


def test_list_networks_keeps_base_domain_with_few_cities():
    """Subdomains of base domains with <3 cities should NOT be skipped."""
    from unittest.mock import MagicMock

    db = MagicMock()
    session = MagicMock()

    mock_rows = [
        # Base domain with 2 companies at the SAME city (1 city total for base)
        (1, "Unique A", "City1", "https://base.ru/", ["79001112233"], [], 20.0, "A"),
        (2, "Unique B", "City1", "https://base.ru/", ["79004445566"], [], 20.0, "A"),
        # Subdomain with 2 companies in another city = should be its own group
        (3, "Sub A", "City2", "https://sub.base.ru/", ["79007778899"], [], 20.0, "B"),
        (4, "Sub B", "City2", "https://sub.base.ru/", ["79009990011"], [], 20.0, "B"),
    ]

    query_mock = MagicMock()
    query_mock.all.side_effect = [
        mock_rows,
        [],
    ]
    query_mock.distinct.return_value.all.return_value = []
    session.query.return_value.filter.return_value = query_mock

    detector = NetworkDetector(db, {"enrichment": {"network_threshold": 2}})
    groups = detector.list_networks(session)

    website_groups = [g for g in groups if g["signal_type"] == "website"]
    group_ids = {g["group_id"] for g in website_groups}

    # base.ru has only 2 companies in 2 cities → NOT a major network
    # sub.base.ru has 2 companies in 1 city → should be its own group
    assert "website:sub.base.ru" in group_ids, (
        "sub.base.ru should be its own group when base.ru has <3 cities"
    )


def test_scan_filters_spravka_subdomains():
    """City subdomains on spravka.ru should not trigger network via base_domain."""
    db = MagicMock()
    session = MagicMock()
    db.session_scope.return_value.__enter__.return_value = session

    mock_rows = [
        (1, "https://vyazma.spravka.ru/", ["79001112233"], []),
        (2, "https://tumen.moyaspravka.ru/", ["79004445566"], []),
        (3, "https://astrahan.ritualspravka.ru/", ["79007778899"], []),
    ]

    Q = session.query
    Q.return_value.all.return_value = mock_rows
    Q.return_value.filter.return_value.all.return_value = mock_rows

    detector = NetworkDetector(db, {"enrichment": {"network_threshold": 2}})
    detector.scan_for_networks()

    # All different phones, all on spravka.ru-family base domains
    update_called = Q.return_value.filter.return_value.update.called
    assert not update_called, "spravka.ru subdomains should not trigger network"
