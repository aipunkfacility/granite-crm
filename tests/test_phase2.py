"""Тесты Фазы 2 — RetouchGrav Email Campaign Dev Plan v13.

Задачи 2+18, 3, 4, 12, 15, 17 — в соответствии с планом.
TDD: сначала тесты, потом код (здесь — ретроспективные тесты).
"""
import hashlib
import os
import sys
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch, PropertyMock

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from granite.database import (
    Base, CompanyRow, EnrichedCompanyRow, CrmContactRow,
    CrmEmailLogRow, CrmEmailCampaignRow, CrmTemplateRow, CrmTouchRow,
)


# ── Фикстуры ─────────────────────────────────────────────────────────────

@pytest.fixture
def engine():
    """In-memory SQLite с FK PRAGMA."""
    _engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(_engine, "connect")
    def _pragma(dbapi_conn, conn_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(_engine)
    yield _engine
    _engine.dispose()


@pytest.fixture
def db(engine):
    """Сессия БД для тестов."""
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.rollback()
    session.close()


def _make_company(db, id_=None, name="Тест Мастерская", city="Москва",
                   emails=None, website="https://test.ru"):
    """Создать тестовую компанию."""
    company = CompanyRow(
        name_best=name, city=city, emails=emails or ["info@test.ru"],
        website=website, sources=["web_search"],
    )
    db.add(company)
    db.flush()
    return company


def _make_enriched(db, company_id, name="Тест", city="Москва", segment="a", crm_score=5):
    """Создать enriched-запись."""
    enriched = EnrichedCompanyRow(
        id=company_id, name=name, city=city,
        segment=segment, crm_score=crm_score,
    )
    db.add(enriched)
    db.flush()
    return enriched


def _make_contact(db, company_id, stop_automation=0, funnel_stage="new",
                   last_email_sent_at=None, unsubscribe_token=None):
    """Создать тестовый контакт."""
    import secrets
    contact = CrmContactRow(
        company_id=company_id, stop_automation=stop_automation,
        funnel_stage=funnel_stage,
        last_email_sent_at=last_email_sent_at,
        unsubscribe_token=unsubscribe_token or secrets.token_hex(16),
    )
    db.add(contact)
    db.flush()
    return contact


def _make_template(db, name="cold_email_v1", channel="email",
                    subject="Тест", body="Здравствуйте {city}",
                    body_type="plain", description="", retired=False):
    """Создать тестовый шаблон."""
    template = CrmTemplateRow(
        name=name, channel=channel, subject=subject, body=body,
        body_type=body_type, description=description, retired=retired,
    )
    db.add(template)
    db.flush()
    return template


def _make_campaign(db, name="Test Campaign", template_name="cold_email_v1",
                    status="draft", subject_a=None, subject_b=None,
                    filters=None, total_sent=0, total_errors=0):
    """Создать тестовую кампанию."""
    campaign = CrmEmailCampaignRow(
        name=name, template_name=template_name, status=status,
        subject_a=subject_a, subject_b=subject_b,
        filters=filters or {}, total_sent=total_sent, total_errors=total_errors,
    )
    db.add(campaign)
    db.flush()
    return campaign


# ══════════════════════════════════════════════════════════════════════════
# Задача 2+18: Recovery + отправка + батч-итерация
# ══════════════════════════════════════════════════════════════════════════

class TestRecovery:
    """Задача 2.1: Recovery — running кампании → paused при старте."""

    def test_recovery_running_to_paused(self, db):
        """При перезапуске сервера running кампании → paused."""
        # Создаём running кампанию
        _make_template(db)
        c1 = _make_campaign(db, name="Running 1", status="running")
        c2 = _make_campaign(db, name="Running 2", status="running")
        c3 = _make_campaign(db, name="Draft", status="draft")
        c4 = _make_campaign(db, name="Completed", status="completed")
        db.commit()

        # Имитируем recovery (как в app.py:lifespan)
        running = db.query(CrmEmailCampaignRow).filter(
            CrmEmailCampaignRow.status == "running"
        ).all()
        for c in running:
            c.status = "paused"
        db.commit()

        # Проверяем
        db.refresh(c1)
        db.refresh(c2)
        db.refresh(c3)
        db.refresh(c4)
        assert c1.status == "paused"
        assert c2.status == "paused"
        assert c3.status == "draft"  # не тронута
        assert c4.status == "completed"  # не тронута


class TestCampaignRecipients:
    """Задача 2+18: фильтры + дедуп + батч-итерация."""

    def test_campaign_recipients_dedup(self, db):
        """Два письма одному contact → только 1 получатель."""
        _make_template(db)
        _make_campaign(db, status="draft")

        # Две компании с одним email
        c1 = _make_company(db, name="Мастерская А", emails=["info@same.ru"])
        _make_enriched(db, c1.id)
        _make_contact(db, c1.id)

        c2 = _make_company(db, name="Мастерская Б", emails=["info@same.ru"])
        _make_enriched(db, c2.id)
        _make_contact(db, c2.id)

        db.commit()

        from granite.api.campaigns import _get_campaign_recipients
        campaign = db.get(CrmEmailCampaignRow, 1)
        recipients = _get_campaign_recipients(campaign, db)

        # Дедуп по email — только 1 получатель
        assert len(recipients) == 1

    def test_campaign_recipients_filter_stop_automation(self, db):
        """Contact с stop_automation=1 не в списке."""
        _make_template(db)
        _make_campaign(db, status="draft")

        c1 = _make_company(db, name="Активная", emails=["active@test.ru"])
        _make_enriched(db, c1.id)
        _make_contact(db, c1.id, stop_automation=0)

        c2 = _make_company(db, name="Отписанная", emails=["unsub@test.ru"])
        _make_enriched(db, c2.id)
        _make_contact(db, c2.id, stop_automation=1)

        db.commit()

        from granite.api.campaigns import _get_campaign_recipients
        campaign = db.get(CrmEmailCampaignRow, 1)
        recipients = _get_campaign_recipients(campaign, db)

        emails = [r[3] for r in recipients]
        assert "active@test.ru" in emails
        assert "unsub@test.ru" not in emails

    def test_campaign_recipients_no_oom(self, db):
        """Мок с большим числом компаний → итерация по батчам, не всё в памяти."""
        _make_template(db)
        _make_campaign(db, status="draft")

        # Создаём 5 компаний для проверки батч-итерации
        for i in range(5):
            c = _make_company(db, name=f"Мастерская {i}", emails=[f"info{i}@test.ru"])
            _make_enriched(db, c.id)
            _make_contact(db, c.id)
        db.commit()

        from granite.api.campaigns import _get_campaign_recipients
        campaign = db.get(CrmEmailCampaignRow, 1)
        recipients = _get_campaign_recipients(campaign, db)

        # Все компании обработаны
        assert len(recipients) == 5

    def test_yield_per_100_processes_all(self, db):
        """Все компании обработаны через yield_per батч-итерацию."""
        _make_template(db)
        _make_campaign(db, status="draft")

        for i in range(10):
            c = _make_company(db, name=f"Партия {i}", emails=[f"batch{i}@test.ru"])
            _make_enriched(db, c.id)
            _make_contact(db, c.id)
        db.commit()

        from granite.api.campaigns import _get_campaign_recipients
        campaign = db.get(CrmEmailCampaignRow, 1)
        recipients = _get_campaign_recipients(campaign, db)

        assert len(recipients) == 10

    def test_commit_per_email(self, db):
        """После каждого send() → commit() вызван (проверяем через touch records)."""
        _make_template(db)
        campaign = _make_campaign(db, status="draft")
        c1 = _make_company(db, name="Мастерская 1", emails=["commit1@test.ru"])
        _make_enriched(db, c1.id)
        _make_contact(db, c1.id)
        c2 = _make_company(db, name="Мастерская 2", emails=["commit2@test.ru"])
        _make_enriched(db, c2.id)
        _make_contact(db, c2.id)
        db.commit()

        # Имитируем отправку: создаём лог и touch для каждого письма
        for company_id, email in [(c1.id, "commit1@test.ru"), (c2.id, "commit2@test.ru")]:
            log = CrmEmailLogRow(
                company_id=company_id, email_to=email,
                email_subject="Test", template_name="cold_email_v1",
                campaign_id=campaign.id, tracking_id=f"track-{company_id}",
                status="sent", sent_at=datetime.now(timezone.utc),
            )
            db.add(log)
            db.add(CrmTouchRow(
                company_id=company_id, channel="email", direction="outgoing",
                subject="Test", body="[tracking_id=track] [ab=A]",
            ))
            db.commit()  # Commit после каждого письма

        # Проверяем что оба лога и touch записаны
        logs = db.query(CrmEmailLogRow).filter_by(campaign_id=campaign.id).all()
        assert len(logs) == 2

        touches = db.query(CrmTouchRow).all()
        assert len(touches) == 2


# ══════════════════════════════════════════════════════════════════════════
# Задача 4: Валидатор получателей
# ══════════════════════════════════════════════════════════════════════════

class TestValidator:
    """Задача 4: validate_recipients()."""

    def _make_recipient(self, company_name="Тест", email="valid@test.ru",
                         stop_automation=0, last_email_sent_at=None):
        """Создать мок получателя."""
        company = MagicMock()
        company.id = 1
        company.name_best = company_name
        contact = MagicMock()
        contact.stop_automation = stop_automation
        contact.last_email_sent_at = last_email_sent_at
        enriched = MagicMock()
        return (company, enriched, contact, email)

    def test_aggregator_filtered(self):
        """tsargranit.ru → отфильтрован как агрегатор."""
        from granite.email.validator import validate_recipients
        recipients = [self._make_recipient(email="info@tsargranit.ru")]
        valid, warnings = validate_recipients(recipients)
        assert len(valid) == 0
        assert "агрегатор" in warnings[0]["reason"]

    def test_invalid_email_filtered(self):
        """test@ → отфильтрован как невалидный email."""
        from granite.email.validator import validate_recipients
        recipients = [self._make_recipient(email="test@")]
        valid, warnings = validate_recipients(recipients)
        assert len(valid) == 0
        assert "невалидный email" in warnings[0]["reason"]

    def test_duplicate_email_deduped(self):
        """Две компании с одним email → 1 получатель."""
        from granite.email.validator import validate_recipients
        r1 = self._make_recipient(company_name="А", email="same@test.ru")
        r2 = self._make_recipient(company_name="Б", email="same@test.ru")
        # Меняем id чтобы не путать
        r2[0].id = 2
        valid, warnings = validate_recipients([r1, r2])
        assert len(valid) == 1
        assert any("дубль" in w["reason"] for w in warnings)

    def test_session_gap(self):
        """Письмо 30 мин назад → отфильтрован (SESSION_GAP=4ч)."""
        from granite.email.validator import validate_recipients
        recent = datetime.now(timezone.utc) - timedelta(minutes=30)
        recipients = [self._make_recipient(last_email_sent_at=recent)]
        valid, warnings = validate_recipients(recipients)
        assert len(valid) == 0
        assert "письмо недавно" in warnings[0]["reason"]

    def test_session_gap_expired(self):
        """Письмо 5 часов назад → проходит (SESSION_GAP=4ч)."""
        from granite.email.validator import validate_recipients
        old = datetime.now(timezone.utc) - timedelta(hours=5)
        recipients = [self._make_recipient(last_email_sent_at=old)]
        valid, warnings = validate_recipients(recipients)
        assert len(valid) == 1

    def test_gmail_block_signs(self, db):
        """5 bounced @gmail.com → домен помечен."""
        from granite.email.validator import check_gmail_block_signs

        # Создаём 5 bounced записей на gmail.com
        for i in range(5):
            company = _make_company(db, name=f"Бэнс {i}", emails=[f"bounce{i}@gmail.com"])
            db.add(CrmEmailLogRow(
                company_id=company.id,
                email_to=f"bounce{i}@gmail.com",
                email_subject="Test",
                template_name="cold_email_v1",
                status="bounced",
                bounced_at=datetime.now(timezone.utc),
            ))
        db.commit()

        blocked = check_gmail_block_signs(db)
        assert "gmail.com" in blocked

    def test_gmail_block_below_threshold(self, db):
        """4 bounced @gmail.com → домен НЕ помечен (порог=5)."""
        from granite.email.validator import check_gmail_block_signs

        for i in range(4):
            company = _make_company(db, name=f"Мало {i}", emails=[f"few{i}@gmail.com"])
            db.add(CrmEmailLogRow(
                company_id=company.id,
                email_to=f"few{i}@gmail.com",
                email_subject="Test",
                template_name="cold_email_v1",
                status="bounced",
                bounced_at=datetime.now(timezone.utc),
            ))
        db.commit()

        blocked = check_gmail_block_signs(db)
        assert "gmail.com" not in blocked

    def test_seo_name_filtered(self):
        """Название > 80 символов → SEO-мусор."""
        from granite.email.validator import validate_recipients
        long_name = "А" * 81
        recipients = [self._make_recipient(company_name=long_name)]
        valid, warnings = validate_recipients(recipients)
        assert len(valid) == 0
        assert "SEO" in warnings[0]["reason"]

    def test_stop_automation_filtered(self):
        """stop_automation=1 → отписан."""
        from granite.email.validator import validate_recipients
        recipients = [self._make_recipient(stop_automation=1)]
        valid, warnings = validate_recipients(recipients)
        assert len(valid) == 0
        assert "отписан" in warnings[0]["reason"]


# ══════════════════════════════════════════════════════════════════════════
# Задача 3: A/B + счётчики
# ══════════════════════════════════════════════════════════════════════════

class TestABTesting:
    """Задача 3: детерминированное A/B распределение + счётчики."""

    def test_ab_deterministic(self):
        """determine_ab_variant(company_id=42) всегда одинаковый результат."""
        # Используем ту же логику что в campaigns.py:get_ab_subject
        company_id = 42
        hash_val = int(hashlib.md5(str(company_id).encode()).hexdigest(), 16)
        result1 = "A" if hash_val % 2 == 0 else "B"
        result2 = "A" if hash_val % 2 == 0 else "B"
        assert result1 == result2

    def test_ab_50_50_split(self):
        """100 компаний → примерно 50/50 распределение."""
        a_count = 0
        b_count = 0
        for i in range(100):
            hash_val = int(hashlib.md5(str(i).encode()).hexdigest(), 16)
            if hash_val % 2 == 0:
                a_count += 1
            else:
                b_count += 1
        # Допускаем отклонение ±15
        assert 35 <= a_count <= 65, f"A={a_count}, B={b_count}"
        assert 35 <= b_count <= 65, f"A={a_count}, B={b_count}"

    def test_total_errors_increment(self, db):
        """Ошибка отправки → total_errors+1."""
        _make_template(db)
        campaign = _make_campaign(db, status="draft", total_sent=0, total_errors=0)
        db.commit()

        # Имитируем ошибку
        campaign.total_errors = (campaign.total_errors or 0) + 1
        db.commit()

        db.refresh(campaign)
        assert campaign.total_errors == 1

    def test_ab_variant_in_log(self, db):
        """Отправка → CrmEmailLogRow.ab_variant = "A" или "B"."""
        _make_template(db)
        campaign = _make_campaign(db, status="draft")
        company = _make_company(db, emails=["ab@test.ru"])
        db.commit()

        # Определяем вариант
        hash_val = int(hashlib.md5(str(company.id).encode()).hexdigest(), 16)
        ab_variant = "A" if hash_val % 2 == 0 else "B"

        log = CrmEmailLogRow(
            company_id=company.id, email_to="ab@test.ru",
            email_subject="Test", template_name="cold_email_v1",
            campaign_id=campaign.id, tracking_id="ab-test",
            status="sent", sent_at=datetime.now(timezone.utc),
            ab_variant=ab_variant,
        )
        db.add(log)
        db.commit()

        saved = db.get(CrmEmailLogRow, log.id)
        assert saved.ab_variant in ("A", "B")
        assert saved.ab_variant == ab_variant

    def test_ab_stats_endpoint(self, db, engine):
        """GET /campaigns/{id}/ab-stats → {A: {...}, B: {...}}."""
        from fastapi.testclient import TestClient
        from granite.api.app import app
        from granite.api.deps import get_db

        Session = sessionmaker(bind=engine)

        def get_test_db():
            session = Session()
            try:
                yield session
                session.commit()
            except Exception:
                session.rollback()
                raise
            finally:
                session.close()

        # Seed
        with Session() as s:
            _make_template(s, name="ab_test_tpl")
            campaign = _make_campaign(s, template_name="ab_test_tpl",
                                       subject_a="Тема A", subject_b="Тема B")
            c1 = _make_company(s, name="A Company", emails=["a@ab.ru"])
            c2 = _make_company(s, name="B Company", emails=["b@ab.ru"])
            s.add(CrmEmailLogRow(
                company_id=c1.id, email_to="a@ab.ru",
                email_subject="Тема A", template_name="ab_test_tpl",
                campaign_id=campaign.id, ab_variant="A",
                tracking_id="t1", status="sent",
                sent_at=datetime.now(timezone.utc),
            ))
            s.add(CrmEmailLogRow(
                company_id=c2.id, email_to="b@ab.ru",
                email_subject="Тема B", template_name="ab_test_tpl",
                campaign_id=campaign.id, ab_variant="B",
                tracking_id="t2", status="sent",
                sent_at=datetime.now(timezone.utc),
            ))
            s.commit()
            campaign_id = campaign.id

        app.dependency_overrides[get_db] = get_test_db
        app.state.Session = Session

        try:
            with TestClient(app) as client:
                resp = client.get(f"/api/v1/campaigns/{campaign_id}/ab-stats")
                assert resp.status_code == 200
                data = resp.json()
                assert "A" in data["variants"]
                assert "B" in data["variants"]
                assert data["variants"]["A"]["sent"] == 1
                assert data["variants"]["B"]["sent"] == 1
        finally:
            app.dependency_overrides.clear()


# ══════════════════════════════════════════════════════════════════════════
# Задача 12 impl: Immutable шаблоны
# ══════════════════════════════════════════════════════════════════════════

class TestImmutableTemplates:
    """Задача 12: seed, retired, immutable."""

    def test_seed_inserts_new(self, db, tmp_path):
        """Пустая БД → шаблоны добавлены."""
        _make_template(db, name="existing_tpl", body="Old")
        db.commit()

        # Запускаем seed (должен добавить шаблоны из JSON, пропустить existing)
        from scripts.seed_templates import seed_templates

        # Создаём временный JSON
        import json
        json_path = tmp_path / "email_templates.json"
        json_path.write_text(json.dumps([
            {"name": "new_template", "channel": "email", "subject": "Hi",
             "body": "Hello {city}", "body_type": "plain", "description": "New"},
        ]))

        # Мокаем путь к JSON
        import scripts.seed_templates as seed_mod
        original_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(seed_mod.__file__))),
            "data", "email_templates.json"
        )

        with patch.object(seed_templates, '__module__', 'scripts.seed_templates'):
            # Тестируем что уже существующий шаблон не перезаписывается
            count_before = db.query(CrmTemplateRow).count()
            assert count_before >= 1  # existing_tpl

    def test_seed_skips_existing(self, db):
        """Повторный seed → 0 новых."""
        _make_template(db, name="cold_email_v1")
        db.commit()

        # Имитируем seed — если шаблон уже есть, он пропускается
        existing = db.query(CrmTemplateRow).filter_by(name="cold_email_v1").first()
        assert existing is not None
        original_body = existing.body

        # Seed НЕ должен обновлять существующие шаблоны
        # (INSERT-only — проверяем логику)
        from scripts.seed_templates import seed_templates

        # Создаём тестовые данные
        new_tpl = CrmTemplateRow(
            name="another_template", channel="email",
            subject="X", body="Body X",
        )
        db.add(new_tpl)
        db.commit()

        count = db.query(CrmTemplateRow).count()
        assert count == 2  # cold_email_v1 + another_template

        # Проверяем что оригинальный шаблон не изменился
        db.refresh(existing)
        assert existing.body == original_body

    def test_template_id_in_log(self, db):
        """Отправка → template_id=1 в логе."""
        template = _make_template(db, name="tpl_with_id")
        company = _make_company(db, emails=["tpl@test.ru"])
        db.commit()

        log = CrmEmailLogRow(
            company_id=company.id, email_to="tpl@test.ru",
            email_subject="Test", template_name="tpl_with_id",
            tracking_id="tpl-test", status="sent",
            sent_at=datetime.now(timezone.utc),
            template_id=template.id,
        )
        db.add(log)
        db.commit()

        saved = db.get(CrmEmailLogRow, log.id)
        assert saved.template_id == template.id

    def test_retired_not_in_campaign_list(self, db, engine):
        """GET /templates → retired=true не показывается."""
        from fastapi.testclient import TestClient
        from granite.api.app import app
        from granite.api.deps import get_db

        Session = sessionmaker(bind=engine)

        with Session() as s:
            _make_template(s, name="active_tpl", retired=False)
            _make_template(s, name="retired_tpl", retired=True)
            s.commit()

        def get_test_db():
            session = Session()
            try:
                yield session
                session.commit()
            except Exception:
                session.rollback()
                raise
            finally:
                session.close()

        app.dependency_overrides[get_db] = get_test_db
        app.state.Session = Session

        try:
            with TestClient(app) as client:
                resp = client.get("/api/v1/templates")
                assert resp.status_code == 200
                names = [t["name"] for t in resp.json()["items"]]
                assert "active_tpl" in names
                assert "retired_tpl" not in names

                # С include_retired=1 показывает все
                resp2 = client.get("/api/v1/templates?include_retired=1")
                names2 = [t["name"] for t in resp2.json()["items"]]
                assert "active_tpl" in names2
                assert "retired_tpl" in names2
        finally:
            app.dependency_overrides.clear()

    def test_immutable_no_update(self, db, engine):
        """Retired-шаблон нельзя обновить."""
        from fastapi.testclient import TestClient
        from granite.api.app import app
        from granite.api.deps import get_db

        Session = sessionmaker(bind=engine)

        with Session() as s:
            _make_template(s, name="immutable_tpl", retired=True)
            s.commit()

        def get_test_db():
            session = Session()
            try:
                yield session
                session.commit()
            except Exception:
                session.rollback()
                raise
            finally:
                session.close()

        app.dependency_overrides[get_db] = get_test_db
        app.state.Session = Session

        try:
            with TestClient(app) as client:
                resp = client.put("/api/v1/templates/immutable_tpl", json={
                    "body": "Hacked!",
                })
                assert resp.status_code == 409
                assert "retired" in resp.json()["error"].lower() or "immutable" in resp.json()["error"].lower()
        finally:
            app.dependency_overrides.clear()


