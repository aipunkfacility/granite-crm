"""Тесты фильтров GET /companies — TDD Red phase.

Ожидается: ВСЕ тесты падают до написания кода в companies.py.
"""
from tests.helpers import create_company


class TestHasEmailFilter:
    """FIX: has_email == 0 — отсутствовал в API."""

    def test_has_email_1(self, client, db_session):
        """Компании с email."""
        create_company(db_session, emails=["info@test.ru"])
        db_session.commit()
        r = client.get("/api/v1/companies?has_email=1")
        assert r.status_code == 200
        assert r.json()["total"] == 1

    def test_has_email_0(self, client, db_session):
        """Компании без email — текущий BUG, тест ДОЛЖЕН упасть."""
        create_company(db_session, emails=[])
        db_session.commit()
        r = client.get("/api/v1/companies?has_email=0")
        assert r.status_code == 200
        assert r.json()["total"] == 1

    def test_has_email_0_excludes_companies_with_email(self, client, db_session):
        """has_email=0 не включает компании с email."""
        create_company(db_session, emails=["info@test.ru"])
        db_session.commit()
        r = client.get("/api/v1/companies?has_email=0")
        assert r.json()["total"] == 0


class TestMultiSegment:
    """segment=A&segment=B — multi-select."""

    def test_multi_segment(self, client, db_session):
        """Два сегмента — обе компании."""
        create_company(db_session, segment="A", crm_score=60)
        create_company(db_session, segment="B", crm_score=35)
        create_company(db_session, segment="C", crm_score=20)
        db_session.commit()
        r = client.get("/api/v1/companies?segment=A&segment=B")
        assert r.status_code == 200
        assert r.json()["total"] == 2

    def test_single_segment_compat(self, client, db_session):
        """Один сегмент — обратно совместимо."""
        create_company(db_session, segment="A", crm_score=60)
        create_company(db_session, segment="B", crm_score=35)
        db_session.commit()
        r = client.get("/api/v1/companies?segment=A")
        assert r.json()["total"] == 1

    def test_empty_segment_ignored(self, client, db_session):
        """segment= (пустая строка) — все компании."""
        create_company(db_session, segment="A")
        db_session.commit()
        r = client.get("/api/v1/companies?segment=")
        assert r.json()["total"] == 1


class TestIsNetworkFilter:
    def test_is_network_1(self, client, db_session):
        create_company(db_session, is_network=True)
        create_company(db_session)  # default False
        db_session.commit()
        r = client.get("/api/v1/companies?is_network=1")
        assert r.json()["total"] == 1

    def test_is_network_0(self, client, db_session):
        create_company(db_session, is_network=True)
        create_company(db_session)
        db_session.commit()
        r = client.get("/api/v1/companies?is_network=0")
        assert r.json()["total"] == 1


class TestHasWebsiteFilter:
    def test_has_website_1(self, client, db_session):
        create_company(db_session, website="https://example.com")
        create_company(db_session, website=None)
        db_session.commit()
        r = client.get("/api/v1/companies?has_website=1")
        assert r.json()["total"] == 1

    def test_has_website_0(self, client, db_session):
        create_company(db_session, website=None)
        create_company(db_session, website="https://example.com")
        db_session.commit()
        r = client.get("/api/v1/companies?has_website=0")
        assert r.json()["total"] == 1

    def test_has_website_empty_string(self, client, db_session):
        """website='' считается как отсутствие сайта."""
        create_company(db_session, website="")
        db_session.commit()
        r = client.get("/api/v1/companies?has_website=1")
        assert r.json()["total"] == 0
        r = client.get("/api/v1/companies?has_website=0")
        assert r.json()["total"] == 1


class TestHasVkFilter:
    def test_has_vk_1(self, client, db_session):
        create_company(db_session, messengers={"vk": "vk.com/test"})
        db_session.commit()
        r = client.get("/api/v1/companies?has_vk=1")
        assert r.json()["total"] == 1

    def test_has_vk_0(self, client, db_session):
        create_company(db_session, messengers={})
        db_session.commit()
        r = client.get("/api/v1/companies?has_vk=0")
        assert r.json()["total"] == 1

    def test_has_vk_empty_value(self, client, db_session):
        """vk: '' не считается наличием."""
        create_company(db_session, messengers={"vk": ""})
        db_session.commit()
        r = client.get("/api/v1/companies?has_vk=1")
        assert r.json()["total"] == 0


