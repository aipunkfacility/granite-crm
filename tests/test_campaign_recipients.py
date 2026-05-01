"""Тесты для manual campaign recipients (TDD).

Фазы 2–4, 7 из дев-плана.
Покрывает: добавление/удаление recipients, manual-режим при запуске,
cascade-удаления, интеграционные тесты полного флоу.
"""
import pytest
from datetime import datetime, timezone, timedelta

from granite.database import (
    CompanyRow, EnrichedCompanyRow, CrmContactRow,
    CrmEmailLogRow, CrmEmailCampaignRow, CampaignRecipientRow,
)


# ============================================================
# Фаза 2: POST /recipients, POST /recipients/remove, GET /recipients
# ============================================================

class TestAddRecipients:
    """POST /campaigns/{id}/recipients — добавление компаний."""

    def test_add_single_recipient(self, db_session, client):
        """Базовый сценарий: добавить одну компанию в черновик кампании."""
        company = CompanyRow(name_best="Тест", city="москва", emails=["test@mail.ru"])
        db_session.add(company); db_session.flush()
        contact = CrmContactRow(company_id=company.id)
        db_session.add(contact); db_session.commit()
        campaign = CrmEmailCampaignRow(name="Test", template_name="cold_email_v1", recipient_mode="manual")
        db_session.add(campaign); db_session.commit()

        resp = client.post(f"/api/v1/campaigns/{campaign.id}/recipients",
                           json={"company_ids": [company.id]})

        assert resp.status_code == 200
        assert resp.json()["added"] == 1
        assert resp.json()["skipped"] == 0
        row = db_session.query(CampaignRecipientRow).filter_by(campaign_id=campaign.id).first()
        assert row is not None
        assert row.company_id == company.id

    def test_add_multiple_recipients(self, db_session, client):
        """Добавить несколько компаний за один запрос."""
        ids = []
        for i in range(3):
            c = CompanyRow(name_best=f"Тест {i}", city="москва", emails=[f"test{i}@mail.ru"])
            db_session.add(c); db_session.flush()
            contact = CrmContactRow(company_id=c.id)
            db_session.add(contact); db_session.flush()
            ids.append(c.id)
        db_session.commit()
        campaign = CrmEmailCampaignRow(name="Test", template_name="cold_email_v1", recipient_mode="manual")
        db_session.add(campaign); db_session.commit()

        resp = client.post(f"/api/v1/campaigns/{campaign.id}/recipients",
                           json={"company_ids": ids})

        assert resp.json()["added"] == 3
        assert resp.json()["skipped"] == 0

    def test_add_to_filter_campaign_without_force_returns_409(self, db_session, client):
        """Добавление в filter-кампанию без force → 409 (аудит, п.2)."""
        company = CompanyRow(name_best="Тест", city="москва", emails=["test@mail.ru"])
        db_session.add(company); db_session.flush()
        contact = CrmContactRow(company_id=company.id)
        db_session.add(contact); db_session.commit()
        campaign = CrmEmailCampaignRow(name="Test", template_name="cold_email_v1", recipient_mode="filter")
        db_session.add(campaign); db_session.commit()

        resp = client.post(f"/api/v1/campaigns/{campaign.id}/recipients",
                           json={"company_ids": [company.id]})
        assert resp.status_code == 409
        # Режим не изменился
        db_session.refresh(campaign)
        assert campaign.recipient_mode == "filter"

    def test_add_to_filter_campaign_with_force_switches_to_manual(self, db_session, client):
        """Добавление в filter-кампанию С force → переключение на manual (аудит, п.2)."""
        company = CompanyRow(name_best="Тест", city="москва", emails=["test@mail.ru"])
        db_session.add(company); db_session.flush()
        contact = CrmContactRow(company_id=company.id)
        db_session.add(contact); db_session.commit()
        campaign = CrmEmailCampaignRow(name="Test", template_name="cold_email_v1", recipient_mode="filter")
        db_session.add(campaign); db_session.commit()

        resp = client.post(f"/api/v1/campaigns/{campaign.id}/recipients",
                           json={"company_ids": [company.id], "force": True})

        assert resp.status_code == 200
        db_session.refresh(campaign)
        assert campaign.recipient_mode == "manual"

    def test_add_recipient_without_email_skipped(self, db_session, client):
        """Компания без email — пропускается."""
        company = CompanyRow(name_best="Без email", city="москва", emails=[])
        db_session.add(company); db_session.commit()
        campaign = CrmEmailCampaignRow(name="Test", template_name="cold_email_v1", recipient_mode="manual")
        db_session.add(campaign); db_session.commit()

        resp = client.post(f"/api/v1/campaigns/{campaign.id}/recipients",
                           json={"company_ids": [company.id]})

        assert resp.json()["added"] == 0
        assert resp.json()["skipped"] == 1

    def test_add_deleted_company_skipped(self, db_session, client):
        """Удалённая компания — пропускается."""
        company = CompanyRow(name_best="Удалён", city="москва", emails=["del@mail.ru"],
                             deleted_at=datetime.now(timezone.utc))
        db_session.add(company); db_session.commit()
        campaign = CrmEmailCampaignRow(name="Test", template_name="cold_email_v1", recipient_mode="manual")
        db_session.add(campaign); db_session.commit()

        resp = client.post(f"/api/v1/campaigns/{campaign.id}/recipients",
                           json={"company_ids": [company.id]})

        assert resp.json()["skipped"] == 1

    def test_add_duplicate_recipient_skipped(self, db_session, client):
        """Добавить одну компанию дважды — второй раз skipped."""
        company = CompanyRow(name_best="Тест", city="москва", emails=["test@mail.ru"])
        db_session.add(company); db_session.flush()
        contact = CrmContactRow(company_id=company.id)
        db_session.add(contact); db_session.commit()
        campaign = CrmEmailCampaignRow(name="Test", template_name="cold_email_v1", recipient_mode="manual")
        db_session.add(campaign); db_session.commit()

        resp1 = client.post(f"/api/v1/campaigns/{campaign.id}/recipients",
                            json={"company_ids": [company.id]})
        assert resp1.json()["added"] == 1

        resp2 = client.post(f"/api/v1/campaigns/{campaign.id}/recipients",
                            json={"company_ids": [company.id]})
        assert resp2.json()["added"] == 0
        assert resp2.json()["skipped"] == 1

    def test_add_to_running_campaign_forbidden(self, db_session, client):
        """Добавлять в running-кампанию — 409."""
        company = CompanyRow(name_best="Тест", city="москва", emails=["test@mail.ru"])
        db_session.add(company); db_session.commit()
        campaign = CrmEmailCampaignRow(name="Test", template_name="cold_email_v1",
                                       recipient_mode="manual", status="running")
        db_session.add(campaign); db_session.commit()

        resp = client.post(f"/api/v1/campaigns/{campaign.id}/recipients",
                           json={"company_ids": [company.id]})

        assert resp.status_code == 409

    def test_add_to_nonexistent_campaign_404(self, db_session, client):
        """Несуществующая кампания — 404."""
        resp = client.post("/api/v1/campaigns/99999/recipients",
                           json={"company_ids": [1]})
        assert resp.status_code == 404

    def test_add_nonexistent_company_skipped(self, db_session, client):
        """Несуществующий company_id — skipped."""
        campaign = CrmEmailCampaignRow(name="Test", template_name="cold_email_v1", recipient_mode="manual")
        db_session.add(campaign); db_session.commit()

        resp = client.post(f"/api/v1/campaigns/{campaign.id}/recipients",
                           json={"company_ids": [99999]})

        assert resp.json()["skipped"] == 1
        assert resp.json()["added"] == 0


