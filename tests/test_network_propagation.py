"""Tests for NetworkDetector.propagate_shared_contacts()."""
import pytest
from unittest.mock import MagicMock
from granite.database import CompanyRow, EnrichedCompanyRow, CompanyEmailRow
from granite.email.sync import sync_company_emails


class TestPropagateSharedContacts:

    def test_propagates_emails_by_website_domain(self, db_session):
        """Companies sharing a website domain get shared emails propagated."""
        c1 = CompanyRow(name_best="C1", city="москва", website="https://guravli.agency/msk",
                        emails=["info@guravli.agency"])
        c2 = CompanyRow(name_best="C2", city="спб", website="https://guravli.agency/spb", emails=[])
        c3 = CompanyRow(name_best="C3", city="крд", website="https://guravli.agency/krd",
                        emails=["info@guravli.agency"])
        db_session.add_all([c1, c2, c3]); db_session.flush()
        for c in [c1, c2, c3]:
            db_session.add(EnrichedCompanyRow(id=c.id, name=c.name_best, city=c.city,
                                              website=c.website, emails=c.emails, is_network=True))
            sync_company_emails(db_session, c.id, c.emails)
        db_session.commit()

        from granite.enrichers.network_detector import NetworkDetector
        from granite.database import Database
        db = MagicMock(spec=Database)
        db.session_scope.return_value.__enter__.return_value = db_session
        detector = NetworkDetector(db, {"enrichment": {"network_threshold": 2}})
        detector.propagate_shared_contacts()
        db_session.flush(); db_session.expire_all()

        updated_c2 = db_session.get(EnrichedCompanyRow, c2.id)
        assert "info@guravli.agency" in (updated_c2.emails or [])
        c2_email_rows = db_session.query(CompanyEmailRow).filter(
            CompanyEmailRow.company_id == c2.id, CompanyEmailRow.is_active == True).all()
        assert any("info@guravli.agency" in r.email for r in c2_email_rows)

    def test_propagates_emails_by_email_domain(self, db_session):
        """Companies sharing an email domain get emails propagated."""
        c1 = CompanyRow(name_best="C1", city="москва", emails=["info@guravli.agency"])
        c2 = CompanyRow(name_best="C2", city="спб", emails=["support@guravli.agency"])
        c3 = CompanyRow(name_best="C3", city="крд", emails=[])
        db_session.add_all([c1, c2, c3]); db_session.flush()
        for c in [c1, c2, c3]:
            db_session.add(EnrichedCompanyRow(id=c.id, name=c.name_best, city=c.city,
                                              emails=c.emails, is_network=True))
            sync_company_emails(db_session, c.id, c.emails)
        db_session.commit()

        from granite.enrichers.network_detector import NetworkDetector
        from granite.database import Database
        db = MagicMock(spec=Database)
        db.session_scope.return_value.__enter__.return_value = db_session
        detector = NetworkDetector(db, {"enrichment": {"network_threshold": 2}})
        detector.propagate_shared_contacts()
        db_session.flush(); db_session.expire_all()

        updated_c3 = db_session.get(EnrichedCompanyRow, c3.id)
        assert "info@guravli.agency" in (updated_c3.emails or [])
        assert "support@guravli.agency" in (updated_c3.emails or [])

    def test_does_not_propagate_free_email_domains(self, db_session):
        """Free email domains (mail.ru, gmail.com) should never trigger propagation."""
        c1 = CompanyRow(name_best="C1", city="москва", emails=["a@mail.ru"])
        c2 = CompanyRow(name_best="C2", city="спб", emails=["b@mail.ru"])
        c3 = CompanyRow(name_best="C3", city="крд", emails=[])
        db_session.add_all([c1, c2, c3]); db_session.flush()
        for c in [c1, c2, c3]:
            db_session.add(EnrichedCompanyRow(id=c.id, name=c.name_best, city=c.city,
                                              emails=c.emails, is_network=True))
        db_session.commit()

        from granite.enrichers.network_detector import NetworkDetector
        from granite.database import Database
        db = MagicMock(spec=Database)
        db.session_scope.return_value.__enter__.return_value = db_session
        detector = NetworkDetector(db, {})
        detector.propagate_shared_contacts()
        db_session.flush(); db_session.expire_all()

        updated_c3 = db_session.get(EnrichedCompanyRow, c3.id)
        assert not (updated_c3.emails or [])

    def test_does_not_propagate_single_company_group(self, db_session):
        """A network of 1 should not propagate."""
        c1 = CompanyRow(name_best="C1", city="москва", website="https://standalone.ru",
                        emails=["info@standalone.ru"])
        db_session.add(c1); db_session.flush()
        db_session.add(EnrichedCompanyRow(id=c1.id, name=c1.name_best, city=c1.city,
                                          website=c1.website, emails=c1.emails, is_network=True))
        db_session.commit()

        from granite.enrichers.network_detector import NetworkDetector
        from granite.database import Database
        db = MagicMock(spec=Database)
        db.session_scope.return_value.__enter__.return_value = db_session
        detector = NetworkDetector(db, {})
        detector.propagate_shared_contacts()
        db_session.flush(); db_session.expire_all()

        updated = db_session.get(EnrichedCompanyRow, c1.id)
        assert updated.emails == ["info@standalone.ru"]

    def test_does_not_propagate_to_fully_synced_company(self, db_session):
        """A company with all network emails already should not change."""
        c1 = CompanyRow(name_best="C1", city="москва", emails=["info@guravli.agency"])
        c2 = CompanyRow(name_best="C2", city="спб", emails=["info@guravli.agency"])
        db_session.add_all([c1, c2]); db_session.flush()
        for c in [c1, c2]:
            db_session.add(EnrichedCompanyRow(id=c.id, name=c.name_best, city=c.city,
                                              emails=c.emails, is_network=True))
        db_session.commit()

        from granite.enrichers.network_detector import NetworkDetector
        from granite.database import Database
        db = MagicMock(spec=Database)
        db.session_scope.return_value.__enter__.return_value = db_session
        detector = NetworkDetector(db, {})
        detector.propagate_shared_contacts()
        db_session.flush(); db_session.expire_all()

        assert db_session.get(EnrichedCompanyRow, c1.id).emails == ["info@guravli.agency"]
        assert db_session.get(EnrichedCompanyRow, c2.id).emails == ["info@guravli.agency"]
