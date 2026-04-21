# tests/test_merger.py — Тесты merger.py: FIX 2.1 (SEO-name приоритет) + A-5 (не-локальные телефоны)
import pytest
from granite.dedup.merger import merge_cluster


class TestMergeClusterSeoNamePriority:
    """FIX 2.1: При слиянии кластеров SEO-названия НЕ должны побеждать реальные имена."""

    def test_real_name_wins_over_seo(self):
        """Реальное имя 'Гранит-Мастер' побеждает SEO 'купить памятники в Абакане'."""
        records = [
            {"id": 1, "name": "купить памятники в Абакане недорого", "phones": ["79031234567"],
             "address_raw": "", "website": "", "emails": [], "city": "Абаза"},
            {"id": 2, "name": "Гранит-Мастер", "phones": [], "address_raw": "",
             "website": "", "emails": [], "city": "Абаза"},
        ]
        merged = merge_cluster(records)
        assert merged["name_best"] == "Гранит-Мастер"

    def test_shortest_seo_when_all_seo(self):
        """Если все имена — SEO, берётся самое короткое (ближе к реальному)."""
        records = [
            {"id": 1, "name": "купить памятники в Абакане недорого с установкой от производителя", "phones": [],
             "address_raw": "", "website": "", "emails": [], "city": "Абаза"},
            {"id": 2, "name": "памятники из гранита", "phones": [],
             "address_raw": "", "website": "", "emails": [], "city": "Абаза"},
        ]
        merged = merge_cluster(records)
        # "памятники из гранита" короче — это лучшее из SEO
        assert merged["name_best"] == "памятники из гранита"

    def test_longest_real_name_wins(self):
        """Из нескольких реальных имён берётся самое длинное (наиболее полное)."""
        records = [
            {"id": 1, "name": "Гранит-Мастер", "phones": [],
             "address_raw": "", "website": "", "emails": [], "city": "Абаза"},
            {"id": 2, "name": "Гранит-Мастер ООО Памятники", "phones": [],
             "address_raw": "", "website": "", "emails": [], "city": "Абаза"},
        ]
        merged = merge_cluster(records)
        assert merged["name_best"] == "Гранит-Мастер ООО Памятники"

    def test_single_record_name_preserved(self):
        """Одиночная запись — имя сохраняется как есть."""
        records = [
            {"id": 1, "name": "ИП Смирнов", "phones": ["79031234567"],
             "address_raw": "ул. Ленина, 10", "website": "http://test.ru", "emails": [],
             "city": "Абаза"},
        ]
        merged = merge_cluster(records)
        assert merged["name_best"] == "ИП Смирнов"

    def test_empty_cluster(self):
        """Пустой кластер → пустой результат."""
        merged = merge_cluster([])
        assert merged == {}

    def test_seo_name_with_city(self):
        """SEO-имя с городом ('Памятники в Абакане') считается SEO."""
        records = [
            {"id": 1, "name": "Памятники в Абакане", "phones": [],
             "address_raw": "", "website": "", "emails": [], "city": "Абаза"},
            {"id": 2, "name": "Мастерская Памяти", "phones": [],
             "address_raw": "", "website": "", "emails": [], "city": "Абаза"},
        ]
        merged = merge_cluster(records)
        assert merged["name_best"] == "Мастерская Памяти"


