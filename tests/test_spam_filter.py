"""TDD Red: тесты спам-фильтра. Все падают до реализации.

Фаза 1: Spam-фильтр по умолчанию + include_spam/include_deleted
"""
from datetime import datetime, timezone

from tests.helpers import create_company


class TestIncludeSpamDefault:
    """По умолчанию спам скрыт."""

    def test_spam_hidden_by_default(self, client, db_session):
        """segment='spam' + deleted_at=NULL -> скрыта без явного include_spam."""
        create_company(db_session, segment="spam", crm_score=0)
        db_session.commit()
        r = client.get("/api/v1/companies")
        assert r.json()["total"] == 0

    def test_non_spam_visible_by_default(self, client, db_session):
        """segment='B' -> видна по умолчанию."""
        create_company(db_session, segment="B", crm_score=30)
        db_session.commit()
        r = client.get("/api/v1/companies")
        assert r.json()["total"] == 1

    def test_include_spam_1_shows_spam(self, client, db_session):
        """include_spam=1 -> спам виден."""
        create_company(db_session, segment="spam", crm_score=0)
        db_session.commit()
        r = client.get("/api/v1/companies?include_spam=1")
        assert r.json()["total"] == 1

    def test_include_spam_2_only_spam(self, client, db_session):
        """include_spam=2 -> только спам."""
        create_company(db_session, segment="spam", crm_score=0)
        create_company(db_session, segment="B", crm_score=30)
        db_session.commit()
        r = client.get("/api/v1/companies?include_spam=2")
        assert r.json()["total"] == 1
        assert r.json()["items"][0]["segment"] == "spam"


class TestIncludeDeleted:
    """Админ-фильтр include_deleted."""

    def test_deleted_hidden_by_default(self, client, db_session):
        """deleted_at IS NOT NULL -> скрыта."""
        create_company(db_session, deleted_at=datetime.now(timezone.utc))
        db_session.commit()
        r = client.get("/api/v1/companies")
        assert r.json()["total"] == 0

    def test_include_deleted_1_shows_deleted(self, client, db_session):
        """include_deleted=1 -> удалённые видны."""
        create_company(db_session, deleted_at=datetime.now(timezone.utc))
        db_session.commit()
        r = client.get("/api/v1/companies?include_deleted=1")
        assert r.json()["total"] == 1

    def test_include_deleted_with_include_spam(self, client, db_session):
        """include_deleted=1 + include_spam=1 -> все компании."""
        create_company(db_session, segment="B", crm_score=30)
        create_company(db_session, segment="spam", crm_score=0)
        create_company(db_session, segment="spam", crm_score=0, deleted_at=datetime.now(timezone.utc))
        db_session.commit()
        r = client.get("/api/v1/companies?include_deleted=1&include_spam=1")
        assert r.json()["total"] == 3


class TestSpamFilterWithSegment:
    """Взаимодействие include_spam и segment фильтра."""

    def test_segment_a_excludes_spam(self, client, db_session):
        """segment=A не включает spam, даже если include_spam=1."""
        create_company(db_session, segment="A", crm_score=60)
        create_company(db_session, segment="spam", crm_score=0)
        db_session.commit()
        r = client.get("/api/v1/companies?segment=A&include_spam=1")
        assert r.json()["total"] == 1

    def test_segment_spam_with_include_spam(self, client, db_session):
        """segment=spam + include_spam=1 -> только спам."""
        create_company(db_session, segment="spam", crm_score=0)
        create_company(db_session, segment="B", crm_score=30)
        db_session.commit()
        r = client.get("/api/v1/companies?segment=spam&include_spam=1")
        assert r.json()["total"] == 1

    def test_spam_with_deleted_at_hidden_even_with_include_spam_1(self, client, db_session):
        """segment='spam' + deleted_at -> скрыта даже с include_spam=1 (deleted фильтр)."""
        create_company(db_session, segment="spam", crm_score=0, deleted_at=datetime.now(timezone.utc))
        db_session.commit()
        r = client.get("/api/v1/companies?include_spam=1")
        assert r.json()["total"] == 0  # скрыта через deleted_at

    def test_spam_with_deleted_at_visible_with_both_flags(self, client, db_session):
        """segment='spam' + deleted_at -> видна только с include_spam=1 + include_deleted=1."""
        create_company(db_session, segment="spam", crm_score=0, deleted_at=datetime.now(timezone.utc))
        db_session.commit()
        r = client.get("/api/v1/companies?include_spam=1&include_deleted=1")
        assert r.json()["total"] == 1