class TestHasAddressFilter:
    def test_has_address_1(self, client, db_session):
        create_company(db_session, address="г. Москва, ул. Тестовая, 1")
        db_session.commit()
        r = client.get("/api/v1/companies?has_address=1")
        assert r.json()["total"] == 1

    def test_has_address_0(self, client, db_session):
        create_company(db_session, address="")
        db_session.commit()
        r = client.get("/api/v1/companies?has_address=0")
        assert r.json()["total"] == 1


class TestMaxScoreFilter:
    def test_max_score(self, client, db_session):
        create_company(db_session, crm_score=30)
        create_company(db_session, crm_score=70)
        db_session.commit()
        r = client.get("/api/v1/companies?max_score=40")
        assert r.json()["total"] == 1
        assert r.json()["items"][0]["crm_score"] == 30

    def test_score_range(self, client, db_session):
        """Комбинация min_score + max_score."""
        create_company(db_session, crm_score=10)
        create_company(db_session, crm_score=30)
        create_company(db_session, crm_score=50)
        create_company(db_session, crm_score=70)
        db_session.commit()
        r = client.get("/api/v1/companies?min_score=25&max_score=55")
        assert r.json()["total"] == 2  # 30 и 50


class TestNeedsReviewFilter:
    def test_needs_review_1(self, client, db_session):
        create_company(db_session, needs_review=True)
        db_session.commit()
        r = client.get("/api/v1/companies?needs_review=1")
        assert r.json()["total"] == 1

    def test_needs_review_0(self, client, db_session):
        create_company(db_session)  # default False
        db_session.commit()
        r = client.get("/api/v1/companies?needs_review=0")
        assert r.json()["total"] == 1


class TestStopAutomationFilter:
    def test_stop_automation_1(self, client, db_session):
        create_company(db_session, stop_automation=1)
        db_session.commit()
        r = client.get("/api/v1/companies?stop_automation=1")
        assert r.json()["total"] == 1

    def test_stop_automation_0(self, client, db_session):
        create_company(db_session)  # default 0
        db_session.commit()
        r = client.get("/api/v1/companies?stop_automation=0")
        assert r.json()["total"] == 1


class TestCmsFilter:
    def test_cms_exact(self, client, db_session):
        create_company(db_session, cms="bitrix")
        create_company(db_session, cms="wordpress")
        create_company(db_session)  # cms="unknown" (default)
        db_session.commit()
        r = client.get("/api/v1/companies?cms=bitrix")
        assert r.json()["total"] == 1

    def test_cms_not_found(self, client, db_session):
        create_company(db_session, cms="bitrix")
        db_session.commit()
        r = client.get("/api/v1/companies?cms=nonexistent")
        assert r.json()["total"] == 0


class TestHasMarquizFilter:
    def test_has_marquiz_1(self, client, db_session):
        create_company(db_session, has_marquiz=True)
        db_session.commit()
        r = client.get("/api/v1/companies?has_marquiz=1")
        assert r.json()["total"] == 1

    def test_has_marquiz_0(self, client, db_session):
        create_company(db_session)  # default False
        db_session.commit()
        r = client.get("/api/v1/companies?has_marquiz=0")
        assert r.json()["total"] == 1


class TestOrderByExpansion:
    """Расширенный whitelist order_by."""

    def test_order_by_segment(self, client, db_session):
        create_company(db_session, segment="B", crm_score=30)
        create_company(db_session, segment="A", crm_score=30)
        db_session.commit()
        r = client.get("/api/v1/companies?order_by=segment&order_dir=asc")
        assert r.status_code == 200
        items = r.json()["items"]
        assert items[0]["segment"] == "A"
        assert items[1]["segment"] == "B"

    def test_order_by_is_network(self, client, db_session):
        create_company(db_session, is_network=False, crm_score=30)
        create_company(db_session, is_network=True, crm_score=30)
        db_session.commit()
        r = client.get("/api/v1/companies?order_by=is_network&order_dir=desc")
        assert r.status_code == 200
        items = r.json()["items"]
        assert items[0]["is_network"] is True

    def test_order_by_invalid_rejected(self, client):
        """Невалидный order_by — 422."""
        r = client.get("/api/v1/companies?order_by=invalid_field")
        assert r.status_code == 422