class TestRemoveRecipients:
    """POST /campaigns/{id}/recipients/remove — удаление компаний."""

    def test_remove_single_recipient(self, db_session, client):
        """Удалить одну компанию из списка."""
        company = CompanyRow(name_best="Тест", city="москва", emails=["test@mail.ru"])
        db_session.add(company); db_session.flush()
        campaign = CrmEmailCampaignRow(name="Test", template_name="cold_email_v1", recipient_mode="manual")
        db_session.add(campaign); db_session.flush()
        db_session.add(CampaignRecipientRow(campaign_id=campaign.id, company_id=company.id))
        db_session.commit()

        resp = client.post(f"/api/v1/campaigns/{campaign.id}/recipients/remove",
                           json={"company_ids": [company.id]})

        assert resp.json()["removed"] >= 1

    def test_remove_nonexistent_recipient_zero_removed(self, db_session, client):
        """Удалить компанию, которой нет в списке — removed = 0."""
        company = CompanyRow(name_best="Тест", city="москва", emails=["test@mail.ru"])
        db_session.add(company); db_session.commit()
        campaign = CrmEmailCampaignRow(name="Test", template_name="cold_email_v1", recipient_mode="manual")
        db_session.add(campaign); db_session.commit()

        resp = client.post(f"/api/v1/campaigns/{campaign.id}/recipients/remove",
                           json={"company_ids": [company.id]})

        assert resp.json()["removed"] == 0

    def test_remove_from_running_forbidden(self, db_session, client):
        """Удалять из running-кампании — 409."""
        company = CompanyRow(name_best="Тест", city="москва", emails=["test@mail.ru"])
        db_session.add(company); db_session.commit()
        campaign = CrmEmailCampaignRow(name="Test", template_name="cold_email_v1",
                                       recipient_mode="manual", status="running")
        db_session.add(campaign); db_session.commit()

        resp = client.post(f"/api/v1/campaigns/{campaign.id}/recipients/remove",
                           json={"company_ids": [company.id]})

        assert resp.status_code == 409


