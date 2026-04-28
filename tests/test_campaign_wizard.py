"""Тесты для Campaign Wizard: A/B поля, filters, preview-recipients, validator_warnings, ab-stats."""
from granite.database import CrmEmailCampaignRow
from tests.helpers import create_company


class TestCampaignABSubjects:
    """Создание и обновление кампаний с A/B subject-полями."""

    def test_create_with_ab_subjects(self, client, db_session):
        """Создание кампании с subject_a и subject_b."""
        resp = client.post("/api/v1/campaigns", json={
            "name": "A/B Test Campaign",
            "template_name": "cold_email_1",
            "subject_a": "Тема варианта A",
            "subject_b": "Тема варианта B",
        })
        assert resp.status_code == 201, f"Got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data["ok"] is True
        assert data["id"] is not None

        detail = client.get(f"/api/v1/campaigns/{data['id']}")
        assert detail.status_code == 200
        d = detail.json()
        assert d["subject_a"] == "Тема варианта A"
        assert d["subject_b"] == "Тема варианта B"

    def test_create_without_ab(self, client, db_session):
        """Создание кампании без A/B — subject_a и subject_b = null."""
        resp = client.post("/api/v1/campaigns", json={
            "name": "Simple Campaign No AB",
            "template_name": "cold_email_1",
        })
        assert resp.status_code == 201
        data = resp.json()

        detail = client.get(f"/api/v1/campaigns/{data['id']}")
        d = detail.json()
        assert d["subject_a"] is None
        assert d["subject_b"] is None

    def test_update_subjects(self, client, db_session):
        """Обновление subject_a и subject_b через PATCH."""
        resp = client.post("/api/v1/campaigns", json={
            "name": "Update Subjects Test",
            "template_name": "cold_email_1",
        })
        assert resp.status_code == 201
        cid = resp.json()["id"]

        resp2 = client.patch(f"/api/v1/campaigns/{cid}", json={
            "subject_a": "New Subject A",
            "subject_b": "New Subject B",
        })
        assert resp2.status_code == 200

        detail = client.get(f"/api/v1/campaigns/{cid}")
        d = detail.json()
        assert d["subject_a"] == "New Subject A"
        assert d["subject_b"] == "New Subject B"

    def test_campaign_list_includes_ab_fields(self, client, db_session):
        """Список кампаний включает subject_a, subject_b, total_errors."""
        client.post("/api/v1/campaigns", json={
            "name": "List AB Fields Test",
            "template_name": "cold_email_1",
            "subject_a": "A",
            "subject_b": "B",
        })

        resp = client.get("/api/v1/campaigns")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) > 0
        item = data["items"][0]
        assert "subject_a" in item
        assert "subject_b" in item
        assert "total_errors" in item


class TestCampaignFilters:
    """Фильтры кампаний: city, segment, min_score, cities[]."""

    def test_update_filters(self, client, db_session):
        """Обновление filters через PATCH."""
        resp = client.post("/api/v1/campaigns", json={
            "name": "Filter Update Test",
            "template_name": "cold_email_1",
        })
        assert resp.status_code == 201
        cid = resp.json()["id"]

        resp2 = client.patch(f"/api/v1/campaigns/{cid}", json={
            "filters": {"city": "Москва", "segment": "A", "min_score": 50},
        })
        assert resp2.status_code == 200

        detail = client.get(f"/api/v1/campaigns/{cid}")
        d = detail.json()
        assert d["filters"]["city"] == "Москва"
        assert d["filters"]["segment"] == "A"
        assert d["filters"]["min_score"] == 50

    def test_multi_city_filter(self, client, db_session):
        """CampaignFilters принимает список cities."""
        resp = client.post("/api/v1/campaigns/preview-recipients", json={
            "cities": ["Москва", "СПб"],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "total" in data


class TestPreviewRecipients:
    """POST /campaigns/preview-recipients — предпросмотр получателей."""

    def test_preview_with_filters(self, client, db_session):
        """Предпросмотр получателей с фильтрами — возвращает total и sample."""
        create_company(db_session, city="Москва", segment="A")
        db_session.commit()

        resp = client.post("/api/v1/campaigns/preview-recipients", json={
            "city": "Москва",
            "segment": "A",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "total" in data
        assert "sample" in data
        assert isinstance(data["sample"], list)

    def test_preview_empty_filters(self, client, db_session):
        """Предпросмотр без фильтров."""
        resp = client.post("/api/v1/campaigns/preview-recipients", json={})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 0


class TestValidatorWarnings:
    """validator_warnings в деталях draft-кампании."""

    def test_warnings_on_zero_recipients(self, client, db_session):
        """Несуществующий город в фильтрах → предупреждение о 0 получателях."""
        resp = client.post("/api/v1/campaigns", json={
            "name": "Validator Warnings Test",
            "template_name": "cold_email_1",
            "filters": {"city": "НесуществующийГород12345"},
        })
        assert resp.status_code == 201
        cid = resp.json()["id"]

        detail = client.get(f"/api/v1/campaigns/{cid}")
        d = detail.json()
        assert isinstance(d["validator_warnings"], list)
        if d["preview_recipients"] == 0:
            assert any("Нет получателей" in w for w in d["validator_warnings"])

    def test_detail_includes_total_errors(self, client, db_session):
        """Детали кампании включают total_errors."""
        resp = client.post("/api/v1/campaigns", json={
            "name": "Total Errors Test",
            "template_name": "cold_email_1",
        })
        cid = resp.json()["id"]

        detail = client.get(f"/api/v1/campaigns/{cid}")
        d = detail.json()
        assert "total_errors" in d


class TestABStats:
    """GET /campaigns/{id}/ab-stats — статистика A/B теста."""

    def test_ab_stats_endpoint(self, client, db_session):
        """ab-stats возвращает 200 для кампании с A/B."""
        resp = client.post("/api/v1/campaigns", json={
            "name": "AB Stats Endpoint Test",
            "template_name": "cold_email_1",
            "subject_a": "Subject A",
            "subject_b": "Subject B",
        })
        cid = resp.json()["id"]

        resp2 = client.get(f"/api/v1/campaigns/{cid}/ab-stats")
        assert resp2.status_code == 200
