import pytest
from granite.database import Database, CompanyRow, EnrichedCompanyRow, RawCompanyRow
from granite.cleanup_emails import cleanup_placeholder_emails


def _make_company(db_session, table_cls, id, emails, name="Test Company"):
    kwargs = dict(
        id=id,
        city="Test City",
        region="Test Region",
        phones=[],
        emails=emails,
        website=None,
    )
    if table_cls.__tablename__ == "companies":
        kwargs["name_best"] = name
        kwargs["status"] = "raw"
    else:
        kwargs["name"] = name
    if table_cls.__tablename__ == "raw_companies":
        kwargs["source"] = "test"
        kwargs["source_url"] = ""
    row = table_cls(**kwargs)
    db_session.add(row)
    db_session.flush()


class TestCleanupPlaceholderEmails:
    def test_removes_placeholder_emails(self, engine, db_session):
        _make_company(db_session, CompanyRow, 1,
                      ["real@example.ru", "fake@email.com", "alsofake@example.com"])
        _make_company(db_session, EnrichedCompanyRow, 1,
                      ["real@example.ru", "fake@email.com", "alsofake@example.com"])
        _make_company(db_session, RawCompanyRow, 1,
                      ["real@example.ru", "fake@email.com", "alsofake@example.com"])
        db_session.commit()

        db = Database(engine=engine)
        stats = cleanup_placeholder_emails(db, dry_run=False)

        assert stats["raw"] == 1
        assert stats["companies"] == 1
        assert stats["enriched"] == 1

        for table_cls in [CompanyRow, EnrichedCompanyRow, RawCompanyRow]:
            row = db_session.get(table_cls, 1)
            assert row.emails == ["real@example.ru"], f"{table_cls.__tablename__}: {row.emails}"

    def test_skips_companies_without_placeholder(self, engine, db_session):
        _make_company(db_session, CompanyRow, 1,
                      ["real@example.ru", "real@test.com"])
        db_session.commit()

        db = Database(engine=engine)
        stats = cleanup_placeholder_emails(db, dry_run=False)

        assert stats["companies"] == 0
        row = db_session.get(CompanyRow, 1)
        assert row.emails == ["real@example.ru", "real@test.com"]

    def test_dry_run_does_not_modify(self, engine, db_session):
        _make_company(db_session, CompanyRow, 1,
                      ["real@example.ru", "fake@email.com"])
        db_session.commit()

        db = Database(engine=engine)
        stats = cleanup_placeholder_emails(db, dry_run=True)

        assert stats["companies"] == 1
        row = db_session.get(CompanyRow, 1)
        assert row.emails == ["real@example.ru", "fake@email.com"]

    def test_handles_empty_emails(self, engine, db_session):
        _make_company(db_session, CompanyRow, 1, [])
        db_session.commit()

        db = Database(engine=engine)
        stats = cleanup_placeholder_emails(db, dry_run=False)

        assert stats["companies"] == 0

    def test_handles_none_emails(self, engine, db_session):
        _make_company(db_session, CompanyRow, 1, None)
        db_session.commit()

        db = Database(engine=engine)
        stats = cleanup_placeholder_emails(db, dry_run=False)

        assert stats["companies"] == 0

    def test_case_insensitive_domain(self, engine, db_session):
        _make_company(db_session, CompanyRow, 1,
                      ["FAKE@EMAIL.COM", "Fake@Example.com"])
        db_session.commit()

        db = Database(engine=engine)
        stats = cleanup_placeholder_emails(db, dry_run=False)

        assert stats["companies"] == 1
        row = db_session.get(CompanyRow, 1)
        assert row.emails == []

    def test_only_placeholder_domains_removed(self, engine, db_session):
        _make_company(db_session, CompanyRow, 1,
                      ["good@email.ru", "good@example.org", "bad@email.com"])
        db_session.commit()

        db = Database(engine=engine)
        stats = cleanup_placeholder_emails(db, dry_run=False)

        assert stats["companies"] == 1
        row = db_session.get(CompanyRow, 1)
        assert set(row.emails) == {"good@email.ru", "good@example.org"}
