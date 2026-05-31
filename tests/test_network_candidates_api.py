"""Tests for network candidates API endpoints."""
import pytest

from granite.database import EnrichedCompanyRow, CompanyRow


class TestListNetworkCandidates:
    def test_returns_groups(self, client, db_session):
        """GET /network-candidates возвращает группы."""
        for i in range(3):
            db_session.add(EnrichedCompanyRow(
                id=i + 1,
                name=f"Branch {i}",
                city=f"City{i}",
                emails=["office@network.ru"],
                website=f"http://n{i}.ru",
                phones=[],
            ))
            db_session.add(CompanyRow(
                id=i + 1,
                name_best=f"Branch {i}",
                city=f"City{i}",
            ))
        db_session.commit()

        resp = client.get("/api/v1/network-candidates")
        assert resp.status_code == 200
        data = resp.json()
        assert "groups" in data
        assert data["total"] >= 1

        email_groups = [g for g in data["groups"] if g["signal_type"] == "email_domain"]
        assert any(g["signal_value"] == "network.ru" for g in email_groups)

    def test_empty_db_returns_empty(self, client):
        """GET /network-candidates returns empty when no data."""
        resp = client.get("/api/v1/network-candidates")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["groups"] == []

    def test_filters_by_signal_type(self, client, db_session):
        """GET /network-candidates?signal_type=email_domain returns only email groups."""
        for i in range(3):
            db_session.add(EnrichedCompanyRow(
                id=i + 100, name=f"E{i}", city=f"C{i}",
                emails=["office@net.ru"], website=f"http://e{i}.ru", phones=[],
            ))
            db_session.add(CompanyRow(
                id=i + 100, name_best=f"E{i}", city=f"C{i}",
            ))
        db_session.add(EnrichedCompanyRow(
            id=200, name="W", city="Moscow",
            emails=[], website="http://common.ru", phones=[],
        ))
        db_session.add(CompanyRow(
            id=200, name_best="W", city="Moscow",
        ))
        db_session.add(EnrichedCompanyRow(
            id=201, name="W2", city="Spb",
            emails=[], website="http://common.ru", phones=[],
        ))
        db_session.add(CompanyRow(
            id=201, name_best="W2", city="Spb",
        ))
        db_session.commit()

        resp = client.get("/api/v1/network-candidates?signal_type=email_domain")
        assert resp.status_code == 200
        data = resp.json()
        types = {g["signal_type"] for g in data["groups"]}
        assert types == {"email_domain"}

    def test_include_resolved_param(self, client, db_session):
        """GET /network-candidates?include_resolved=true includes resolved groups."""
        for i in range(3):
            db_session.add(EnrichedCompanyRow(
                id=i + 300, name=f"R{i}", city=f"C{i}",
                emails=["office@marked.ru"], website=f"http://r{i}.ru",
                phones=[], is_network=True,
            ))
            db_session.add(CompanyRow(
                id=i + 300, name_best=f"R{i}", city=f"C{i}",
            ))
        db_session.commit()

        resp = client.get("/api/v1/network-candidates?include_resolved=true&min_companies=2")
        assert resp.status_code == 200
        data = resp.json()
        marked = [g for g in data["groups"] if g["signal_value"] == "marked.ru"]
        assert len(marked) >= 1

    def test_min_companies_param(self, client, db_session):
        """GET /network-candidates?min_companies=5 filters small groups."""
        for i in range(3):
            db_session.add(EnrichedCompanyRow(
                id=i + 400, name=f"S{i}", city=f"C{i}",
                emails=["office@small.ru"], website=f"http://s{i}.ru", phones=[],
            ))
            db_session.add(CompanyRow(
                id=i + 400, name_best=f"S{i}", city=f"C{i}",
            ))
        db_session.commit()

        resp = client.get("/api/v1/network-candidates?min_companies=5")
        assert resp.status_code == 200
        data = resp.json()
        small_ru = [g for g in data["groups"] if g["signal_value"] == "small.ru"]
        assert len(small_ru) == 0


class TestResolveNetworkGroup:
    @pytest.fixture
    def seeded_db(self, client, db_session):
        """Seed test data and return the session."""
        for i in range(3):
            db_session.add(EnrichedCompanyRow(
                id=i + 1,
                name=f"Branch {i}",
                city=f"City{i}",
                emails=["office@network.ru"],
                website=f"http://n{i}.ru",
                phones=[],
            ))
            db_session.add(CompanyRow(
                id=i + 1,
                name_best=f"Branch {i}",
                city=f"City{i}",
            ))
        db_session.commit()
        return db_session

    def test_resolve_as_network(self, client, seeded_db):
        """POST /network-candidates/resolve с action=network."""
        resp = client.get("/api/v1/network-candidates")
        groups = resp.json()["groups"]
        if not groups:
            pytest.skip("No groups to resolve")
        email_group = next(g for g in groups if g["signal_type"] == "email_domain")

        resp = client.post("/api/v1/network-candidates/resolve", json={
            "group_id": email_group["group_id"],
            "action": "network",
        })
        assert resp.status_code == 200, f"Response: {resp.json()}"
        result = resp.json()
        assert result["ok"] is True

        for c in seeded_db.query(EnrichedCompanyRow).all():
            assert c.is_network, f"Company {c.id} should be network"

    def test_resolve_duplicate_missing_target(self, client, seeded_db):
        """POST /network-candidates/resolve with duplicate but no target_id."""
        resp = client.post("/api/v1/network-candidates/resolve", json={
            "group_id": "email:network.ru",
            "action": "duplicate",
        })
        assert resp.status_code == 400

    def test_resolve_nonexistent_group(self, client):
        """POST /network-candidates/resolve with non-existent group."""
        resp = client.post("/api/v1/network-candidates/resolve", json={
            "group_id": "email:nonexistent.ru",
            "action": "network",
        })
        assert resp.status_code == 404
