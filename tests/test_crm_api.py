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
        data = r.json()
        assert data["items"] == []
        assert data["total"] == 0


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
        data = r.json()
        names = [t["name"] for t in data["items"]]
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
        assert "active campaign" in r.json()["error"]


class TestStatsEndpoint:
    """B2: GET /stats."""

    def test_stats_empty(self, client):
        r = client.get("/api/v1/stats")
        assert r.status_code == 200
        data = r.json()
        assert data["total_companies"] == 0
        assert isinstance(data["funnel"], dict) and all(v == 0 for v in data["funnel"].values())
        assert isinstance(data["segments"], dict) and all(v == 0 for v in data["segments"].values())
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

    def test_email_templates_contain_url(self, db_session):
        """MISS-7: Email-шаблоны содержат ссылку monument-web."""
        from granite.database import CrmTemplateRow
        from scripts.seed_crm_templates import _apply_templates

        _apply_templates(db_session)
        email_templates = db_session.query(CrmTemplateRow).filter_by(channel="email").all()
        for t in email_templates:
            assert "monument-web" in t.body, f"{t.name} missing monument-web URL"

    def test_messenger_templates_no_url(self, db_session):
        """MISS-7: TG/WA-шаблоны НЕ содержат URL (лучше delivery rate)."""
        from granite.database import CrmTemplateRow
        from scripts.seed_crm_templates import _apply_templates

        _apply_templates(db_session)
        msg_templates = db_session.query(CrmTemplateRow).filter(
            CrmTemplateRow.channel.in_(["tg", "wa"])
        ).all()
        for t in msg_templates:
            assert "http" not in t.body, f"{t.name} should not contain URL"


class TestTasksWithCompany:
    """C1: GET /tasks с JOIN + GET /companies/{id}/tasks."""

    def test_list_tasks_includes_company_name(self, client, db_session):
        """GET /tasks возвращает company_name и company_city."""
        from tests.helpers import create_task
        cid = create_company(db_session, city="Омск")
        create_task(db_session, company_id=cid, title="Follow up")
        db_session.commit()

        r = client.get("/api/v1/tasks")
        assert r.status_code == 200
        items = r.json()["items"]
        assert len(items) == 1
        assert items[0]["company_name"] == "Test Company"
        assert items[0]["company_city"] == "Омск"

    def test_list_tasks_null_company(self, client, db_session):
        """Задача без компании: company_name=null, не падает."""
        from granite.database import CrmTaskRow
        task = CrmTaskRow(title="Orphan task", task_type="other", status="pending")
        db_session.add(task)
        db_session.commit()

        r = client.get("/api/v1/tasks?include_unlinked=true")
        assert r.status_code == 200
        orphans = [i for i in r.json()["items"] if i["title"] == "Orphan task"]
        assert len(orphans) == 1
        assert orphans[0]["company_name"] is None
        assert orphans[0]["company_city"] is None

    def test_list_tasks_filter_task_type(self, client, db_session):
        """GET /tasks?task_type=follow_up фильтрует корректно."""
        from tests.helpers import create_task
        cid = create_company(db_session)
        create_task(db_session, company_id=cid, title="Follow", task_type="follow_up")
        create_task(db_session, company_id=cid, title="Portfolio", task_type="send_portfolio")
        db_session.commit()

        r = client.get("/api/v1/tasks?task_type=follow_up")
        assert r.status_code == 200
        items = r.json()["items"]
        assert len(items) == 1
        assert items[0]["title"] == "Follow"

    def test_list_company_tasks(self, client, db_session):
        """GET /companies/{id}/tasks — 200 с задачами компании."""
        from tests.helpers import create_task
        cid = create_company(db_session)
        create_task(db_session, company_id=cid, title="Task A")
        create_task(db_session, company_id=cid, title="Task B")
        db_session.commit()

        r = client.get(f"/api/v1/companies/{cid}/tasks")
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2

    def test_list_company_tasks_404(self, client):
        """GET /companies/9999/tasks — 404."""
        r = client.get("/api/v1/companies/9999/tasks")
        assert r.status_code == 404

    def test_list_company_tasks_filter_status(self, client, db_session):
        """GET /companies/{id}/tasks?status=pending фильтрует по статусу."""
        from tests.helpers import create_task
        cid = create_company(db_session)
        create_task(db_session, company_id=cid, title="Pending", status="pending")
        create_task(db_session, company_id=cid, title="Done", status="done")
        db_session.commit()

        r = client.get(f"/api/v1/companies/{cid}/tasks?status=pending")
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 1
        assert data["items"][0]["title"] == "Pending"

    def test_pagination_total_correct(self, client, db_session):
        """total в GET /tasks считается корректно при JOIN."""
        from tests.helpers import create_task
        cid = create_company(db_session)
        for i in range(5):
            create_task(db_session, company_id=cid, title=f"Task {i}")
        db_session.commit()

        r = client.get("/api/v1/tasks?per_page=2&page=1")
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 5
        assert len(data["items"]) == 2


