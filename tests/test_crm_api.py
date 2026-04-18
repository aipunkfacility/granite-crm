"""Smoke-тесты для CRM API.

Фикстуры (engine, db_session, client) — в tests/conftest.py.
Фабрики (create_company, create_task) — в tests/helpers.py.
"""
from tests.helpers import create_company


class TestHealthEndpoint:
    def test_health_with_db(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        assert data["db"] is True

    def test_funnel_empty(self, client):
        r = client.get("/api/v1/funnel")
        assert r.status_code == 200
        data = r.json()
        assert data["new"] == 0
        assert "email_sent" in data
        # All 9 stages present
        assert len(data) == 9

    def test_campaigns_list_empty(self, client):
        r = client.get("/api/v1/campaigns")
        assert r.status_code == 200
        assert r.json() == []


class TestValidation:
    def test_touch_invalid_channel(self, client):
        r = client.post("/api/v1/companies/1/touches", json={"channel": "fax"})
        assert r.status_code == 422  # Pydantic validation

    def test_update_invalid_stage(self, client):
        r = client.patch("/api/v1/companies/1", json={"funnel_stage": "banana"})
        assert r.status_code == 422

    def test_send_invalid_channel(self, client):
        r = client.post("/api/v1/companies/1/send", json={"channel": "sms"})
        assert r.status_code == 422

    def test_task_invalid_priority(self, client):
        r = client.post("/api/v1/companies/1/tasks", json={"priority": "urgent"})
        assert r.status_code == 422

    def test_task_invalid_call_type(self, client):
        """A2: task_type 'call' удалён из допустимых значений."""
        r = client.post("/api/v1/companies/1/tasks", json={"task_type": "call"})
        assert r.status_code == 422


class TestJsonExtractFilters:
    """A3: Фильтры has_telegram / has_whatsapp через json_extract."""

    def test_filter_has_telegram(self, client, db_session):
        create_company(db_session, messengers={"telegram": "t.me/test"})
        db_session.commit()
        r = client.get("/api/v1/companies?has_telegram=1")
        assert r.status_code == 200
        assert r.json()["total"] == 1

    def test_filter_has_telegram_empty_value(self, client, db_session):
        """telegram: '' не считается наличием мессенджера."""
        create_company(db_session, messengers={"telegram": ""})
        db_session.commit()
        r = client.get("/api/v1/companies?has_telegram=1")
        assert r.status_code == 200
        assert r.json()["total"] == 0

    def test_filter_no_telegram(self, client, db_session):
        create_company(db_session, messengers={"whatsapp": "wa.me/79001234567"})
        db_session.commit()
        r = client.get("/api/v1/companies?has_telegram=0")
        assert r.status_code == 200
        assert r.json()["total"] == 1

    def test_filter_has_whatsapp(self, client, db_session):
        create_company(db_session, messengers={"whatsapp": "wa.me/79001234567"})
        db_session.commit()
        r = client.get("/api/v1/companies?has_whatsapp=1")
        assert r.status_code == 200
        assert r.json()["total"] == 1

    def test_filter_has_whatsapp_empty_value(self, client, db_session):
        """whatsapp: '' не считается наличием мессенджера."""
        create_company(db_session, messengers={"whatsapp": ""})
        db_session.commit()
        r = client.get("/api/v1/companies?has_whatsapp=1")
        assert r.status_code == 200
        assert r.json()["total"] == 0

    def test_filter_no_whatsapp(self, client, db_session):
        create_company(db_session, messengers={"telegram": "t.me/test"})
        db_session.commit()
        r = client.get("/api/v1/companies?has_whatsapp=0")
        assert r.status_code == 200
        assert r.json()["total"] == 1
