"""TDD Red: TG Trust фильтр.

Фаза 2: TG Trust — фильтр + визуализация
"""
from tests.helpers import create_company


class TestTgTrustFilter:

    def test_tg_trust_min_2(self, client, db_session):
        """tg_trust_min=2 -> только живые TG."""
        create_company(db_session, messengers={"telegram": "t.me/a"},
                       tg_trust={"trust_score": 2, "has_avatar": True})
        create_company(db_session, messengers={"telegram": "t.me/b"},
                       tg_trust={"trust_score": 0})
        db_session.commit()
        r = client.get("/api/v1/companies?tg_trust_min=2")
        assert r.json()["total"] == 1

    def test_tg_trust_min_0_all_with_tg(self, client, db_session):
        """tg_trust_min=0 -> все с TG (включая мёртвых)."""
        create_company(db_session, messengers={"telegram": "t.me/a"},
                       tg_trust={"trust_score": 0})
        create_company(db_session, messengers={"telegram": "t.me/b"},
                       tg_trust={"trust_score": 3})
        db_session.commit()
        r = client.get("/api/v1/companies?tg_trust_min=0")
        assert r.json()["total"] == 2

    def test_tg_trust_min_without_telegram(self, client, db_session):
        """tg_trust_min=2 без has_telegram -> компании без TG не показываются."""
        create_company(db_session, messengers={})  # нет TG
        db_session.commit()
        r = client.get("/api/v1/companies?tg_trust_min=2")
        assert r.json()["total"] == 0

    def test_tg_trust_max_0_dead_only(self, client, db_session):
        """tg_trust_max=0 -> только мёртвые TG."""
        create_company(db_session, messengers={"telegram": "t.me/a"},
                       tg_trust={"trust_score": 0})
        create_company(db_session, messengers={"telegram": "t.me/b"},
                       tg_trust={"trust_score": 2})
        db_session.commit()
        r = client.get("/api/v1/companies?tg_trust_max=0")
        assert r.json()["total"] == 1

    def test_tg_trust_min_invalid(self, client):
        """tg_trust_min=5 -> 422 (max 3)."""
        r = client.get("/api/v1/companies?tg_trust_min=5")
        assert r.status_code == 422

    def test_tg_trust_null_excluded_by_min(self, client, db_session):
        """tg_trust=NULL (нет TG) -> исключена при tg_trust_min=1."""
        create_company(db_session, messengers={"telegram": "t.me/a"},
                       tg_trust={})  # trust_score отсутствует
        db_session.commit()
        r = client.get("/api/v1/companies?tg_trust_min=1")
        assert r.json()["total"] == 0
