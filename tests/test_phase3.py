"""Этап 3: Обратная связь — follow-up, bounce, reply, IMAP helpers.

TDD: сначала тесты (красные), потом реализация.
"""
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from granite.database import (
    CompanyRow, EnrichedCompanyRow, CrmContactRow, CrmTaskRow,
    CrmTouchRow, CrmEmailLogRow, CrmEmailCampaignRow, CrmTemplateRow,
)
from tests.helpers import create_company, create_task


# ═══════════════════════════════════════════════════════════
# Задача 19: IMAP helpers
# ═══════════════════════════════════════════════════════════

class TestImapHelpers:
    """Тесты для granite/email/imap_helpers.py"""

    def test_extract_email_brackets(self):
        """'Иван <ivan@mail.ru>' → 'ivan@mail.ru'"""
        from granite.email.imap_helpers import extract_email
        assert extract_email("Иван <ivan@mail.ru>") == "ivan@mail.ru"

    def test_extract_email_plain(self):
        """'ivan@mail.ru' → 'ivan@mail.ru'"""
        from granite.email.imap_helpers import extract_email
        assert extract_email("ivan@mail.ru") == "ivan@mail.ru"

    def test_extract_email_empty(self):
        """Пустая строка → None"""
        from granite.email.imap_helpers import extract_email
        assert extract_email("") is None

    def test_extract_body_plain(self):
        """text/plain часть извлечена из email.message.Message"""
        from granite.email.imap_helpers import extract_body
        from email.mime.text import MIMEText

        msg = MIMEText("Текст ответа", "plain", "utf-8")
        assert extract_body(msg) == "Текст ответа"

    def test_extract_body_multipart(self):
        """Из multipart-письма извлекается text/plain часть"""
        from granite.email.imap_helpers import extract_body
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText

        msg = MIMEMultipart("alternative")
        msg.attach(MIMEText("Письмо текст", "plain", "utf-8"))
        msg.attach(MIMEText("<p>Письмо html</p>", "html", "utf-8"))
        assert extract_body(msg) == "Письмо текст"

    def test_is_bounce_dsn(self):
        """DSN 5.1.1 → True (bounce)"""
        from granite.email.imap_helpers import is_bounce
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText

        msg = MIMEMultipart("report")
        msg["Content-Type"] = 'multipart/report; report-type=delivery-status'
        msg["From"] = "mailer-daemon@example.com"
        msg["Subject"] = "Delivery Status Notification (Failure)"
        msg.attach(MIMEText("Bounce notification", "plain"))
        assert is_bounce(msg) is True

    def test_is_bounce_normal(self):
        """Обычное письмо → False (не bounce)"""
        from granite.email.imap_helpers import is_bounce
        from email.message import Message

        msg = Message()
        msg.set_type("text/plain")
        msg.set_payload("Здравствуйте, спасибо за письмо")
        assert is_bounce(msg) is False

    def test_is_ooo_russian(self):
        """'Автоответ' в Subject → True"""
        from granite.email.imap_helpers import is_ooo
        from email.message import Message

        msg = Message()
        msg["Subject"] = "Автоответ: нет на месте"
        msg.set_payload("Я в отпуске")
        assert is_ooo(msg) is True

    def test_is_ooo_english(self):
        """'Out of Office' в Subject → True"""
        from granite.email.imap_helpers import is_ooo
        from email.message import Message

        msg = Message()
        msg["Subject"] = "Out of Office: on vacation"
        msg.set_payload("I am on vacation")
        assert is_ooo(msg) is True

    def test_is_ooo_normal(self):
        """Обычное письмо → False (не автоответ)"""
        from granite.email.imap_helpers import is_ooo
        from email.message import Message

        msg = Message()
        msg["Subject"] = "Re: Ретушь портретов"
        msg.set_payload("Интересно, давайте обсудим")
        assert is_ooo(msg) is False

    def test_extract_bounced_email(self):
        """Final-Recipient извлечён из DSN"""
        from granite.email.imap_helpers import extract_bounced_email

        dsn_text = (
            "Reporting-MTA: dns; mail.ru\n"
            "Final-Recipient: rfc822; user_unknown@example.com\n"
            "Diagnostic-Code: smtp; 5.1.1 User unknown\n"
        )
        assert extract_bounced_email(dsn_text) == "user_unknown@example.com"

    def test_extract_bounced_email_not_found(self):
        """Нет Final-Recipient → None"""
        from granite.email.imap_helpers import extract_bounced_email
        assert extract_bounced_email("Some random text") is None

    def test_extract_dsn(self):
        """DSN-код извлечён из delivery-status"""
        from granite.email.imap_helpers import extract_dsn

        dsn_text = (
            "Reporting-MTA: dns; mail.ru\n"
            "Diagnostic-Code: smtp; 5.1.1 User unknown\n"
        )
        assert extract_dsn(dsn_text) == "5.1.1"

    def test_extract_dsn_not_found(self):
        """Нет Diagnostic-Code → None"""
        from granite.email.imap_helpers import extract_dsn
        assert extract_dsn("No diagnostic here") is None