class TestListRecipients:
    """GET /campaigns/{id}/recipients — список получателей."""

    def test_list_recipients_paginated(self, db_session, client):
        """Список с пагинацией."""
        campaign = CrmEmailCampaignRow(name="Test", template_name="cold_email_v1", recipient_mode="manual")
        db_session.add(campaign); db_session.flush()

        for i in range(5):
            c = CompanyRow(name_best=f"Тест {i}", city="москва", emails=[f"t{i}@mail.ru"])
            db_session.add(c); db_session.flush()
            db_session.add(CampaignRecipientRow(campaign_id=campaign.id, company_id=c.id))
        db_session.commit()

        resp = client.get(f"/api/v1/campaigns/{campaign.id}/recipients?page=1&per_page=3")

        assert resp.json()["total"] == 5
        assert len(resp.json()["items"]) == 3

    def test_list_recipients_empty(self, db_session, client):
        """Пустой список — 0 items."""
        campaign = CrmEmailCampaignRow(name="Test", template_name="cold_email_v1", recipient_mode="manual")
        db_session.add(campaign); db_session.commit()

        resp = client.get(f"/api/v1/campaigns/{campaign.id}/recipients")

        assert resp.json()["total"] == 0
        assert resp.json()["items"] == []

    def test_list_recipients_includes_company_fields(self, db_session, client):
        """Ответ содержит нужные поля компании."""
        company = CompanyRow(name_best="Тест", city="москва", emails=["test@mail.ru"])
        db_session.add(company); db_session.flush()
        enriched = EnrichedCompanyRow(id=company.id, name="Тест", city="москва",
                                       emails=["test@mail.ru"], segment="A", crm_score=50)
        db_session.add(enriched); db_session.flush()
        campaign = CrmEmailCampaignRow(name="Test", template_name="cold_email_v1", recipient_mode="manual")
        db_session.add(campaign); db_session.flush()
        db_session.add(CampaignRecipientRow(campaign_id=campaign.id, company_id=company.id))
        db_session.commit()

        resp = client.get(f"/api/v1/campaigns/{campaign.id}/recipients")
        item = resp.json()["items"][0]

        assert item["id"] == company.id
        assert item["name"] == "Тест"
        assert item["city"] == "москва"
        assert item["emails"] == ["test@mail.ru"]
        assert item["segment"] == "A"
        assert item["crm_score"] == 50


# ============================================================
# Фаза 3: _get_manual_recipients — логика при запуске
# ============================================================

