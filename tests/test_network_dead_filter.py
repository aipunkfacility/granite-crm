from datetime import datetime, timezone
import pytest
from granite.database import Database, CompanyRow, EnrichedCompanyRow
from granite.enrichers.network_detector import NetworkDetector


def _make_network_company(db_session, id, deleted_at=None, merged_into=None):
    c = CompanyRow(
        id=id,
        name_best=f"Company {id}",
        city="Test City",
        region="Test Region",
        phones=[],
        emails=[],
        website="https://example.com",
        status="enriched",
        deleted_at=deleted_at,
        merged_into=merged_into,
        segment="D",
    )
    db_session.add(c)

    e = EnrichedCompanyRow(
        id=id,
        name=f"Company {id}",
        city="Test City",
        region="Test Region",
        phones=[],
        emails=[],
        website="https://example.com",
        is_network=True,
        segment="D",
        crm_score=10,
    )
    db_session.add(e)
    db_session.flush()


class TestNetworkDeadFilter:
    def test_alive_company_appears_in_detail(self, engine, db_session):
        _make_network_company(db_session, 1)
        db_session.commit()

        db = Database(engine=engine)
        detector = NetworkDetector(db)
        detail = detector.get_network_detail(db_session, "website:example.com")

        assert detail is not None
        ids = {c["id"] for c in detail["companies"]}
        assert 1 in ids

    def test_deleted_company_excluded_from_detail(self, engine, db_session):
        _make_network_company(db_session, 1)
        _make_network_company(db_session, 2, deleted_at=datetime.now(timezone.utc))
        db_session.commit()

        db = Database(engine=engine)
        detector = NetworkDetector(db)
        detail = detector.get_network_detail(db_session, "website:example.com")

        assert detail is not None
        ids = {c["id"] for c in detail["companies"]}
        assert 1 in ids
        assert 2 not in ids

    def test_merged_company_excluded_from_detail(self, engine, db_session):
        _make_network_company(db_session, 1)
        _make_network_company(db_session, 2, merged_into=1)
        db_session.commit()

        db = Database(engine=engine)
        detector = NetworkDetector(db)
        detail = detector.get_network_detail(db_session, "website:example.com")

        assert detail is not None
        ids = {c["id"] for c in detail["companies"]}
        assert 1 in ids
        assert 2 not in ids

    def test_dead_companies_excluded_from_list(self, engine, db_session):
        _make_network_company(db_session, 1)
        _make_network_company(db_session, 2)
        _make_network_company(db_session, 3)
        _make_network_company(db_session, 4, deleted_at=datetime.now(timezone.utc))
        _make_network_company(db_session, 5, merged_into=1)
        db_session.commit()

        db = Database(engine=engine)
        detector = NetworkDetector(db)
        groups = detector.list_networks(db_session)

        for g in groups:
            if g["signal_value"] == "example.com":
                assert g["company_count"] == 3
                break
        else:
            pytest.fail("Network not found")

    def test_all_dead_network_has_zero_count(self, engine, db_session):
        _make_network_company(db_session, 1, deleted_at=datetime.now(timezone.utc))
        _make_network_company(db_session, 2, deleted_at=datetime.now(timezone.utc))
        db_session.commit()

        db = Database(engine=engine)
        detector = NetworkDetector(db)
        groups = detector.list_networks(db_session)

        for g in groups:
            if g["signal_value"] == "example.com":
                assert g["company_count"] == 0
                break