class TestCmsTypesEndpoint:
    """GET /cms-types — новый endpoint."""

    def test_cms_types_empty(self, client):
        """Пустая БД — пустой список."""
        r = client.get("/api/v1/cms-types")
        assert r.status_code == 200
        assert r.json()["items"] == []

    def test_cms_types_returns_unique(self, client, db_session):
        """Две компании с одинаковой CMS — одна запись."""
        create_company(db_session, cms="bitrix")
        create_company(db_session, cms="bitrix")
        create_company(db_session, cms="wordpress")
        db_session.commit()
        r = client.get("/api/v1/cms-types")
        items = r.json()["items"]
        assert "bitrix" in items
        assert "wordpress" in items
        assert len(items) == 2

    def test_cms_types_excludes_unknown(self, client, db_session):
        """cms='unknown' не включается в список."""
        create_company(db_session)  # default cms="unknown"
        create_company(db_session, cms="bitrix")
        db_session.commit()
        r = client.get("/api/v1/cms-types")
        items = r.json()["items"]
        assert "unknown" not in items
        assert len(items) == 1

    def test_cms_types_sorted(self, client, db_session):
        """Результат отсортирован по алфавиту."""
        create_company(db_session, cms="wordpress")
        create_company(db_session, cms="bitrix")
        create_company(db_session, cms="tilda")
        db_session.commit()
        r = client.get("/api/v1/cms-types")
        assert r.json()["items"] == ["bitrix", "tilda", "wordpress"]


class TestCombinedFilters:
    """Комбинация нескольких фильтров одновременно."""

    def test_segment_and_telegram(self, client, db_session):
        """Сегмент A + Telegram — обе компании."""
        create_company(db_session, segment="A", messengers={"telegram": "t.me/a"})
        create_company(db_session, segment="A", messengers={})
        create_company(db_session, segment="B", messengers={"telegram": "t.me/b"})
        db_session.commit()
        r = client.get("/api/v1/companies?segment=A&has_telegram=1")
        assert r.json()["total"] == 1

    def test_network_and_website(self, client, db_session):
        """Не сети + с сайтом."""
        create_company(db_session, is_network=True, website="https://net.ru")
        create_company(db_session, is_network=False, website="https://solo.ru")
        create_company(db_session, is_network=False, website=None)
        db_session.commit()
        r = client.get("/api/v1/companies?is_network=0&has_website=1")
        assert r.json()["total"] == 1

    def test_triple_filter(self, client, db_session):
        """Сегмент A + TG + min_score."""
        create_company(db_session, segment="A", crm_score=60, messengers={"telegram": "t.me/a"})
        create_company(db_session, segment="A", crm_score=20, messengers={"telegram": "t.me/b"})
        create_company(db_session, segment="B", crm_score=60, messengers={"telegram": "t.me/c"})
        db_session.commit()
        r = client.get("/api/v1/companies?segment=A&has_telegram=1&min_score=30")
        assert r.json()["total"] == 1
        assert r.json()["items"][0]["crm_score"] == 60

    def test_all_toggle_zeros(self, client, db_session):
        """Все toggle = 0 — крайний фильтр: нет мессенджеров, нет сайта, не сеть."""
        create_company(
            db_session,
            messengers={}, emails=[], website=None, is_network=False,
        )
        create_company(
            db_session,
            messengers={"telegram": "t.me/x"}, emails=["info@test.ru"],
            website="https://test.ru", is_network=True,
        )
        db_session.commit()
        r = client.get(
            "/api/v1/companies"
            "?has_telegram=0&has_whatsapp=0&has_email=0"
            "&has_website=0&has_vk=0&is_network=0"
        )
        assert r.json()["total"] == 1