# ═══════════════════════════════════════════════════════════
# Задача 5: Follow-up создание + отмена + счётчики
# ═══════════════════════════════════════════════════════════

class TestFollowupCreationAndCounters:
    """Тесты для _maybe_create_followup_task() и total_opened++"""

    def test_followup_created_on_open(self, db_session):
        """Tracking pixel → CrmTaskRow(task_type='follow_up', due_date=+7d)"""
        from granite.email.followup_logic import maybe_create_followup_task

        company_id = create_company(db_session, funnel_stage="email_sent")
        contact = db_session.query(CrmContactRow).filter_by(company_id=company_id).one()

        # Создаём кампанию и лог отправленного письма
        campaign = CrmEmailCampaignRow(
            name="test", template_name="cold_email_1", status="running"
        )
        db_session.add(campaign)
        db_session.flush()

        log = CrmEmailLogRow(
            company_id=company_id, email_to="info@test.ru",
            email_subject="Test", template_name="cold_email_1",
            campaign_id=campaign.id, tracking_id="test1234abcd",
            status="sent", sent_at=datetime.now(timezone.utc),
        )
        db_session.add(log)
        db_session.commit()

        # Симулируем открытие — вызываем maybe_create_followup_task
        maybe_create_followup_task(contact, campaign.id, db_session)
        db_session.commit()

        tasks = db_session.query(CrmTaskRow).filter_by(
            company_id=company_id, task_type="follow_up", status="pending"
        ).all()
        assert len(tasks) == 1
        # due_date ~ +7 дней
        assert tasks[0].due_date is not None
        delta = tasks[0].due_date.replace(tzinfo=None) - datetime.now(timezone.utc).replace(tzinfo=None)
        assert 6 <= delta.days <= 8  # ≈7 дней с допуском

    def test_followup_not_created_if_already_exists(self, db_session):
        """Повторный вызов не создаёт дубликат follow-up задачи"""
        from granite.email.followup_logic import maybe_create_followup_task

        company_id = create_company(db_session, funnel_stage="email_sent")
        contact = db_session.query(CrmContactRow).filter_by(company_id=company_id).one()

        campaign = CrmEmailCampaignRow(
            name="test", template_name="cold_email_1", status="running"
        )
        db_session.add(campaign)
        db_session.commit()

        maybe_create_followup_task(contact, campaign.id, db_session)
        db_session.commit()

        maybe_create_followup_task(contact, campaign.id, db_session)
        db_session.commit()

        tasks = db_session.query(CrmTaskRow).filter_by(
            company_id=company_id, task_type="follow_up", status="pending"
        ).all()
        assert len(tasks) == 1  # только одна, не дубликат

    def test_followup_cancelled_on_reply(self, db_session):
        """Ответ → pending follow-up = cancelled"""
        from granite.api.helpers import cancel_followup_tasks

        company_id = create_company(db_session, funnel_stage="email_sent")
        create_task(db_session, company_id, task_type="follow_up", status="pending")
        db_session.commit()

        cancel_followup_tasks(company_id, "replied", db_session)
        db_session.commit()

        tasks = db_session.query(CrmTaskRow).filter_by(
            company_id=company_id, task_type="follow_up"
        ).all()
        assert all(t.status == "cancelled" for t in tasks)

    def test_followup_cancelled_on_unsubscribe(self, db_session):
        """Отписка → pending follow-up = cancelled"""
        from granite.api.helpers import cancel_followup_tasks

        company_id = create_company(db_session, funnel_stage="email_sent")
        create_task(db_session, company_id, task_type="follow_up", status="pending")
        db_session.commit()

        cancel_followup_tasks(company_id, "not_interested", db_session)
        db_session.commit()

        tasks = db_session.query(CrmTaskRow).filter_by(
            company_id=company_id, task_type="follow_up"
        ).all()
        assert all(t.status == "cancelled" for t in tasks)

    def test_total_opened_increment(self, db_session):
        """Tracking pixel → campaign.total_opened+1"""
        from granite.email.followup_logic import increment_campaign_opened

        company_id = create_company(db_session, funnel_stage="email_sent")

        campaign = CrmEmailCampaignRow(
            name="test", template_name="cold_email_1",
            status="running", total_opened=0,
        )
        db_session.add(campaign)
        db_session.flush()

        log = CrmEmailLogRow(
            company_id=company_id, email_to="info@test.ru",
            email_subject="Test", template_name="cold_email_1",
            campaign_id=campaign.id, tracking_id="test1234abcd",
            status="sent", sent_at=datetime.now(timezone.utc),
        )
        db_session.add(log)
        db_session.commit()

        increment_campaign_opened(campaign.id, db_session)
        db_session.commit()

        db_session.refresh(campaign)
        assert campaign.total_opened == 1