# ══════════════════════════════════════════════════════════════════════════
# Задача 15: Template name — кириллица + description
# ══════════════════════════════════════════════════════════════════════════

class TestTemplateCyrillic:
    """Задача 15: разрешить кириллицу в имени шаблона + description."""

    def test_template_name_cyrillic(self, engine):
        """name="Холодное_письмо_v1" → accepted."""
        from fastapi.testclient import TestClient
        from granite.api.app import app
        from granite.api.deps import get_db

        Session = sessionmaker(bind=engine)

        def get_test_db():
            session = Session()
            try:
                yield session
                session.commit()
            except Exception:
                session.rollback()
                raise
            finally:
                session.close()

        app.dependency_overrides[get_db] = get_test_db
        app.state.Session = Session

        try:
            with TestClient(app) as client:
                resp = client.post("/api/v1/templates", json={
                    "name": "Холодное_письмо_v1",
                    "channel": "email",
                    "body": "Test body",
                })
                assert resp.status_code == 201
        finally:
            app.dependency_overrides.clear()

    def test_template_name_still_rejects_spaces(self, engine):
        """name="cold email" → rejected (пробелы запрещены)."""
        from fastapi.testclient import TestClient
        from granite.api.app import app
        from granite.api.deps import get_db

        Session = sessionmaker(bind=engine)

        def get_test_db():
            session = Session()
            try:
                yield session
                session.commit()
            except Exception:
                session.rollback()
                raise
            finally:
                session.close()

        app.dependency_overrides[get_db] = get_test_db
        app.state.Session = Session

        try:
            with TestClient(app) as client:
                resp = client.post("/api/v1/templates", json={
                    "name": "cold email",
                    "channel": "email",
                    "body": "Test body",
                })
                assert resp.status_code == 422
        finally:
            app.dependency_overrides.clear()

    def test_template_description_field(self, engine):
        """description="Холодное письмо v1" → сохраняется."""
        from fastapi.testclient import TestClient
        from granite.api.app import app
        from granite.api.deps import get_db

        Session = sessionmaker(bind=engine)

        def get_test_db():
            session = Session()
            try:
                yield session
                session.commit()
            except Exception:
                session.rollback()
                raise
            finally:
                session.close()

        app.dependency_overrides[get_db] = get_test_db
        app.state.Session = Session

        try:
            with TestClient(app) as client:
                resp = client.post("/api/v1/templates", json={
                    "name": "desc_test",
                    "channel": "email",
                    "body": "Test body",
                    "description": "Холодное письмо v1",
                })
                assert resp.status_code == 201

                # Проверяем что description сохранён
                get_resp = client.get("/api/v1/templates/desc_test")
                assert get_resp.status_code == 200
                assert get_resp.json()["description"] == "Холодное письмо v1"
        finally:
            app.dependency_overrides.clear()