class TestGetManualRecipients:
    """_get_manual_recipients() — логика отбора при запуске кампании."""

    def test_manual_recipients_from_campaign_recipients_table(self, db_session):
        """Получатели берутся из campaign_recipients, не из фильтров."""
        company = CompanyRow(name_best="Тест", city="москва", emails=["test@mail.ru"])
        db_session.add(company); db_session.flush()
        contact = CrmContactRow(company_id=company.id)
        db_session.add(contact); db_session.flush()
        enriched = EnrichedCompanyRow(id=company.id, name="Тест", city="москва",
                                       emails=["test@mail.ru"], segment="C", crm_score=10)
        db_session.add(enriched); db_session.flush()
        # Кампания с фильтром segment=A — но компания C
        campaign = CrmEmailCampaignRow(
            name="Test", template_name="cold_email_v1",
            recipient_mode="manual",
            filters={"segment": "A"},
        )
        db_session.add(campaign); db_session.flush()
        db_session.add(CampaignRecipientRow(campaign_id=campaign.id, company_id=company.id))
        db_session.commit()

        from granite.api.campaigns import _get_campaign_recipients
        recipients = _get_campaign_recipients(campaign, db_session)

        assert len(recipients) == 1
        assert recipients[0][0].id == company.id

    def test_manual_skips_already_sent(self, db_session):
        """Компании, которым уже отправили — пропускаются."""
        company = CompanyRow(name_best="Тест", city="москва", emails=["test@mail.ru"])
        db_session.add(company); db_session.flush()
        contact = CrmContactRow(company_id=company.id)
        db_session.add(contact); db_session.flush()
        campaign = CrmEmailCampaignRow(name="Test", template_name="cold_email_v1", recipient_mode="manual")
        db_session.add(campaign); db_session.flush()
        db_session.add(CampaignRecipientRow(campaign_id=campaign.id, company_id=company.id))
        db_session.flush()

        db_session.add(CrmEmailLogRow(company_id=company.id, campaign_id=campaign.id,
                              email_to="test@mail.ru", status="sent"))
        db_session.commit()

        from granite.api.campaigns import _get_campaign_recipients
        recipients = _get_campaign_recipients(campaign, db_session)

        assert len(recipients) == 0

    def test_manual_skips_stop_automation(self, db_session):
        """stop_automation — компания в списке, но письмо не уйдёт."""
        company = CompanyRow(name_best="Тест", city="москва", emails=["test@mail.ru"])
        db_session.add(company); db_session.flush()
        contact = CrmContactRow(company_id=company.id, stop_automation=1)
        db_session.add(contact); db_session.flush()
        campaign = CrmEmailCampaignRow(name="Test", template_name="cold_email_v1", recipient_mode="manual")
        db_session.add(campaign); db_session.flush()
        db_session.add(CampaignRecipientRow(campaign_id=campaign.id, company_id=company.id))
        db_session.commit()

        from granite.api.campaigns import _get_campaign_recipients
        recipients = _get_campaign_recipients(campaign, db_session)

        assert len(recipients) == 0

    def test_manual_skips_deleted_company(self, db_session):
        """Soft-deleted компания — пропускается при запуске (аудит, мелочь)."""
        company = CompanyRow(name_best="Удалён", city="москва", emails=["del@mail.ru"],
                             deleted_at=datetime.now(timezone.utc))
        db_session.add(company); db_session.flush()
        contact = CrmContactRow(company_id=company.id)
        db_session.add(contact); db_session.flush()
        campaign = CrmEmailCampaignRow(name="Test", template_name="cold_email_v1", recipient_mode="manual")
        db_session.add(campaign); db_session.flush()
        db_session.add(CampaignRecipientRow(campaign_id=campaign.id, company_id=company.id))
        db_session.commit()

        from granite.api.campaigns import _get_campaign_recipients
        recipients = _get_campaign_recipients(campaign, db_session)

        assert len(recipients) == 0

    def test_manual_session_gap_ignored(self, db_session):
        """SESSION_GAP НЕ применяется для manual-режима (аудит, п.4)."""
        company = CompanyRow(name_best="Тест", city="москва", emails=["test@mail.ru"])
        db_session.add(company); db_session.flush()
        contact = CrmContactRow(
            company_id=company.id,
            last_email_sent_at=datetime.now(timezone.utc) - timedelta(minutes=30),
        )
        db_session.add(contact); db_session.flush()
        campaign = CrmEmailCampaignRow(name="Test", template_name="cold_email_v1", recipient_mode="manual")
        db_session.add(campaign); db_session.flush()
        db_session.add(CampaignRecipientRow(campaign_id=campaign.id, company_id=company.id))
        db_session.commit()

        from granite.api.campaigns import _get_campaign_recipients
        recipients = _get_campaign_recipients(campaign, db_session)

        # В manual-режиме SESSION_GAP игнорируется — компания проходит
        assert len(recipients) == 1

    def test_manual_dedup_same_email(self, db_session):
        """Два получателя с одним email — письмо только первому."""
        c1 = CompanyRow(name_best="А", city="москва", emails=["same@mail.ru"])
        c2 = CompanyRow(name_best="Б", city="москва", emails=["same@mail.ru"])
        db_session.add_all([c1, c2]); db_session.flush()
        db_session.add(CrmContactRow(company_id=c1.id)); db_session.flush()
        db_session.add(CrmContactRow(company_id=c2.id)); db_session.flush()
        campaign = CrmEmailCampaignRow(name="Test", template_name="cold_email_v1", recipient_mode="manual")
        db_session.add(campaign); db_session.flush()
        db_session.add(CampaignRecipientRow(campaign_id=campaign.id, company_id=c1.id))
        db_session.add(CampaignRecipientRow(campaign_id=campaign.id, company_id=c2.id))
        db_session.commit()

        from granite.api.campaigns import _get_campaign_recipients
        recipients = _get_campaign_recipients(campaign, db_session)

        assert len(recipients) == 1
        assert recipients[0][0].id == c1.id

    def test_manual_empty_recipients_returns_empty(self, db_session):
        """Пустой список получателей — пустой результат."""
        campaign = CrmEmailCampaignRow(name="Test", template_name="cold_email_v1", recipient_mode="manual")
        db_session.add(campaign); db_session.commit()

        from granite.api.campaigns import _get_campaign_recipients
        recipients = _get_campaign_recipients(campaign, db_session)

        assert recipients == []