# ═══════════════════════════════════════════════════════════
# Задача 11: Follow-up executor
# ═══════════════════════════════════════════════════════════

class TestFollowupExecutor:
    """Тесты для granite/email/process_followups.py"""

    def test_followup_sent_when_due(self, db_session):
        """Задача с due_date < now → письмо отправлено, статус done"""
        from granite.email.process_followups import process_followups

        company_id = create_company(db_session, funnel_stage="email_opened",
                                     emails=["test@example.com"])

        # Создаём шаблон follow_up_email_v1
        tpl = CrmTemplateRow(
            name="follow_up_email_v1", channel="email",
            subject="Re: {{original_subject}}",
            body="Добрый день. Писал на прошлой неделе.",
        )
        db_session.add(tpl)

        # Создаём созревшую follow-up задачу (due_date в прошлом)
        task = CrmTaskRow(
            company_id=company_id,
            title="Follow-up email",
            task_type="follow_up",
            status="pending",
            due_date=datetime.now(timezone.utc) - timedelta(hours=1),
        )
        db_session.add(task)

        # Создаём исходный touch (для извлечения темы)
        touch = CrmTouchRow(
            company_id=company_id, channel="email", direction="outgoing",
            subject="Подготовка фото под гравировку",
        )
        db_session.add(touch)
        db_session.commit()

        # Мокаем EmailSender
        with patch("granite.email.process_followups.EmailSender") as MockSender:
            mock_instance = MockSender.return_value
            mock_instance.send.return_value = "trackid123"
            mock_instance.base_url = "http://localhost:8000"

            process_followups(db_session)

        # Задача выполнена
        db_session.refresh(task)
        assert task.status == "done"
        assert task.completed_at is not None

        # EmailSender.send вызван
        mock_instance.send.assert_called_once()

    def test_followup_not_sent_when_future(self, db_session):
        """Задача с due_date > now → ничего не делаем"""
        from granite.email.process_followups import process_followups

        company_id = create_company(db_session, funnel_stage="email_opened")

        # Задача ещё не созрела
        task = CrmTaskRow(
            company_id=company_id,
            title="Follow-up email",
            task_type="follow_up",
            status="pending",
            due_date=datetime.now(timezone.utc) + timedelta(days=3),
        )
        db_session.add(task)
        db_session.commit()

        with patch("granite.email.process_followups.EmailSender"):
            process_followups(db_session)

        db_session.refresh(task)
        assert task.status == "pending"  # не меняется

    def test_followup_not_sent_when_cancelled(self, db_session):
        """Статус cancelled → ничего не делаем"""
        from granite.email.process_followups import process_followups

        company_id = create_company(db_session, funnel_stage="email_opened")

        task = CrmTaskRow(
            company_id=company_id,
            title="Follow-up email",
            task_type="follow_up",
            status="cancelled",
            due_date=datetime.now(timezone.utc) - timedelta(hours=1),
        )
        db_session.add(task)
        db_session.commit()

        with patch("granite.email.process_followups.EmailSender"):
            process_followups(db_session)

        db_session.refresh(task)
        assert task.status == "cancelled"  # не меняется

    def test_followup_uses_reply_subject(self, db_session):
        """Тема Re: {original_subject} — подставляется тема исходного письма"""
        from granite.email.process_followups import process_followups

        company_id = create_company(db_session, funnel_stage="email_opened",
                                     emails=["test@example.com"])

        tpl = CrmTemplateRow(
            name="follow_up_email_v1", channel="email",
            subject="Re: {{original_subject}}",
            body="Добрый день.",
        )
        db_session.add(tpl)

        task = CrmTaskRow(
            company_id=company_id,
            title="Follow-up email",
            task_type="follow_up",
            status="pending",
            due_date=datetime.now(timezone.utc) - timedelta(hours=1),
        )
        db_session.add(task)

        touch = CrmTouchRow(
            company_id=company_id, channel="email", direction="outgoing",
            subject="Ретушь под памятник: старые фото",
        )
        db_session.add(touch)
        db_session.commit()

        with patch("granite.email.process_followups.EmailSender") as MockSender:
            mock_instance = MockSender.return_value
            mock_instance.send.return_value = "trackid456"
            mock_instance.base_url = "http://localhost:8000"

            process_followups(db_session)

            # Проверяем что в send() передана тема с Re:
            call_args = mock_instance.send.call_args
            # subject — именованный аргумент
            subject = call_args.kwargs.get("subject")
            # Предмет должен содержать "Re:" и оригинальную тему
            assert subject is not None
            assert "Re:" in subject
            assert "Ретушь под памятник" in subject


