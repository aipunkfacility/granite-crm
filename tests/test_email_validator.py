"""Тесты email-валидатора — агрегаторы, дубли, SESSION_GAP, Gmail block signs, реэкспорты."""
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from unittest.mock import MagicMock

from granite.database import (
    Base, CompanyRow, CrmEmailLogRow,
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


# ══════════════════════════════════════════════════════════════════════════
# Валидатор получателей
# ══════════════════════════════════════════════════════════════════════════

class TestValidator:
    """validate_recipients() — фильтры и проверки."""

    def _make_recipient(self, company_name="Тест", email="valid@test.ru",
                         stop_automation=0, last_email_sent_at=None):
        company = MagicMock()
        company.id = 1
        company.name_best = company_name
        contact = MagicMock()
        contact.stop_automation = stop_automation
        contact.last_email_sent_at = last_email_sent_at
        enriched = MagicMock()
        return (company, enriched, contact, email)

    def test_aggregator_filtered(self):
        from granite.email.validator import validate_recipients
        recipients = [self._make_recipient(email="info@tsargranit.ru")]
        valid, warnings = validate_recipients(recipients)
        assert len(valid) == 0
        assert "агрегатор" in warnings[0]["reason"]

    def test_invalid_email_filtered(self):
        from granite.email.validator import validate_recipients
        recipients = [self._make_recipient(email="test@")]
        valid, warnings = validate_recipients(recipients)
        assert len(valid) == 0
        assert "невалидный email" in warnings[0]["reason"]

    def test_duplicate_email_deduped(self):
        from granite.email.validator import validate_recipients
        r1 = self._make_recipient(company_name="А", email="same@test.ru")
        r2 = self._make_recipient(company_name="Б", email="same@test.ru")
        r2[0].id = 2
        valid, warnings = validate_recipients([r1, r2])
        assert len(valid) == 1
        assert any("дубль" in w["reason"] for w in warnings)

    def test_session_gap(self):
        from granite.email.validator import validate_recipients
        recent = datetime.now(timezone.utc) - timedelta(minutes=30)
        recipients = [self._make_recipient(last_email_sent_at=recent)]
        valid, warnings = validate_recipients(recipients)
        assert len(valid) == 0
        assert "письмо недавно" in warnings[0]["reason"]

    def test_session_gap_expired(self):
        from granite.email.validator import validate_recipients
        old = datetime.now(timezone.utc) - timedelta(hours=5)
        recipients = [self._make_recipient(last_email_sent_at=old)]
        valid, warnings = validate_recipients(recipients)
        assert len(valid) == 1

    def test_gmail_block_signs(self, db):
        from granite.email.validator import check_gmail_block_signs

        for i in range(5):
            company = _make_company(db, name=f"Бэнс {i}", emails=[f"bounce{i}@gmail.com"])
            db.add(CrmEmailLogRow(
                company_id=company.id,
                email_to=f"bounce{i}@gmail.com",
                email_subject="Test",
                template_name="cold_email_v1",
                status="bounced",
                bounced_at=datetime.now(timezone.utc),
            ))
        db.commit()

        blocked = check_gmail_block_signs(db)
        assert "gmail.com" in blocked

    def test_gmail_block_below_threshold(self, db):
        from granite.email.validator import check_gmail_block_signs

        for i in range(4):
            company = _make_company(db, name=f"Мало {i}", emails=[f"few{i}@gmail.com"])
            db.add(CrmEmailLogRow(
                company_id=company.id,
                email_to=f"few{i}@gmail.com",
                email_subject="Test",
                template_name="cold_email_v1",
                status="bounced",
                bounced_at=datetime.now(timezone.utc),
            ))
        db.commit()

        blocked = check_gmail_block_signs(db)
        assert "gmail.com" not in blocked

    def test_seo_name_filtered(self):
        from granite.email.validator import validate_recipients
        long_name = "А" * 81
        recipients = [self._make_recipient(company_name=long_name)]
        valid, warnings = validate_recipients(recipients)
        assert len(valid) == 0
        assert "SEO" in warnings[0]["reason"]

    def test_stop_automation_filtered(self):
        from granite.email.validator import validate_recipients
        recipients = [self._make_recipient(stop_automation=1)]
        valid, warnings = validate_recipients(recipients)
        assert len(valid) == 0
        assert "отписан" in warnings[0]["reason"]


# ══════════════════════════════════════════════════════════════════════════
# Реэкспорты из granite.email
# ══════════════════════════════════════════════════════════════════════════

class TestEmailReexports:
    """granite.email реэкспортирует ключевые функции."""

    def test_import_determine_ab_variant_from_email(self):
        from granite.email import determine_ab_variant
        v, s = determine_ab_variant(1, "A", "B")
        assert v in ("A", "B")

    def test_import_validate_recipients_from_email(self):
        from granite.email import validate_recipients
        assert callable(validate_recipients)

    def test_import_check_gmail_block_signs_from_email(self):
        from granite.email import check_gmail_block_signs
        assert callable(check_gmail_block_signs)