class TestCreateCampaignWithManualMode:
    """Создание кампании в manual-режиме."""

    def test_create_manual_campaign_with_company_ids(self, db_session, client):
        """Создать кампанию с recipient_mode=manual и начальным списком."""
        company = CompanyRow(name_best="Тест", city="москва", emails=["test@mail.ru"])
        db_session.add(company); db_session.flush()
        db_session.add(CrmContactRow(company_id=company.id)); db_session.commit()

        resp = client.post("/api/v1/campaigns", json={
            "name": "Ручная кампания",
            "template_name": "cold_email_v1",
            "recipient_mode": "manual",
            "company_ids": [company.id],
        })

        assert resp.status_code == 201
        campaign_id = resp.json()["id"]
        count = db_session.query(CampaignRecipientRow).filter_by(campaign_id=campaign_id).count()
        assert count == 1

    def test_create_manual_campaign_without_company_ids(self, db_session, client):
        """Создать пустую manual-кампанию — список пуст."""
        resp = client.post("/api/v1/campaigns", json={
            "name": "Пустая ручная",
            "template_name": "cold_email_v1",
            "recipient_mode": "manual",
        })

        assert resp.status_code == 201

    def test_create_filter_campaign_with_company_ids_rejected(self, db_session, client):
        """filter-режим + company_ids → 422 (аудит, п.3)."""
        company = CompanyRow(name_best="Тест", city="москва", emails=["test@mail.ru"])
        db_session.add(company); db_session.commit()

        resp = client.post("/api/v1/campaigns", json={
            "name": "Фильтр кампания",
            "template_name": "cold_email_v1",
            "recipient_mode": "filter",
            "company_ids": [company.id],
        })

        assert resp.status_code == 422


