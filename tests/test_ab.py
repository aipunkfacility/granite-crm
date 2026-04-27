"""Тесты A/B тестирования — детерминированное распределение, счётчики, ab-stats."""
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from granite.database import (
    Base, CompanyRow, CrmEmailLogRow, CrmEmailCampaignRow, CrmTemplateRow,
)


# ── Фикстуры ─────────────────────────────────────────────────────────────

@pytest.fixture
def engine():
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
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.rollback()
    session.close()


def _make_company(db, name="Тест Мастерская", city="Москва",
                   emails=None, website="https://test.ru"):
    company = CompanyRow(
        name_best=name, city=city, emails=emails or ["info@test.ru"],
        website=website, sources=["web_search"],
    )
    db.add(company)
    db.flush()
    return company


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
# A/B тестирование
# ══════════════════════════════════════════════════════════════════════════

class TestABTesting:
    """Детерминированное A/B распределение + счётчики."""

    def test_ab_deterministic(self):
        from granite.email.ab import determine_ab_variant
        v1, s1 = determine_ab_variant(42, "Subject A", "Subject B")
        v2, s2 = determine_ab_variant(42, "Subject A", "Subject B")
        assert v1 == v2
        assert s1 == s2

    def test_ab_50_50_split(self):
        from granite.email.ab import determine_ab_variant
        a_count = 0
        b_count = 0
        for i in range(100):
            variant, _ = determine_ab_variant(i, "Subject A", "Subject B")
            if variant == "A":
                a_count += 1
            else:
                b_count += 1
        assert 35 <= a_count <= 65, f"A={a_count}, B={b_count}"
        assert 35 <= b_count <= 65, f"A={a_count}, B={b_count}"

    def test_ab_no_variant_b_returns_a(self):
        from granite.email.ab import determine_ab_variant
        variant, subject = determine_ab_variant(42, "Only A")
        assert variant == "A"
        assert subject == "Only A"

    def test_ab_variant_b_works(self):
        from granite.email.ab import determine_ab_variant
        for cid in range(200):
            variant, subject = determine_ab_variant(cid, "A subject", "B subject")
            if variant == "B":
                assert subject == "B subject"
                break
        else:
            pytest.fail("Не удалось найти company_id с вариантом B")

    def test_total_errors_increment(self, db):
        _make_template(db)
        campaign = _make_campaign(db, status="draft", total_sent=0, total_errors=0)
        db.commit()

        campaign.total_errors = (campaign.total_errors or 0) + 1
        db.commit()

        db.refresh(campaign)
        assert campaign.total_errors == 1

    def test_ab_variant_in_log(self, db):
        from granite.email.ab import determine_ab_variant

        _make_template(db)
        campaign = _make_campaign(db, status="draft")
        company = _make_company(db, emails=["ab@test.ru"])
        db.commit()

        ab_variant, _ = determine_ab_variant(company.id, "Subject A", "Subject B")

        log = CrmEmailLogRow(
            company_id=company.id, email_to="ab@test.ru",
            email_subject="Test", template_name="cold_email_v1",
            campaign_id=campaign.id, tracking_id="ab-test",
            status="sent", sent_at=datetime.now(timezone.utc),
            ab_variant=ab_variant,
        )
        db.add(log)
        db.commit()

        saved = db.get(CrmEmailLogRow, log.id)
        assert saved.ab_variant in ("A", "B")
        assert saved.ab_variant == ab_variant

    def test_ab_stats_endpoint(self, db, engine):
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

        with Session() as s:
            _make_template(s, name="ab_test_tpl")
            campaign = _make_campaign(s, template_name="ab_test_tpl",
                                       subject_a="Тема A", subject_b="Тема B")
            c1 = _make_company(s, name="A Company", emails=["a@ab.ru"])
            c2 = _make_company(s, name="B Company", emails=["b@ab.ru"])
            s.add(CrmEmailLogRow(
                company_id=c1.id, email_to="a@ab.ru",
                email_subject="Тема A", template_name="ab_test_tpl",
                campaign_id=campaign.id, ab_variant="A",
                tracking_id="t1", status="sent",
                sent_at=datetime.now(timezone.utc),
            ))
            s.add(CrmEmailLogRow(
                company_id=c2.id, email_to="b@ab.ru",
                email_subject="Тема B", template_name="ab_test_tpl",
                campaign_id=campaign.id, ab_variant="B",
                tracking_id="t2", status="sent",
                sent_at=datetime.now(timezone.utc),
            ))
            s.commit()
            campaign_id = campaign.id

        app.dependency_overrides[get_db] = get_test_db
        app.state.Session = Session

        try:
            with TestClient(app) as client:
                resp = client.get(f"/api/v1/campaigns/{campaign_id}/ab-stats")
                assert resp.status_code == 200
                data = resp.json()
                assert "A" in data["variants"]
                assert "B" in data["variants"]
                assert data["variants"]["A"]["sent"] == 1
                assert data["variants"]["B"]["sent"] == 1
        finally:
            app.dependency_overrides.clear()
