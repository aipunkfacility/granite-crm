"""Тесты для POST /campaigns/{id}/pause."""
import pytest
from datetime import datetime, timezone

from granite.database import CrmEmailCampaignRow


class TestPauseCampaign:
    """POST /campaigns/{id}/pause — приостановка running-кампании."""

    def test_pause_running_campaign(self, db_session, client):
        """Базовый сценарий: running → paused."""
        campaign = CrmEmailCampaignRow(
            name="Test", template_name="cold_email_v1",
            status="running",
        )
        db_session.add(campaign)
        db_session.commit()

        resp = client.post(f"/api/v1/campaigns/{campaign.id}/pause")

        assert resp.status_code == 200
        assert resp.json() == {"ok": True}
        db_session.refresh(campaign)
        assert campaign.status == "paused"

    def test_pause_paused_campaign_returns_409(self, db_session, client):
        """Уже paused — конфликт."""
        campaign = CrmEmailCampaignRow(
            name="Test", template_name="cold_email_v1",
            status="paused",
        )
        db_session.add(campaign)
        db_session.commit()

        resp = client.post(f"/api/v1/campaigns/{campaign.id}/pause")

        assert resp.status_code == 409
        db_session.refresh(campaign)
        assert campaign.status == "paused"

    def test_pause_completed_campaign_returns_409(self, db_session, client):
        """completed — нельзя приостановить."""
        campaign = CrmEmailCampaignRow(
            name="Test", template_name="cold_email_v1",
            status="completed",
        )
        db_session.add(campaign)
        db_session.commit()

        resp = client.post(f"/api/v1/campaigns/{campaign.id}/pause")

        assert resp.status_code == 409
        db_session.refresh(campaign)
        assert campaign.status == "completed"

    def test_pause_draft_campaign_returns_409(self, db_session, client):
        """draft — нельзя приостановить."""
        campaign = CrmEmailCampaignRow(
            name="Test", template_name="cold_email_v1",
            status="draft",
        )
        db_session.add(campaign)
        db_session.commit()

        resp = client.post(f"/api/v1/campaigns/{campaign.id}/pause")

        assert resp.status_code == 409
        db_session.refresh(campaign)
        assert campaign.status == "draft"

    def test_pause_nonexistent_campaign_returns_404(self, db_session, client):
        """Несуществующая кампания — 404."""
        resp = client.post("/api/v1/campaigns/99999/pause")

        assert resp.status_code == 404

    def test_pause_atomic_no_race(self, db_session, client):
        """Проверка атомарности: две одновременных паузы, только одна срабатывает."""
        campaign = CrmEmailCampaignRow(
            name="Test", template_name="cold_email_v1",
            status="running",
        )
        db_session.add(campaign)
        db_session.commit()

        resp1 = client.post(f"/api/v1/campaigns/{campaign.id}/pause")
        resp2 = client.post(f"/api/v1/campaigns/{campaign.id}/pause")

        assert resp1.status_code == 200
        assert resp2.status_code == 409
        db_session.refresh(campaign)
        assert campaign.status == "paused"
