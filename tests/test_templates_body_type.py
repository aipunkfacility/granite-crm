"""Тесты для body_type: HTML-шаблоны, валидация, рендер, EmailSender.

После рефакторинга шаблоны читаются из TemplateRegistry (JSON — source of truth).
POST/PUT/DELETE /templates удалены — правишь JSON руками.

Покрывает:
- EmailTemplate.render() с HTML-escaping (из granite/templates.py)
- EmailTemplate.render_subject() без экранирования
- html_to_plain_text() утилита
- EmailSender.send() с body_html и rendered_body
- GET /templates — список шаблонов из TemplateRegistry
- GET /templates/{name} — один шаблон
- POST /templates/reload — перезагрузка JSON
- Campaigns: channel=email при создании
"""
import json
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone


# ============================================================
# Unit-тесты: EmailTemplate.render() и render_subject()
# ============================================================

class TestEmailTemplateRender:
    """Тесты метода render() класса EmailTemplate (из granite/templates.py)."""

    def _make_template(self, body_type="plain", body="Hello {city}!", name="test_tpl"):
        from granite.templates import EmailTemplate
        return EmailTemplate(
            name=name,
            channel="email",
            subject="Offer for {company_name}",
            body=body,
            body_type=body_type,
        )

    def test_render_plain_replaces_literal(self):
        """Plain-шаблон: плейсхолдеры заменяются как есть (литерально)."""
        t = self._make_template(body_type="plain", body="Hello {city}!")
        result = t.render(city="Москва")
        assert result == "Hello Москва!"

    def test_render_plain_no_escaping(self):
        """Plain-шаблон: спецсимволы НЕ экранируются."""
        t = self._make_template(body_type="plain", body="Company: {company_name}")
        result = t.render(company_name="<script>alert('xss')</script>")
        assert result == "Company: <script>alert('xss')</script>"

    def test_render_html_escapes_values(self):
        """HTML-шаблон: значения плейсхолдеров экранируются через html.escape()."""
        t = self._make_template(body_type="html", body="<p>{company_name}</p>")
        result = t.render(company_name="<script>alert('xss')</script>")
        assert "&lt;script&gt;" in result
        assert "<script>" not in result
        assert "<p>" in result  # Тело шаблона НЕ экранируется

    def test_render_html_ampersand_escaped(self):
        """HTML-шаблон: амперсанд экранируется."""
        t = self._make_template(body_type="html", body="<p>{company_name}</p>")
        result = t.render(company_name="A & B")
        assert "A &amp; B" in result

    def test_render_html_quotes_escaped(self):
        """HTML-шаблон: кавычки экранируются."""
        t = self._make_template(body_type="html", body='<span>{city}</span>')
        result = t.render(city='Моск"ва')
        assert "Моск&quot;ва" in result

    def test_render_multiple_placeholders(self):
        """Несколько плейсхолдеров заменяются корректно."""
        t = self._make_template(
            body_type="html",
            body="<p>{from_name} из {city} для {company_name}</p>"
        )
        result = t.render(from_name="Александр", city="Москва", company_name="Гранит-М")
        assert "Александр" in result
        assert "Москва" in result
        assert "Гранит-М" in result

    def test_render_subject_no_escaping_for_html(self):
        """render_subject() НЕ экранирует даже для HTML-шаблонов (RFC 2047)."""
        t = self._make_template(body_type="html", body="<p>test</p>")
        result = t.render_subject(company_name="A & B <Co>")
        assert "A & B <Co>" in result  # Без экранирования
        assert "&amp;" not in result   # Экранирования быть не должно


# ============================================================
# Unit-тесты: html_to_plain_text()
# ============================================================

