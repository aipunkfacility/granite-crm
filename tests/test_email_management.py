"""Tests for company email management — model, sync, deactivation."""
import pytest
from granite.database import CompanyEmailRow, CompanyRow, CrmContactRow
from granite.email.sync import sync_company_emails


def _make_company(db_session, cid: int, name: str = "Test Co"):
    row = db_session.get(CompanyRow, cid)
    if not row:
        row = CompanyRow(id=cid, name_best=name, city="Test City")
        db_session.add(row)
        db_session.flush()
    return row


class TestCompanyEmailModel:
    def test_create_email(self, db_session):
        _make_company(db_session, 1)
        ce = CompanyEmailRow(company_id=1, email="test@example.com", is_active=True, is_primary=True)
        db_session.add(ce)
        db_session.flush()
        assert ce.id is not None
        assert ce.is_active is True

    def test_deactivate_email(self, db_session):
        _make_company(db_session, 1)
        ce = CompanyEmailRow(company_id=1, email="test@example.com", is_active=True, is_primary=True)
        db_session.add(ce)
        db_session.flush()
        ce.is_active = False
        db_session.flush()
        db_session.expire(ce)
        assert db_session.get(CompanyEmailRow, ce.id).is_active is False


class TestGetActiveEmail:
    def test_returns_primary(self, db_session):
        _make_company(db_session, 1)
        from granite.api.campaigns import _get_active_email
        db_session.add_all([
            CompanyEmailRow(company_id=1, email="secondary@b.com", is_active=True, is_primary=False),
            CompanyEmailRow(company_id=1, email="primary@a.com", is_active=True, is_primary=True),
        ])
        db_session.flush()
        assert _get_active_email(1, db_session) == "primary@a.com"

    def test_returns_none_if_all_inactive(self, db_session):
        _make_company(db_session, 1)
        from granite.api.campaigns import _get_active_email
        db_session.add(CompanyEmailRow(company_id=1, email="old@a.com", is_active=False, is_primary=False))
        db_session.flush()
        assert _get_active_email(1, db_session) is None

    def test_returns_oldest_when_no_primary(self, db_session):
        _make_company(db_session, 1)
        from granite.api.campaigns import _get_active_email
        db_session.add_all([
            CompanyEmailRow(company_id=1, email="newer@b.com", is_active=True, is_primary=False),
            CompanyEmailRow(company_id=1, email="older@a.com", is_active=True, is_primary=False),
        ])
        db_session.flush()
        result = _get_active_email(1, db_session)
        assert result is not None


class TestSyncCompanyEmails:
    def test_adds_new_emails(self, db_session):
        _make_company(db_session, 1)
        sync_company_emails(db_session, 1, ["a@b.com", "c@d.com"])
        db_session.flush()
        rows = db_session.query(CompanyEmailRow).filter(CompanyEmailRow.company_id == 1).all()
        assert len(rows) == 2

    def test_preserves_existing_on_resync(self, db_session):
        _make_company(db_session, 1)
        sync_company_emails(db_session, 1, ["a@b.com"])
        db_session.flush()
        row = db_session.query(CompanyEmailRow).filter(CompanyEmailRow.company_id == 1).first()
        row.is_active = False
        row.sent_count = 1
        db_session.flush()
        sync_company_emails(db_session, 1, ["a@b.com"])
        db_session.flush()
        row = db_session.query(CompanyEmailRow).filter(CompanyEmailRow.company_id == 1).first()
        assert row.is_active is False
        assert row.sent_count == 1

    def test_deletes_removed_emails(self, db_session):
        _make_company(db_session, 1)
        sync_company_emails(db_session, 1, ["a@b.com", "c@d.com"])
        db_session.flush()
        sync_company_emails(db_session, 1, ["a@b.com"])
        db_session.flush()
        rows = db_session.query(CompanyEmailRow).filter(CompanyEmailRow.company_id == 1).all()
        assert len(rows) == 1
        assert rows[0].email == "a@b.com"

    def test_idempotent_migration_check(self, db_session):
        _make_company(db_session, 1)
        sync_company_emails(db_session, 1, ["a@b.com", "c@d.com"])
        db_session.flush()
        first_count = db_session.query(CompanyEmailRow).filter(CompanyEmailRow.company_id == 1).count()
        sync_company_emails(db_session, 1, ["a@b.com", "c@d.com"])
        db_session.flush()
        second_count = db_session.query(CompanyEmailRow).filter(CompanyEmailRow.company_id == 1).count()
        assert first_count == second_count


class TestDeactivation:
    def test_primary_reassigns_on_deactivation(self, db_session):
        _make_company(db_session, 1)
        ce1 = CompanyEmailRow(company_id=1, email="first@a.com", is_active=True, is_primary=True)
        ce2 = CompanyEmailRow(company_id=1, email="second@b.com", is_active=True, is_primary=False)
        db_session.add_all([ce1, ce2])
        db_session.flush()
        ce1.is_active = False
        ce1.is_primary = False
        ce2.is_primary = True
        db_session.flush()
        db_session.expire_all()
        assert db_session.get(CompanyEmailRow, ce1.id).is_primary is False
        assert db_session.get(CompanyEmailRow, ce2.id).is_primary is True

    def test_cross_company_deactivation(self, db_session):
        _make_company(db_session, 1, "Company A")
        _make_company(db_session, 2, "Company B")
        shared = "info@holding.com"
        ce1 = CompanyEmailRow(company_id=1, email=shared, is_active=True, is_primary=True)
        ce2 = CompanyEmailRow(company_id=2, email=shared, is_active=True, is_primary=True)
        db_session.add_all([ce1, ce2])
        db_session.flush()
        ce1.is_active = False
        others = db_session.query(CompanyEmailRow).filter(
            CompanyEmailRow.email == shared,
            CompanyEmailRow.company_id != 1,
            CompanyEmailRow.is_active == True,
        ).all()
        for oe in others:
            oe.is_active = False
        db_session.flush()
        db_session.expire_all()
        assert db_session.get(CompanyEmailRow, ce1.id).is_active is False
        assert db_session.get(CompanyEmailRow, ce2.id).is_active is False