class TestFollowupPagination:
    """C2+C3: segment, region, пагинация /followup."""

    def _make_followup_companies(self, db_session, count, city="Москва"):
        """Создать N компаний с TG, готовых к follow-up (stage=new)."""
        cids = []
        for i in range(count):
            cid = create_company(
                db_session, city=city,
                messengers={"telegram": f"t.me/user{i}"},
            )
            cids.append(cid)
        db_session.commit()
        return cids

    def test_followup_pagination_page1(self, client, db_session):
        """page=1&per_page=3 из 5 записей — 3 items, total=5."""
        self._make_followup_companies(db_session, 5)
        r = client.get("/api/v1/followup?per_page=3&page=1")
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 5
        assert len(data["items"]) == 3
        assert data["page"] == 1
        assert data["per_page"] == 3

    def test_followup_pagination_page2(self, client, db_session):
        """page=2&per_page=3 из 5 — 2 items."""
        self._make_followup_companies(db_session, 5)
        r = client.get("/api/v1/followup?per_page=3&page=2")
        assert r.status_code == 200
        assert len(r.json()["items"]) == 2

    def test_followup_limit_compat(self, client, db_session):
        """?limit=2 (старый параметр) работает как per_page=2."""
        self._make_followup_companies(db_session, 5)
        r = client.get("/api/v1/followup?limit=2")
        assert r.status_code == 200
        assert len(r.json()["items"]) == 2

    def test_followup_segment_filter(self, client, db_session):
        """?segment=A фильтрует по сегменту."""
        create_company(db_session, segment="A", messengers={"telegram": "t.me/a"})
        create_company(db_session, segment="B", messengers={"telegram": "t.me/b"})
        db_session.commit()

        r = client.get("/api/v1/followup?segment=A")
        assert r.status_code == 200
        assert r.json()["total"] == 1

    def test_followup_segment_invalid(self, client):
        """?segment=Z — 422 (не в паттерне ABCD)."""
        r = client.get("/api/v1/followup?segment=Z")
        assert r.status_code == 422

    def test_followup_region_in_response(self, client, db_session):
        """Ответ содержит поле region."""
        create_company(db_session, messengers={"telegram": "t.me/x"})
        db_session.commit()

        r = client.get("/api/v1/followup")
        assert r.status_code == 200
        items = r.json()["items"]
        if items:
            assert "region" in items[0]


class TestMultipleCityFilter:
    """C4: множественный фильтр по городу."""

    def test_companies_single_city_compat(self, client, db_session):
        """?city=Москва — обратно совместимо."""
        create_company(db_session, city="Москва")
        create_company(db_session, city="Казань")
        db_session.commit()

        r = client.get("/api/v1/companies?city=Москва")
        assert r.status_code == 200
        assert r.json()["total"] == 1

    def test_companies_multiple_cities(self, client, db_session):
        """?city=Москва&city=Казань — обе компании."""
        create_company(db_session, city="Москва")
        create_company(db_session, city="Казань")
        create_company(db_session, city="Омск")
        db_session.commit()

        r = client.get("/api/v1/companies?city=Москва&city=Казань")
        assert r.status_code == 200
        assert r.json()["total"] == 2

    def test_companies_city_not_found(self, client, db_session):
        """?city=НесуществующийГород — total=0."""
        create_company(db_session)
        db_session.commit()

        r = client.get("/api/v1/companies?city=НесуществующийГород")
        assert r.status_code == 200
        assert r.json()["total"] == 0

    def test_companies_empty_city_ignored(self, client, db_session):
        """?city= (пустая строка) игнорируется — все компании."""
        create_company(db_session, city="Москва")
        db_session.commit()

        r = client.get("/api/v1/companies?city=")
        assert r.status_code == 200
        assert r.json()["total"] == 1

    def test_followup_multiple_cities(self, client, db_session):
        """?city=Москва&city=Казань в /followup."""
        create_company(db_session, city="Москва", messengers={"telegram": "t.me/a"})
        create_company(db_session, city="Казань", messengers={"telegram": "t.me/b"})
        create_company(db_session, city="Омск", messengers={"telegram": "t.me/c"})
        db_session.commit()

        r = client.get("/api/v1/followup?city=Москва&city=Казань")
        assert r.status_code == 200
        assert r.json()["total"] == 2

    def test_followup_single_city_compat(self, client, db_session):
        """?city=Москва в /followup — обратно совместимо."""
        create_company(db_session, city="Москва", messengers={"telegram": "t.me/a"})
        create_company(db_session, city="Казань", messengers={"telegram": "t.me/b"})
        db_session.commit()

        r = client.get("/api/v1/followup?city=Москва")
        assert r.status_code == 200
        assert r.json()["total"] == 1


