"""Tests for networks-as-entities feature."""
import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.pool import StaticPool
from granite.database import (
    Base, Database, EnrichedCompanyRow, CompanyRow,
    NetworkRow, NetworkEmailToggleRow,
)


@pytest.fixture
def db():
    """In-memory DB with FK PRAGMA, auto-creates all tables."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _pragma(dbapi_conn, conn_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    database = Database(engine=engine)
    yield database
    engine.dispose()


def test_scan_creates_network_from_shared_domain(db):
    """scan_for_networks() creates a NetworkRow for companies sharing a base_domain."""
    from granite.enrichers.network_detector import NetworkDetector

    with db.session_scope() as session:
        c1 = CompanyRow(name_best="Филиал Омск", city="Омск", website="https://omsk.danila-master.ru")
        c2 = CompanyRow(name_best="Филиал Тюмень", city="Тюмень", website="https://tyumen.danila-master.ru")
        session.add_all([c1, c2])
        session.flush()

        e1 = EnrichedCompanyRow(
            id=c1.id, name="Филиал Омск", city="Омск",
            website="https://omsk.danila-master.ru",
            is_network=False, emails=["omsk@danila-master.ru"],
            phones=["+73812123456"],
        )
        e2 = EnrichedCompanyRow(
            id=c2.id, name="Филиал Тюмень", city="Тюмень",
            website="https://tyumen.danila-master.ru",
            is_network=False, emails=["tyumen@danila-master.ru"],
            phones=["+73432123456"],
        )
        session.add_all([e1, e2])
        session.flush()
        c1_id, c2_id = c1.id, c2.id

    detector = NetworkDetector(db)
    detector.scan_for_networks(threshold=2)

    with db.session_scope() as session:
        networks = session.query(NetworkRow).all()
        assert len(networks) == 1
        nw = networks[0]
        assert nw.base_domain == "danila-master.ru"
        assert nw.company_count == 2
        assert "omsk.danila-master.ru" in nw.subdomains
        assert "tyumen.danila-master.ru" in nw.subdomains
        assert "omsk@danila-master.ru" in nw.emails
        assert "tyumen@danila-master.ru" in nw.emails
        assert nw.segment_dist == {"D": 2}

        e1 = session.get(EnrichedCompanyRow, c1_id)
        e2 = session.get(EnrichedCompanyRow, c2_id)
        assert e1.network_id == nw.id
        assert e2.network_id == nw.id
        assert e1.is_network is True
        assert e2.is_network is True


def test_scan_resets_non_network_companies(db):
    """Companies not in any network get network_id=NULL, is_network=False."""
    from granite.enrichers.network_detector import NetworkDetector

    with db.session_scope() as session:
        c1 = CompanyRow(name_best="Solo", city="Омск", website="https://solo.ru")
        session.add(c1)
        session.flush()
        e1 = EnrichedCompanyRow(
            id=c1.id, name="Solo", city="Омск", website="https://solo.ru",
            is_network=True, network_id=None,
        )
        session.add(e1)
        session.flush()
        c1_id = c1.id

    detector = NetworkDetector(db)
    detector.scan_for_networks(threshold=2)

    with db.session_scope() as session:
        e = session.get(EnrichedCompanyRow, c1_id)
        assert e.is_network is False
        assert e.network_id is None


def test_scan_excludes_deleted_companies(db):
    """Soft-deleted companies are excluded from network detection."""
    from granite.enrichers.network_detector import NetworkDetector
    from datetime import datetime, timezone

    with db.session_scope() as session:
        c1 = CompanyRow(name_best="Alive", city="Омск", website="https://net.ru")
        c2 = CompanyRow(name_best="Dead", city="Омск", website="https://net.ru",
                        deleted_at=datetime.now(timezone.utc))
        session.add_all([c1, c2])
        session.flush()

        e1 = EnrichedCompanyRow(id=c1.id, name="Alive", city="Омск",
                                website="https://net.ru", emails=["a@net.ru"])
        e2 = EnrichedCompanyRow(id=c2.id, name="Dead", city="Омск",
                                website="https://net.ru", emails=["b@net.ru"])
        session.add_all([e1, e2])
        session.flush()
        c1_id = c1.id

    detector = NetworkDetector(db)
    detector.scan_for_networks(threshold=2)

    with db.session_scope() as session:
        networks = session.query(NetworkRow).all()
        assert len(networks) == 0  # only 1 alive company, below threshold
        e = session.get(EnrichedCompanyRow, c1_id)
        assert e.is_network is False


def test_scan_updates_existing_network(db):
    """scan_for_networks() updates existing NetworkRow instead of duplicating."""
    from granite.enrichers.network_detector import NetworkDetector

    with db.session_scope() as session:
        nw = NetworkRow(
            name="Old Name", base_domain="test.ru",
            signal_type="website", network_type="local",
            emails=["old@test.ru"], company_count=1,
        )
        session.add(nw)
        session.flush()
        network_id = nw.id

        c1 = CompanyRow(name_best="A", city="Омск", website="https://a.test.ru")
        c2 = CompanyRow(name_best="B", city="Тюмень", website="https://b.test.ru")
        session.add_all([c1, c2])
        session.flush()

        e1 = EnrichedCompanyRow(id=c1.id, name="A", city="Омск",
                                website="https://a.test.ru", emails=["a@test.ru"])
        e2 = EnrichedCompanyRow(id=c2.id, name="B", city="Тюмень",
                                website="https://b.test.ru", emails=["b@test.ru"])
        session.add_all([e1, e2])
        session.flush()

    detector = NetworkDetector(db)
    detector.scan_for_networks(threshold=2)

    with db.session_scope() as session:
        networks = session.query(NetworkRow).all()
        assert len(networks) == 1  # no duplicate
        nw = session.get(NetworkRow, network_id)
        assert nw.company_count == 2
        assert "a@test.ru" in nw.emails
        assert "b@test.ru" in nw.emails


def test_company_list_hides_network_branches(db):
    """Companies with network_id are hidden from default list."""
    from fastapi.testclient import TestClient
    from granite.api.app import app

    original = getattr(app.state, 'Session', None)
    app.state.Session = db.SessionLocal
    try:
        client = TestClient(app)

        with db.session_scope() as session:
            c1 = CompanyRow(name_best="Solo", city="Омск", website="https://solo.ru")
            session.add(c1)
            session.flush()
            e1 = EnrichedCompanyRow(id=c1.id, name="Solo", city="Омск",
                                    website="https://solo.ru", network_id=None)
            session.add(e1)

            c2 = CompanyRow(name_best="Branch", city="Омск", website="https://net.ru")
            session.add(c2)
            session.flush()
            nw = NetworkRow(name="Net", base_domain="net.ru",
                            signal_type="website", network_type="local",
                            emails=["a@net.ru"], company_count=1)
            session.add(nw)
            session.flush()
            e2 = EnrichedCompanyRow(id=c2.id, name="Branch", city="Омск",
                                    website="https://net.ru", network_id=nw.id,
                                    is_network=True)
            session.add(e2)
            session.flush()

        resp = client.get("/api/v1/companies")
        names = [c["name"] for c in resp.json()["items"]]
        assert "Solo" in names
        assert "Branch" not in names

        resp = client.get("/api/v1/companies?is_network=1")
        names = [c["name"] for c in resp.json()["items"]]
        assert "Solo" not in names
        assert "Branch" in names
    finally:
        if original is not None:
            app.state.Session = original
        else:
            del app.state.Session


def test_scan_city_filter(db):
    """scan_for_networks(city='Омск') only processes companies in that city."""
    from granite.enrichers.network_detector import NetworkDetector

    with db.session_scope() as session:
        c1 = CompanyRow(name_best="Омск A", city="Омск", website="https://net.ru")
        c2 = CompanyRow(name_best="Тюмень B", city="Тюмень", website="https://net.ru")
        session.add_all([c1, c2])
        session.flush()

        e1 = EnrichedCompanyRow(id=c1.id, name="Омск A", city="Омск",
                                website="https://net.ru", emails=["a@net.ru"])
        e2 = EnrichedCompanyRow(id=c2.id, name="Тюмень B", city="Тюмень",
                                website="https://net.ru", emails=["b@net.ru"])
        session.add_all([e1, e2])
        session.flush()
        c1_id, c2_id = c1.id, c2.id

    detector = NetworkDetector(db)
    detector.scan_for_networks(threshold=2, city="Омск")

    with db.session_scope() as session:
        networks = session.query(NetworkRow).all()
        assert len(networks) == 0  # only 1 company in Омск, below threshold
        e1 = session.get(EnrichedCompanyRow, c1_id)
        e2 = session.get(EnrichedCompanyRow, c2_id)
        assert e1.is_network is False
        assert e2.is_network is False


def test_toggle_email_rejects_unknown_email(db):
    """Toggle rejects email not in network's emails list."""
    from fastapi.testclient import TestClient
    from granite.api.app import app

    original = getattr(app.state, 'Session', None)
    app.state.Session = db.SessionLocal
    try:
        client = TestClient(app)

        with db.session_scope() as session:
            nw = NetworkRow(name="Test", base_domain="test.ru",
                            signal_type="website", network_type="local",
                            emails=["a@test.ru"], company_count=1)
            session.add(nw)
            session.flush()
            network_id = nw.id

        resp = client.post(
            f"/api/v1/networks/{network_id}/emails/toggle",
            json={"email": "x@test.ru", "is_disabled": True},
        )
        assert resp.status_code == 400
        assert "не найден" in resp.json()["error"]
    finally:
        if original is not None:
            app.state.Session = original
        else:
            del app.state.Session


