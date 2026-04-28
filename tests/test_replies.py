"""Тесты для granite/email/process_replies.py — обработка ответов из IMAP."""
from datetime import datetime, timedelta, timezone
from email.mime.text import MIMEText
from unittest.mock import patch

from granite.database import (
    CrmContactRow, CrmTaskRow, CrmTouchRow,
    CrmEmailLogRow, CrmEmailCampaignRow,
)
from granite.email.process_replies import process_replies
from tests.helpers import create_company, create_task


class TestReplyParser:
    """Обработка ответов из IMAP."""

    def test_reply_detected(self, db_session):
        """Мок IMAP с ответом → funnel_stage='replied'"""
        company_id = create_company(db_session, funnel_stage="email_sent")
        contact = db_session.query(CrmContactRow).filter_by(company_id=company_id).one()

        campaign = CrmEmailCampaignRow(
            name="test", template_name="cold_email_1", status="running"
        )
        db_session.add(campaign)
        db_session.flush()

        log = CrmEmailLogRow(
            company_id=company_id, email_to="info@test.ru",
            email_subject="Ретушь под памятник",
            template_name="cold_email_1",
            campaign_id=campaign.id, tracking_id="replytest1",
            status="sent", sent_at=datetime.now(timezone.utc),
        )
        db_session.add(log)
        db_session.commit()

        mock_messages = _make_reply_messages(
            "info@test.ru", "Re: Ретушь под памятник", "Интересно, давайте обсудим"
        )

        with patch("granite.email.process_replies.fetch_imap_messages",
                    return_value=mock_messages):
            process_replies(db_session)

        db_session.refresh(contact)
        assert contact.funnel_stage == "replied"

    def test_reply_cancels_followup(self, db_session):
        """Ответ → pending follow-up = cancelled"""
        company_id = create_company(db_session, funnel_stage="email_sent")

        create_task(db_session, company_id, task_type="follow_up", status="pending")

        campaign = CrmEmailCampaignRow(
            name="test", template_name="cold_email_1", status="running"
        )
        db_session.add(campaign)
        db_session.flush()

        log = CrmEmailLogRow(
            company_id=company_id, email_to="info@test.ru",
            email_subject="Test", template_name="cold_email_1",
            campaign_id=campaign.id, tracking_id="replytest2",
            status="sent", sent_at=datetime.now(timezone.utc),
        )
        db_session.add(log)
        db_session.commit()

        mock_messages = _make_reply_messages(
            "info@test.ru", "Re: Test", "Хочу узнать подробнее"
        )

        with patch("granite.email.process_replies.fetch_imap_messages",
                    return_value=mock_messages):
            process_replies(db_session)

        tasks = db_session.query(CrmTaskRow).filter_by(
            company_id=company_id, task_type="follow_up"
        ).all()
        assert all(t.status == "cancelled" for t in tasks)

    def test_reply_increments_total_replied(self, db_session):
        """Ответ → campaign.total_replied+1"""
        company_id = create_company(db_session, funnel_stage="email_sent")

        campaign = CrmEmailCampaignRow(
            name="test", template_name="cold_email_1",
            status="running", total_replied=0,
        )
        db_session.add(campaign)
        db_session.flush()

        log = CrmEmailLogRow(
            company_id=company_id, email_to="info@test.ru",
            email_subject="Test", template_name="cold_email_1",
            campaign_id=campaign.id, tracking_id="replytest3",
            status="sent", sent_at=datetime.now(timezone.utc),
        )
        db_session.add(log)
        db_session.commit()

        mock_messages = _make_reply_messages(
            "info@test.ru", "Re: Test", "Да, интересно"
        )

        with patch("granite.email.process_replies.fetch_imap_messages",
                    return_value=mock_messages):
            process_replies(db_session)

        db_session.refresh(campaign)
        assert campaign.total_replied == 1

    def test_reply_touch_body_unified(self, db_session):
        """CrmTouchRow.body= заполнен текстом ответа"""
        company_id = create_company(db_session, funnel_stage="email_sent")

        campaign = CrmEmailCampaignRow(
            name="test", template_name="cold_email_1", status="running"
        )
        db_session.add(campaign)
        db_session.flush()

        log = CrmEmailLogRow(
            company_id=company_id, email_to="info@test.ru",
            email_subject="Test", template_name="cold_email_1",
            campaign_id=campaign.id, tracking_id="replytest4",
            status="sent", sent_at=datetime.now(timezone.utc),
        )
        db_session.add(log)
        db_session.commit()

        reply_body = "Да, нам нужна ретушь, пришлите примеры"
        mock_messages = _make_reply_messages(
            "info@test.ru", "Re: Test", reply_body
        )

        with patch("granite.email.process_replies.fetch_imap_messages",
                    return_value=mock_messages):
            process_replies(db_session)

        touches = db_session.query(CrmTouchRow).filter_by(
            company_id=company_id, direction="incoming"
        ).all()
        assert len(touches) >= 1
        assert reply_body in touches[-1].body

    def test_ooo_ignored(self, db_session):
        """Автоответчик → без изменений (не replied)"""
        company_id = create_company(db_session, funnel_stage="email_sent")
        contact = db_session.query(CrmContactRow).filter_by(company_id=company_id).one()

        campaign = CrmEmailCampaignRow(
            name="test", template_name="cold_email_1", status="running"
        )
        db_session.add(campaign)
        db_session.flush()

        log = CrmEmailLogRow(
            company_id=company_id, email_to="info@test.ru",
            email_subject="Test", template_name="cold_email_1",
            campaign_id=campaign.id, tracking_id="ooorest1",
            status="sent", sent_at=datetime.now(timezone.utc),
        )
        db_session.add(log)
        db_session.commit()

        mock_messages = _make_reply_messages(
            "info@test.ru", "Автоответ: я в отпуске", "Буду после 15 мая"
        )

        with patch("granite.email.process_replies.fetch_imap_messages",
                    return_value=mock_messages):
            process_replies(db_session)

        db_session.refresh(contact)
        assert contact.funnel_stage == "email_sent"

    def test_spam_complaint(self, db_session):
        """'Это спам' → stop_automation=1"""
        company_id = create_company(db_session, funnel_stage="email_sent")
        contact = db_session.query(CrmContactRow).filter_by(company_id=company_id).one()

        campaign = CrmEmailCampaignRow(
            name="test", template_name="cold_email_1", status="running"
        )
        db_session.add(campaign)
        db_session.flush()

        log = CrmEmailLogRow(
            company_id=company_id, email_to="info@test.ru",
            email_subject="Test", template_name="cold_email_1",
            campaign_id=campaign.id, tracking_id="spamtest1",
            status="sent", sent_at=datetime.now(timezone.utc),
        )
        db_session.add(log)
        db_session.commit()

        mock_messages = _make_reply_messages(
            "info@test.ru", "Re: Test", "Это спам, не пишите больше"
        )

        with patch("granite.email.process_replies.fetch_imap_messages",
                    return_value=mock_messages):
            process_replies(db_session)

        db_session.refresh(contact)
        assert contact.stop_automation == 1

    def test_spam_complaint_cancels_followup(self, db_session):
        """Спам-жалоба → pending follow-up = cancelled"""
        company_id = create_company(db_session, funnel_stage="email_sent")

        create_task(db_session, company_id, task_type="follow_up", status="pending")

        campaign = CrmEmailCampaignRow(
            name="test", template_name="cold_email_1", status="running"
        )
        db_session.add(campaign)
        db_session.flush()

        log = CrmEmailLogRow(
            company_id=company_id, email_to="info@test.ru",
            email_subject="Test", template_name="cold_email_1",
            campaign_id=campaign.id, tracking_id="spamcancel1",
            status="sent", sent_at=datetime.now(timezone.utc),
        )
        db_session.add(log)
        db_session.commit()

        mock_messages = _make_reply_messages(
            "info@test.ru", "Re: Test", "Это спам, отпишитесь"
        )

        with patch("granite.email.process_replies.fetch_imap_messages",
                    return_value=mock_messages):
            process_replies(db_session)

        tasks = db_session.query(CrmTaskRow).filter_by(
            company_id=company_id, task_type="follow_up"
        ).all()
        assert all(t.status == "cancelled" for t in tasks)

    def test_integration_reply_sets_replied_and_cancels_followup(self, db_session):
        """Отправка → ответ → replied + follow-up отменён"""
        company_id = create_company(db_session, funnel_stage="email_opened")
        contact = db_session.query(CrmContactRow).filter_by(company_id=company_id).one()

        create_task(db_session, company_id, task_type="follow_up", status="pending",
                    due_date=datetime.now(timezone.utc) + timedelta(days=5))

        campaign = CrmEmailCampaignRow(
            name="integration_reply", template_name="cold_email_1",
            status="completed", total_sent=1, total_replied=0,
        )
        db_session.add(campaign)
        db_session.flush()

        log = CrmEmailLogRow(
            company_id=company_id, email_to="info@test.ru",
            email_subject="Ретушь под памятник",
            template_name="cold_email_1",
            campaign_id=campaign.id, tracking_id="intreply1",
            status="sent", sent_at=datetime.now(timezone.utc),
        )
        db_session.add(log)
        db_session.commit()

        reply_msg = MIMEText("Да, нам интересна ретушь", "plain", "utf-8")
        reply_msg["From"] = "info@test.ru"
        reply_msg["Subject"] = "Re: Ретушь под памятник"

        with patch("granite.email.process_replies.fetch_imap_messages",
                    return_value=[(b"1", reply_msg)]):
            process_replies(db_session)

        db_session.refresh(contact)
        assert contact.funnel_stage == "replied"

        tasks = db_session.query(CrmTaskRow).filter_by(
            company_id=company_id, task_type="follow_up"
        ).all()
        assert all(t.status == "cancelled" for t in tasks)

        db_session.refresh(campaign)
        assert campaign.total_replied == 1


# ── Helpers ──

def _make_reply_messages(from_email, subject, body):
    """Создать мок IMAP-сообщений с ответом."""
    msg = MIMEText(body, "plain", "utf-8")
    msg["From"] = f"Отвечающий <{from_email}>"
    msg["To"] = "ai.punk.facility@gmail.com"
    msg["Subject"] = subject

    return [(b"2", msg)]