class TestCitiesAndRegions:
    """S1.1: GET /cities и GET /regions."""

    def test_cities_empty(self, client):
        """Пустая БД — пустой список городов."""
        r = client.get("/api/v1/cities")
        assert r.status_code == 200
        data = r.json()
        assert data["items"] == []
        assert data["total"] == 0

    def test_cities_returns_unique(self, client, db_session):
        """Две компании в одном городе — один город в списке."""
        create_company(db_session, city="Москва")
        create_company(db_session, city="Москва")
        create_company(db_session, city="Казань")
        db_session.commit()

        r = client.get("/api/v1/cities")
        assert r.status_code == 200
        data = r.json()
        cities = data["items"]
        assert len(cities) == 2
        assert "Казань" in cities
        assert "Москва" in cities

    def test_cities_sorted(self, client, db_session):
        """Города отсортированы по алфавиту."""
        create_company(db_session, city="Ярославль")
        create_company(db_session, city="Астрахань")
        db_session.commit()

        r = client.get("/api/v1/cities")
        data = r.json()
        assert data["items"] == ["Астрахань", "Ярославль"]

    def test_regions_empty(self, client):
        r = client.get("/api/v1/regions")
        assert r.status_code == 200
        data = r.json()
        assert data["items"] == []
        assert data["total"] == 0

    def test_regions_returns_unique(self, client, db_session):
        create_company(db_session, region="Московская обл.")
        create_company(db_session, region="Московская обл.")
        create_company(db_session, region="Татарстан")
        db_session.commit()

        r = client.get("/api/v1/regions")
        data = r.json()
        regions = data["items"]
        assert len(regions) == 2
        assert "Татарстан" in regions
        assert "Московская обл." in regions


class TestTouchesPagination:
    """S1.2: Пагинация GET /companies/{id}/touches."""

    def test_touches_paginated(self, client, db_session):
        """Пагинация касаний: page=1&per_page=2 из 3 — 2 items."""
        cid = create_company(db_session)
        from granite.database import CrmTouchRow
        for i in range(3):
            t = CrmTouchRow(
                company_id=cid, channel="email", direction="outgoing",
                subject=f"Subj {i}", body=f"Body {i}",
            )
            db_session.add(t)
        db_session.commit()

        r = client.get(f"/api/v1/companies/{cid}/touches?page=1&per_page=2")
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 3
        assert len(data["items"]) == 2
        assert data["page"] == 1
        assert data["per_page"] == 2

    def test_touches_page2(self, client, db_session):
        """page=2&per_page=2 из 3 — 1 item."""
        cid = create_company(db_session)
        from granite.database import CrmTouchRow
        for i in range(3):
            t = CrmTouchRow(
                company_id=cid, channel="email", direction="outgoing",
                subject=f"Subj {i}",
            )
            db_session.add(t)
        db_session.commit()

        r = client.get(f"/api/v1/companies/{cid}/touches?page=2&per_page=2")
        data = r.json()
        assert len(data["items"]) == 1

    def test_touches_empty(self, client, db_session):
        """Нет касаний — total=0, items=[]."""
        cid = create_company(db_session)
        db_session.commit()

        r = client.get(f"/api/v1/companies/{cid}/touches")
        data = r.json()
        assert data["total"] == 0
        assert data["items"] == []


