"""Tests for mark_vsepamyatniki_network one-time script."""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from granite.database import EnrichedCompanyRow, NetworkRow, Base
from scripts.mark_vsepamyatniki_network import mark_network


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


class TestMarkVsepamyatnikiNetwork:
    def test_mark_vsepamyatniki_network_creates_network_record(self, db_session):
        companies = [
            EnrichedCompanyRow(
                id=1, name="Branch 1", city="Москва",
                emails=["info1@vsepamyatniki.ru"],
                website="http://moscow.vsepamyatniki.ru",
                phones=["79001234567"], crm_score=80, segment="A",
            ),
            EnrichedCompanyRow(
                id=2, name="Branch 2", city="СПб",
                emails=["info2@vsepamyatniki.ru"],
                website="http://spb.vsepamyatniki.ru",
                phones=["79007654321"], crm_score=60, segment="B",
            ),
            EnrichedCompanyRow(
                id=3, name="Branch 3", city="Москва",
                emails=["info3@vsepamyatniki.ru"],
                website="http://other.vsepamyatniki.ru",
                phones=[], crm_score=70, segment="A",
            ),
        ]
        for c in companies:
            db_session.add(c)
        db_session.commit()

        mark_network(session=db_session)

        network = db_session.query(NetworkRow).filter_by(
            base_domain="vsepamyatniki.ru"
        ).first()
        assert network is not None
        assert network.name == "ВсеПамятники / vsepamyatniki.ru"
        assert network.company_count == 3
        assert network.city_count == 2
        assert network.signal_type == "email_domain"
        assert network.network_type == "franchise"

    def test_mark_vsepamyatniki_network_sets_is_network(self, db_session):
        companies = [
            EnrichedCompanyRow(
                id=10, name="Branch A", city="Москва",
                emails=["a@vsepamyatniki.ru"],
                website="http://a.vsepamyatniki.ru",
                phones=[], crm_score=50, segment="B",
            ),
            EnrichedCompanyRow(
                id=11, name="Branch B", city="Казань",
                emails=["b@vsepamyatniki.ru"],
                website="http://b.vsepamyatniki.ru",
                phones=[], crm_score=70, segment="A",
            ),
        ]
        for c in companies:
            db_session.add(c)
        db_session.commit()

        mark_network(session=db_session)

        rows = db_session.query(EnrichedCompanyRow).filter(
            EnrichedCompanyRow.id.in_([10, 11])
        ).all()
        assert all(r.is_network for r in rows)

        network = db_session.query(NetworkRow).filter_by(
            base_domain="vsepamyatniki.ru"
        ).first()
        assert all(r.network_id == network.id for r in rows)

    def test_mark_vsepamyatniki_network_skips_unrelated(self, db_session):
        companies = [
            EnrichedCompanyRow(
                id=20, name="Related", city="Москва",
                emails=["r@vsepamyatniki.ru"],
                website="http://r.vsepamyatniki.ru",
                phones=[], crm_score=50, segment="B",
            ),
            EnrichedCompanyRow(
                id=21, name="Unrelated", city="Москва",
                emails=["info@other.ru"],
                website="http://other.ru",
                phones=[], crm_score=50, segment="B",
            ),
        ]
        for c in companies:
            db_session.add(c)
        db_session.commit()

        mark_network(session=db_session)

        related = db_session.get(EnrichedCompanyRow, 20)
        assert related.is_network is True
        assert related.network_id is not None

        unrelated = db_session.get(EnrichedCompanyRow, 21)
        assert unrelated.is_network is False
        assert unrelated.network_id is None

    def test_mark_vsepamyatniki_network_idempotent(self, db_session):
        companies = [
            EnrichedCompanyRow(
                id=30, name="Branch X", city="Москва",
                emails=["x@vsepamyatniki.ru"],
                website="http://x.vsepamyatniki.ru",
                phones=[], crm_score=50, segment="B",
            ),
        ]
        for c in companies:
            db_session.add(c)
        db_session.commit()

        mark_network(session=db_session)
        network_count_before = db_session.query(NetworkRow).count()

        mark_network(session=db_session)

        network_count_after = db_session.query(NetworkRow).count()
        assert network_count_after == network_count_before
        assert network_count_after == 1

        row = db_session.get(EnrichedCompanyRow, 30)
        assert row.is_network is True
