"""Tests for network list/detail API endpoints."""
import pytest
from granite.database import EnrichedCompanyRow, CompanyRow


class TestListNetworks:
    def test_returns_empty_when_no_networks(self, client):
        """GET /networks returns empty list when nothing is marked."""
        resp = client.get("/api/v1/networks")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["items"] == []

    def test_returns_network_summaries(self, client, db_session):
        """GET /networks returns networks with stats."""
        for i in range(3):
            db_session.add(EnrichedCompanyRow(
                id=i + 1, name=f"Branch {i}", city="Moscow",
                emails=["office@net.ru"], website="http://net.ru",
                phones=["+74951111111"], is_network=True, crm_score=4.0,
            ))
            db_session.add(CompanyRow(id=i + 1, name_best=f"Branch {i}", city="Moscow"))
        db_session.commit()

        resp = client.get("/api/v1/networks?min_companies=2")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        net = data["items"][0]
        assert "group_id" in net
        assert net["company_count"] >= 1
        assert net["city_count"] >= 1

    def test_filters_by_signal_type(self, client, db_session):
        """GET /networks?signal_type=website returns only website networks."""
        for i in range(3):
            db_session.add(EnrichedCompanyRow(
                id=i + 10, name=f"W{i}", city="Moscow",
                emails=[], website="http://w.net",
                phones=[], is_network=True,
            ))
            db_session.add(CompanyRow(id=i + 10, name_best=f"W{i}", city="Moscow"))
        db_session.commit()

        resp = client.get("/api/v1/networks?signal_type=phone")
        assert resp.status_code == 200
        data = resp.json()
        types = {g["signal_type"] for g in data["items"]}
        assert types.issubset({"phone"}), f"Expected only 'phone' signal types, got {types}"

    def test_min_companies_filter(self, client, db_session):
        """GET /networks?min_companies=5 filters small networks."""
        for i in range(3):
            db_session.add(EnrichedCompanyRow(
                id=i + 20, name=f"S{i}", city=f"C{i}",
                emails=[], website="http://small.ru",
                phones=[], is_network=True,
            ))
            db_session.add(CompanyRow(id=i + 20, name_best=f"S{i}", city=f"C{i}"))
        db_session.commit()

        resp = client.get("/api/v1/networks?min_companies=5")
        assert resp.status_code == 200
        data = resp.json()
        small = [g for g in data["items"] if g["signal_value"] == "small.ru"]
        assert len(small) == 0


class TestGetNetworkDetail:
    def test_returns_404_for_nonexistent(self, client):
        """GET /networks/nonexistent returns 404."""
        resp = client.get("/api/v1/networks/website:nonexistent.ru")
        assert resp.status_code == 404

    def test_returns_detail_with_companies(self, client, db_session):
        """GET /networks/{id} returns network with companies."""
        for i in range(3):
            db_session.add(EnrichedCompanyRow(
                id=i + 100, name=f"B{i}", city="Moscow",
                emails=["o@detail.ru"], website="http://detail.ru",
                phones=[], is_network=True, crm_score=3.5 + i,
            ))
            db_session.add(CompanyRow(id=i + 100, name_best=f"B{i}", city="Moscow"))
        db_session.commit()

        resp = client.get("/api/v1/networks/website:detail.ru")
        assert resp.status_code == 200
        data = resp.json()
        assert data["signal_value"] == "detail.ru"
        assert data["company_count"] == 3
        assert len(data["companies"]) == 3
        assert "score" in data["companies"][0]

    def test_has_top_cities(self, client, db_session):
        """GET /networks/{id} includes top_cities."""
        for i in range(5):
            db_session.add(EnrichedCompanyRow(
                id=i + 200, name=f"TC{i}", city="Moscow",
                emails=["o@tc.ru"], website="http://tc.ru",
                phones=[], is_network=True,
            ))
            db_session.add(CompanyRow(id=i + 200, name_best=f"TC{i}", city="Moscow"))
        db_session.commit()

        resp = client.get("/api/v1/networks/website:tc.ru")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["top_cities"]) >= 1
        assert data["top_cities"][0]["name"] == "Moscow"

    def test_email_based_network(self, client, db_session):
        """GET /networks/email:{domain} returns detail for email-based network.
        Group ID prefix is 'email:' but signal_type is 'email_domain'.
        This tests the mapping logic in get_network_detail()."""
        for i in range(2):
            db_session.add(EnrichedCompanyRow(
                id=i + 400, name=f"E{i}", city="Moscow",
                emails=["info@chain.ru"], website="http://chain.ru",
                phones=[], is_network=True, crm_score=3.0,
            ))
            db_session.add(CompanyRow(id=i + 400, name_best=f"E{i}", city="Moscow"))
        db_session.commit()

        resp = client.get("/api/v1/networks/email:chain.ru")
        assert resp.status_code == 200
        data = resp.json()
        assert data["signal_value"] == "chain.ru"
        assert data["company_count"] == 2
        assert len(data["companies"]) == 2
        assert data["signal_type"] == "email_domain"


class TestUnmarkNetwork:
    def test_unmark_clears_flag(self, client, db_session):
        """POST /networks/{id}/unmark clears is_network."""
        for i in range(3):
            db_session.add(EnrichedCompanyRow(
                id=i + 300, name=f"U{i}", city="Moscow",
                emails=["o@unmark.ru"], website="http://unmark.ru",
                phones=[], is_network=True,
            ))
            db_session.add(CompanyRow(id=i + 300, name_best=f"U{i}", city="Moscow"))
        db_session.commit()

        resp = client.post("/api/v1/networks/website:unmark.ru/unmark")
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

        for c in db_session.query(EnrichedCompanyRow).filter(
            EnrichedCompanyRow.id.in_([300, 301, 302])
        ).all():
            assert c.is_network is False

    def test_unmark_nonexistent_returns_404(self, client):
        """POST /networks/{id}/unmark on nonexistent returns 404."""
        resp = client.post("/api/v1/networks/website:ghost.ru/unmark")
        assert resp.status_code == 404