class TestTouchGetAndDelete:
    """S1.3: GET /companies/{id}/touches/{touch_id} и DELETE /touches/{id}."""

    def _create_touch(self, db_session, company_id):
        from granite.database import CrmTouchRow
        t = CrmTouchRow(
            company_id=company_id, channel="email",
            direction="outgoing", subject="Test subj", body="Test body",
        )
        db_session.add(t)
        db_session.flush()
        return t.id

    def test_get_touch(self, client, db_session):
        """Получить конкретное касание."""
        cid = create_company(db_session)
        tid = self._create_touch(db_session, cid)
        db_session.commit()

        r = client.get(f"/api/v1/companies/{cid}/touches/{tid}")
        assert r.status_code == 200
        data = r.json()
        assert data["id"] == tid
        assert data["channel"] == "email"
        assert data["subject"] == "Test subj"

    def test_get_touch_wrong_company(self, client, db_session):
        """Касание чужой компании — 404."""
        cid1 = create_company(db_session, city="Казань")
        cid2 = create_company(db_session, city="Омск")
        tid = self._create_touch(db_session, cid1)
        db_session.commit()

        r = client.get(f"/api/v1/companies/{cid2}/touches/{tid}")
        assert r.status_code == 404

    def test_get_touch_not_found(self, client):
        """Несуществующее касание — 404."""
        r = client.get("/api/v1/companies/1/touches/9999")
        assert r.status_code == 404

    def test_delete_touch(self, client, db_session):
        """Удалить касание."""
        cid = create_company(db_session)
        tid = self._create_touch(db_session, cid)
        db_session.commit()

        r = client.delete(f"/api/v1/touches/{tid}")
        assert r.status_code == 200
        assert r.json()["ok"] is True

        # Проверяем что касание удалено
        r = client.get(f"/api/v1/companies/{cid}/touches")
        assert r.json()["total"] == 0

    def test_delete_touch_not_found(self, client):
        """Несуществующее касание — 404."""
        r = client.delete("/api/v1/touches/9999")
        assert r.status_code == 404


class TestCampaignPatchAndDelete:
    """S1.4: PATCH /campaigns/{id} и DELETE /campaigns/{id}."""

    def _create_campaign(self, db_session, **kwargs):
        from granite.database import CrmEmailCampaignRow
        defaults = {"name": "Test Campaign", "template_name": "cold_email_1", "status": "draft"}
        defaults.update(kwargs)
        c = CrmEmailCampaignRow(**defaults)
        db_session.add(c)
        db_session.flush()
        return c.id

    def test_patch_campaign_name(self, client, db_session):
        """Обновить имя кампании-черновика."""
        cid = self._create_campaign(db_session)
        db_session.commit()

        r = client.patch(f"/api/v1/campaigns/{cid}", json={"name": "Updated Name"})
        assert r.status_code == 200
        assert r.json()["ok"] is True

        r = client.get(f"/api/v1/campaigns/{cid}")
        assert r.json()["name"] == "Updated Name"

    def test_patch_campaign_template(self, client, db_session):
        """Обновить template_name кампании."""
        cid = self._create_campaign(db_session)
        db_session.commit()

        r = client.patch(f"/api/v1/campaigns/{cid}", json={"template_name": "tg_intro"})
        assert r.status_code == 200

        r = client.get(f"/api/v1/campaigns/{cid}")
        assert r.json()["template_name"] == "tg_intro"

    def test_patch_campaign_bad_template(self, client, db_session):
        """Несуществующий шаблон — 404."""
        cid = self._create_campaign(db_session)
        db_session.commit()

        r = client.patch(f"/api/v1/campaigns/{cid}", json={"template_name": "nonexistent"})
        assert r.status_code == 404

    def test_patch_running_campaign_rejected(self, client, db_session):
        """Нельзя обновить запущенную кампанию."""
        cid = self._create_campaign(db_session, status="running")
        db_session.commit()

        r = client.patch(f"/api/v1/campaigns/{cid}", json={"name": "New Name"})
        assert r.status_code == 409
        assert "running" in r.json()["error"]

    def test_patch_completed_campaign_rejected(self, client, db_session):
        """Нельзя обновить завершённую кампанию."""
        cid = self._create_campaign(db_session, status="completed")
        db_session.commit()

        r = client.patch(f"/api/v1/campaigns/{cid}", json={"name": "New Name"})
        assert r.status_code == 409

    def test_patch_paused_campaign_allowed(self, client, db_session):
        """Приостановленную кампанию можно обновить."""
        cid = self._create_campaign(db_session, status="paused")
        db_session.commit()

        r = client.patch(f"/api/v1/campaigns/{cid}", json={"name": "Resumed"})
        assert r.status_code == 200

    def test_patch_not_found(self, client):
        r = client.patch("/api/v1/campaigns/9999", json={"name": "x"})
        assert r.status_code == 404

    def test_delete_draft_campaign(self, client, db_session):
        """Удалить черновик — 200."""
        cid = self._create_campaign(db_session)
        db_session.commit()

        r = client.delete(f"/api/v1/campaigns/{cid}")
        assert r.status_code == 200
        assert r.json()["ok"] is True

        r = client.get(f"/api/v1/campaigns/{cid}")
        assert r.status_code == 404

    def test_delete_running_rejected(self, client, db_session):
        """Нельзя удалить запущенную кампанию."""
        cid = self._create_campaign(db_session, status="running")
        db_session.commit()

        r = client.delete(f"/api/v1/campaigns/{cid}")
        assert r.status_code == 409

    def test_delete_completed_rejected(self, client, db_session):
        """Нельзя удалить завершённую кампанию."""
        cid = self._create_campaign(db_session, status="completed")
        db_session.commit()

        r = client.delete(f"/api/v1/campaigns/{cid}")
        assert r.status_code == 409

    def test_delete_paused_rejected(self, client, db_session):
        """Нельзя удалить приостановленную кампанию."""
        cid = self._create_campaign(db_session, status="paused")
        db_session.commit()

        r = client.delete(f"/api/v1/campaigns/{cid}")
        assert r.status_code == 409

    def test_delete_not_found(self, client):
        r = client.delete("/api/v1/campaigns/9999")
        assert r.status_code == 404