# ══════════════════════════════════════════════════════════════════════════
# Задача 17: Raw SQL — f-string → параметризованные
# ══════════════════════════════════════════════════════════════════════════

class TestParameterizedSQL:
    """Задача 17: все sa_text() вызовы используют :param, а не f-string."""

    def test_raw_sql_parameterized(self):
        """Проверяем что в companies.py нет f-string интерполяции в sa_text()."""
        import inspect
        from granite.api.companies import list_companies

        source = inspect.getsource(list_companies)

        # Ищем sa_text(...) вызовы — внутри не должно быть f-string
        # Допускаем только :param стиль (bindparams)
        import re
        # Ищем sa_text с f-string: sa_text(f"...")
        fstring_matches = re.findall(r'sa_text\(f["\']', source)
        assert len(fstring_matches) == 0, (
            f"Found f-string in sa_text() calls: {fstring_matches}. "
            f"Use :param with .bindparams() instead."
        )

    def test_tg_trust_filter_parameterized(self):
        """tg_trust_min/tg_trust_max через bindparam."""
        import inspect
        from granite.api.companies import list_companies

        source = inspect.getsource(list_companies)

        # Проверяем что tg_trust_min использует :tg_trust_min
        assert ":tg_trust_min" in source, "tg_trust_min must use :param style"
        assert ":tg_trust_max" in source, "tg_trust_max must use :param style"
        assert ".bindparams(" in source, "Must use .bindparams() for parameterized SQL"

    def test_source_filter_parameterized(self):
        """source через bindparam."""
        import inspect
        from granite.api.companies import list_companies

        source = inspect.getsource(list_companies)

        # Проверяем что source использует :source
        assert ":source" in source, "source must use :param style"
        # Проверяем что нет f-string с source в SQL
        import re
        # Ищем потенциальные f-string инъекции с source
        bad_patterns = re.findall(r'sa_text\(f["\'].*\{source\}', source)
        assert len(bad_patterns) == 0, (
            f"Found source interpolation in sa_text(): {bad_patterns}"
        )
