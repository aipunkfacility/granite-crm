"""TDD Red: source фильтр.

Фаза 10: Source фильтр (денормализация)
"""
from tests.helpers import create_company


class TestSourceFilter:

    def test_filter_by_jsprav(self, client, db_session):
        cid = create_company(db_session, sources=["jsprav"])
        create_company(db_session, sources=["web_search"])
        db_session.commit()
        r = client.get("/api/v1/companies?source=jsprav")
        assert r.json()["total"] == 1

    def test_multi_source_company(self, client, db_session):
        """Компания из 2 источников показывается по обоим."""
        cid = create_company(db_session, sources=["jsprav", "web_search"])
        db_session.commit()
        r1 = client.get("/api/v1/companies?source=jsprav")
        r2 = client.get("/api/v1/companies?source=web_search")
        assert r1.json()["total"] == 1
        assert r2.json()["total"] == 1

    def test_source_not_found(self, client, db_session):
        create_company(db_session, sources=["jsprav"])
        db_session.commit()
        r = client.get("/api/v1/companies?source=2gis")
        assert r.json()["total"] == 0

    def test_source_invalid(self, client):
        r = client.get("/api/v1/companies?source=invalid_source")
        assert r.status_code == 422