class TestTemplateChannelFilter:
    """S1.6: GET /templates?channel=email|tg|wa."""

    def test_filter_channel_email(self, client, db_session):
        """Фильтр по channel=email — только email-шаблоны."""
        from granite.database import CrmTemplateRow
        db_session.add(CrmTemplateRow(
            name="tg_only", channel="tg", body="TG template",
        ))
        db_session.commit()

        r = client.get("/api/v1/templates?channel=email")
        assert r.status_code == 200
        templates = r.json()["items"]
        assert len(templates) >= 1
        assert all(t["channel"] == "email" for t in templates)

    def test_filter_channel_tg(self, client, db_session):
        """Фильтр по channel=tg — только tg-шаблоны."""
        r = client.get("/api/v1/templates?channel=tg")
        assert r.status_code == 200
        templates = r.json()["items"]
        assert len(templates) >= 1
        assert all(t["channel"] == "tg" for t in templates)

    def test_filter_no_match(self, client, db_session):
        """Фильтр по каналу без результатов — пустой список."""
        r = client.get("/api/v1/templates?channel=wa")
        assert r.status_code == 200
        data = r.json()
        assert data["items"] == []
        assert data["total"] == 0

    def test_filter_invalid_channel(self, client):
        """Невалидный channel — 422."""
        r = client.get("/api/v1/templates?channel=invalid")
        assert r.status_code == 422

    def test_no_filter_returns_all(self, client):
        """Без фильтра — все шаблоны."""
        r = client.get("/api/v1/templates")
        assert r.status_code == 200
        data = r.json()
        assert data["total"] >= 2  # cold_email_1 + tg_intro из conftest
        assert len(data["items"]) >= 2


class TestExportCsv:
    """S1.7: GET /api/v1/export/{city}.csv."""

    def test_export_csv_success(self, client, db_session):
        """Успешный экспорт города в CSV."""
        create_company(db_session, city="Омск", crm_score=30)
        db_session.commit()

        r = client.get("/api/v1/export/Омск.csv")
        assert r.status_code == 200
        assert "text/csv" in r.headers["content-type"]
        assert "attachment" in r.headers["content-disposition"]

        content = r.content.decode("utf-8-sig")
        assert "id" in content  # CSV header
        assert "Омск" in content

    def test_export_csv_no_data(self, client, db_session):
        """Нет enriched данных для города — 404."""
        create_company(db_session, city="Нижневартовск", crm_score=0)
        db_session.commit()

        r = client.get("/api/v1/export/Нижневартовск.csv")
        assert r.status_code == 404

    def test_export_csv_city_not_found(self, client):
        """Город не существует — 404."""
        r = client.get("/api/v1/export/НеизвестныйГород.csv")
        assert r.status_code == 404

    def test_export_csv_utf8_bom(self, client, db_session):
        """CSV начинается с BOM для корректного отображения в Excel."""
        create_company(db_session, city="Самара", crm_score=20)
        db_session.commit()

        r = client.get("/api/v1/export/Самара.csv")
        assert r.status_code == 200
        # UTF-8 BOM: 0xEF, 0xBB, 0xBF
        assert r.content[:3] == b'\xef\xbb\xbf'


