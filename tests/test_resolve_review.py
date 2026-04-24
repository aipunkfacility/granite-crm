"""TDD Red: resolve-review.

Фаза 5: Resolve-review + needs_review queue
"""
from granite.database import CompanyRow
from tests.helpers import create_company, get_touches


class TestResolveReviewApprove:

    def test_approve_clears_needs_review(self, client, db_session):
        cid = create_company(db_session, needs_review=True, review_reason="geo_mismatch")
        db_session.commit()
        r = client.post(f"/api/v1/companies/{cid}/resolve-review",
                        json={"action": "approve"})
        assert r.status_code == 200
        company = db_session.get(CompanyRow, cid)
        assert company.needs_review is False
        assert company.review_reason == ""

    def test_approve_creates_audit(self, client, db_session):
        cid = create_company(db_session, needs_review=True, review_reason="suspicious")
        db_session.commit()
        client.post(f"/api/v1/companies/{cid}/resolve-review",
                    json={"action": "approve"})
        touches = get_touches(db_session, cid)
        assert any("resolve-review" in t.note and "approved" in t.note for t in touches)


class TestResolveReviewSpam:

    def test_spam_delegates_mark_spam(self, client, db_session):
        """action=spam делегирует mark-spam."""
        cid = create_company(db_session, needs_review=True)
        db_session.commit()
        r = client.post(f"/api/v1/companies/{cid}/resolve-review",
                        json={"action": "spam", "reason": "aggregator"})
        assert r.status_code == 200
        company = db_session.get(CompanyRow, cid)
        assert company.segment == "spam"
        assert company.deleted_at is not None


class TestResolveReviewDuplicate:

    def test_duplicate_delegates_mark_duplicate(self, client, db_session):
        """action=duplicate делегирует mark-duplicate."""
        cid1 = create_company(db_session, needs_review=True)
        cid2 = create_company(db_session)
        db_session.commit()
        r = client.post(f"/api/v1/companies/{cid1}/resolve-review",
                        json={"action": "duplicate", "target_id": cid2})
        assert r.status_code == 200
        source = db_session.get(CompanyRow, cid1)
        assert source.merged_into == cid2

    def test_duplicate_without_target_id_400(self, client, db_session):
        """action=duplicate без target_id -> 400."""
        cid = create_company(db_session, needs_review=True)
        db_session.commit()
        r = client.post(f"/api/v1/companies/{cid}/resolve-review",
                        json={"action": "duplicate"})
        assert r.status_code == 400


class TestResolveReviewValidation:

    def test_invalid_action_422(self, client, db_session):
        cid = create_company(db_session)
        db_session.commit()
        r = client.post(f"/api/v1/companies/{cid}/resolve-review",
                        json={"action": "invalid"})
        assert r.status_code == 422

    def test_404_company_not_found(self, client):
        r = client.post("/api/v1/companies/9999/resolve-review",
                        json={"action": "approve"})
        assert r.status_code == 404
