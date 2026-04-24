"""TDD Red: админ-режим.

Фаза 6: Admin mode — HMAC-токен для batch-операций
"""
from granite.database import CompanyRow
from tests.helpers import create_company


class TestAdminLogin:

    def test_admin_login_success(self, client, monkeypatch):
        monkeypatch.setenv("GRANITE_ADMIN_PASSWORD", "test_secret")
        r = client.post("/api/v1/admin/login", json={"password": "test_secret"})
        assert r.status_code == 200
        assert "token" in r.json()

    def test_admin_login_wrong_password(self, client, monkeypatch):
        monkeypatch.setenv("GRANITE_ADMIN_PASSWORD", "test_secret")
        r = client.post("/api/v1/admin/login", json={"password": "wrong"})
        assert r.status_code == 401

    def test_admin_login_not_configured(self, client, monkeypatch):
        monkeypatch.delenv("GRANITE_ADMIN_PASSWORD", raising=False)
        r = client.post("/api/v1/admin/login", json={"password": "anything"})
        assert r.status_code == 403


class TestAdminTokenVerification:

    def test_batch_without_token_401(self, client, db_session, monkeypatch):
        monkeypatch.setenv("GRANITE_ADMIN_PASSWORD", "test_secret")
        r = client.post("/api/v1/companies/batch/approve",
                        json={"company_ids": [1, 2]})
        assert r.status_code == 401

    def test_batch_with_valid_token_200(self, client, db_session, monkeypatch):
        monkeypatch.setenv("GRANITE_ADMIN_PASSWORD", "test_secret")
        # Логинимся
        login_r = client.post("/api/v1/admin/login", json={"password": "test_secret"})
        token = login_r.json()["token"]
        # Создаём компании с needs_review
        cid1 = create_company(db_session, needs_review=True)
        db_session.commit()
        # Batch approve
        r = client.post("/api/v1/companies/batch/approve",
                        json={"company_ids": [cid1]},
                        headers={"X-Admin-Token": token})
        assert r.status_code == 200

    def test_batch_with_invalid_token_401(self, client, db_session, monkeypatch):
        monkeypatch.setenv("GRANITE_ADMIN_PASSWORD", "test_secret")
        cid1 = create_company(db_session, needs_review=True)
        db_session.commit()
        r = client.post("/api/v1/companies/batch/approve",
                        json={"company_ids": [cid1]},
                        headers={"X-Admin-Token": "invalid_token"})
        assert r.status_code == 401

    def test_batch_approve_clears_needs_review(self, client, db_session, monkeypatch):
        monkeypatch.setenv("GRANITE_ADMIN_PASSWORD", "test_secret")
        login_r = client.post("/api/v1/admin/login", json={"password": "test_secret"})
        token = login_r.json()["token"]
        cid1 = create_company(db_session, needs_review=True, review_reason="test")
        cid2 = create_company(db_session, needs_review=True, review_reason="test2")
        db_session.commit()
        r = client.post("/api/v1/companies/batch/approve",
                        json={"company_ids": [cid1, cid2]},
                        headers={"X-Admin-Token": token})
        assert r.status_code == 200
        data = r.json()
        assert data["ok"] is True
        assert data["processed"] == 2
        # Проверяем что needs_review сброшен
        c1 = db_session.get(CompanyRow, cid1)
        c2 = db_session.get(CompanyRow, cid2)
        assert c1.needs_review is False
        assert c2.needs_review is False

    def test_batch_spam(self, client, db_session, monkeypatch):
        monkeypatch.setenv("GRANITE_ADMIN_PASSWORD", "test_secret")
        login_r = client.post("/api/v1/admin/login", json={"password": "test_secret"})
        token = login_r.json()["token"]
        cid1 = create_company(db_session, segment="B", crm_score=30)
        db_session.commit()
        r = client.post("/api/v1/companies/batch/spam",
                        json={"company_ids": [cid1], "reason": "aggregator"},
                        headers={"X-Admin-Token": token})
        assert r.status_code == 200
        assert r.json()["processed"] == 1
        c1 = db_session.get(CompanyRow, cid1)
        assert c1.segment == "spam"
        assert c1.deleted_at is not None