class TestCreateCampaignTemplateValidation:
    """S1.5 (HIGH-7): Валидация template_name при создании кампании."""

    def test_create_campaign_bad_template(self, client):
        """Несуществующий шаблон — 404."""
        r = client.post("/api/v1/campaigns", json={
            "name": "Bad Campaign",
            "template_name": "nonexistent_template",
        })
        assert r.status_code == 404
        assert "Template" in r.json()["error"]

    def test_create_campaign_valid_template(self, client):
        """Существующий шаблон — 201."""
        r = client.post("/api/v1/campaigns", json={
            "name": "Good Campaign",
            "template_name": "cold_email_1",
        })
        assert r.status_code == 201
        assert r.json()["id"] is not None


# ============================================================
# Phase 3: API — недостающие эндпоинты для фронтенда
# ============================================================


class TestPipelineStatus:
    """Phase 3.1: GET /pipeline/status — статус пайплайна по городам."""

    def test_pipeline_status_empty(self, client):
        """Пустая БД — total_cities=0, cities=[]."""
        r = client.get("/api/v1/pipeline/status")
        assert r.status_code == 200
        data = r.json()
        assert data["total_cities"] == 0
        assert data["cities"] == []

    def test_pipeline_status_with_data(self, client, db_session):
        """Город с enriched компаниями — stage=enriched, is_running=False."""
        create_company(db_session, city="Омск", segment="A")
        create_company(db_session, city="Омск", segment="B")
        db_session.commit()

        r = client.get("/api/v1/pipeline/status")
        assert r.status_code == 200
        data = r.json()
        assert data["total_cities"] >= 1

        omsk = next((c for c in data["cities"] if c["city"] == "Омск"), None)
        assert omsk is not None
        assert omsk["stage"] == "enriched"
        assert omsk["is_running"] is False
        assert omsk["company_count"] >= 2
        assert omsk["enriched_count"] >= 2
        assert omsk["enrichment_progress"] > 0

    def test_pipeline_status_is_running_default(self, client, db_session):
        """is_running=False по умолчанию (нет запущенных пайплайнов)."""
        create_company(db_session, city="Казань")
        db_session.commit()

        r = client.get("/api/v1/pipeline/status")
        assert r.status_code == 200
        for city in r.json()["cities"]:
            assert city["is_running"] is False

    def test_pipeline_status_limit(self, client, db_session):
        """limit=1 — только один город в ответе."""
        create_company(db_session, city="Астрахань")
        create_company(db_session, city="Ярославль")
        db_session.commit()

        r = client.get("/api/v1/pipeline/status?limit=1")
        assert r.status_code == 200
        data = r.json()
        assert data["returned"] <= 1

    def test_pipeline_status_segments(self, client, db_session):
        """segments dict содержит распределение по сегментам."""
        create_company(db_session, city="Тверь", segment="A")
        create_company(db_session, city="Тверь", segment="A")
        create_company(db_session, city="Тверь", segment="B")
        db_session.commit()

        r = client.get("/api/v1/pipeline/status")
        tver = next((c for c in r.json()["cities"] if c["city"] == "Тверь"), None)
        assert tver is not None
        assert tver["segments"].get("A", 0) == 2
        assert tver["segments"].get("B", 0) == 1


