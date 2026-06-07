"""Integration tests for networks API."""
import pytest
from fastapi.testclient import TestClient
from granite.api.app import app
from granite.database import Database

db = Database()
app.state.Session = db.SessionLocal
client = TestClient(app)


def test_networks_list_has_new_fields():
    """Network list items include type, email, contact_status."""
    resp = client.get("/api/v1/networks?min_companies=2")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert data["total"] > 0
    for item in data["items"]:
        assert "network_type" in item
        assert item["network_type"] in ("franchise", "aggregator", "regional", "local")
        assert "contact_status" in item
        assert item["contact_status"] in ("none", "sent")
        assert "primary_email" in item
        assert "sent_count" in item
        assert "total_count" in item
        assert "segment_dist" in item


def test_networks_filter_by_type():
    """Filter by network_type returns only matching items."""
    resp = client.get("/api/v1/networks?min_companies=2&network_type=franchise")
    assert resp.status_code == 200
    data = resp.json()
    for item in data["items"]:
        assert item["network_type"] == "franchise"


def test_networks_filter_by_contact_status():
    """Filter by contact_status returns only matching items."""
    resp = client.get("/api/v1/networks?min_companies=2&contact_status=sent")
    assert resp.status_code == 200
    data = resp.json()
    for item in data["items"]:
        assert item["contact_status"] == "sent"


def test_networks_no_cms_domains():
    """CMS/hosting domains like clients.site are excluded."""
    resp = client.get("/api/v1/networks?min_companies=2")
    assert resp.status_code == 200
    data = resp.json()
    for item in data["items"]:
        assert "clients.site" not in item["signal_value"]
        assert "turbo.site" not in item["signal_value"]
        assert "business.site" not in item["signal_value"]