class TestCampaignResponseFields:
    """Новые поля в ответе кампании."""

    def test_campaign_detail_includes_recipient_mode(self, db_session, client):
        """Детальный ответ содержит recipient_mode."""
        campaign = CrmEmailCampaignRow(name="Test", template_name="cold_email_v1", recipient_mode="manual")
        db_session.add(campaign); db_session.commit()

        resp = client.get(f"/api/v1/campaigns/{campaign.id}")
        assert resp.json()["recipient_mode"] == "manual"

    def test_campaign_detail_includes_recipient_count(self, db_session, client):
        """Детальный ответ содержит recipient_count для manual-кампаний."""
        company = CompanyRow(name_best="Тест", city="москва", emails=["test@mail.ru"])
        db_session.add(company); db_session.flush()
        campaign = CrmEmailCampaignRow(name="Test", template_name="cold_email_v1", recipient_mode="manual")
        db_session.add(campaign); db_session.flush()
        db_session.add(CampaignRecipientRow(campaign_id=campaign.id, company_id=company.id))
        db_session.commit()

        resp = client.get(f"/api/v1/campaigns/{campaign.id}")
        assert resp.json()["recipient_count"] == 1

    def test_filter_campaign_recipient_count_is_none(self, db_session, client):
        """Для filter-кампаний recipient_count = null."""
        campaign = CrmEmailCampaignRow(name="Test", template_name="cold_email_v1", recipient_mode="filter")
        db_session.add(campaign); db_session.commit()

        resp = client.get(f"/api/v1/campaigns/{campaign.id}")
        assert resp.json()["recipient_count"] is None

    def test_campaign_list_includes_recipient_mode(self, db_session, client):
        """Список кампаний содержит recipient_mode."""
        campaign = CrmEmailCampaignRow(name="Test", template_name="cold_email_v1", recipient_mode="manual")
        db_session.add(campaign); db_session.commit()

        resp = client.get("/api/v1/campaigns")
        items = resp.json()["items"]
        found = [i for i in items if i["id"] == campaign.id]
        assert len(found) == 1
        assert found[0]["recipient_mode"] == "manual"


# ============================================================
# Фаза 4: Cascade deletes
# ============================================================

class TestCascadeDeletes:
    """Поведение при удалении кампании/компании."""

    def test_delete_campaign_cascades_recipients(self, db_session):
        """Удаление кампании удаляет все записи из campaign_recipients."""
        company = CompanyRow(name_best="Тест", city="москва", emails=["test@mail.ru"])
        db_session.add(company); db_session.flush()
        campaign = CrmEmailCampaignRow(name="Test", template_name="cold_email_v1", recipient_mode="manual")
        db_session.add(campaign); db_session.flush()
        db_session.add(CampaignRecipientRow(campaign_id=campaign.id, company_id=company.id))
        db_session.flush()

        db_session.delete(campaign)
        db_session.flush()

        count = db_session.query(CampaignRecipientRow).filter_by(company_id=company.id).count()
        assert count == 0

    def test_delete_company_cascades_recipients(self, db_session):
        """Удаление компании удаляет её записи из campaign_recipients."""
        company = CompanyRow(name_best="Тест", city="москва", emails=["test@mail.ru"])
        db_session.add(company); db_session.flush()
        campaign = CrmEmailCampaignRow(name="Test", template_name="cold_email_v1", recipient_mode="manual")
        db_session.add(campaign); db_session.flush()
        db_session.add(CampaignRecipientRow(campaign_id=campaign.id, company_id=company.id))
        db_session.flush()

        db_session.delete(company)
        db_session.flush()

        count = db_session.query(CampaignRecipientRow).filter_by(campaign_id=campaign.id).count()
        assert count == 0


# ============================================================
# Фаза 7: Интеграционные тесты (полный флоу)
# ============================================================

