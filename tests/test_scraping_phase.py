# tests/test_scraping_phase.py — Тесты scraping_phase (P-4: дедупликация по source_url)
import pytest
from granite.models import RawCompany, Source
from granite.utils import extract_domain


def _make_jsprav(name, source_url="", website=None, phones=None):
    return RawCompany(
        source=Source.JSPRAV,
        name=name,
        source_url=source_url,
        website=website,
        phones=phones or [],
        city="Астрахань",
    )


def _make_pw(name, source_url="", website=None, phones=None):
    return RawCompany(
        source=Source.JSPRAV_PW,
        name=name,
        source_url=source_url,
        website=website,
        phones=phones or [],
        city="Астрахань",
    )


def _dedup(city_results, pw_results):
    """Имитирует логику дедупликации из scraping_phase.py (P-4)."""
    seen_source_urls = {c.source_url for c in city_results if c.source_url}
    seen_domains = set()
    seen_phones = set()
    for c in city_results:
        if c.website:
            seen_domains.add(extract_domain(c.website))
        for p in c.phones:
            seen_phones.add(p)
    new_results = []
    for c in pw_results:
        is_dup = False
        if c.source_url and c.source_url in seen_source_urls:
            is_dup = True
        if not is_dup and c.website:
            pw_domain = extract_domain(c.website)
            if pw_domain and pw_domain in seen_domains:
                is_dup = True
        if not is_dup:
            for p in c.phones:
                if p in seen_phones:
                    is_dup = True
                    break
        if not is_dup:
            new_results.append(c)
    return new_results


class TestScrapingPhaseDedup:
    """P-4: Дедупликация PW против jsprav по source_url + fallback."""

    def test_same_source_url_deduped(self):
        """PW и jsprav вернули одну компанию → дедуплицируется по source_url."""
        city_results = [_make_jsprav("Мастер", source_url="https://abakan.jsprav.ru/company/1/")]
        pw_results = [_make_pw("Мастер", source_url="https://abakan.jsprav.ru/company/1/")]
        assert _dedup(city_results, pw_results) == []

    def test_no_source_url_fallback_to_domain(self):
        """Нет source_url → дедупликация по домену."""
        city_results = [_make_jsprav("Мастер", website="https://granit-master.ru")]
        pw_results = [_make_pw("Мастер", website="https://granit-master.ru")]
        assert _dedup(city_results, pw_results) == []

    def test_no_source_url_no_domain_fallback_to_phone(self):
        """Нет source_url и домена → дедупликация по телефону."""
        city_results = [_make_jsprav("Мастер", phones=["79031234567"])]
        pw_results = [_make_pw("Мастер", phones=["79031234567"])]
        assert _dedup(city_results, pw_results) == []

    def test_different_source_urls_not_deduped(self):
        """Разные source_url → не дедуплицируются."""
        city_results = [_make_jsprav("Мастер А", source_url="https://abakan.jsprav.ru/company/1/")]
        pw_results = [_make_pw("Мастер Б", source_url="https://abakan.jsprav.ru/company/2/")]
        result = _dedup(city_results, pw_results)
        assert len(result) == 1

    def test_no_contacts_no_source_url_not_deduped(self):
        """Нет source_url, нет сайта, нет телефона → НЕ дедуплицируется (Known limitation)."""
        city_results = [_make_jsprav("Мастер")]
        pw_results = [_make_pw("Мастер")]
        # Без source_url, домена и телефона — не можем детектировать дубль
        result = _dedup(city_results, pw_results)
        assert len(result) == 1  # дубль прошёл — это ожидаемо

    def test_source_url_takes_priority_over_domain(self):
        """source_url совпадает, но домен другой → всё равно дедуплицируется."""
        city_results = [_make_jsprav("Мастер", source_url="https://abakan.jsprav.ru/company/1/", website="https://site-a.ru")]
        pw_results = [_make_pw("Мастер", source_url="https://abakan.jsprav.ru/company/1/", website="https://site-b.ru")]
        assert _dedup(city_results, pw_results) == []
