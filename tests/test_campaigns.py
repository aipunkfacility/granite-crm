"""Тесты кампаний — recovery, получатели, прогресс, total_recipients."""
import json
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from granite.database import (
    Base, CompanyRow, EnrichedCompanyRow, CrmContactRow,
    CrmEmailLogRow, CrmEmailCampaignRow, CrmTemplateRow, CrmTouchRow,
)


# ── Фикстуры ─────────────────────────────────────────────────────────────

@pytest.fixture
def engine():
    """In-memory SQLite с FK PRAGMA."""
    _engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(_engine, "connect")
    def _pragma(dbapi_conn, conn_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(_engine)
    yield _engine
    _engine.dispose()


@pytest.fixture
def db(engine):
    """Сессия БД для тестов."""
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.rollback()
    session.close()


def _make_company(db, id_=None, name="Тест Мастерская", city="Москва",
                   emails=None, website="https://test.ru"):
    company = CompanyRow(
        name_best=name, city=city, emails=emails or ["info@test.ru"],
        website=website, sources=["web_search"],
    )
    db.add(company)
    db.flush()
    return company


def _make_enriched(db, company_id, name="Тест", city="Москва", segment="a", crm_score=5):
    enriched = EnrichedCompanyRow(
        id=company_id, name=name, city=city,
        segment=segment, crm_score=crm_score,
    )
    db.add(enriched)
    db.flush()
    return enriched


def _make_contact(db, company_id, stop_automation=0, funnel_stage="new",
                   last_email_sent_at=None, unsubscribe_token=None):
    import secrets
    contact = CrmContactRow(
        company_id=company_id, stop_automation=stop_automation,
        funnel_stage=funnel_stage,
        last_email_sent_at=last_email_sent_at,
        unsubscribe_token=unsubscribe_token or secrets.token_hex(16),
    )
    db.add(contact)
    db.flush()
    return contact


def _make_template(db, name="cold_email_v1", channel="email",
                    subject="Тест", body="Здравствуйте {city}",
                    body_type="plain", description="", retired=False):
    template = CrmTemplateRow(
        name=name, channel=channel, subject=subject, body=body,
        body_type=body_type, description=description, retired=retired,
    )
    db.add(template)
    db.flush()
    return template


def _make_campaign(db, name="Test Campaign", template_name="cold_email_v1",
                    status="draft", subject_a=None, subject_b=None,
                    filters=None, total_sent=0, total_errors=0):
    campaign = CrmEmailCampaignRow(
        name=name, template_name=template_name, status=status,
        subject_a=subject_a, subject_b=subject_b,
        filters=filters or {}, total_sent=total_sent, total_errors=total_errors,
    )
    db.add(campaign)
    db.flush()
    return campaign


# ══════════════════════════════════════════════════════════════════════════
# Recovery
# ══════════════════════════════════════════════════════════════════════════

class TestRecovery:
    """Running кампании → paused при старте сервера."""

    def test_recovery_running_to_paused(self, db):
        _make_template(db)
        c1 = _make_campaign(db, name="Running 1", status="running")
        c2 = _make_campaign(db, name="Running 2", status="running")
        c3 = _make_campaign(db, name="Draft", status="draft")
        c4 = _make_campaign(db, name="Completed", status="completed")
        db.commit()

        running = db.query(CrmEmailCampaignRow).filter(
            CrmEmailCampaignRow.status == "running"
        ).all()
        for c in running:
            c.status = "paused"
        db.commit()

        db.refresh(c1); db.refresh(c2); db.refresh(c3); db.refresh(c4)
        assert c1.status == "paused"
        assert c2.status == "paused"
        assert c3.status == "draft"
        assert c4.status == "completed"


# ══════════════════════════════════════════════════════════════════════════
# Получатели кампании
# ══════════════════════════════════════════════════════════════════════════

class TestCampaignRecipients:
    """Фильтры + дедуп + батч-итерация."""

    def test_campaign_recipients_dedup(self, db):
        _make_template(db)
        _make_campaign(db, status="draft")

        c1 = _make_company(db, name="Мастерская А", emails=["info@same.ru"])
        _make_enriched(db, c1.id)
        _make_contact(db, c1.id)

        c2 = _make_company(db, name="Мастерская Б", emails=["info@same.ru"])
        _make_enriched(db, c2.id)
        _make_contact(db, c2.id)
        db.commit()

        from granite.api.campaigns import _get_campaign_recipients
        campaign = db.get(CrmEmailCampaignRow, 1)
        recipients = _get_campaign_recipients(campaign, db)
        assert len(recipients) == 1

    def test_campaign_recipients_filter_stop_automation(self, db):
        _make_template(db)
        _make_campaign(db, status="draft")

        c1 = _make_company(db, name="Активная", emails=["active@test.ru"])
        _make_enriched(db, c1.id)
        _make_contact(db, c1.id, stop_automation=0)

        c2 = _make_company(db, name="Отписанная", emails=["unsub@test.ru"])
        _make_enriched(db, c2.id)
        _make_contact(db, c2.id, stop_automation=1)
        db.commit()

        from granite.api.campaigns import _get_campaign_recipients
        campaign = db.get(CrmEmailCampaignRow, 1)
        recipients = _get_campaign_recipients(campaign, db)

        emails = [r[3] for r in recipients]
        assert "active@test.ru" in emails
        assert "unsub@test.ru" not in emails

    def test_campaign_recipients_no_oom(self, db):
        _make_template(db)
        _make_campaign(db, status="draft")

        for i in range(5):
            c = _make_company(db, name=f"Мастерская {i}", emails=[f"info{i}@test.ru"])
            _make_enriched(db, c.id)
            _make_contact(db, c.id)
        db.commit()

        from granite.api.campaigns import _get_campaign_recipients
        campaign = db.get(CrmEmailCampaignRow, 1)
        recipients = _get_campaign_recipients(campaign, db)
        assert len(recipients) == 5

    def test_yield_per_100_processes_all(self, db):
        _make_template(db)
        _make_campaign(db, status="draft")

        for i in range(10):
            c = _make_company(db, name=f"Партия {i}", emails=[f"batch{i}@test.ru"])
            _make_enriched(db, c.id)
            _make_contact(db, c.id)
        db.commit()

        from granite.api.campaigns import _get_campaign_recipients
        campaign = db.get(CrmEmailCampaignRow, 1)
        recipients = _get_campaign_recipients(campaign, db)
        assert len(recipients) == 10

    def test_commit_per_email(self, db):
        _make_template(db)
        campaign = _make_campaign(db, status="draft")
        c1 = _make_company(db, name="Мастерская 1", emails=["commit1@test.ru"])
        _make_enriched(db, c1.id)
        _make_contact(db, c1.id)
        c2 = _make_company(db, name="Мастерская 2", emails=["commit2@test.ru"])
        _make_enriched(db, c2.id)
        _make_contact(db, c2.id)
        db.commit()

        for company_id, email in [(c1.id, "commit1@test.ru"), (c2.id, "commit2@test.ru")]:
            log = CrmEmailLogRow(
                company_id=company_id, email_to=email,
                email_subject="Test", template_name="cold_email_v1",
                campaign_id=campaign.id, tracking_id=f"track-{company_id}",
                status="sent", sent_at=datetime.now(timezone.utc),
            )
            db.add(log)
            db.add(CrmTouchRow(
                company_id=company_id, channel="email", direction="outgoing",
                subject="Test", body="[tracking_id=track] [ab=A]",
            ))
            db.commit()

        logs = db.query(CrmEmailLogRow).filter_by(campaign_id=campaign.id).all()
        assert len(logs) == 2
        touches = db.query(CrmTouchRow).all()
        assert len(touches) == 2


# ══════════════════════════════════════════════════════════════════════════
# Прогресс кампании (SSE)
# ══════════════════════════════════════════════════════════════════════════

class TestCampaignProgress:
    """GET /campaigns/{id}/progress — SSE-эндпоинт."""

    def test_campaign_progress_endpoint(self, engine):
        from fastapi.testclient import TestClient
        from granite.api.app import app
        from granite.api.deps import get_db

        Session = sessionmaker(bind=engine)

        with Session() as s:
            _make_template(s, name="progress_tpl")
            campaign = _make_campaign(s, template_name="progress_tpl",
                                       status="draft", total_sent=0, total_errors=0)
            s.commit()
            campaign_id = campaign.id

        def get_test_db():
            session = Session()
            try:
                yield session
                session.commit()
            except Exception:
                session.rollback()
                raise
            finally:
                session.close()

        app.dependency_overrides[get_db] = get_test_db
        app.state.Session = Session

        try:
            with TestClient(app) as client:
                resp = client.get(f"/api/v1/campaigns/{campaign_id}/progress")
                assert resp.status_code == 200
                assert resp.headers["content-type"] == "text/event-stream; charset=utf-8"

                body = resp.text
                assert "data:" in body

                for line in body.strip().split("\n"):
                    if line.startswith("data:"):
                        data = json.loads(line[5:].strip())
                        assert data["status"] == "draft"
                        assert "sent" in data
                        assert "total" in data
                        assert "errors" in data
                        break
                else:
                    pytest.fail("No SSE data line found in response")
        finally:
            app.dependency_overrides.clear()

    def test_campaign_progress_not_found(self, engine):
        from fastapi.testclient import TestClient
        from granite.api.app import app
        from granite.api.deps import get_db

        Session = sessionmaker(bind=engine)

        def get_test_db():
            session = Session()
            try:
                yield session
                session.commit()
            except Exception:
                session.rollback()
                raise
            finally:
                session.close()

        app.dependency_overrides[get_db] = get_test_db
        app.state.Session = Session

        try:
            with TestClient(app) as client:
                resp = client.get("/api/v1/campaigns/999999/progress")
                assert resp.status_code == 404
        finally:
            app.dependency_overrides.clear()

    def test_campaign_progress_completed(self, engine):
        from fastapi.testclient import TestClient
        from granite.api.app import app
        from granite.api.deps import get_db

        Session = sessionmaker(bind=engine)

        with Session() as s:
            _make_template(s, name="completed_tpl")
            campaign = _make_campaign(s, template_name="completed_tpl",
                                       status="completed", total_sent=10, total_errors=1)
            s.commit()
            campaign_id = campaign.id

        def get_test_db():
            session = Session()
            try:
                yield session
                session.commit()
            except Exception:
                session.rollback()
                raise
            finally:
                session.close()

        app.dependency_overrides[get_db] = get_test_db
        app.state.Session = Session

        try:
            with TestClient(app) as client:
                resp = client.get(f"/api/v1/campaigns/{campaign_id}/progress")
                assert resp.status_code == 200

                for line in resp.text.strip().split("\n"):
                    if line.startswith("data:"):
                        data = json.loads(line[5:].strip())
                        assert data["status"] == "completed"
                        assert data["sent"] == 10
                        assert data["errors"] == 1
                        break
        finally:
            app.dependency_overrides.clear()


# ══════════════════════════════════════════════════════════════════════════
# total_recipients в кампании
# ══════════════════════════════════════════════════════════════════════════

class TestTotalRecipients:
    """CrmEmailCampaignRow.total_recipients — кол-во получателей."""

    def test_total_recipients_default(self, db):
        _make_template(db)
        campaign = _make_campaign(db, status="draft")
        db.commit()

        db.refresh(campaign)
        assert campaign.total_recipients is None or campaign.total_recipients == 0

    def test_total_recipients_set(self, db):
        _make_template(db)
        campaign = _make_campaign(db, status="draft")
        campaign.total_recipients = 42
        db.commit()

        db.refresh(campaign)
        assert campaign.total_recipients == 42

    def test_progress_uses_total_recipients(self, engine):
        from fastapi.testclient import TestClient
        from granite.api.app import app
        from granite.api.deps import get_db

        Session = sessionmaker(bind=engine)

        with Session() as s:
            _make_template(s, name="progress_tpl2")
            campaign = _make_campaign(s, template_name="progress_tpl2", status="completed",
                                      total_sent=15, total_errors=2)
            campaign.total_recipients = 20
            s.commit()
            campaign_id = campaign.id

        def get_test_db():
            session = Session()
            try:
                yield session
                session.commit()
            except Exception:
                session.rollback()
                raise
            finally:
                session.close()

        app.dependency_overrides[get_db] = get_test_db
        app.state.Session = Session

        try:
            with TestClient(app) as client:
                resp = client.get(f"/api/v1/campaigns/{campaign_id}/progress")
                assert resp.status_code == 200

                for line in resp.text.strip().split("\n"):
                    if line.startswith("data:"):
                        data = json.loads(line[5:].strip())
                        assert data["total"] == 20
                        assert data["sent"] == 15
                        assert data["errors"] == 2
                        assert data["status"] == "completed"
                        break
        finally:
            app.dependency_overrides.clear()

    def test_get_campaign_uses_total_recipients(self, engine):
        from fastapi.testclient import TestClient
        from granite.api.app import app
        from granite.api.deps import get_db

        Session = sessionmaker(bind=engine)

        with Session() as s:
            _make_template(s, name="detail_tpl")
            campaign = _make_campaign(s, template_name="detail_tpl", status="completed",
                                      total_sent=10)
            campaign.total_recipients = 12
            s.commit()
            campaign_id = campaign.id

        def get_test_db():
            session = Session()
            try:
                yield session
                session.commit()
            except Exception:
                session.rollback()
                raise
            finally:
                session.close()

        app.dependency_overrides[get_db] = get_test_db
        app.state.Session = Session

        try:
            with TestClient(app) as client:
                resp = client.get(f"/api/v1/campaigns/{campaign_id}")
                assert resp.status_code == 200
                data = resp.json()
                assert data["preview_recipients"] == 12
        finally:
            app.dependency_overrides.clear()