class TestManualCampaignFullFlow:
    """Полный цикл: создать → добавить → запустить → проверить."""

    def test_full_manual_campaign_flow(self, db_session, client):
        """E2E: создание + добавление + удаление + проверка recipient_count."""
        # 1. Создать 3 компании
        ids = []
        for i in range(3):
            c = CompanyRow(name_best=f"Мастерская {i}", city="москва", emails=[f"master{i}@mail.ru"])
            db_session.add(c); db_session.flush()
            contact = CrmContactRow(company_id=c.id)
            db_session.add(contact); db_session.flush()
            enriched = EnrichedCompanyRow(id=c.id, name=f"Мастерская {i}", city="москва",
                                           emails=[f"master{i}@mail.ru"])
            db_session.add(enriched); db_session.flush()
            ids.append(c.id)
        db_session.commit()

        # 2. Создать manual-кампанию
        resp = client.post("/api/v1/campaigns", json={
            "name": "Ручной тест",
            "template_name": "cold_email_v1",
            "recipient_mode": "manual",
            "company_ids": ids[:2],
        })
        assert resp.status_code == 201
        campaign_id = resp.json()["id"]

        # 3. Проверить recipient_count
        resp = client.get(f"/api/v1/campaigns/{campaign_id}")
        assert resp.json()["recipient_count"] == 2

        # 4. Добавить третью
        resp = client.post(f"/api/v1/campaigns/{campaign_id}/recipients",
                           json={"company_ids": [ids[2]]})
        assert resp.json()["added"] == 1

        # 5. Проверить обновлённый recipient_count
        resp = client.get(f"/api/v1/campaigns/{campaign_id}")
        assert resp.json()["recipient_count"] == 3

        # 6. Удалить одну (POST /remove — аудит, п.6)
        resp = client.post(f"/api/v1/campaigns/{campaign_id}/recipients/remove",
                           json={"company_ids": [ids[0]]})
        assert resp.json()["removed"] >= 1

        # 7. Проверить финальный recipient_count
        resp = client.get(f"/api/v1/campaigns/{campaign_id}")
        assert resp.json()["recipient_count"] == 2

        # 8. Проверить список получателей через GET
        resp = client.get(f"/api/v1/campaigns/{campaign_id}/recipients")
        assert resp.json()["total"] == 2

    def test_manual_campaign_after_partial_run(self, db_session, client):
        """После частичной отправки — перезапуск не дублирует письма."""
        company = CompanyRow(name_best="Тест", city="москва", emails=["test@mail.ru"])
        db_session.add(company); db_session.flush()
        contact = CrmContactRow(company_id=company.id)
        db_session.add(contact); db_session.flush()
        enriched = EnrichedCompanyRow(id=company.id, name="Тест", city="москва",
                                       emails=["test@mail.ru"])
        db_session.add(enriched); db_session.flush()
        campaign = CrmEmailCampaignRow(name="Test", template_name="cold_email_v1", recipient_mode="manual")
        db_session.add(campaign); db_session.flush()
        db_session.add(CampaignRecipientRow(campaign_id=campaign.id, company_id=company.id))
        db_session.flush()

        db_session.add(CrmEmailLogRow(company_id=company.id, campaign_id=campaign.id,
                              email_to="test@mail.ru", status="sent"))
        db_session.commit()

        from granite.api.campaigns import _get_campaign_recipients
        recipients = _get_campaign_recipients(campaign, db_session)
        assert len(recipients) == 0

    def test_add_to_filter_campaign_flow(self, db_session, client):
        """Полный флоу: попытка добавить в filter-кампанию (аудит, п.2)."""
        company = CompanyRow(name_best="Тест", city="москва", emails=["test@mail.ru"])
        db_session.add(company); db_session.flush()
        db_session.add(CrmContactRow(company_id=company.id)); db_session.commit()

        # Создать filter-кампанию
        resp = client.post("/api/v1/campaigns", json={
            "name": "Фильтр кампания",
            "template_name": "cold_email_v1",
            "recipient_mode": "filter",
        })
        assert resp.status_code == 201
        campaign_id = resp.json()["id"]

        # Попытка добавить без force → 409
        resp = client.post(f"/api/v1/campaigns/{campaign_id}/recipients",
                           json={"company_ids": [company.id]})
        assert resp.status_code == 409

        # С force → успех
        resp = client.post(f"/api/v1/campaigns/{campaign_id}/recipients",
                           json={"company_ids": [company.id], "force": True})
        assert resp.status_code == 200

        # Режим переключился
        resp = client.get(f"/api/v1/campaigns/{campaign_id}")
        assert resp.json()["recipient_mode"] == "manual"
