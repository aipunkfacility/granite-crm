"""TDD Red: mark-duplicate.

Фаза 4: Mark-duplicate — «лёгкий» merge
"""
from datetime import datetime, timezone

from granite.database import CompanyRow
from tests.helpers import create_company, get_touches


class TestMarkDuplicate:

    def test_mark_duplicate_success(self, client, db_session):
        cid1 = create_company(db_session, name_best="Дубль")
        cid2 = create_company(db_session, name_best="Оригинал")
        db_session.commit()
        r = client.post(f"/api/v1/companies/{cid1}/mark-duplicate",
                        json={"target_id": cid2})
        assert r.status_code == 200

    def test_mark_duplicate_sets_merged_into(self, client, db_session):
        cid1 = create_company(db_session)
        cid2 = create_company(db_session)
        db_session.commit()
        client.post(f"/api/v1/companies/{cid1}/mark-duplicate",
                    json={"target_id": cid2})
        source = db_session.get(CompanyRow, cid1)
        assert source.merged_into == cid2
        assert source.deleted_at is not None

    def test_mark_duplicate_hides_from_list(self, client, db_session):
        cid1 = create_company(db_session)
        cid2 = create_company(db_session)
        db_session.commit()
        client.post(f"/api/v1/companies/{cid1}/mark-duplicate",
                    json={"target_id": cid2})
        r = client.get("/api/v1/companies")
        assert r.json()["total"] == 1  # только cid2

    def test_mark_duplicate_self_error(self, client, db_session):
        cid = create_company(db_session)
        db_session.commit()
        r = client.post(f"/api/v1/companies/{cid}/mark-duplicate",
                        json={"target_id": cid})
        assert r.status_code == 400

    def test_mark_duplicate_target_not_found(self, client, db_session):
        cid = create_company(db_session)
        db_session.commit()
        r = client.post(f"/api/v1/companies/{cid}/mark-duplicate",
                        json={"target_id": 9999})
        assert r.status_code == 404

    def test_mark_duplicate_source_already_deleted(self, client, db_session):
        cid1 = create_company(db_session, deleted_at=datetime.now(timezone.utc))
        cid2 = create_company(db_session)
        db_session.commit()
        r = client.post(f"/api/v1/companies/{cid1}/mark-duplicate",
                        json={"target_id": cid2})
        assert r.status_code == 400

    def test_mark_duplicate_creates_audit(self, client, db_session):
        cid1 = create_company(db_session)
        cid2 = create_company(db_session)
        db_session.commit()
        client.post(f"/api/v1/companies/{cid1}/mark-duplicate",
                    json={"target_id": cid2})
        touches = get_touches(db_session, cid1)
        assert len(touches) == 1
        assert "mark-duplicate" in touches[0].note
        assert str(cid2) in touches[0].note

    def test_mark_duplicate_no_data_transfer(self, client, db_session):
        """В отличие от merge — телефоны НЕ переносятся."""
        cid1 = create_company(db_session, phones=["79001112233"])
        cid2 = create_company(db_session, phones=[])
        db_session.commit()
        client.post(f"/api/v1/companies/{cid1}/mark-duplicate",
                    json={"target_id": cid2})
        target = db_session.get(CompanyRow, cid2)
        assert target.phones == []  # телефоны НЕ перенесены
