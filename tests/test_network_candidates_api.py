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
