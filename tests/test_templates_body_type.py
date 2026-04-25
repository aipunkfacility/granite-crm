"""Тесты для body_type: HTML-шаблоны, валидация, рендер, EmailSender.

TDD: тесты пишутся ДО кода. После реализации все тесты должны проходить.

Покрывает:
- CrmTemplateRow.render() с HTML-escaping
- CrmTemplateRow.render_subject() без экранирования
- html_to_plain_text() утилита
- EmailSender.send() с body_html
- API CRUD шаблонов с body_type
- Валидация HTML только для email
- Campaigns: channel=email при создании
"""
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone


# ============================================================
# Unit-тесты: CrmTemplateRow.render() и render_subject()
# ============================================================

class TestCrmTemplateRowRender:
    """Тесты метода render() модели CrmTemplateRow."""

    def _make_template(self, body_type="plain", body="Hello {city}!", name="test_tpl"):
        """Создать CrmTemplateRow без БД через конструктор."""
        from granite.database import CrmTemplateRow
        t = CrmTemplateRow(
            name=name,
            channel="email",
            subject="Offer for {company_name}",
            body=body,
            body_type=body_type,
        )
        return t

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
        assert "A & B <Co>" in result  # Без экранирования (subject = "Offer for {company_name}")
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
        # Не должно быть 2+ пустых строк подряд
        consecutive_blank = 0
        for line in lines:
            if not line.strip():
                consecutive_blank += 1
            else:
                consecutive_blank = 0
            assert consecutive_blank == 0, f"Found {consecutive_blank} consecutive blank lines"


# ============================================================
# Unit-тесты: EmailSender с body_html
# ============================================================

class TestEmailSenderHtml:
    """Тесты EmailSender с поддержкой HTML."""

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
        # Пройти по MIME-частям и найти HTML
        for part in msg.walk():
            ct = part.get_content_type()
            if ct == "text/html":
                return part.get_payload(decode=True).decode("utf-8")
        return ""  # HTML не найден

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
        # Pixel должен быть ПЕРЕД </body>
        pixel_pos = html_part.find('width="1"')
        body_close_pos = html_part.rfind("</body>")
        assert pixel_pos > 0
        assert body_close_pos > 0
        assert pixel_pos < body_close_pos

    def test_html_no_body_tag_pixel_appended(self):
        """Без </body>: tracking pixel добавляется в конец."""
        sender = self._make_sender()
        html_part = self._get_sent_msg_html(
            sender,
            company_id=1,
            email_to="test@example.com",
            subject="Test",
            body_text="Content",
            body_html="<html><p>Content without body tag</p></html>",
        )
        # Pixel должен быть в конце HTML
        assert 'width="1"' in html_part

    def test_plain_tracking_pixel_in_pre(self):
        """Plain text: tracking pixel после <pre>."""
        sender = self._make_sender()
        html_part = self._get_sent_msg_html(
            sender,
            company_id=1,
            email_to="test@example.com",
            subject="Test",
            body_text="Hello",
        )
        assert "<pre" in html_part
        assert 'width="1"' in html_part


# ============================================================
# API-тесты: CRUD шаблонов с body_type
# ============================================================

