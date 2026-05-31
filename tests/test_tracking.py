"""Tests for tracking pixel (suspicious open detection)."""
from datetime import datetime, timedelta, timezone

from granite.database import (
    CrmEmailLogRow, CrmContactRow, CrmEmailCampaignRow,
)


class TestSuspiciousOpen:

    def _make_log(self, db_session, sent_seconds_ago: int, company_id: int = 999, tracking_id: str = None):
        if tracking_id is None:
            import uuid
            tracking_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        log = CrmEmailLogRow(
            company_id=company_id,
            email_to="test@example.com",
            tracking_id=tracking_id,
            sent_at=now - timedelta(seconds=sent_seconds_ago),
            status="sent",
        )
        db_session.add(log)
        db_session.flush()
        return log

    def _make_company(self, db_session, company_id: int = 999):
        from granite.database import CompanyRow
        company = CompanyRow(
            id=company_id,
            name_best=f"Test Co {company_id}",
            phones="[]",
            emails="[]",
            city="Test City",
            status="raw",
        )
        db_session.add(company)
        db_session.flush()
        return company

    def _make_contact(self, db_session, company_id: int = 999):
        self._make_company(db_session, company_id)
        contact = CrmContactRow(
            company_id=company_id,
            funnel_stage="email_sent",
            email_opened_count=0,
        )
        db_session.add(contact)
        db_session.flush()
        return contact

    def _make_campaign(self, db_session, campaign_id: int = 1):
        camp = CrmEmailCampaignRow(
            id=campaign_id,
            name="test",
            template_name="cold_email_v1",
            status="running",
            total_opened=0,
        )
        db_session.add(camp)
        db_session.flush()
        return camp

    # --- Suspicious: ≤30s ---

    def test_suspicious_open_does_not_update_contact(self, client, db_session):
        self._make_contact(db_session)
        log = self._make_log(db_session, sent_seconds_ago=5)
        db_session.commit()

        resp = client.get(f"/api/v1/track/open/{log.tracking_id}.png")
        assert resp.status_code == 200

        db_session.refresh(log)
        assert log.suspicious_open is True

        contact = db_session.get(CrmContactRow, 999)
        assert contact.email_opened_count == 0
        assert contact.funnel_stage == "email_sent"
        assert contact.last_email_opened_at is None

    def test_suspicious_open_at_threshold(self, client, db_session):
        self._make_contact(db_session)
        log = self._make_log(db_session, sent_seconds_ago=29)
        db_session.commit()

        client.get(f"/api/v1/track/open/{log.tracking_id}.png")

        db_session.refresh(log)
        assert log.suspicious_open is True

    def test_suspicious_open_does_not_increment_campaign(self, client, db_session):
        self._make_contact(db_session)
        camp = self._make_campaign(db_session)
        log = self._make_log(db_session, sent_seconds_ago=5)
        log.campaign_id = camp.id
        db_session.commit()

        client.get(f"/api/v1/track/open/{log.tracking_id}.png")

        db_session.refresh(camp)
        assert camp.total_opened == 0

    # --- Normal: >30s ---

    def test_normal_open_updates_contact(self, client, db_session):
        self._make_contact(db_session)
        log = self._make_log(db_session, sent_seconds_ago=60)
        db_session.commit()

        client.get(f"/api/v1/track/open/{log.tracking_id}.png")

        db_session.refresh(log)
        assert log.suspicious_open is False

        contact = db_session.get(CrmContactRow, 999)
        assert contact.email_opened_count == 1
        assert contact.funnel_stage == "email_opened"
        assert contact.last_email_opened_at is not None

    def test_normal_open_increments_campaign(self, client, db_session):
        self._make_contact(db_session)
        camp = self._make_campaign(db_session)
        log = self._make_log(db_session, sent_seconds_ago=60)
        log.campaign_id = camp.id
        db_session.commit()

        client.get(f"/api/v1/track/open/{log.tracking_id}.png")

        db_session.refresh(camp)
        assert camp.total_opened == 1

    # --- Edge cases ---

    def test_no_sent_at_is_normal(self, client, db_session):
        self._make_contact(db_session, company_id=998)
        log = CrmEmailLogRow(
            company_id=998,
            email_to="test@example.com",
            tracking_id="test-no-sent-at",
            sent_at=None,
            status="sent",
        )
        db_session.add(log)
        db_session.commit()

        client.get(f"/api/v1/track/open/{log.tracking_id}.png")

        db_session.refresh(log)
        assert log.suspicious_open is False

        contact = db_session.get(CrmContactRow, 998)
        assert contact.email_opened_count == 1

    def test_repeated_open_ignores_suspicious_flag(self, client, db_session):
        self._make_contact(db_session)
        log = self._make_log(db_session, sent_seconds_ago=5)
        log.opened_at = datetime.now(timezone.utc) - timedelta(hours=1)
        log.status = "opened"
        db_session.commit()

        client.get(f"/api/v1/track/open/{log.tracking_id}.png")

        db_session.refresh(log)
        assert log.suspicious_open is False
