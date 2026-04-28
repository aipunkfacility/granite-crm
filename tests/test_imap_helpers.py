"""Тесты для granite/email/imap_helpers.py — IMAP-хелперы для bounce/reply."""
from email.message import Message
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from granite.email.imap_helpers import (
    extract_email,
    extract_body,
    is_bounce,
    is_ooo,
    extract_bounced_email,
    extract_dsn,
)


class TestExtractEmail:
    """Извлечение email из заголовка From."""

    def test_brackets(self):
        """'Иван <ivan@mail.ru>' → 'ivan@mail.ru'"""
        assert extract_email("Иван <ivan@mail.ru>") == "ivan@mail.ru"

    def test_plain(self):
        """'ivan@mail.ru' → 'ivan@mail.ru'"""
        assert extract_email("ivan@mail.ru") == "ivan@mail.ru"

    def test_empty(self):
        """Пустая строка → None"""
        assert extract_email("") is None


class TestExtractBody:
    """Извлечение text/plain части из email.message.Message."""

    def test_plain(self):
        """text/plain часть извлечена из простого письма"""
        msg = MIMEText("Текст ответа", "plain", "utf-8")
        assert extract_body(msg) == "Текст ответа"

    def test_multipart(self):
        """Из multipart-письма извлекается text/plain часть"""
        msg = MIMEMultipart("alternative")
        msg.attach(MIMEText("Письмо текст", "plain", "utf-8"))
        msg.attach(MIMEText("<p>Письмо html</p>", "html", "utf-8"))
        assert extract_body(msg) == "Письмо текст"


class TestIsBounce:
    """Определение bounce (Delivery Status Notification)."""

    def test_dsn(self):
        """DSN multipart/report → True"""
        msg = MIMEMultipart("report")
        msg["Content-Type"] = 'multipart/report; report-type=delivery-status'
        msg["From"] = "mailer-daemon@example.com"
        msg["Subject"] = "Delivery Status Notification (Failure)"
        msg.attach(MIMEText("Bounce notification", "plain"))
        assert is_bounce(msg) is True

    def test_normal(self):
        """Обычное письмо → False"""
        msg = Message()
        msg.set_type("text/plain")
        msg.set_payload("Здравствуйте, спасибо за письмо")
        assert is_bounce(msg) is False


class TestIsOoo:
    """Определение автоответчика (Out of Office)."""

    def test_russian(self):
        """'Автоответ' в Subject → True"""
        msg = Message()
        msg["Subject"] = "Автоответ: нет на месте"
        msg.set_payload("Я в отпуске")
        assert is_ooo(msg) is True

    def test_english(self):
        """'Out of Office' в Subject → True"""
        msg = Message()
        msg["Subject"] = "Out of Office: on vacation"
        msg.set_payload("I am on vacation")
        assert is_ooo(msg) is True

    def test_normal(self):
        """Обычное письмо → False"""
        msg = Message()
        msg["Subject"] = "Re: Ретушь портретов"
        msg.set_payload("Интересно, давайте обсудим")
        assert is_ooo(msg) is False

    def test_auto_submitted_header(self):
        """Auto-Submitted: auto-replied → True (RFC 3834)"""
        msg = Message()
        msg["Subject"] = "Re: Ваше предложение"
        msg["Auto-Submitted"] = "auto-replied"
        msg.set_payload("Я в отпуске до 15 мая")
        assert is_ooo(msg) is True


class TestExtractBouncedEmail:
    """Извлечение Final-Recipient из DSN-текста."""

    def test_found(self):
        """Final-Recipient извлечён из DSN"""
        dsn_text = (
            "Reporting-MTA: dns; mail.ru\n"
            "Final-Recipient: rfc822; user_unknown@example.com\n"
            "Diagnostic-Code: smtp; 5.1.1 User unknown\n"
        )
        assert extract_bounced_email(dsn_text) == "user_unknown@example.com"

    def test_not_found(self):
        """Нет Final-Recipient → None"""
        assert extract_bounced_email("Some random text") is None


class TestExtractDsn:
    """Извлечение DSN-кода из delivery-status."""

    def test_found(self):
        """DSN-код извлечён из delivery-status"""
        dsn_text = (
            "Reporting-MTA: dns; mail.ru\n"
            "Diagnostic-Code: smtp; 5.1.1 User unknown\n"
        )
        assert extract_dsn(dsn_text) == "5.1.1"

    def test_not_found(self):
        """Нет Diagnostic-Code → None"""
        assert extract_dsn("No diagnostic here") is None
