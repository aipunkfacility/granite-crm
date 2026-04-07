# tests/test_utils.py
import pytest
from granite.utils import normalize_phone, normalize_phones, extract_emails, \
    compare_names, extract_street, extract_domain, pick_best_value


class TestNormalizePhone:
    def test_full_format_plus7(self):
        assert normalize_phone("+79031234567") == "79031234567"

    def test_full_format_8(self):
        assert normalize_phone("89031234567") == "79031234567"

    def test_with_spaces(self):
        assert normalize_phone("+7 (903) 123-45-67") == "79031234567"

    def test_short_format_10_digits(self):
        assert normalize_phone("9031234567") == "79031234567"

    def test_invalid_empty(self):
        assert normalize_phone("") is None

    def test_invalid_letters(self):
        assert normalize_phone("abc") is None

    def test_invalid_too_short(self):
        assert normalize_phone("123") is None

    def test_normalize_phones_dedup(self):
        result = normalize_phones(["+79031234567", "89031234567", "79031234567"])
        assert result == ["79031234567"]


class TestExtractEmails:
    def test_single(self):
        assert extract_emails("Contact: info@site.ru") == ["info@site.ru"]

    def test_multiple(self):
        result = extract_emails("Email: a@b.com and test@c.ru")
        assert "a@b.com" in result and "test@c.ru" in result

    def test_none_input(self):
        assert extract_emails(None) == []

    def test_no_emails(self):
        assert extract_emails("No emails here") == []


class TestCompareNames:
    def test_exact_match(self):
        assert compare_names("Гранит-Мастер", "Гранит-Мастер") is True

    def test_case_insensitive(self):
        assert compare_names("Гранит-Мастер", "гранит-мастер") is True

    def test_reversed_words(self):
        assert compare_names("Гранит-Мастер Иванов", "Иванов Гранит-Мастер", 85) is True

    def test_different_companies(self):
        assert compare_names("Гранит-Мастер", "Мир Камня", 88) is False

    def test_empty(self):
        assert compare_names("", "Гранит-Мастер") is False


class TestExtractDomain:
    def test_simple(self):
        assert extract_domain("https://site.ru/page") == "site.ru"

    def test_www(self):
        assert extract_domain("www.site.ru") == "site.ru"

    def test_none(self):
        assert extract_domain(None) is None


class TestPickBestValue:
    def test_longest(self):
        assert pick_best_value("коротко", "среднее значение", "самое длинное значение") \
            == "самое длинное значение"

    def test_empty(self):
        assert pick_best_value("", None) == ""
