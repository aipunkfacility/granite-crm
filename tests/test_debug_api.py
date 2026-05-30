"""Tests for debug API endpoints."""
import os

import pytest
from fastapi.testclient import TestClient


class TestDebugImapInbox:
    """GET /api/v1/debug/imap-inbox"""

    def test_no_imap_credentials(self, client: TestClient, admin_headers: dict):
        """Без SMTP_USER — IMAP not configured."""
        os.environ.pop("SMTP_USER", None)
        os.environ.pop("IMAP_PASS", None)
        os.environ.pop("SMTP_PASS", None)

        resp = client.get("/api/v1/debug/imap-inbox", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["imap_ok"] is False
        assert "not configured" in (data.get("error") or "")

    def test_requires_admin_token(self, client: TestClient):
        """Без X-Admin-Token — 401."""
        resp = client.get("/api/v1/debug/imap-inbox")
        assert resp.status_code == 401


class TestDebugProcessReplies:
    """POST /api/v1/debug/process-replies"""

    def test_no_imap_credentials(self, client: TestClient, admin_headers: dict):
        """Без SMTP_USER — IMAP not configured."""
        os.environ.pop("SMTP_USER", None)
        os.environ.pop("IMAP_PASS", None)
        os.environ.pop("SMTP_PASS", None)

        resp = client.post("/api/v1/debug/process-replies", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["imap_ok"] is False
        assert "not configured" in (data.get("error") or "")

    def test_requires_admin_token(self, client: TestClient):
        """Без X-Admin-Token — 401."""
        resp = client.post("/api/v1/debug/process-replies")
        assert resp.status_code == 401


class TestDebugImapInboxMocked:
    """GET /api/v1/debug/imap-inbox с мокнутым fetch_imap_messages."""

    def test_with_mocked_messages(self, client, admin_headers, monkeypatch):
        """IMAP возвращает письма — проверяем структуру ответа."""
        from email.message import Message
        import json

        msg1 = Message()
        msg1["Subject"] = "Re: Test"
        msg1["From"] = "client@example.com"
        msg1["Date"] = "Mon, 30 May 2026 10:00:00 +0000"
        msg1["Message-ID"] = "<abc123@example.com>"

        monkeypatch.setenv("SMTP_USER", "test@example.com")
        monkeypatch.setenv("IMAP_PASS", "test_pass")

        import granite.email.imap_helpers as imap_mod
        monkeypatch.setattr(imap_mod, "fetch_imap_messages", lambda **kw: [(b"1", msg1)])

        resp = client.get("/api/v1/debug/imap-inbox", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["imap_ok"] is True
        assert data["messages_found"] == 1
        assert len(data["messages"]) == 1
        assert data["messages"][0]["subject"] == "Re: Test"
        assert data["messages"][0]["from"] == "client@example.com"


class TestDebugProcessRepliesMocked:
    """POST /api/v1/debug/process-replies с мокнутыми IMAP и process_replies."""

    def test_with_mocked_replies(self, client, admin_headers, monkeypatch):
        """process_replies вернул 1 — проверяем структуру ответа."""
        from email.message import Message

        msg1 = Message()
        msg1["Subject"] = "Re: Test"
        msg1["From"] = "client@example.com"

        monkeypatch.setenv("SMTP_USER", "test@example.com")
        monkeypatch.setenv("IMAP_PASS", "test_pass")

        import granite.email.imap_helpers as imap_mod
        monkeypatch.setattr(imap_mod, "fetch_imap_messages", lambda **kw: [(b"1", msg1)])

        import granite.email.process_replies as replies_mod
        monkeypatch.setattr(replies_mod, "process_replies", lambda db, messages=None: 1)

        resp = client.post("/api/v1/debug/process-replies", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["imap_ok"] is True
        assert data["messages_found"] == 1
        assert data["processed"] == 1
