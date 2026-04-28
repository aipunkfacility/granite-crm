"""Тесты для follow-up логики: создание задач, отмена, счётчики, executor."""
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from granite.database import (
    CrmContactRow, CrmTaskRow, CrmTouchRow,
    CrmEmailLogRow, CrmEmailCampaignRow, CrmTemplateRow,
)
from granite.email.followup_logic import (
    maybe_create_followup_task,
    increment_campaign_opened,
)
from granite.email.process_followups import process_followups
from granite.api.helpers import cancel_followup_tasks
from tests.helpers import create_company, create_task


class TestFollowupCreation:
    """Создание follow-up задачи при первом открытии письма."""

    def test_created_on_open(self, db_session):
        """Tracking pixel → CrmTaskRow(task_type='follow_up', due_date=+7d)"""
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
            campaign_id=campaign.id, tracking_id="test1234abcd",
            status="sent", sent_at=datetime.now(timezone.utc),
        )
        db_session.add(log)
        db_session.commit()

        maybe_create_followup_task(contact, campaign.id, db_session)
        db_session.commit()

        tasks = db_session.query(CrmTaskRow).filter_by(
            company_id=company_id, task_type="follow_up", status="pending"
        ).all()
        assert len(tasks) == 1
        assert tasks[0].due_date is not None
        delta = tasks[0].due_date.replace(tzinfo=None) - datetime.now(timezone.utc).replace(tzinfo=None)
        assert 6 <= delta.days <= 8

    def test_not_created_if_already_exists(self, db_session):
        """Повторный вызов не создаёт дубликат follow-up задачи"""
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
        assert len(tasks) == 1

    def test_title_without_campaign(self, db_session):
        """Non-campaign письмо → title без None"""
        company_id = create_company(db_session, funnel_stage="email_sent")
        contact = db_session.query(CrmContactRow).filter_by(company_id=company_id).one()

        maybe_create_followup_task(contact, None, db_session)
        db_session.commit()

        task = db_session.query(CrmTaskRow).filter_by(
            company_id=company_id, task_type="follow_up"
        ).first()
        assert task is not None
        assert "None" not in task.title


class TestFollowupCancellation:
    """Отмена follow-up задач при терминальных стадиях."""

    def test_cancelled_on_reply(self, db_session):
        """Ответ → pending follow-up = cancelled"""
        company_id = create_company(db_session, funnel_stage="email_sent")
        create_task(db_session, company_id, task_type="follow_up", status="pending")
        db_session.commit()

        cancel_followup_tasks(company_id, "replied", db_session)
        db_session.commit()

        tasks = db_session.query(CrmTaskRow).filter_by(
            company_id=company_id, task_type="follow_up"
        ).all()
        assert all(t.status == "cancelled" for t in tasks)

    def test_cancelled_on_unsubscribe(self, db_session):
        """Отписка → pending follow-up = cancelled"""
        company_id = create_company(db_session, funnel_stage="email_sent")
        create_task(db_session, company_id, task_type="follow_up", status="pending")
        db_session.commit()

        cancel_followup_tasks(company_id, "not_interested", db_session)
        db_session.commit()

        tasks = db_session.query(CrmTaskRow).filter_by(
            company_id=company_id, task_type="follow_up"
        ).all()
        assert all(t.status == "cancelled" for t in tasks)


class TestTotalOpened:
    """Инкремент campaign.total_opened при tracking pixel."""

    def test_increment(self, db_session):
        """Tracking pixel → campaign.total_opened+1"""
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


class TestFollowupExecutor:
    """Отправка follow-up по созревшим задачам."""

    def test_sent_when_due(self, db_session):
        """Задача с due_date < now → письмо отправлено, статус done"""
        company_id = create_company(db_session, funnel_stage="email_opened",
                                     emails=["test@example.com"])

        tpl = CrmTemplateRow(
            name="follow_up_email_v1", channel="email",
            subject="Re: {{original_subject}}",
            body="Добрый день. Писал на прошлой неделе.",
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
            subject="Подготовка фото под гравировку",
        )
        db_session.add(touch)
        db_session.commit()

        with patch("granite.email.process_followups.EmailSender") as MockSender:
            mock_instance = MockSender.return_value
            mock_instance.send.return_value = "trackid123"
            mock_instance.base_url = "http://localhost:8000"

            process_followups(db_session)

        db_session.refresh(task)
        assert task.status == "done"
        assert task.completed_at is not None
        mock_instance.send.assert_called_once()

    def test_not_sent_when_future(self, db_session):
        """Задача с due_date > now → ничего не делаем"""
        company_id = create_company(db_session, funnel_stage="email_opened")

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
        assert task.status == "pending"

    def test_not_sent_when_cancelled(self, db_session):
        """Статус cancelled → ничего не делаем"""
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
        assert task.status == "cancelled"

    def test_uses_reply_subject(self, db_session):
        """Тема Re: {original_subject} — подставляется тема исходного письма"""
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

            call_args = mock_instance.send.call_args
            subject = call_args.kwargs.get("subject")
            assert subject is not None
            assert "Re:" in subject
            assert "Ретушь под памятник" in subject

    def test_failed_after_max_retries(self, db_session):
        """3 неудачные отправки → status='failed'"""
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
            description="[retry:2]",
            task_type="follow_up",
            status="pending",
            due_date=datetime.now(timezone.utc) - timedelta(hours=1),
        )
        db_session.add(task)
        db_session.commit()

        with patch("granite.email.process_followups.EmailSender") as MockSender:
            mock_instance = MockSender.return_value
            mock_instance.send.return_value = None
            mock_instance.base_url = "http://localhost:8000"

            process_followups(db_session)

        db_session.refresh(task)
        assert task.status == "failed"
        assert task.completed_at is not None