class TestTemplatesApiBodyType:
    """Тесты API /templates с полем body_type."""

    def test_create_plain_template(self, client, db_session):
        """POST /templates с body_type=plain → 201, в БД body_type='plain'."""
        from granite.database import CrmTemplateRow
        resp = client.post("/api/v1/templates", json={
            "name": "test_plain",
            "channel": "email",
            "subject": "Test",
            "body": "Hello {city}",
            "body_type": "plain",
        })
        assert resp.status_code == 201
        t = db_session.query(CrmTemplateRow).filter_by(name="test_plain").first()
        assert t is not None
        assert t.body_type == "plain"

    def test_create_html_template(self, client, db_session):
        """POST /templates с body_type=html → 201, в БД body_type='html'."""
        from granite.database import CrmTemplateRow
        resp = client.post("/api/v1/templates", json={
            "name": "test_html",
            "channel": "email",
            "subject": "HTML Test",
            "body": "<html><body><p>Hello</p></body></html>",
            "body_type": "html",
        })
        assert resp.status_code == 201
        t = db_session.query(CrmTemplateRow).filter_by(name="test_html").first()
        assert t is not None
        assert t.body_type == "html"

    def test_create_template_default_plain(self, client, db_session):
        """POST /templates без body_type → body_type='plain' по умолчанию."""
        from granite.database import CrmTemplateRow
        resp = client.post("/api/v1/templates", json={
            "name": "test_default",
            "channel": "email",
            "subject": "Default",
            "body": "Hello",
        })
        assert resp.status_code == 201
        t = db_session.query(CrmTemplateRow).filter_by(name="test_default").first()
        assert t is not None
        assert t.body_type == "plain"

    def test_create_html_template_non_email_rejected(self, client, db_session):
        """POST /templates с body_type=html + channel='tg' → 422."""
        resp = client.post("/api/v1/templates", json={
            "name": "test_tg_html",
            "channel": "tg",
            "subject": "",
            "body": "<p>Hello</p>",
            "body_type": "html",
        })
        assert resp.status_code == 422

    def test_create_html_template_wa_rejected(self, client, db_session):
        """POST /templates с body_type=html + channel='wa' → 422."""
        resp = client.post("/api/v1/templates", json={
            "name": "test_wa_html",
            "channel": "wa",
            "subject": "",
            "body": "<p>Hello</p>",
            "body_type": "html",
        })
        assert resp.status_code == 422

    def test_update_body_type(self, client, db_session):
        """PUT /templates/{name} с body_type=html → обновляется."""
        from granite.database import CrmTemplateRow
        resp = client.put("/api/v1/templates/cold_email_1", json={
            "body_type": "html",
            "body": "<html><body>HTML body</body></html>",
        })
        assert resp.status_code == 200
        db_session.expire_all()
        t = db_session.query(CrmTemplateRow).filter_by(name="cold_email_1").first()
        assert t.body_type == "html"

    def test_update_body_type_channel_conflict(self, client, db_session):
        """PUT: body_type=html + channel='tg' → 400."""
        # Сначала создаём шаблон email/html
        client.post("/api/v1/templates", json={
            "name": "test_conflict",
            "channel": "email",
            "subject": "Conflict",
            "body": "<p>Hello</p>",
            "body_type": "html",
        })
        # Пытаемся переключить на tg
        resp = client.put("/api/v1/templates/test_conflict", json={
            "channel": "tg",
        })
        assert resp.status_code == 400

    def test_list_templates_includes_body_type(self, client):
        """GET /templates → каждый item содержит body_type."""
        resp = client.get("/api/v1/templates")
        assert resp.status_code == 200
        data = resp.json()
        for item in data.get("items", []):
            assert "body_type" in item
            assert item["body_type"] in ("plain", "html")

    def test_get_template_includes_body_type(self, client):
        """GET /templates/{name} → содержит body_type."""
        resp = client.get("/api/v1/templates/cold_email_1")
        assert resp.status_code == 200
        data = resp.json()
        assert "body_type" in data
        assert data["body_type"] in ("plain", "html")

    def test_body_max_length_validation(self, client):
        """POST /templates с body > 500000 символов → 422."""
        resp = client.post("/api/v1/templates", json={
            "name": "test_too_long",
            "channel": "email",
            "subject": "Big",
            "body": "x" * 500_001,
            "body_type": "plain",
        })
        assert resp.status_code == 422

    def test_body_type_invalid_value(self, client):
        """POST /templates с body_type='markdown' → 422."""
        resp = client.post("/api/v1/templates", json={
            "name": "test_invalid_type",
            "channel": "email",
            "subject": "Invalid",
            "body": "Hello",
            "body_type": "markdown",
        })
        assert resp.status_code == 422


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
            "template_name": "cold_email_1",
        })
        assert resp.status_code == 201
