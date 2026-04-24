"""TDD Red: mark-spam и unmark-spam.

Фаза 3: Mark-spam endpoint + UI
"""
from datetime import datetime, timezone

from granite.database import CompanyRow, EnrichedCompanyRow, CrmContactRow
from tests.helpers import create_company, get_touches

# Допустимые причины mark-spam
VALID_REASONS = {"aggregator", "closed", "wrong_category", "duplicate_contact", "other"}


class TestMarkSpam:

    def test_mark_spam_success(self, client, db_session):
        """POST /companies/{id}/mark-spam -> 200."""
        cid = create_company(db_session, segment="B", crm_score=30)
        db_session.commit()
        r = client.post(f"/api/v1/companies/{cid}/mark-spam",
                        json={"reason": "aggregator"})
        assert r.status_code == 200
        assert r.json()["ok"] is True

    def test_mark_spam_sets_fields(self, client, db_session):
        """После mark-spam: segment='spam', deleted_at установлен, stop_automation=1."""
        cid = create_company(db_session, segment="B", crm_score=30)
        db_session.commit()
        client.post(f"/api/v1/companies/{cid}/mark-spam",
                    json={"reason": "closed"})
        # Проверяем через include_deleted + include_spam
        r = client.get(f"/api/v1/companies?include_deleted=1&include_spam=1")
        items = [i for i in r.json()["items"] if i["id"] == cid]
        assert len(items) == 1
        assert items[0]["segment"] == "spam"
        assert items[0]["stop_automation"] is True

    def test_mark_spam_hides_from_list(self, client, db_session):
        """После mark-spam компания не видна по умолчанию."""
        cid = create_company(db_session, segment="B", crm_score=30)
        db_session.commit()
        client.post(f"/api/v1/companies/{cid}/mark-spam",
                    json={"reason": "aggregator"})
        r = client.get("/api/v1/companies")
        assert r.json()["total"] == 0

    def test_mark_spam_syncs_enriched(self, client, db_session):
        """segment='spam' синхронизируется в enriched_companies."""
        cid = create_company(db_session, segment="B", crm_score=30)
        db_session.commit()
        client.post(f"/api/v1/companies/{cid}/mark-spam",
                    json={"reason": "aggregator"})
        enriched = db_session.get(EnrichedCompanyRow, cid)
        assert enriched.segment == "spam"

    def test_mark_spam_saves_prev_segment(self, client, db_session):
        """review_reason содержит предыдущий сегмент для undo."""
        cid = create_company(db_session, segment="B", crm_score=30)
        db_session.commit()
        client.post(f"/api/v1/companies/{cid}/mark-spam",
                    json={"reason": "aggregator"})
        company = db_session.get(CompanyRow, cid)
        assert "prev_segment=B" in company.review_reason

    def test_mark_spam_creates_audit_touch(self, client, db_session):
        """mark-spam создаёт CrmTouchRow."""
        cid = create_company(db_session, segment="B", crm_score=30)
        db_session.commit()
        client.post(f"/api/v1/companies/{cid}/mark-spam",
                    json={"reason": "aggregator"})
        touches = get_touches(db_session, cid)
        assert len(touches) == 1
        assert "mark-spam" in touches[0].note
        assert "aggregator" in touches[0].note

    def test_mark_spam_404(self, client):
        """Несуществующая компания -> 404."""
        r = client.post("/api/v1/companies/9999/mark-spam",
                        json={"reason": "aggregator"})
        assert r.status_code == 404

    def test_mark_spam_already_deleted(self, client, db_session):
        """Уже удалённая -> 400."""
        cid = create_company(db_session, deleted_at=datetime.now(timezone.utc))
        db_session.commit()
        r = client.post(f"/api/v1/companies/{cid}/mark-spam",
                        json={"reason": "aggregator"})
        assert r.status_code == 400

    def test_mark_spam_invalid_reason(self, client, db_session):
        """Невалидная причина -> 422."""
        cid = create_company(db_session)
        db_session.commit()
        r = client.post(f"/api/v1/companies/{cid}/mark-spam",
                        json={"reason": "bad_reason"})
        assert r.status_code == 422


class TestUnmarkSpam:

    def test_unmark_spam_restores(self, client, db_session):
        """unmark-spam восстанавливает deleted_at=None и предыдущий сегмент."""
        cid = create_company(db_session, segment="B", crm_score=30)
        db_session.commit()
        client.post(f"/api/v1/companies/{cid}/mark-spam",
                    json={"reason": "aggregator"})
        r = client.post(f"/api/v1/companies/{cid}/unmark-spam")
        assert r.status_code == 200
        # Теперь видна в обычном списке
        r = client.get("/api/v1/companies")
        assert r.json()["total"] == 1

    def test_unmark_spam_restores_prev_segment(self, client, db_session):
        """Сегмент восстанавливается из review_reason."""
        cid = create_company(db_session, segment="A", crm_score=60)
        db_session.commit()
        client.post(f"/api/v1/companies/{cid}/mark-spam",
                    json={"reason": "closed"})
        client.post(f"/api/v1/companies/{cid}/unmark-spam")
        company = db_session.get(CompanyRow, cid)
        assert company.segment == "A"
        assert company.deleted_at is None

    def test_unmark_spam_syncs_enriched(self, client, db_session):
        """Сегмент в enriched тоже восстанавливается."""
        cid = create_company(db_session, segment="B", crm_score=30)
        db_session.commit()
        client.post(f"/api/v1/companies/{cid}/mark-spam",
                    json={"reason": "aggregator"})
        client.post(f"/api/v1/companies/{cid}/unmark-spam")
        enriched = db_session.get(EnrichedCompanyRow, cid)
        assert enriched.segment == "B"

    def test_unmark_spam_resets_stop_automation(self, client, db_session):
        """stop_automation сбрасывается при восстановлении."""
        cid = create_company(db_session, segment="B")
        db_session.commit()
        client.post(f"/api/v1/companies/{cid}/mark-spam",
                    json={"reason": "aggregator"})
        client.post(f"/api/v1/companies/{cid}/unmark-spam")
        contact = db_session.get(CrmContactRow, cid)
        assert contact.stop_automation == 0

    def test_unmark_spam_creates_audit(self, client, db_session):
        """unmark-spam создаёт CrmTouchRow."""
        cid = create_company(db_session, segment="B")
        db_session.commit()
        client.post(f"/api/v1/companies/{cid}/mark-spam",
                    json={"reason": "aggregator"})
        client.post(f"/api/v1/companies/{cid}/unmark-spam")
        touches = get_touches(db_session, cid)
        assert len(touches) == 2
        assert "unmark-spam" in touches[1].note

    def test_unmark_spam_404(self, client):
        """Несуществующая компания -> 404."""
        r = client.post("/api/v1/companies/9999/unmark-spam")
        assert r.status_code == 404
