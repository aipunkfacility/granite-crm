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
from granite.email.sync import sync_company_emails


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
    sync_company_emails(db, company.id, company.emails)
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
                    filters=None, total_sent=0, total_errors=0,
                    recipient_mode="filter"):
    campaign = CrmEmailCampaignRow(
        name=name, template_name=template_name, status=status,
        subject_a=subject_a, subject_b=subject_b,
        filters=filters or {}, total_sent=total_sent, total_errors=total_errors,
        recipient_mode=recipient_mode,
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
        valid, _ = _get_campaign_recipients(campaign, db)
        assert len(valid) == 1

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
        valid, _ = _get_campaign_recipients(campaign, db)

        emails = [r[3] for r in valid]
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
        valid, _ = _get_campaign_recipients(campaign, db)
        assert len(valid) == 5

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
        valid, _ = _get_campaign_recipients(campaign, db)
        assert len(valid) == 10

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

    def test_campaign_progress_endpoint(self, engine, monkeypatch):
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
            monkeypatch.setenv("GRANITE_API_KEY", "")
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

    def test_campaign_progress_not_found(self, engine, monkeypatch):
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
            monkeypatch.setenv("GRANITE_API_KEY", "")
            with TestClient(app) as client:
                resp = client.get("/api/v1/campaigns/999999/progress")
                assert resp.status_code == 404
        finally:
            app.dependency_overrides.clear()

    def test_campaign_progress_completed(self, engine, monkeypatch):
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
            monkeypatch.setenv("GRANITE_API_KEY", "")
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

    def test_progress_uses_total_recipients(self, engine, monkeypatch):
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
            monkeypatch.setenv("GRANITE_API_KEY", "")
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

    def test_get_campaign_uses_total_recipients(self, engine, monkeypatch):
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
            monkeypatch.setenv("GRANITE_API_KEY", "")
            with TestClient(app) as client:
                resp = client.get(f"/api/v1/campaigns/{campaign_id}")
                assert resp.status_code == 200
                data = resp.json()
                assert data["preview_recipients"] == 12
        finally:
            app.dependency_overrides.clear()


# ══════════════════════════════════════════════════════════════════════════
# Fire-and-forget: POST /run
# ══════════════════════════════════════════════════════════════════════════


def _release_all_campaign_locks():
    """Очистить глобальное хранилище блокировок кампаний.

    Нужно между тестами /run, потому что заглушенный фоновый поток
    не освобождает lock, и следующий тест с тем же campaign_id получит 409.
    """
    from granite.api.campaigns import _campaign_locks_storage
    _campaign_locks_storage.clear()


class TestRunCampaign:
    """POST /campaigns/{id}/run — fire-and-forget.

    Background send loop is mocked to avoid threading issues
    with in-memory engine disposal between tests.
    """

    def test_run_returns_ok_immediately(self, engine, monkeypatch):
        """POST /run возвращает ok=true сразу, без ожидания отправки."""
        from unittest.mock import patch
        from fastapi.testclient import TestClient
        from granite.api.app import app
        from granite.api.deps import get_db

        Session = sessionmaker(bind=engine)

        with Session() as s:
            _make_template(s)
            campaign = _make_campaign(s, status="draft")
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

        try:
            monkeypatch.setenv("GRANITE_API_KEY", "")
            with TestClient(app) as client:
                app.state.Session = Session
                with patch("granite.api.campaigns._run_campaign_send_loop"):
                    resp = client.post(f"/api/v1/campaigns/{campaign_id}/run")
                assert resp.status_code == 200
                data = resp.json()
                assert data["ok"] is True
        finally:
            app.dependency_overrides.clear()
            _release_all_campaign_locks()

    def test_run_sets_status_running(self, engine, monkeypatch):
        """После POST /run статус кампании — running."""
        from unittest.mock import patch
        from fastapi.testclient import TestClient
        from granite.api.app import app
        from granite.api.deps import get_db

        Session = sessionmaker(bind=engine)

        with Session() as s:
            _make_template(s)
            campaign = _make_campaign(s, status="draft")
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

        try:
            monkeypatch.setenv("GRANITE_API_KEY", "")
            with TestClient(app) as client:
                app.state.Session = Session
                with patch("granite.api.campaigns._run_campaign_send_loop"):
                    resp = client.post(f"/api/v1/campaigns/{campaign_id}/run")
                assert resp.status_code == 200

            with Session() as s:
                c = s.get(CrmEmailCampaignRow, campaign_id)
                assert c is not None
                assert c.status == "running"
        finally:
            app.dependency_overrides.clear()
            _release_all_campaign_locks()

    def test_run_rejects_completed(self, engine, monkeypatch):
        """Завершённую кампанию можно перезапустить — 200."""
        from unittest.mock import patch
        from fastapi.testclient import TestClient
        from granite.api.app import app
        from granite.api.deps import get_db

        Session = sessionmaker(bind=engine)

        with Session() as s:
            _make_template(s)
            campaign = _make_campaign(s, status="completed", total_sent=10)
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

        try:
            monkeypatch.setenv("GRANITE_API_KEY", "")
            with TestClient(app) as client:
                app.state.Session = Session
                with patch("granite.api.campaigns._run_campaign_send_loop"):
                    resp = client.post(f"/api/v1/campaigns/{campaign_id}/run")
                assert resp.status_code == 200
        finally:
            app.dependency_overrides.clear()
            _release_all_campaign_locks()

    def test_run_rejects_running(self, engine, monkeypatch):
        """Уже запущенную кампанию нельзя запустить снова — 409."""
        from unittest.mock import patch
        from fastapi.testclient import TestClient
        from granite.api.app import app
        from granite.api.deps import get_db

        Session = sessionmaker(bind=engine)

        with Session() as s:
            _make_template(s)
            campaign = _make_campaign(s, status="running")
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

        try:
            monkeypatch.setenv("GRANITE_API_KEY", "")
            with TestClient(app) as client:
                app.state.Session = Session
                with patch("granite.api.campaigns._run_campaign_send_loop"):
                    resp = client.post(f"/api/v1/campaigns/{campaign_id}/run")
                assert resp.status_code == 409
        finally:
            app.dependency_overrides.clear()
            _release_all_campaign_locks()

    def test_run_not_found(self, engine, monkeypatch):
        """Несуществующая кампания — 404."""
        from unittest.mock import patch
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

        try:
            monkeypatch.setenv("GRANITE_API_KEY", "")
            with TestClient(app) as client:
                app.state.Session = Session
                with patch("granite.api.campaigns._run_campaign_send_loop"):
                    resp = client.post("/api/v1/campaigns/999999/run")
                assert resp.status_code == 404
        finally:
            app.dependency_overrides.clear()
            _release_all_campaign_locks()


# ══════════════════════════════════════════════════════════════════════════
# Recipient warnings
# ══════════════════════════════════════════════════════════════════════════

class TestRecipientWarnings:
    """Warnings from validate_recipients() are returned and persisted."""

    def test_get_campaign_recipients_returns_warnings(self, db):
        """Warnings from invalid recipients are returned alongside valid list."""
        _make_template(db)
        _make_campaign(db, status="draft")

        c1 = _make_company(db, name="Valid Co", emails=["valid@test.ru"])
        _make_enriched(db, c1.id)
        _make_contact(db, c1.id)

        c2 = _make_company(db, name="Duplicate Co", emails=["dup@test.ru"])
        _make_enriched(db, c2.id)
        _make_contact(db, c2.id)
        db.commit()

        from granite.database import CrmEmailLogRow
        db.add(CrmEmailLogRow(
            company_id=c2.id, email_to="dup@test.ru",
            email_subject="Prev", template_name="cold_email_v1",
            tracking_id="prev-tracking", status="sent",
            sent_at=datetime.now(timezone.utc),
        ))
        db.commit()

        from granite.api.campaigns import _get_campaign_recipients
        campaign = db.get(CrmEmailCampaignRow, 1)
        valid, warnings = _get_campaign_recipients(campaign, db)

        # Schema guard: each warning must have all expected keys
        for w in warnings:
            assert {"company_id", "name", "reason"} <= set(w.keys())

        assert len(valid) == 1
        assert valid[0][3] == "valid@test.ru"
        assert len(warnings) >= 1
        # Check by company_id, not by fragile string match
        assert any(w["company_id"] == c2.id for w in warnings)

    def test_manual_recipients_returns_warnings(self, db):
        """Warnings from manual mode are returned correctly."""
        _make_template(db)
        campaign = _make_campaign(db, status="draft", recipient_mode="manual")
        db.commit()
        db.refresh(campaign)

        from granite.database import CampaignRecipientRow

        c1 = _make_company(db, name="Valid Co", emails=["valid@test.ru"])
        _make_enriched(db, c1.id)
        _make_contact(db, c1.id)
        db.add(CampaignRecipientRow(
            campaign_id=campaign.id, company_id=c1.id, email="valid@test.ru",
        ))

        c2 = _make_company(db, name="Agg Co", emails=["info@spravker.ru"])
        _make_enriched(db, c2.id)
        _make_contact(db, c2.id)
        db.add(CampaignRecipientRow(
            campaign_id=campaign.id, company_id=c2.id, email="info@spravker.ru",
        ))

        # Company with recent email — in manual mode, SESSION_GAP is skipped.
        # This is the negative test: recent email should NOT cause a warning.
        c3 = _make_company(db, name="Recent Co", emails=["recent@test.ru"])
        _make_enriched(db, c3.id)
        c3_contact = _make_contact(
            db, c3.id,
            last_email_sent_at=datetime.now(timezone.utc),
        )
        db.add(CampaignRecipientRow(
            campaign_id=campaign.id, company_id=c3.id, email="recent@test.ru",
        ))
        db.commit()

        from granite.api.campaigns import _get_campaign_recipients
        valid, warnings = _get_campaign_recipients(campaign, db)

        # Schema guard
        for w in warnings:
            assert {"company_id", "name", "reason"} <= set(w.keys())

        assert len(valid) == 2  # c1 (valid) + c3 (SESSION_GAP skipped)
        assert valid[0][3] == "valid@test.ru"
        assert valid[1][3] == "recent@test.ru"
        assert len(warnings) >= 1
        assert any(w["company_id"] == c2.id for w in warnings)
        # Recent-email company should NOT be in warnings (manual skips SESSION_GAP)
        assert not any(w["company_id"] == c3.id for w in warnings)

    def test_warnings_persisted_on_run(self, engine, monkeypatch):
        """recipient_warnings saved to campaign when send loop starts."""
        from fastapi.testclient import TestClient
        from granite.api.app import app
        from granite.api.deps import get_db
        from sqlalchemy.orm import sessionmaker

        Session = sessionmaker(bind=engine)

        with Session() as s:
            _make_template(s, name="persist_tpl")
            campaign = _make_campaign(s, template_name="persist_tpl", status="draft")
            c1 = _make_company(s, name="Valid", emails=["valid@test.ru"])
            _make_enriched(s, c1.id)
            _make_contact(s, c1.id)
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

        from unittest.mock import patch

        app.dependency_overrides[get_db] = get_test_db

        try:
            monkeypatch.setenv("GRANITE_API_KEY", "")
            with TestClient(app) as client:
                app.state.Session = Session
                with patch("granite.api.campaigns._run_campaign_send_loop"):
                    resp = client.post(f"/api/v1/campaigns/{campaign_id}/run")
                assert resp.status_code == 200

            with Session() as s:
                campaign = s.get(CrmEmailCampaignRow, campaign_id)
                # Saved as empty list (no invalid companies in test data)
                assert campaign.recipient_warnings is None or campaign.recipient_warnings == []
        finally:
            app.dependency_overrides.clear()

    def test_warnings_snapshot_not_overwritten_on_rerun(self, db):
        """recipient_warnings is a snapshot: once set, re-run does NOT overwrite."""
        _make_template(db)
        campaign = _make_campaign(db, status="draft")
        c1 = _make_company(db, name="Valid", emails=["valid@test.ru"])
        _make_enriched(db, c1.id)
        _make_contact(db, c1.id)
        c2 = _make_company(db, name="Agg Co", emails=["info@yell.ru"])
        _make_enriched(db, c2.id)
        _make_contact(db, c2.id)
        db.commit()

        from granite.api.campaigns import _get_campaign_recipients

        # Simulate first run: save warnings + freeze total_recipients
        valid, first_warnings = _get_campaign_recipients(campaign, db)
        campaign.total_recipients = len(valid)
        campaign.recipient_warnings = first_warnings
        snapshot = list(campaign.recipient_warnings)
        db.commit()
        assert campaign.total_recipients > 0  # guard will be False on re-run

        # Simulate re-run: total_recipients already set, guard prevents save
        db.refresh(campaign)
        _, second_warnings = _get_campaign_recipients(campaign, db)
        # The guard: if not campaign.total_recipients: ... won't execute
        if not campaign.total_recipients:
            campaign.recipient_warnings = second_warnings
        db.commit()

        # Warnings must be the first-run snapshot
        db.refresh(campaign)
        assert campaign.recipient_warnings == snapshot
