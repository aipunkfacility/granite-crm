"""Tests for CRM server - SMTP timeout, logging, DB endpoints"""

import asyncio
import json
import os
import sys
import tempfile
from unittest.mock import patch, MagicMock

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def test_smtp_timeout():
    """Verify SMTP connection uses timeout=30"""
    import importlib
    import server

    # Reload to get fresh module
    importlib.reload(server)

    with patch("server.smtplib.SMTP") as mock_smtp:
        mock_instance = MagicMock()
        mock_smtp.return_value = mock_instance

        asyncio.run(server.send_single_email("test@example.com", "<html>test</html>"))

        # Check SMTP was called with timeout
        call_args = mock_smtp.call_args
        assert (
            call_args.kwargs.get("timeout") == 30 or call_args[1].get("timeout") == 30
        ), f"SMTP called without timeout=30. Args: {call_args}"
        print("[PASS] SMTP timeout=30 verified")


def test_logging_setup():
    """Verify logging is configured"""
    import server
    import logging

    assert hasattr(server, "logger"), "Module should have 'logger'"
    assert isinstance(server.logger, logging.Logger), (
        "logger should be a Logger instance"
    )
    print("[PASS] Logging configured")


def test_logging_on_success():
    """Verify success logs are written"""
    import server
    from unittest.mock import patch, MagicMock

    with (
        patch("server.smtplib.SMTP") as mock_smtp,
        patch.object(server.logger, "info") as mock_info,
    ):
        mock_instance = MagicMock()
        mock_smtp.return_value = mock_instance

        asyncio.run(server.send_single_email("test@example.com", "<html>test</html>"))

        assert mock_info.called, "logger.info should be called on success"
        calls = [str(c) for c in mock_info.call_args_list]
        assert any("test@example.com" in c for c in calls), (
            f"Log should contain email address. Calls: {calls}"
        )
        print("[PASS] Success logging verified")


def test_logging_on_failure():
    """Verify error logs are written"""
    import server
    from unittest.mock import patch, MagicMock

    with (
        patch("server.smtplib.SMTP") as mock_smtp,
        patch.object(server.logger, "error") as mock_error,
    ):
        mock_smtp.side_effect = Exception("Connection refused")

        asyncio.run(server.send_single_email("bad@example.com", "<html>test</html>"))

        assert mock_error.called, "logger.error should be called on failure"
        calls = [str(c) for c in mock_error.call_args_list]
        # Connection failure logs "SMTP connection failed" without email
        assert any(
            "bad@example.com" in c or "SMTP connection failed" in c for c in calls
        ), f"Error log should contain email or connection error. Calls: {calls}"
        print("[PASS] Error logging verified")


def test_db_path_traversal():
    """Verify DB endpoints prevent path traversal"""
    from fastapi.testclient import TestClient
    import server

    client = TestClient(server.app)

    # Try path traversal
    resp = client.get("/db/../../../etc/passwd")
    assert resp.status_code in [400, 404], (
        f"Path traversal should be blocked, got {resp.status_code}"
    )
    print("[PASS] Path traversal protection verified")


def test_health_endpoint():
    """Verify health endpoint works"""
    from fastapi.testclient import TestClient
    import server

    client = TestClient(server.app)
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    print("[PASS] Health endpoint works")


def test_render_xss_fix():
    """Verify render.js uses data attributes instead of inline onclick"""
    js_path = os.path.join(os.path.dirname(__file__), "js", "render.js")
    with open(js_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Should NOT have inline onclick with area name
    assert "onclick=\"Render.editArea('" not in content, (
        "render.js should not have inline onclick with area name"
    )
    assert "onclick=\"Render.deleteArea('" not in content, (
        "render.js should not have inline onclick with area name"
    )

    # Should have data attributes
    assert "data-area-edit" in content, "render.js should use data-area-edit attribute"
    assert "data-area-delete" in content, (
        "render.js should use data-area-delete attribute"
    )
    print("[PASS] XSS fix in render.js verified")


def test_import_export_xss_fix():
    """Verify import-export.js escapes filename"""
    js_path = os.path.join(os.path.dirname(__file__), "js", "import-export.js")
    with open(js_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Should escape fileName
    assert "esc(fileName)" in content, "import-export.js should use esc(fileName)"
    print("[PASS] XSS fix in import-export.js verified")


if __name__ == "__main__":
    print("=== CRM Server Tests ===\n")

    tests = [
        test_smtp_timeout,
        test_logging_setup,
        test_logging_on_success,
        test_logging_on_failure,
        test_db_path_traversal,
        test_health_endpoint,
        test_render_xss_fix,
        test_import_export_xss_fix,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            print(f"[PASS] {test.__name__}")
            passed += 1
        except Exception as e:
            print(f"[FAIL] {test.__name__}: {e}")
            failed += 1

    print(f"\n=== Results: {passed} passed, {failed} failed ===")
    sys.exit(0 if failed == 0 else 1)