def test_toggle_email_creates_and_updates(db):
    """Toggle creates new toggle row and updates existing."""
    from fastapi.testclient import TestClient
    from granite.api.app import app

    original = getattr(app.state, 'Session', None)
    app.state.Session = db.SessionLocal
    try:
        client = TestClient(app)

        with db.session_scope() as session:
            nw = NetworkRow(name="Test", base_domain="test.ru",
                            signal_type="website", network_type="local",
                            emails=["a@test.ru", "b@test.ru"], company_count=2)
            session.add(nw)
            session.flush()
            network_id = nw.id

        # Disable email
        resp = client.post(
            f"/api/v1/networks/{network_id}/emails/toggle",
            json={"email": "a@test.ru", "is_disabled": True, "reason": "bounced"},
        )
        assert resp.status_code == 200
        assert resp.json()["ok"] is True
        assert "отключен" in resp.json()["message"]

        # Verify toggle was created
        with db.session_scope() as session:
            t = session.query(NetworkEmailToggleRow).filter(
                NetworkEmailToggleRow.network_id == network_id,
                NetworkEmailToggleRow.email == "a@test.ru",
            ).first()
            assert t is not None
            assert t.is_disabled is True
            assert t.reason == "bounced"

        # Re-enable email
        resp = client.post(
            f"/api/v1/networks/{network_id}/emails/toggle",
            json={"email": "a@test.ru", "is_disabled": False},
        )
        assert resp.status_code == 200
        assert "включен" in resp.json()["message"]

        with db.session_scope() as session:
            t = session.query(NetworkEmailToggleRow).filter(
                NetworkEmailToggleRow.network_id == network_id,
                NetworkEmailToggleRow.email == "a@test.ru",
            ).first()
            assert t.is_disabled is False
    finally:
        if original is not None:
            app.state.Session = original
        else:
            del app.state.Session


