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

    # P4R-L8: Поиск по ID вместо [0]
    def test_campaign_list_includes_ab_fields(self, client, db_session):
        """Список кампаний включает subject_a, subject_b, total_errors, total_recipients."""
        resp = client.post("/api/v1/campaigns", json={
            "name": "List AB Fields Test",
            "template_name": "cold_email_1",
            "subject_a": "A",
            "subject_b": "B",
        })
        assert resp.status_code == 201
        cid = resp.json()["id"]

        list_resp = client.get("/api/v1/campaigns")
        assert list_resp.status_code == 200
        data = list_resp.json()
        # P4R-L8: Находим созданную кампанию по ID
        item = next((i for i in data["items"] if i["id"] == cid), None)
        assert item is not None, f"Created campaign {cid} not found in list"
        assert "subject_a" in item
        assert "subject_b" in item
        assert "total_errors" in item
        assert "total_recipients" in item  # P4R-M5


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
        # P4R-M6: preview возвращает is_approximate
        assert "is_approximate" in data


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

    # P4R-L7: Безусловный assert — убран условный if
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
        # P4R-L7: Безусловная проверка — фильтр по несуществующему городу должен давать 0
        assert d["preview_recipients"] == 0, (
            f"Expected 0 recipients for nonexistent city, got {d['preview_recipients']}"
        )
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

    # P4R-L11: Проверяем структуру AB-stats ответа
    def test_ab_stats_endpoint(self, client, db_session):
        """ab-stats возвращает 200 для кампании с A/B, проверяем структуру."""
        resp = client.post("/api/v1/campaigns", json={
            "name": "AB Stats Endpoint Test",
            "template_name": "cold_email_1",
            "subject_a": "Subject A",
            "subject_b": "Subject B",
        })
        cid = resp.json()["id"]

        resp2 = client.get(f"/api/v1/campaigns/{cid}/ab-stats")
        assert resp2.status_code == 200
        data = resp2.json()
        # P4R-L11: Проверяем структуру ответа
        assert "variants" in data
        assert "winner" in data
        assert "note" in data
        assert isinstance(data["variants"], dict)

    def test_ab_stats_no_ab_campaign(self, client, db_session):
        """ab-stats для кампании без A/B — возвращает «Не A/B тест»."""
        resp = client.post("/api/v1/campaigns", json={
            "name": "No AB Stats Test",
            "template_name": "cold_email_1",
        })
        cid = resp.json()["id"]

        resp2 = client.get(f"/api/v1/campaigns/{cid}/ab-stats")
        assert resp2.status_code == 200
        data = resp2.json()
        assert data["note"] == "Не A/B тест"


# P4R-L9: Тест PATCH 409 для running-кампании
class TestUpdateCampaignStatusGuard:
    """Защита от обновления запущенных/завершённых кампаний."""

    def test_update_running_campaign_returns_409(self, client, db_session):
        """PATCH для running кампании → 409."""
        resp = client.post("/api/v1/campaigns", json={
            "name": "Running Campaign Update Test",
            "template_name": "cold_email_1",
        })
        cid = resp.json()["id"]

        # Устанавливаем статус manually
        campaign = db_session.get(CrmEmailCampaignRow, cid)
        campaign.status = "running"
        db_session.commit()

        resp2 = client.patch(f"/api/v1/campaigns/{cid}", json={
            "name": "Should Fail",
        })
        assert resp2.status_code == 409

    def test_update_completed_campaign_returns_409(self, client, db_session):
        """PATCH для completed кампании → 409."""
        resp = client.post("/api/v1/campaigns", json={
            "name": "Completed Campaign Update Test",
            "template_name": "cold_email_1",
        })
        cid = resp.json()["id"]

        campaign = db_session.get(CrmEmailCampaignRow, cid)
        campaign.status = "completed"
        db_session.commit()

        resp2 = client.patch(f"/api/v1/campaigns/{cid}", json={
            "name": "Should Fail",
        })
        assert resp2.status_code == 409


# P4R-L10: Тесты DELETE endpoint
class TestDeleteCampaign:
    """DELETE /campaigns/{id} — удаление кампании-черновика."""

    def test_delete_draft_success(self, client, db_session):
        """Удаление черновика — успешно."""
        resp = client.post("/api/v1/campaigns", json={
            "name": "Delete Draft Test",
            "template_name": "cold_email_1",
        })
        cid = resp.json()["id"]

        resp2 = client.delete(f"/api/v1/campaigns/{cid}")
        assert resp2.status_code == 200
        assert resp2.json()["ok"] is True

        # Проверяем, что кампания удалена
        resp3 = client.get(f"/api/v1/campaigns/{cid}")
        assert resp3.status_code == 404

    def test_delete_not_found(self, client):
        """Удаление несуществующей кампании — 404."""
        resp = client.delete("/api/v1/campaigns/99999")
        assert resp.status_code == 404

    def test_delete_running_campaign_returns_409(self, client, db_session):
        """Удаление running кампании → 409."""
        resp = client.post("/api/v1/campaigns", json={
            "name": "Delete Running Test",
            "template_name": "cold_email_1",
        })
        cid = resp.json()["id"]

        campaign = db_session.get(CrmEmailCampaignRow, cid)
        campaign.status = "running"
        db_session.commit()

        resp2 = client.delete(f"/api/v1/campaigns/{cid}")
        assert resp2.status_code == 409