# ═══════════════════════════════════════════════════════════
# Задача 6: Bounce parser
# ═══════════════════════════════════════════════════════════

class TestBounceParser:
    """Тесты для granite/email/process_bounces.py"""

    def test_bounce_511_user_unknown(self, db_session):
        """DSN 5.1.1 → статус bounced, funnel unreachable"""
        from granite.email.process_bounces import process_bounces

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

        # Мокаем IMAP — возвращаем bounce-письмо с DSN 5.1.1
        mock_imap_messages = self._make_bounce_messages(
            "bad@example.com", "5.1.1", "User unknown"
        )

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
        from granite.email.process_bounces import process_bounces

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

        mock_imap_messages = self._make_bounce_messages(
            "full@example.com", "5.2.2", "Mailbox full"
        )

        with patch("granite.email.process_bounces.fetch_imap_messages",
                    return_value=mock_imap_messages):
            process_bounces(db_session)

        db_session.refresh(log)
        assert log.status == "bounced"

        db_session.refresh(contact)
        assert contact.funnel_stage == "email_sent"  # НЕ меняется

    def test_bounce_571_blocked(self, db_session):
        """DSN 5.7.1 → stop_automation=1"""
        from granite.email.process_bounces import process_bounces

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

        mock_imap_messages = self._make_bounce_messages(
            "blocked@example.com", "5.7.1", "Delivery not authorized"
        )

        with patch("granite.email.process_bounces.fetch_imap_messages",
                    return_value=mock_imap_messages):
            process_bounces(db_session)

        db_session.refresh(contact)
        assert contact.stop_automation == 1

    def test_bounce_imap_connection_error(self, db_session):
        """IMAP недоступен → graceful, не крашится"""
        from granite.email.process_bounces import process_bounces

        with patch("granite.email.process_bounces.fetch_imap_messages",
                    side_effect=Exception("IMAP connection refused")):
            # Не должно бросить исключение
            process_bounces(db_session)

    # ── Helpers ──

    def _make_bounce_messages(self, bounced_email, dsn_code, dsn_message):
        """Создать мок IMAP-сообщений с bounce."""
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText

        dsn_body = (
            f"Reporting-MTA: dns; mail.example.com\n"
            f"Final-Recipient: rfc822; {bounced_email}\n"
            f"Diagnostic-Code: smtp; {dsn_code} {dsn_message}\n"
        )

        msg = MIMEMultipart("report")
        msg["From"] = "mailer-daemon@example.com"
        msg["To"] = "ai.punk.facility@gmail.com"
        msg["Subject"] = f"Delivery Status Notification (Failure)"
        msg.attach(MIMEText("This is a bounce notification", "plain"))
        msg.attach(MIMEText(dsn_body, "plain"))

        return [(b"1", msg)]


# ═══════════════════════════════════════════════════════════
# Задача 9: Reply parser
# ═══════════════════════════════════════════════════════════