def test_list_network_emails_with_badges(db):
    """list_network_emails returns correct badges."""
    from fastapi.testclient import TestClient
    from granite.api.app import app

    original = getattr(app.state, 'Session', None)
    app.state.Session = db.SessionLocal
    try:
        client = TestClient(app)

        with db.session_scope() as session:
            nw = NetworkRow(name="Test", base_domain="test.ru",
                            signal_type="website", network_type="local",
                            emails=["a@test.ru", "b@test.ru"], company_count=2)
            session.add(nw)
            session.flush()
            network_id = nw.id

            # Disable a@test.ru
            session.add(NetworkEmailToggleRow(
                network_id=network_id, email="a@test.ru", is_disabled=True, reason="test",
            ))

        resp = client.get(f"/api/v1/networks/{network_id}/emails")
        assert resp.status_code == 200
        items = resp.json()
        assert len(items) == 2

        by_email = {i["email"]: i for i in items}
        assert by_email["a@test.ru"]["is_disabled"] is True
        assert by_email["a@test.ru"]["badge"] == "disabled"
        assert by_email["a@test.ru"]["reason"] == "test"
        assert by_email["b@test.ru"]["is_disabled"] is False
        assert by_email["b@test.ru"]["badge"] == ""
    finally:
        if original is not None:
            app.state.Session = original
        else:
            del app.state.Session


def test_toggle_email_404_for_missing_network(db):
    """Toggle returns 404 for non-existent network."""
    from fastapi.testclient import TestClient
    from granite.api.app import app

    original = getattr(app.state, 'Session', None)
    app.state.Session = db.SessionLocal
    try:
        client = TestClient(app)

        resp = client.post(
            "/api/v1/networks/999/emails/toggle",
            json={"email": "x@test.ru", "is_disabled": True},
        )
        assert resp.status_code == 404
    finally:
        if original is not None:
            app.state.Session = original
        else:
            del app.state.Session