class TestHtmlToPlainText:
    """Тесты утилиты html_to_plain_text()."""

    def test_basic_html_stripped(self):
        """Базовые HTML-теги удаляются, текст остаётся."""
        from granite.utils import html_to_plain_text
        result = html_to_plain_text("<p>Hello</p><p>World</p>")
        assert "Hello" in result
        assert "World" in result
        assert "<p>" not in result

    def test_entities_decoded(self):
        """HTML-сущности декодируются (&amp; → &, &nbsp; → пробел)."""
        from granite.utils import html_to_plain_text
        result = html_to_plain_text("<p>A &amp; B</p>")
        assert "A & B" in result

    def test_scripts_removed(self):
        """<script> вырезается полностью."""
        from granite.utils import html_to_plain_text
        result = html_to_plain_text(
            "<p>Hello</p><script>alert('bad')</script><p>World</p>"
        )
        assert "alert" not in result
        assert "Hello" in result
        assert "World" in result

    def test_styles_removed(self):
        """<style> вырезается полностью."""
        from granite.utils import html_to_plain_text
        result = html_to_plain_text(
            "<style>body{color:red}</style><p>Hello</p>"
        )
        assert "color" not in result
        assert "Hello" in result

    def test_excessive_blank_lines_removed(self):
        """Избыточные пустые строки удаляются."""
        from granite.utils import html_to_plain_text
        result = html_to_plain_text("<p>A</p><p></p><p></p><p>B</p>")
        lines = result.split("\n")
        consecutive_blank = 0
        for line in lines:
            if not line.strip():
                consecutive_blank += 1
            else:
                consecutive_blank = 0
            assert consecutive_blank == 0, f"Found {consecutive_blank} consecutive blank lines"


# ============================================================
# Unit-тесты: EmailSender с body_html и rendered_body
# ============================================================

class TestEmailSenderHtml:
    """Тесты EmailSender с поддержкой HTML и rendered_body."""

    def _make_sender(self):
        from granite.email.sender import EmailSender
        return EmailSender()

    def _get_sent_msg_html(self, sender, **send_kwargs):
        """Вызвать send() с моком и вернуть декодированную HTML-часть сообщения."""
        sent_msgs = []
        def capture_send(email_to, msg):
            sent_msgs.append(msg)
        with patch.object(sender, '_smtp_send', side_effect=capture_send):
            with patch.object(sender, '_log_to_db'):
                sender.send(**send_kwargs)
        assert len(sent_msgs) == 1
        msg = sent_msgs[0]
        for part in msg.walk():
            ct = part.get_content_type()
            if ct == "text/html":
                return part.get_payload(decode=True).decode("utf-8")
        return ""

    def test_plain_generates_pre_tag(self):
        """Без body_html: plain text оборачивается в <pre>."""
        sender = self._make_sender()
        html_part = self._get_sent_msg_html(
            sender,
            company_id=1,
            email_to="test@example.com",
            subject="Test",
            body_text="Hello world",
        )
        assert "<pre" in html_part

    def test_html_uses_body_html_as_is(self):
        """С body_html: используется переданный HTML напрямую."""
        sender = self._make_sender()
        html_part = self._get_sent_msg_html(
            sender,
            company_id=1,
            email_to="test@example.com",
            subject="Test",
            body_text="Hello",
            body_html="<html><body><h1>Hello</h1></body></html>",
        )
        assert "<h1>Hello</h1>" in html_part

    def test_html_tracking_pixel_before_body_close(self):
        """Tracking pixel вставляется перед </body>."""
        sender = self._make_sender()
        html_part = self._get_sent_msg_html(
            sender,
            company_id=1,
            email_to="test@example.com",
            subject="Test",
            body_text="Content",
            body_html="<html><body><p>Content</p></body></html>",
        )
        pixel_pos = html_part.find('width="1"')
        body_close_pos = html_part.rfind("</body>")
        assert pixel_pos > 0
        assert body_close_pos > 0
        assert pixel_pos < body_close_pos

    def test_rendered_body_passed_to_log(self):
        """rendered_body передаётся в _log_to_db."""
        sender = self._make_sender()
        sent_msgs = []
        def capture_send(email_to, msg):
            sent_msgs.append(msg)
        log_calls = []
        def capture_log(session, company_id, email_to, subject, template_name,
                         tracking_id, error="", rendered_body="", campaign_id=None, ab_variant=None):
            log_calls.append({"rendered_body": rendered_body, "template_name": template_name})
        # Создаём mock db_session, чтобы sender.send() вызывал _log_to_db
        mock_db = MagicMock()
        with patch.object(sender, '_smtp_send', side_effect=capture_send):
            with patch.object(sender, '_log_to_db', side_effect=capture_log):
                sender.send(
                    company_id=1,
                    email_to="test@example.com",
                    subject="Test",
                    body_text="Hello Moscow",
                    template_name="cold_email_v1",
                    rendered_body="Hello Moscow",
                    db_session=mock_db,
                )
        assert len(log_calls) == 1
        assert log_calls[0]["rendered_body"] == "Hello Moscow"
        assert log_calls[0]["template_name"] == "cold_email_v1"