class TestPipelineCities:
    """Phase 3.1: GET /pipeline/cities — справочник городов."""

    def test_pipeline_cities_empty(self, client):
        """Пустая БД — пустой список."""
        r = client.get("/api/v1/pipeline/cities")
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 0
        assert data["cities"] == []

    def test_pipeline_cities_returns_ref(self, client, db_session):
        """Города из cities_ref таблицы (если есть)."""
        from granite.database import CityRefRow
        city = CityRefRow(name="Омск", region="Омская обл.", is_populated=True)
        db_session.add(city)
        db_session.commit()

        r = client.get("/api/v1/pipeline/cities")
        assert r.status_code == 200
        data = r.json()
        assert data["total"] >= 1
        names = [c["name"] for c in data["cities"]]
        assert "Омск" in names

    def test_pipeline_cities_fields(self, client, db_session):
        """Поля name, region, is_populated, is_doppelganger."""
        from granite.database import CityRefRow
        db_session.add(CityRefRow(
            name="Москва", region="Москва", is_populated=True, is_doppelganger=False,
        ))
        db_session.commit()

        r = client.get("/api/v1/pipeline/cities")
        cities = r.json()["cities"]
        msk = next((c for c in cities if c["name"] == "Москва"), None)
        assert msk is not None
        assert msk["region"] == "Москва"
        assert msk["is_populated"] is True
        assert msk["is_doppelganger"] is False


class TestSimilarCompanies:
    """Phase 3.3: GET /companies/{id}/similar — похожие компании."""

    def test_similar_no_matches(self, client, db_session):
        """Компания без совпадений — similar=[], total=0."""
        cid = create_company(db_session, city="Омск", name_best="Уникальная")
        db_session.commit()

        r = client.get(f"/api/v1/companies/{cid}/similar")
        assert r.status_code == 200
        data = r.json()
        assert data["company_id"] == cid
        assert data["similar"] == []
        assert data["total"] == 0

    def test_similar_shared_phone(self, client, db_session):
        """Компании с общим телефоном — similar по shared_phone."""
        cid1 = create_company(
            db_session, city="Омск", name_best="Компания А",
            phones=["79001234567", "79009999999"],
        )
        cid2 = create_company(
            db_session, city="Омск", name_best="Компания Б",
            phones=["79001234567"],
        )
        db_session.commit()

        r = client.get(f"/api/v1/companies/{cid1}/similar")
        assert r.status_code == 200
        data = r.json()
        assert data["total"] >= 1
        similar_ids = [s["id"] for s in data["similar"]]
        assert cid2 in similar_ids

        # match_reason должен содержать shared_phone
        sim = next(s for s in data["similar"] if s["id"] == cid2)
        assert "shared_phone" in sim["match_reason"]

    def test_similar_shared_domain(self, client, db_session):
        """Компании с общим доменом — similar по shared_domain."""
        cid1 = create_company(
            db_session, city="Казань", name_best="Филиал 1",
            website="https://granit.ru/about",
        )
        cid2 = create_company(
            db_session, city="Омск", name_best="Филиал 2",
            website="https://granit.ru/contacts",
        )
        db_session.commit()

        r = client.get(f"/api/v1/companies/{cid1}/similar")
        assert r.status_code == 200
        data = r.json()
        similar_ids = [s["id"] for s in data["similar"]]
        assert cid2 in similar_ids

    def test_similar_company_not_found(self, client):
        """Несуществующая компания — 404."""
        r = client.get("/api/v1/companies/9999/similar")
        assert r.status_code == 404

    def test_similar_limit_param(self, client, db_session):
        """limit ограничивает количество результатов."""
        # Создаём компанию и несколько "похожих" через общий телефон
        cid = create_company(
            db_session, city="Москва", name_best="Главная",
            phones=["79001112233"],
        )
        for i in range(5):
            create_company(
                db_session, city="Москва", name_best=f"Дубль {i}",
                phones=["79001112233"],
            )
        db_session.commit()

        r = client.get(f"/api/v1/companies/{cid}/similar?limit=2")
        assert r.status_code == 200
        data = r.json()
        assert len(data["similar"]) <= 2

    def test_similar_response_schema(self, client, db_session):
        """Проверяем поля ответа: company_id, similar, total."""
        cid = create_company(db_session)
        db_session.commit()

        r = client.get(f"/api/v1/companies/{cid}/similar")
        data = r.json()
        assert "company_id" in data
        assert "similar" in data
        assert "total" in data


