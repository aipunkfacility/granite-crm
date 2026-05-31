"""Tests for email domain detection in NetworkDetector and find_candidate_groups."""
import pytest
from unittest.mock import MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from granite.database import EnrichedCompanyRow, Base
from granite.enrichers.network_detector import NetworkDetector
from granite.database import Database


@pytest.fixture
def in_memory_db():
    """Create in-memory SQLite with schema for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


class TestEmailDomainDetection:
    def test_email_domain_network_detection(self, in_memory_db):
        """Companies with same email domain (not free) are marked as network."""
        session = in_memory_db
        for i in range(3):
            session.add(EnrichedCompanyRow(
                id=i + 1,
                name=f"Branch {i}",
                city="City",
                emails=["office@vsepamyatniki.ru"],
                website="http://site{i}.ru",
                phones=[],
            ))
        session.commit()

        db = MagicMock(spec=Database)
        db.session_scope.return_value.__enter__.return_value = session

        detector = NetworkDetector(db)
        detector.scan_for_networks(threshold=2)

        results = session.query(EnrichedCompanyRow).all()
        assert all(r.is_network for r in results), "All should be marked as network"

    def test_free_email_not_detected_as_network(self, in_memory_db):
        """Companies with same free email domain (gmail.com) are NOT marked as network."""
        session = in_memory_db
        for i in range(3):
            session.add(EnrichedCompanyRow(
                id=i + 10,
                name=f"User {i}",
                city="City",
                emails=[f"user{i}@gmail.com"],
                website=f"http://site{i}.ru",
                phones=[],
            ))
        session.commit()

        db = MagicMock(spec=Database)
        db.session_scope.return_value.__enter__.return_value = session

        detector = NetworkDetector(db)
        detector.scan_for_networks(threshold=2)

        results = session.query(EnrichedCompanyRow).all()
        assert not any(r.is_network for r in results), "Free email should not trigger network"

    def test_yandex_email_not_detected_as_network(self, in_memory_db):
        """yandex.ru is in FREE_EMAIL_DOMAINS - should not trigger."""
        session = in_memory_db
        for i in range(3):
            session.add(EnrichedCompanyRow(
                id=i + 20,
                name=f"User {i}",
                city="City",
                emails=[f"user{i}@yandex.ru"],
                website=f"http://site{i}.ru",
                phones=[],
            ))
        session.commit()

        db = MagicMock(spec=Database)
        db.session_scope.return_value.__enter__.return_value = session

        detector = NetworkDetector(db)
        detector.scan_for_networks(threshold=2)

        results = session.query(EnrichedCompanyRow).all()
        assert not any(r.is_network for r in results)

    def test_empty_emails_no_error(self, in_memory_db):
        """Companies with no emails should not cause errors."""
        session = in_memory_db
        for i in range(3):
            session.add(EnrichedCompanyRow(
                id=i + 30,
                name=f"Company {i}",
                city="City",
                emails=[],
                website=f"http://site{i}.ru",
                phones=[],
            ))
        session.commit()

        db = MagicMock(spec=Database)
        db.session_scope.return_value.__enter__.return_value = session

        detector = NetworkDetector(db)
        detector.scan_for_networks(threshold=2)

        results = session.query(EnrichedCompanyRow).all()
        # Should not crash, should not mark as network
        assert not any(r.is_network for r in results)


class TestFindCandidateGroups:
    def test_find_groups_by_email_domain(self, in_memory_db):
        """find_candidate_groups returns email domain groups."""
        session = in_memory_db
        for i in range(3):
            session.add(EnrichedCompanyRow(
                id=i + 40,
                name=f"Branch {i}",
                city=f"City{i}",
                emails=["office@network.ru"],
                website=f"http://n{i}.ru",
                phones=[],
            ))
        session.commit()

        detector = NetworkDetector(MagicMock(spec=Database))
        groups = detector.find_candidate_groups(session, threshold=2)

        email_groups = [g for g in groups if g["signal_type"] == "email_domain"]
        assert any(g["signal_value"] == "network.ru" for g in email_groups)

    def test_find_groups_website_cross_city(self, in_memory_db):
        """find_candidate_groups returns website groups across cities."""
        session = in_memory_db
        session.add(EnrichedCompanyRow(
            id=50, name="Main", city="Moscow",
            emails=[], website="http://common.ru", phones=[],
        ))
        session.add(EnrichedCompanyRow(
            id=51, name="Branch", city="Spb",
            emails=[], website="http://common.ru", phones=[],
        ))
        session.commit()

        detector = NetworkDetector(MagicMock(spec=Database))
        groups = detector.find_candidate_groups(session, threshold=2)

        web_groups = [g for g in groups if g["signal_type"] == "website"]
        assert any(g["signal_value"] == "common.ru" for g in web_groups)

    def test_no_groups_below_threshold(self, in_memory_db):
        """Companies with different signals should not create groups."""
        session = in_memory_db
        session.add(EnrichedCompanyRow(
            id=60, name="A", city="City",
            emails=["a@foo.ru"], website="http://a.ru", phones=["+79001111111"],
        ))
        session.add(EnrichedCompanyRow(
            id=61, name="B", city="City",
            emails=["b@bar.ru"], website="http://b.ru", phones=["+79002222222"],
        ))
        session.commit()

        detector = NetworkDetector(MagicMock(spec=Database))
        groups = detector.find_candidate_groups(session, threshold=2)
        assert len(groups) == 0