class TestReplyParser:
    """Тесты для granite/email/process_replies.py"""

    def test_reply_detected(self, db_session):
        """Мок IMAP с ответом → funnel_stage='replied'"""
        from granite.email.process_replies import process_replies

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

        mock_messages = self._make_reply_messages(
            "info@test.ru", "Re: Ретушь под памятник", "Интересно, давайте обсудим"
        )

        with patch("granite.email.process_replies.fetch_imap_messages",
                    return_value=mock_messages):
            process_replies(db_session)

        db_session.refresh(contact)
        assert contact.funnel_stage == "replied"

    def test_reply_cancels_followup(self, db_session):
        """Ответ → pending follow-up = cancelled"""
        from granite.email.process_replies import process_replies

        company_id = create_company(db_session, funnel_stage="email_sent")
        contact = db_session.query(CrmContactRow).filter_by(company_id=company_id).one()

        # Создаём pending follow-up задачу
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

        mock_messages = self._make_reply_messages(
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
        from granite.email.process_replies import process_replies

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

        mock_messages = self._make_reply_messages(
            "info@test.ru", "Re: Test", "Да, интересно"
        )

        with patch("granite.email.process_replies.fetch_imap_messages",
                    return_value=mock_messages):
            process_replies(db_session)

        db_session.refresh(campaign)
        assert campaign.total_replied == 1

    def test_reply_touch_body_unified(self, db_session):
        """CrmTouchRow.body= заполнен текстом ответа"""
        from granite.email.process_replies import process_replies

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
        mock_messages = self._make_reply_messages(
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
        from granite.email.process_replies import process_replies

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

        mock_messages = self._make_reply_messages(
            "info@test.ru", "Автоответ: я в отпуске", "Буду после 15 мая"
        )

        with patch("granite.email.process_replies.fetch_imap_messages",
                    return_value=mock_messages):
            process_replies(db_session)

        db_session.refresh(contact)
        assert contact.funnel_stage == "email_sent"  # без изменений

    def test_spam_complaint(self, db_session):
        """'Это спам' → stop_automation=1"""
        from granite.email.process_replies import process_replies

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

        mock_messages = self._make_reply_messages(
            "info@test.ru", "Re: Test", "Это спам, не пишите больше"
        )

        with patch("granite.email.process_replies.fetch_imap_messages",
                    return_value=mock_messages):
            process_replies(db_session)

        db_session.refresh(contact)
        assert contact.stop_automation == 1

    # ── Helpers ──

    def _make_reply_messages(self, from_email, subject, body):
        """Создать мок IMAP-сообщений с ответом."""
        from email.mime.text import MIMEText

        msg = MIMEText(body, "plain", "utf-8")
        msg["From"] = f"Отвечающий <{from_email}>"
        msg["To"] = "ai.punk.facility@gmail.com"
        msg["Subject"] = subject

        return [(b"2", msg)]


# ═══════════════════════════════════════════════════════════
# Интеграционный тест
# ═══════════════════════════════════════════════════════════

class TestPhase3Integration:
    """Интеграционный тест: отправка → bounce/reply → статус + follow-up"""

    def test_bounce_sets_unreachable(self, db_session):
        """Отправка → bounce → проверка unreachable"""
        from granite.email.process_bounces import process_bounces

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

        # Bounce с 5.1.1
        dsn_body = (
            "Reporting-MTA: dns; mail.example.com\n"
            "Final-Recipient: rfc822; dead@example.com\n"
            "Diagnostic-Code: smtp; 5.1.1 User unknown\n"
        )
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText
        bounce_msg = MIMEMultipart("report")
        bounce_msg["From"] = "mailer-daemon@example.com"
        bounce_msg["Subject"] = "Delivery Status Notification (Failure)"
        bounce_msg.attach(MIMEText(dsn_body, "plain"))

        with patch("granite.email.process_bounces.fetch_imap_messages",
                    return_value=[(b"1", bounce_msg)]):
            process_bounces(db_session)

        db_session.refresh(contact)
        assert contact.funnel_stage == "unreachable"

    def test_reply_sets_replied_and_cancels_followup(self, db_session):
        """Отправка → ответ → replied + follow-up отменён"""
        from granite.email.process_replies import process_replies

        company_id = create_company(db_session, funnel_stage="email_opened")
        contact = db_session.query(CrmContactRow).filter_by(company_id=company_id).one()

        # Pending follow-up задача
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

        # Ответ
        from email.mime.text import MIMEText
        reply_msg = MIMEText("Да, нам интересна ретушь", "plain", "utf-8")
        reply_msg["From"] = "info@test.ru"
        reply_msg["Subject"] = "Re: Ретушь под памятник"

        with patch("granite.email.process_replies.fetch_imap_messages",
                    return_value=[(b"1", reply_msg)]):
            process_replies(db_session)

        db_session.refresh(contact)
        assert contact.funnel_stage == "replied"

        # Follow-up отменён
        tasks = db_session.query(CrmTaskRow).filter_by(
            company_id=company_id, task_type="follow_up"
        ).all()
        assert all(t.status == "cancelled" for t in tasks)

        # total_replied увеличен
        db_session.refresh(campaign)
        assert campaign.total_replied == 1