class TestMergeCompanies:
    """Phase 3.4: PATCH /companies/{id}/merge — слияние компаний."""

    def test_merge_basic(self, client, db_session):
        """Простое слияние двух компаний."""
        target_id = create_company(
            db_session, city="Омск", name_best="Target",
            phones=["79001111111"], emails=["info@target.ru"],
        )
        source_id = create_company(
            db_session, city="Омск", name_best="Source",
            phones=["79002222222"], emails=["info@source.ru"],
        )
        db_session.commit()

        r = client.patch(f"/api/v1/companies/{target_id}/merge", json={
            "source_ids": [source_id],
        })
        assert r.status_code == 200
        assert r.json()["ok"] is True

        # Проверяем, что target унаследовал телефоны и emails source
        # Обновляем объекты из БД (API работает через другую сессию)
        from granite.database import CompanyRow
        db_session.expire_all()
        target = db_session.get(CompanyRow, target_id)
        assert "79002222222" in (target.phones or [])
        assert "info@source.ru" in (target.emails or [])

        # Source помечен как merged
        source = db_session.get(CompanyRow, source_id)
        assert source.merged_into == target_id
        assert source.deleted_at is not None

    def test_merge_self_ignored(self, client, db_session):
        """Слияние саму с собой игнорируется."""
        cid = create_company(db_session)
        db_session.commit()

        r = client.patch(f"/api/v1/companies/{cid}/merge", json={
            "source_ids": [cid],
        })
        assert r.status_code == 200
        assert r.json()["ok"] is True

    def test_merge_target_not_found(self, client):
        """Target не найден — 404."""
        r = client.patch("/api/v1/companies/9999/merge", json={
            "source_ids": [1],
        })
        assert r.status_code == 404

    def test_merge_source_not_found_skipped(self, client, db_session):
        """Несуществующий source_id пропускается, не ломает запрос."""
        target_id = create_company(db_session)
        db_session.commit()

        r = client.patch(f"/api/v1/companies/{target_id}/merge", json={
            "source_ids": [99999],
        })
        assert r.status_code == 200
        assert r.json()["ok"] is True

    def test_merge_dedup_phones(self, client, db_session):
        """При слиянии дублирующиеся телефоны не добавляются."""
        target_id = create_company(
            db_session, phones=["79001111111", "79003333333"],
        )
        source_id = create_company(
            db_session, phones=["79001111111", "79004444444"],
        )
        db_session.commit()

        r = client.patch(f"/api/v1/companies/{target_id}/merge", json={
            "source_ids": [source_id],
        })
        assert r.status_code == 200

        from granite.database import CompanyRow
        db_session.expire_all()
        target = db_session.get(CompanyRow, target_id)
        # 79001111111 не дублируется
        phone_count = (target.phones or []).count("79001111111")
        assert phone_count == 1
        # 79004444444 добавлен
        assert "79004444444" in (target.phones or [])

    def test_merge_dedup_emails(self, client, db_session):
        """При слиянии дублирующиеся email не добавляются."""
        target_id = create_company(
            db_session, emails=["info@target.ru", "common@test.ru"],
        )
        source_id = create_company(
            db_session, emails=["common@test.ru", "info@source.ru"],
        )
        db_session.commit()

        r = client.patch(f"/api/v1/companies/{target_id}/merge", json={
            "source_ids": [source_id],
        })
        assert r.status_code == 200

        from granite.database import CompanyRow
        db_session.expire_all()
        target = db_session.get(CompanyRow, target_id)
        common_count = (target.emails or []).count("common@test.ru")
        assert common_count == 1
        assert "info@source.ru" in (target.emails or [])

    def test_merge_merged_from_recorded(self, client, db_session):
        """merged_from записывается в target."""
        target_id = create_company(db_session)
        source_id = create_company(db_session)
        db_session.commit()

        r = client.patch(f"/api/v1/companies/{target_id}/merge", json={
            "source_ids": [source_id],
        })
        assert r.status_code == 200

        from granite.database import CompanyRow
        db_session.expire_all()
        target = db_session.get(CompanyRow, target_id)
        assert source_id in (target.merged_from or [])

    def test_merge_multiple_sources(self, client, db_session):
        """Слияние нескольких source в один target."""
        target_id = create_company(
            db_session, phones=["79001111111"],
        )
        s1 = create_company(db_session, phones=["79002222222"])
        s2 = create_company(db_session, phones=["79003333333"])
        db_session.commit()

        r = client.patch(f"/api/v1/companies/{target_id}/merge", json={
            "source_ids": [s1, s2],
        })
        assert r.status_code == 200

        from granite.database import CompanyRow
        db_session.expire_all()
        target = db_session.get(CompanyRow, target_id)
        assert "79002222222" in (target.phones or [])
        assert "79003333333" in (target.phones or [])
