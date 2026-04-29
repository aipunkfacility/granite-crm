"""Тесты для granite/api/replies.py — POST /companies/{id}/reply и preview.

Шаблон reply_price берётся из TemplateRegistry (JSON — source of truth),
не из БД. conftest.py добавляет его в тестовый JSON.
"""
from unittest.mock import patch

from granite.database import (
    CrmContactRow, CrmTouchRow,
)
from tests.helpers import create_company


def _seed_incoming_touch(db_session, company_id):
    """Создать входящее касание для Re: subject."""
    touch = db_session.query(CrmTouchRow).filter_by(
        company_id=company_id, direction="incoming", subject="Вопрос о ценах"
    ).first()
    if not touch:
        touch = CrmTouchRow(
            company_id=company_id,
            channel="email",
            direction="incoming",
            subject="Вопрос о ценах",
            body="Сколько стоят ваши услуги?",
        )
        db_session.add(touch)
        db_session.commit()
    return touch


class TestPreviewReply:
    """POST /companies/{id}/reply/preview — предпросмотр reply перед отправкой."""

    def test_preview_success(self, client, db_session):
        """Предпросмотр reply — возвращает отрендеренный шаблон."""
        company_id = create_company(db_session, funnel_stage="replied")
        _seed_incoming_touch(db_session, company_id)
        db_session.commit()

        resp = client.post(f"/api/v1/companies/{company_id}/reply/preview", json={
            "template_name": "reply_price",
        })
        assert resp.status_code == 200, f"Got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data["company_id"] == company_id
        assert "Re:" in data["subject"] or "retouch" in data["subject"].lower() or "original" in data["subject"].lower()
        # Шаблон reply_price из JSON содержит "Цена ретуши"
        assert "Цена" in data["body"] or "ретуш" in data["body"]

    def test_preview_template_not_found(self, client, db_session):
        """Предпросмотр reply с несуществующим шаблоном — 404."""
        company_id = create_company(db_session)
        db_session.commit()

        resp = client.post(f"/api/v1/companies/{company_id}/reply/preview", json={
            "template_name": "nonexistent_template",
        })
        assert resp.status_code == 404

    def test_preview_company_not_found(self, client):
        """Предпросмотр reply для несуществующей компании — 404."""
        resp = client.post("/api/v1/companies/99999/reply/preview", json={
            "template_name": "reply_price",
        })
        assert resp.status_code == 404

    # P4R-M14: Тест для компании без email
    def test_preview_no_email(self, client, db_session):
        """Предпросмотр reply для компании без email — 400."""
        company_id = create_company(db_session, emails=[])
        db_session.commit()

        resp = client.post(f"/api/v1/companies/{company_id}/reply/preview", json={
            "template_name": "reply_price",
        })
        assert resp.status_code == 400

    # P4R-M10: Тест stop_automation в preview — должен вернуть предупреждение
    def test_preview_stop_automation_warning(self, client, db_session):
        """Предпросмотр reply для компании с stop_automation — предупреждение."""
        company_id = create_company(db_session, emails=["stop-preview@test.com"])
        # Устанавливаем stop_automation
        contact = db_session.query(CrmContactRow).filter_by(company_id=company_id).first()
        if contact:
            contact.stop_automation = True
        else:
            contact = CrmContactRow(company_id=company_id, stop_automation=True)
            db_session.add(contact)
        db_session.commit()

        resp = client.post(f"/api/v1/companies/{company_id}/reply/preview", json={
            "template_name": "reply_price",
        })
        # Preview должен вернуть 200 с предупреждением
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("stop_automation_warning") is not None


class TestSendReply:
    """POST /companies/{id}/reply — отправка reply с шаблоном."""

    def test_send_success(self, client, db_session):
        """Отправка reply — mock SMTP, проверяем успешный ответ."""
        company_id = create_company(db_session, funnel_stage="replied",
                                    emails=["reply-test@example.com"])
        _seed_incoming_touch(db_session, company_id)
        db_session.commit()

        with patch("granite.email.sender.EmailSender._smtp_send"):
            resp = client.post(f"/api/v1/companies/{company_id}/reply", json={
                "template_name": "reply_price",
            })
            assert resp.status_code == 200, f"Got {resp.status_code}: {resp.text}"
            data = resp.json()
            assert data["ok"] is True
            assert data["id"] is not None

    def test_send_with_subject_override(self, client, db_session):
        """Отправка reply с переопределённой темой."""
        company_id = create_company(db_session, funnel_stage="replied",
                                    emails=["reply-override@example.com"])
        _seed_incoming_touch(db_session, company_id)
        db_session.commit()

        with patch("granite.email.sender.EmailSender._smtp_send"):
            resp = client.post(f"/api/v1/companies/{company_id}/reply", json={
                "template_name": "reply_price",
                "subject_override": "Custom Subject Line",
            })
            assert resp.status_code == 200

    def test_send_template_not_found(self, client, db_session):
        """Отправка reply с несуществующим шаблоном — 404."""
        company_id = create_company(db_session)
        db_session.commit()

        resp = client.post(f"/api/v1/companies/{company_id}/reply", json={
            "template_name": "nonexistent",
        })
        assert resp.status_code == 404

    def test_send_creates_touch(self, client, db_session):
        """Отправка reply — создаётся исходящее касание с отрендеренным телом."""
        company_id = create_company(db_session, funnel_stage="replied",
                                    emails=["reply-touch@example.com"])
        _seed_incoming_touch(db_session, company_id)
        db_session.commit()

        with patch("granite.email.sender.EmailSender._smtp_send"):
            resp = client.post(f"/api/v1/companies/{company_id}/reply", json={
                "template_name": "reply_price",
            })
            assert resp.status_code == 200

        # Проверяем, что появилось исходящее касание
        touches = db_session.query(CrmTouchRow).filter_by(
            company_id=company_id, direction="outgoing"
        ).all()
        assert len(touches) >= 1
        # Body содержит отрендеренный текст (из шаблона reply_price)
        touch = touches[-1]
        assert "ретуш" in touch.body or "Цена" in touch.body
        assert "reply_template=reply_price" in (touch.note or "")

    # P4R-M13: Тест stop_automation — отправка должна вернуть 409
    def test_send_stop_automation(self, client, db_session):
        """Отправка reply при stop_automation=True — 409."""
        company_id = create_company(db_session, emails=["stop-test@example.com"])
        # Устанавливаем stop_automation
        contact = db_session.query(CrmContactRow).filter_by(company_id=company_id).first()
        if contact:
            contact.stop_automation = True
        else:
            contact = CrmContactRow(company_id=company_id, stop_automation=True)
            db_session.add(contact)
        db_session.commit()

        resp = client.post(f"/api/v1/companies/{company_id}/reply", json={
            "template_name": "reply_price",
        })
        assert resp.status_code == 409

    # P4R-M14: Тест компании без email
    def test_send_no_email(self, client, db_session):
        """Отправка reply для компании без email — 400."""
        company_id = create_company(db_session, emails=[])
        db_session.commit()

        resp = client.post(f"/api/v1/companies/{company_id}/reply", json={
            "template_name": "reply_price",
        })
        assert resp.status_code == 400
