"""Тесты для granite/email/process_bounces.py — обработка bounce-уведомлений."""
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from unittest.mock import patch

from granite.database import (
    CrmContactRow, CrmTaskRow, CrmEmailLogRow, CrmEmailCampaignRow,
)
from granite.email.process_bounces import process_bounces
from tests.helpers import create_company


class TestBounceParser:
    """Обработка bounce-уведомлений из IMAP."""

    def test_bounce_511_user_unknown(self, db_session):
        """DSN 5.1.1 → статус bounced, funnel unreachable"""
        company_id = create_company(db_session, funnel_stage="email_sent")
        contact = db_session.query(CrmContactRow).filter_by(company_id=company_id).one()

        campaign = CrmEmailCampaignRow(
            name="test", template_name="cold_email_1", status="running"
        )
        db_session.add(campaign)
        db_session.flush()

        log = CrmEmailLogRow(
            company_id=company_id, email_to="bad@example.com",
            email_subject="Test", template_name="cold_email_1",
            campaign_id=campaign.id, tracking_id="bounce511test",
            status="sent", sent_at=datetime.now(timezone.utc),
        )
        db_session.add(log)
        db_session.commit()

        mock_imap_messages = _make_bounce_messages("bad@example.com", "5.1.1", "User unknown")

        with patch("granite.email.process_bounces.fetch_imap_messages",
                    return_value=mock_imap_messages):
            process_bounces(db_session)

        db_session.refresh(log)
        assert log.status == "bounced"
        assert log.bounced_at is not None

        db_session.refresh(contact)
        assert contact.funnel_stage == "unreachable"

    def test_bounce_522_mailbox_full(self, db_session):
        """DSN 5.2.2 → статус bounced, funnel НЕ меняется (soft bounce)"""
        company_id = create_company(db_session, funnel_stage="email_sent")
        contact = db_session.query(CrmContactRow).filter_by(company_id=company_id).one()

        campaign = CrmEmailCampaignRow(
            name="test", template_name="cold_email_1", status="running"
        )
        db_session.add(campaign)
        db_session.flush()

        log = CrmEmailLogRow(
            company_id=company_id, email_to="full@example.com",
            email_subject="Test", template_name="cold_email_1",
            campaign_id=campaign.id, tracking_id="bounce522test",
            status="sent", sent_at=datetime.now(timezone.utc),
        )
        db_session.add(log)
        db_session.commit()

        mock_imap_messages = _make_bounce_messages("full@example.com", "5.2.2", "Mailbox full")

        with patch("granite.email.process_bounces.fetch_imap_messages",
                    return_value=mock_imap_messages):
            process_bounces(db_session)

        db_session.refresh(log)
        assert log.status == "bounced"

        db_session.refresh(contact)
        assert contact.funnel_stage == "email_sent"  # НЕ меняется

    def test_bounce_571_blocked(self, db_session):
        """DSN 5.7.1 → stop_automation=1"""
        company_id = create_company(db_session, funnel_stage="email_sent")
        contact = db_session.query(CrmContactRow).filter_by(company_id=company_id).one()

        campaign = CrmEmailCampaignRow(
            name="test", template_name="cold_email_1", status="running"
        )
        db_session.add(campaign)
        db_session.flush()

        log = CrmEmailLogRow(
            company_id=company_id, email_to="blocked@example.com",
            email_subject="Test", template_name="cold_email_1",
            campaign_id=campaign.id, tracking_id="bounce571test",
            status="sent", sent_at=datetime.now(timezone.utc),
        )
        db_session.add(log)
        db_session.commit()

        mock_imap_messages = _make_bounce_messages("blocked@example.com", "5.7.1", "Delivery not authorized")

        with patch("granite.email.process_bounces.fetch_imap_messages",
                    return_value=mock_imap_messages):
            process_bounces(db_session)

        db_session.refresh(contact)
        assert contact.stop_automation == 1

    def test_bounce_imap_connection_error(self, db_session):
        """IMAP недоступен → graceful, не крашится"""
        with patch("granite.email.process_bounces.fetch_imap_messages",
                    side_effect=Exception("IMAP connection refused")):
            process_bounces(db_session)

    def test_bounce_x_failed_recipients_fallback(self, db_session):
        """Bounce без Final-Recipient в DSN → X-Failed-Recipients заголовок"""
        company_id = create_company(db_session, funnel_stage="email_sent")
        contact = db_session.query(CrmContactRow).filter_by(company_id=company_id).one()

        campaign = CrmEmailCampaignRow(
            name="test", template_name="cold_email_1", status="running"
        )
        db_session.add(campaign)
        db_session.flush()

        log = CrmEmailLogRow(
            company_id=company_id, email_to="xfail@example.com",
            email_subject="Test", template_name="cold_email_1",
            campaign_id=campaign.id, tracking_id="xfailtest1",
            status="sent", sent_at=datetime.now(timezone.utc),
        )
        db_session.add(log)
        db_session.commit()

        # Bounce-письмо без Final-Recipient, но с X-Failed-Recipients
        msg = MIMEMultipart("report")
        msg["From"] = "mailer-daemon@example.com"
        msg["Subject"] = "Delivery Status Notification (Failure)"
        msg["X-Failed-Recipients"] = "xfail@example.com"
        msg.attach(MIMEText("Bounce notification", "plain"))
        msg.attach(MIMEText("Diagnostic-Code: smtp; 5.1.1 User unknown\n", "plain"))

        with patch("granite.email.process_bounces.fetch_imap_messages",
                    return_value=[(b"1", msg)]):
            process_bounces(db_session)

        db_session.refresh(log)
        assert log.status == "bounced"

        db_session.refresh(contact)
        assert contact.funnel_stage == "unreachable"

    def test_integration_bounce_sets_unreachable(self, db_session):
        """Отправка → bounce → проверка unreachable"""
        company_id = create_company(db_session, funnel_stage="email_sent")
        contact = db_session.query(CrmContactRow).filter_by(company_id=company_id).one()

        campaign = CrmEmailCampaignRow(
            name="integration_bounce", template_name="cold_email_1",
            status="completed", total_sent=1,
        )
        db_session.add(campaign)
        db_session.flush()

        log = CrmEmailLogRow(
            company_id=company_id, email_to="dead@example.com",
            email_subject="Test", template_name="cold_email_1",
            campaign_id=campaign.id, tracking_id="intbounce1",
            status="sent", sent_at=datetime.now(timezone.utc),
        )
        db_session.add(log)
        db_session.commit()

        dsn_body = (
            "Reporting-MTA: dns; mail.example.com\n"
            "Final-Recipient: rfc822; dead@example.com\n"
            "Diagnostic-Code: smtp; 5.1.1 User unknown\n"
        )
        bounce_msg = MIMEMultipart("report")
        bounce_msg["From"] = "mailer-daemon@example.com"
        bounce_msg["Subject"] = "Delivery Status Notification (Failure)"
        bounce_msg.attach(MIMEText(dsn_body, "plain"))

        with patch("granite.email.process_bounces.fetch_imap_messages",
                    return_value=[(b"1", bounce_msg)]):
            process_bounces(db_session)

        db_session.refresh(contact)
        assert contact.funnel_stage == "unreachable"


# ── Helpers ──

def _make_bounce_messages(bounced_email, dsn_code, dsn_message):
    """Создать мок IMAP-сообщений с bounce."""
    dsn_body = (
        f"Reporting-MTA: dns; mail.example.com\n"
        f"Final-Recipient: rfc822; {bounced_email}\n"
        f"Diagnostic-Code: smtp; {dsn_code} {dsn_message}\n"
    )

    msg = MIMEMultipart("report")
    msg["From"] = "mailer-daemon@example.com"
    msg["To"] = "ai.punk.facility@gmail.com"
    msg["Subject"] = "Delivery Status Notification (Failure)"
    msg.attach(MIMEText("This is a bounce notification", "plain"))
    msg.attach(MIMEText(dsn_body, "plain"))

    return [(b"1", msg)]
