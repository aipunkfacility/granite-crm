"""Smoke-тесты для CRM API.

Фикстуры (engine, db_session, client) — в tests/conftest.py.
Фабрики (create_company, create_task) — в tests/helpers.py.
"""
from datetime import datetime, timedelta, timezone

from tests.helpers import create_company


class TestHealthEndpoint:
    def test_health_with_db(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        assert data["db"] is True

    def test_funnel_empty(self, client):
        r = client.get("/api/v1/funnel")
        assert r.status_code == 200
        data = r.json()
        assert data["new"] == 0
        assert "email_sent" in data
        # All 9 stages present
        assert len(data) == 9

    def test_campaigns_list_empty(self, client):
        r = client.get("/api/v1/campaigns")
        assert r.status_code == 200
        assert r.json() == []


class TestValidation:
    def test_touch_invalid_channel(self, client):
        r = client.post("/api/v1/companies/1/touches", json={"channel": "fax"})
        assert r.status_code == 422  # Pydantic validation

    def test_update_invalid_stage(self, client):
        r = client.patch("/api/v1/companies/1", json={"funnel_stage": "banana"})
        assert r.status_code == 422

    def test_send_invalid_channel(self, client):
        r = client.post("/api/v1/companies/1/send", json={"channel": "sms"})
        assert r.status_code == 422

    def test_task_invalid_priority(self, client):
        r = client.post("/api/v1/companies/1/tasks", json={"priority": "urgent"})
        assert r.status_code == 422

    def test_task_invalid_call_type(self, client):
        """A2: task_type 'call' удалён из допустимых значений."""
        r = client.post("/api/v1/companies/1/tasks", json={"task_type": "call"})
        assert r.status_code == 422


class TestJsonExtractFilters:
    """A3: Фильтры has_telegram / has_whatsapp через json_extract."""

    def test_filter_has_telegram(self, client, db_session):
        create_company(db_session, messengers={"telegram": "t.me/test"})
        db_session.commit()
        r = client.get("/api/v1/companies?has_telegram=1")
        assert r.status_code == 200
        assert r.json()["total"] == 1

    def test_filter_has_telegram_empty_value(self, client, db_session):
        """telegram: '' не считается наличием мессенджера."""
        create_company(db_session, messengers={"telegram": ""})
        db_session.commit()
        r = client.get("/api/v1/companies?has_telegram=1")
        assert r.status_code == 200
        assert r.json()["total"] == 0

    def test_filter_no_telegram(self, client, db_session):
        create_company(db_session, messengers={"whatsapp": "wa.me/79001234567"})
        db_session.commit()
        r = client.get("/api/v1/companies?has_telegram=0")
        assert r.status_code == 200
        assert r.json()["total"] == 1

    def test_filter_has_whatsapp(self, client, db_session):
        create_company(db_session, messengers={"whatsapp": "wa.me/79001234567"})
        db_session.commit()
        r = client.get("/api/v1/companies?has_whatsapp=1")
        assert r.status_code == 200
        assert r.json()["total"] == 1

    def test_filter_has_whatsapp_empty_value(self, client, db_session):
        """whatsapp: '' не считается наличием мессенджера."""
        create_company(db_session, messengers={"whatsapp": ""})
        db_session.commit()
        r = client.get("/api/v1/companies?has_whatsapp=1")
        assert r.status_code == 200
        assert r.json()["total"] == 0

    def test_filter_no_whatsapp(self, client, db_session):
        create_company(db_session, messengers={"telegram": "t.me/test"})
        db_session.commit()
        r = client.get("/api/v1/companies?has_whatsapp=0")
        assert r.status_code == 200
        assert r.json()["total"] == 1


class TestTemplatesCrud:
    """B1: CRUD шаблонов."""

    def test_list_templates(self, client):
        """Сидимые шаблоны из conftest возвращаются."""
        r = client.get("/api/v1/templates")
        assert r.status_code == 200
        names = [t["name"] for t in r.json()]
        assert "cold_email_1" in names
        assert "tg_intro" in names

    def test_get_template(self, client):
        r = client.get("/api/v1/templates/cold_email_1")
        assert r.status_code == 200
        assert r.json()["channel"] == "email"
        assert "{from_name}" in r.json()["body"]

    def test_get_template_not_found(self, client):
        r = client.get("/api/v1/templates/nonexistent")
        assert r.status_code == 404

    def test_create_template(self, client):
        r = client.post("/api/v1/templates", json={
            "name": "follow_up_email",
            "channel": "email",
            "subject": "Following up",
            "body": "Hi {from_name}, checking in about {company_name}.",
        })
        assert r.status_code == 201
        assert r.json()["ok"] is True

        # Проверяем что появился в списке
        r = client.get("/api/v1/templates/follow_up_email")
        assert r.status_code == 200
        assert r.json()["body"] == "Hi {from_name}, checking in about {company_name}."

    def test_create_template_duplicate(self, client):
        """Нельзя создать шаблон с существующим name."""
        r = client.post("/api/v1/templates", json={
            "name": "cold_email_1",
            "channel": "email",
            "body": "dup",
        })
        assert r.status_code == 409

    def test_create_template_invalid_name(self, client):
        """name должен соответствовать pattern ^[a-z0-9_]+$."""
        r = client.post("/api/v1/templates", json={
            "name": "My Template!",
            "channel": "email",
            "body": "test",
        })
        assert r.status_code == 422

    def test_create_template_empty_body(self, client):
        r = client.post("/api/v1/templates", json={
            "name": "empty_body",
            "channel": "tg",
            "body": "",
        })
        assert r.status_code == 422

    def test_update_template(self, client):
        r = client.put("/api/v1/templates/tg_intro", json={
            "body": "Updated body for {company_name}.",
        })
        assert r.status_code == 200
        assert r.json()["ok"] is True

        r = client.get("/api/v1/templates/tg_intro")
        assert r.json()["body"] == "Updated body for {company_name}."

    def test_update_template_not_found(self, client):
        r = client.put("/api/v1/templates/nonexistent", json={"body": "x"})
        assert r.status_code == 404

    def test_delete_template(self, client):
        r = client.delete("/api/v1/templates/tg_intro")
        assert r.status_code == 200

        r = client.get("/api/v1/templates/tg_intro")
        assert r.status_code == 404

    def test_delete_template_not_found(self, client):
        r = client.delete("/api/v1/templates/nonexistent")
        assert r.status_code == 404

    def test_delete_template_active_campaign(self, client, db_session):
        """Нельзя удалить шаблон, используемый в активной кампании."""
        from granite.database import CrmEmailCampaignRow
        campaign = CrmEmailCampaignRow(
            name="Active", template_name="cold_email_1", status="running",
        )
        db_session.add(campaign)
        db_session.commit()

        r = client.delete("/api/v1/templates/cold_email_1")
        assert r.status_code == 409
        assert "active campaign" in r.json()["detail"]


class TestStatsEndpoint:
    """B2: GET /stats."""

    def test_stats_empty(self, client):
        r = client.get("/api/v1/stats")
        assert r.status_code == 200
        data = r.json()
        assert data["total_companies"] == 0
        assert data["funnel"] == {}
        assert data["segments"] == {}
        assert data["top_cities"] == []
        assert data["with_telegram"] == 0
        assert data["with_email"] == 0

    def test_stats_with_data(self, client, db_session):
        create_company(db_session, city="Москва", messengers={"telegram": "t.me/a"})
        create_company(db_session, city="Казань", messengers={"whatsapp": "wa.me/1"}, crm_score=30)
        db_session.commit()

        r = client.get("/api/v1/stats")
        assert r.status_code == 200
        data = r.json()
        assert data["total_companies"] == 2
        assert data["with_telegram"] == 1
        assert data["with_whatsapp"] == 1
        assert len(data["top_cities"]) == 2

    def test_stats_filter_by_city(self, client, db_session):
        create_company(db_session, city="Москва")
        create_company(db_session, city="Казань")
        db_session.commit()

        r = client.get("/api/v1/stats?city=Москва")
        assert r.status_code == 200
        assert r.json()["total_companies"] == 1


class TestStopAutomationGuard:
    """B3: PATCH /companies/{id} guard при stop_automation=True."""

    def test_stop_automation_succeeds(self, client, db_session):
        cid = create_company(db_session)
        db_session.commit()

        r = client.patch(f"/api/v1/companies/{cid}", json={"stop_automation": True})
        assert r.status_code == 200
        assert r.json()["ok"] is True

    def test_stop_automation_logs_active_emails(self, client, db_session):
        """B3: при наличии активных email_logs — логируется, но не блокируется."""
        from granite.database import CrmEmailLogRow
        cid = create_company(db_session)
        log = CrmEmailLogRow(
            company_id=cid, email_to="info@test.ru",
            status="sent", tracking_id="test-uuid",
        )
        db_session.add(log)
        db_session.commit()

        # PATCH с stop_automation=True — должен пройти (200)
        r = client.patch(f"/api/v1/companies/{cid}", json={"stop_automation": True})
        assert r.status_code == 200
        assert r.json()["ok"] is True


class TestCampaignWatchdog:
    """D1: POST /campaigns/stale — сброс застрявших кампаний."""

    def _make_campaign(self, db_session, *, status="running",
                       created_at=None, started_at=None, updated_at=None):
        from granite.database import CrmEmailCampaignRow
        c = CrmEmailCampaignRow(
            name=f"Test {status}", template_name="cold_email_1",
            status=status, created_at=created_at,
            started_at=started_at, updated_at=updated_at,
        )
        db_session.add(c)
        db_session.flush()
        return c

    def test_stale_running_reset(self, client, db_session, monkeypatch):
        """Кампания с устаревшим created_at сбрасывается в paused."""
        monkeypatch.setenv("STALE_CAMPAIGN_MINUTES", "5")
        old_time = datetime.now(timezone.utc) - timedelta(minutes=10)
        self._make_campaign(db_session, status="running", created_at=old_time)
        db_session.commit()

        r = client.post("/api/v1/campaigns/stale")
        assert r.status_code == 200
        data = r.json()
        assert data["count"] == 1
        assert data["reset"][0]["name"] == "Test running"

        # Проверяем что статус действительно changed
        from granite.database import CrmEmailCampaignRow
        c = db_session.query(CrmEmailCampaignRow).first()
        assert c.status == "paused"

    def test_fresh_running_not_reset(self, client, db_session, monkeypatch):
        """Свежая кампания (created 1 мин назад) НЕ сбрасывается."""
        monkeypatch.setenv("STALE_CAMPAIGN_MINUTES", "5")
        fresh_time = datetime.now(timezone.utc) - timedelta(minutes=1)
        self._make_campaign(db_session, status="running", created_at=fresh_time)
        db_session.commit()

        r = client.post("/api/v1/campaigns/stale")
        assert r.status_code == 200
        assert r.json()["count"] == 0

    def test_no_running_campaigns(self, client, db_session, monkeypatch):
        """Нет running кампаний — count=0."""
        monkeypatch.setenv("STALE_CAMPAIGN_MINUTES", "5")
        old_time = datetime.now(timezone.utc) - timedelta(minutes=10)
        self._make_campaign(db_session, status="completed", created_at=old_time)
        self._make_campaign(db_session, status="draft", created_at=old_time)
        db_session.commit()

        r = client.post("/api/v1/campaigns/stale")
        assert r.status_code == 200
        assert r.json()["count"] == 0

    def test_updated_at_takes_priority(self, client, db_session, monkeypatch):
        """Если updated_at свежий — кампания НЕ сбрасывается, даже если started_at старый."""
        monkeypatch.setenv("STALE_CAMPAIGN_MINUTES", "5")
        old_started = datetime.now(timezone.utc) - timedelta(minutes=20)
        fresh_updated = datetime.now(timezone.utc) - timedelta(minutes=1)
        self._make_campaign(
            db_session, status="running",
            started_at=old_started, updated_at=fresh_updated,
        )
        db_session.commit()

        r = client.post("/api/v1/campaigns/stale")
        assert r.status_code == 200
        assert r.json()["count"] == 0

    def test_started_at_fallback(self, client, db_session, monkeypatch):
        """Если updated_at=None, но started_at старый — кампания сбрасывается."""
        monkeypatch.setenv("STALE_CAMPAIGN_MINUTES", "5")
        old_started = datetime.now(timezone.utc) - timedelta(minutes=10)
        self._make_campaign(
            db_session, status="running", started_at=old_started,
        )
        db_session.commit()

        r = client.post("/api/v1/campaigns/stale")
        assert r.status_code == 200
        assert r.json()["count"] == 1


class TestSeedUpsert:
    """D2: seed_crm_templates.py использует UPSERT (обновление существующих)."""

    def test_upsert_existing_template(self, db_session):
        """Существующий шаблон обновляется, а не пропускается."""
        from granite.database import CrmTemplateRow
        from scripts.seed_crm_templates import _apply_templates

        # Создаём шаблон вручную
        t = CrmTemplateRow(
            name="cold_email_1", channel="email",
            subject="Old subject", body="Old body",
            description="Old desc",
        )
        db_session.add(t)
        db_session.commit()

        inserted, updated = _apply_templates(db_session)
        assert inserted == 5  # остальные 5 шаблонов созданы
        assert updated == 1  # cold_email_1 обновлён

        # Проверяем что cold_email_1 обновился
        row = db_session.query(CrmTemplateRow).filter_by(name="cold_email_1").first()
        assert row.body != "Old body"
        assert "ретуш" in row.body
        assert row.subject != "Old subject"

    def test_upsert_creates_all_new(self, db_session):
        """На пустой БД — все 6 шаблонов создаются."""
        from granite.database import CrmTemplateRow
        from scripts.seed_crm_templates import _apply_templates

        inserted, updated = _apply_templates(db_session)
        assert inserted == 6
        assert updated == 0

        names = {r[0] for r in db_session.query(CrmTemplateRow.name).all()}
        assert names == {
            "cold_email_1", "follow_up_email",
            "tg_intro", "tg_follow_up",
            "wa_intro", "wa_follow_up",
        }

    def test_upsert_idempotent(self, db_session):
        """Повторный запуск — 0 inserted, 6 updated (без дублей)."""
        from granite.database import CrmTemplateRow
        from scripts.seed_crm_templates import _apply_templates

        inserted1, updated1 = _apply_templates(db_session)
        assert inserted1 == 6
        assert updated1 == 0

        inserted2, updated2 = _apply_templates(db_session)
        assert inserted2 == 0
        assert updated2 == 6

        total = db_session.query(CrmTemplateRow).count()
        assert total == 6