# ============================================================
# API-тесты: GET /templates из TemplateRegistry
# ============================================================

class TestTemplatesApiFromRegistry:
    """Тесты API /templates — чтение из TemplateRegistry (JSON)."""

    def test_list_templates_includes_body_type(self, client):
        """GET /templates → каждый item содержит body_type."""
        resp = client.get("/api/v1/templates")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data.get("items", []):
            assert "body_type" in item
            assert item["body_type"] in ("plain", "html")
            assert "name" in item
            assert "channel" in item

    def test_get_template_includes_body_type(self, client):
        """GET /templates/{name} → содержит body_type."""
        resp = client.get("/api/v1/templates/cold_email_v1")
        assert resp.status_code == 200
        data = resp.json()
        assert "body_type" in data
        assert data["body_type"] in ("plain", "html")

    def test_get_template_not_found(self, client):
        """GET /templates/{name} → 404 для несуществующего шаблона."""
        resp = client.get("/api/v1/templates/nonexistent_template")
        assert resp.status_code == 404

    def test_list_filter_by_channel(self, client):
        """GET /templates?channel=email → только email-шаблоны."""
        resp = client.get("/api/v1/templates?channel=email")
        assert resp.status_code == 200
        data = resp.json()
        for item in data.get("items", []):
            assert item["channel"] == "email"

    def test_reload_templates(self, client):
        """POST /templates/reload → 200, OkResponse."""
        resp = client.post("/api/v1/templates/reload")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert "Reloaded" in data.get("message", "")

    def test_post_templates_not_found(self, client):
        """POST /templates → 405 (CUD удалены)."""
        resp = client.post("/api/v1/templates", json={
            "name": "test_plain",
            "channel": "email",
            "body": "Hello {city}",
            "body_type": "plain",
        })
        # POST /templates больше не существует, только POST /templates/reload
        assert resp.status_code in (404, 405)

    def test_put_templates_not_found(self, client):
        """PUT /templates/{name} → 405 (CUD удалены)."""
        resp = client.put("/api/v1/templates/cold_email_v1", json={
            "body_type": "html",
            "body": "<html><body>HTML body</body></html>",
        })
        assert resp.status_code in (404, 405)


# ============================================================
# API-тесты: Campaigns — валидация channel=email
# ============================================================

class TestCampaignsChannelValidation:
    """Тесты валидации channel=email при создании кампании."""

    def test_campaign_rejects_non_email_template(self, client, db_session):
        """POST /campaigns с template channel='tg' → 400."""
        resp = client.post("/api/v1/campaigns", json={
            "name": "Bad Campaign",
            "template_name": "tg_intro",
        })
        assert resp.status_code == 400

    def test_campaign_accepts_email_template(self, client, db_session):
        """POST /campaigns с template channel='email' → 201."""
        resp = client.post("/api/v1/campaigns", json={
            "name": "Good Campaign",
            "template_name": "cold_email_v1",
        })
        assert resp.status_code == 201

    def test_campaign_rejects_unknown_template(self, client, db_session):
        """POST /campaigns с неизвестным template_name → 404."""
        resp = client.post("/api/v1/campaigns", json={
            "name": "Bad Campaign",
            "template_name": "nonexistent_template",
        })
        assert resp.status_code == 404


# ============================================================
# rendered_body в crm_email_logs
# ============================================================

class TestRenderedBodyInLogs:
    """Тесты что rendered_body корректно пишется в crm_email_logs."""

    def test_rendered_body_stored_in_db(self, db_session):
        """При логировании отправки rendered_body сохраняется в БД."""
        from granite.database import CrmEmailLogRow, CompanyRow
        company = CompanyRow(
            name_best="Test Co",
            city="Москва",
            emails=["test@example.com"],
            website="https://test.ru",
            sources=["test"],
        )
        db_session.add(company)
        db_session.flush()

        test_body = "Здравствуйте. Ищу контакты мастерских в Москве и области."
        log = CrmEmailLogRow(
            company_id=company.id,
            email_to="test@example.com",
            email_subject="Test Subject",
            template_name="cold_email_v1",
            tracking_id="test-track-123",
            status="sent",
            sent_at=datetime.now(timezone.utc),
            rendered_body=test_body,
        )
        db_session.add(log)
        db_session.flush()

        saved = db_session.get(CrmEmailLogRow, log.id)
        assert saved.rendered_body is not None
        assert saved.rendered_body == test_body