class TestMergeClusterNonLocalPhones:
    """A-5: Кластер с НЕ-локальными телефонами помечается needs_review."""

    def test_all_moscow_phones_for_abaza_needs_review(self):
        """Все телефоны — московские DEF для Абазы → needs_review."""
        records = [
            {"id": 1, "name": "Гранит-Мастер", "phones": ["74951234567", "74991234567"],
             "address_raw": "", "website": "http://test.ru", "emails": [], "city": "Абаза"},
        ]
        merged = merge_cluster(records)
        assert merged["needs_review"] is True
        assert "all_non_local_phones" in merged["review_reason"]

    def test_mixed_local_and_nonlocal_ok(self):
        """Микс локальных и не-локальных телефонов → НЕ needs_review (по A-5)."""
        records = [
            {"id": 1, "name": "Гранит-Мастер", "phones": ["74951234567", "79031234567"],
             "address_raw": "", "website": "http://test.ru", "emails": [], "city": "Абаза"},
        ]
        merged = merge_cluster(records)
        # 7903 — мобильный, локальный → не все не-локальные
        assert "all_non_local_phones" not in merged.get("review_reason", "")

    def test_moscow_phones_for_moscow_ok(self):
        """Московские телефоны для Москвы → НЕ needs_review."""
        records = [
            {"id": 1, "name": "Гранит-Мастер", "phones": ["74951234567"],
             "address_raw": "", "website": "http://test.ru", "emails": [], "city": "Москва"},
        ]
        merged = merge_cluster(records)
        assert "all_non_local_phones" not in merged.get("review_reason", "")

    def test_federal_phone_ok(self):
        """8-800 для любого города → НЕ needs_review (федеральный = OK)."""
        records = [
            {"id": 1, "name": "Гранит-Мастер", "phones": ["78001234567"],
             "address_raw": "", "website": "http://test.ru", "emails": [], "city": "Абаза"},
        ]
        merged = merge_cluster(records)
        assert "all_non_local_phones" not in merged.get("review_reason", "")

    def test_spb_phones_for_non_spb_needs_review(self):
        """Питерский DEF (812) для не-СПб → needs_review."""
        records = [
            {"id": 1, "name": "Гранит-Мастер", "phones": ["78121234567"],
             "address_raw": "", "website": "http://test.ru", "emails": [], "city": "Абаза"},
        ]
        merged = merge_cluster(records)
        assert merged["needs_review"] is True
        assert "all_non_local_phones" in merged["review_reason"]

    def test_spb_phones_for_spb_ok(self):
        """Питерский DEF для СПб → OK."""
        records = [
            {"id": 1, "name": "Гранит-Мастер", "phones": ["78121234567"],
             "address_raw": "", "website": "http://test.ru", "emails": [], "city": "Санкт-Петербург"},
        ]
        merged = merge_cluster(records)
        assert "all_non_local_phones" not in merged.get("review_reason", "")

    def test_no_phones_no_review(self):
        """Без телефонов → A-5 не срабатывает."""
        records = [
            {"id": 1, "name": "Гранит-Мастер", "phones": [],
             "address_raw": "", "website": "http://test.ru", "emails": [], "city": "Абаза"},
        ]
        merged = merge_cluster(records)
        assert "all_non_local_phones" not in merged.get("review_reason", "")

    def test_combined_reasons(self):
        """A-5 добавляется к существующим причинам needs_review."""
        records = [
            {"id": 1, "name": "Гранит-Мастер", "phones": ["74951234567"],
             "address_raw": "ул. Ленина, 10", "website": "http://test.ru", "emails": [], "city": "Абаза"},
            {"id": 2, "name": "Мир Камня", "phones": ["74991234567"],
             "address_raw": "ул. Маркса, 5", "website": "", "emails": [], "city": "Абаза"},
        ]
        merged = merge_cluster(records)
        # Разные адреса + все телефоны не-локальные
        assert merged["needs_review"] is True
        assert "all_non_local_phones" in merged["review_reason"]


class TestMergeClusterExistingLogic:
    """Проверка что существующая логика merger не сломана."""

    def test_contacts_over_limit_needs_review(self):
        """Слишком много контактов → needs_review."""
        records = [
            {"id": 1, "name": "Тест", "phones": [f"7903{i:07d}" for i in range(7)],
             "address_raw": "", "website": "", "emails": [], "city": "Абаза"},
        ]
        merged = merge_cluster(records)
        assert merged["needs_review"] is True
        assert "contacts_over_limit" in merged["review_reason"]

    def test_different_cities_needs_review(self):
        """Разные города → needs_review."""
        records = [
            {"id": 1, "name": "Гранит-Мастер", "phones": [], "address_raw": "",
             "website": "", "emails": [], "city": "Абаза"},
            {"id": 2, "name": "Гранит-Мастер", "phones": [], "address_raw": "",
             "website": "", "emails": [], "city": "Абакан"},
        ]
        merged = merge_cluster(records)
        assert merged["needs_review"] is True
        assert "different_cities" in merged["review_reason"]

    def test_normal_merge_no_review(self):
        """Нормальное слияние → needs_review=False."""
        records = [
            {"id": 1, "name": "Гранит-Мастер", "phones": ["79031234567"],
             "address_raw": "ул. Ленина, 10", "website": "http://test.ru",
             "emails": ["info@test.ru"], "city": "Абаза"},
        ]
        merged = merge_cluster(records)
        assert merged["needs_review"] is False
        assert merged["review_reason"] == ""

    def test_merged_from_ids(self):
        """merged_from содержит ID исходных записей."""
        records = [
            {"id": 10, "name": "Тест1", "phones": [], "address_raw": "",
             "website": "", "emails": [], "city": "Абаза"},
            {"id": 20, "name": "Тест2", "phones": [], "address_raw": "",
             "website": "", "emails": [], "city": "Абаза"},
        ]
        merged = merge_cluster(records)
        assert merged["merged_from"] == [10, 20]
