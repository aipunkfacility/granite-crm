"""Tests for POST /api/v1/companies."""
import pytest
from tests.helpers import create_company


class TestCreateCompany:
    def test_create_company_minimal(self, client, db_session):
        resp = client.post("/api/v1/companies", json={
            "name": "Тестовая компания",
            "city": "Москва",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert isinstance(data["id"], int)
        assert data["id"] > 0

    def test_create_company_full(self, client):
        resp = client.post("/api/v1/companies", json={
            "name": "ООО Пример",
            "city": "Казань",
            "phones": ["+79001234567", "+79007654321"],
            "emails": ["info@example.ru"],
            "website": "https://example.ru",
            "address": "ул. Пушкина, 1",
            "messengers": {"telegram": "@example"},
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True

    def test_create_company_missing_name(self, client):
        resp = client.post("/api/v1/companies", json={"city": "Москва"})
        assert resp.status_code == 422

    def test_create_company_missing_city(self, client):
        resp = client.post("/api/v1/companies", json={"name": "Тест"})
        assert resp.status_code == 422

    def test_create_company_empty_name(self, client):
        resp = client.post("/api/v1/companies", json={"name": "", "city": "Москва"})
        assert resp.status_code == 422
