"""Тесты для TemplateRegistry и EmailTemplate (granite/templates.py).

Покрывает:
- Загрузка JSON, get(), list(), reload()
- render() и render_subject() (порт из CrmTemplateRow)
- Валидация при загрузке (обязательные шаблоны, дубликаты, невалидный JSON)
- Unknown placeholders warning
- Hot reload
"""
import json
import pytest
from pathlib import Path
from granite.templates import EmailTemplate, TemplateRegistry


# ============================================================
# Фикстуры
# ============================================================

MINIMAL_TEMPLATES = [
    {
        "name": "follow_up_email_v1",
        "channel": "email",
        "subject": "Re: {original_subject}",
        "body": "Follow-up {city}",
        "body_type": "plain",
        "description": "System required template",
    },
]

FULL_TEMPLATES = [
    {
        "name": "follow_up_email_v1",
        "channel": "email",
        "subject": "Re: {original_subject}",
        "body": "Follow-up for {city}",
        "body_type": "plain",
        "description": "System required",
    },
    {
        "name": "cold_email_v1",
        "channel": "email",
        "subject": "Offer for {city}",
        "body": "Hello from {from_name} in {city}. Unsub: {unsubscribe_url}",
        "body_type": "plain",
        "description": "Cold email v1",
    },
    {
        "name": "tg_intro",
        "channel": "tg",
        "subject": "",
        "body": "Hi from {from_name}",
        "body_type": "plain",
        "description": "TG intro",
    },
    {
        "name": "html_email",
        "channel": "email",
        "subject": "HTML for {company_name}",
        "body": "<p>{from_name}</p> <span>{company_name}</span>",
        "body_type": "html",
        "description": "HTML template",
    },
]


@pytest.fixture
def templates_dir(tmp_path):
    """Директория с тестовыми JSON-файлами шаблонов."""
    return tmp_path


def _write_json(path: Path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)


# ============================================================
# EmailTemplate — render() и render_subject()
# ============================================================

class TestEmailTemplateRender:
    """Unit-тесты EmailTemplate.render() и render_subject()."""

    def _make_template(self, body_type="plain", body="Hello {city}!", name="test_tpl"):
        return EmailTemplate(
            name=name, channel="email",
            subject="Offer for {company_name}",
            body=body, body_type=body_type,
        )

    def test_render_plain_replaces_literal(self):
        t = self._make_template(body_type="plain", body="Hello {city}!")
        assert t.render(city="Москва") == "Hello Москва!"

    def test_render_plain_no_escaping(self):
        t = self._make_template(body_type="plain", body="Company: {company_name}")
        result = t.render(company_name="<script>alert('xss')</script>")
        assert result == "Company: <script>alert('xss')</script>"

    def test_render_html_escapes_values(self):
        t = self._make_template(body_type="html", body="<p>{company_name}</p>")
        result = t.render(company_name="<script>alert('xss')</script>")
        assert "&lt;script&gt;" in result
        assert "<script>" not in result
        assert "<p>" in result  # Тело шаблона НЕ экранируется

    def test_render_html_ampersand_escaped(self):
        t = self._make_template(body_type="html", body="<p>{company_name}</p>")
        result = t.render(company_name="A & B")
        assert "A &amp; B" in result

    def test_render_html_quotes_escaped(self):
        t = self._make_template(body_type="html", body='<span>{city}</span>')
        result = t.render(city='Моск"ва')
        assert "Моск&quot;ва" in result

    def test_render_multiple_placeholders(self):
        t = self._make_template(
            body_type="html",
            body="<p>{from_name} из {city} для {company_name}</p>",
        )
        result = t.render(from_name="Александр", city="Москва", company_name="Гранит-М")
        assert "Александр" in result
        assert "Москва" in result
        assert "Гранит-М" in result

    def test_render_subject_no_escaping_for_html(self):
        t = self._make_template(body_type="html", body="<p>test</p>")
        result = t.render_subject(company_name="A & B <Co>")
        assert "A & B <Co>" in result
        assert "&amp;" not in result

    def test_render_subject_empty_returns_empty(self):
        t = EmailTemplate(name="no_subj", channel="tg", subject="", body="Hi", body_type="plain")
        assert t.render_subject(city="Москва") == ""

    def test_render_unfilled_placeholder_warning(self):
        """Незаполненные плейсхолдеры — warning в лог."""
        import logging
        t = self._make_template(body="Hello {city} and {unknown_var}")
        with pytest.warns(None):  # warning через loguru, не вызывает исключение
            result = t.render(city="Москва")
        assert "Москва" in result
        assert "{unknown_var}" in result  # Остался как есть

    def test_repr(self):
        t = EmailTemplate(name="test", channel="email", subject="Subj", body="Body", body_type="plain")
        assert "test" in repr(t)
        assert "email" in repr(t)


# ============================================================
# TemplateRegistry — загрузка, get, list, reload
# ============================================================

class TestTemplateRegistryLoad:
    """Тесты загрузки TemplateRegistry из JSON."""

    def test_load_valid_json(self, templates_dir):
        path = templates_dir / "templates.json"
        _write_json(path, FULL_TEMPLATES)
        reg = TemplateRegistry(str(path))
        assert len(reg._templates) == 4

    def test_load_missing_file_raises(self, templates_dir):
        with pytest.raises(FileNotFoundError):
            TemplateRegistry(str(templates_dir / "nonexistent.json"))

    def test_load_invalid_json_raises(self, templates_dir):
        path = templates_dir / "bad.json"
        path.write_text("not json{{{", encoding="utf-8")
        with pytest.raises(RuntimeError, match="Invalid JSON"):
            TemplateRegistry(str(path))

    def test_load_not_array_raises(self, templates_dir):
        path = templates_dir / "obj.json"
        _write_json(path, {"not": "array"})
        with pytest.raises(RuntimeError, match="Expected JSON array"):
            TemplateRegistry(str(path))

    def test_load_duplicate_name_raises(self, templates_dir):
        path = templates_dir / "dup.json"
        _write_json(path, [
            {"name": "same_name", "channel": "email", "body": "v1", "body_type": "plain"},
            {"name": "same_name", "channel": "email", "body": "v2", "body_type": "plain"},
        ])
        with pytest.raises(RuntimeError, match="Duplicate template name"):
            TemplateRegistry(str(path))

    def test_load_missing_required_template_raises(self, templates_dir):
        path = templates_dir / "no_required.json"
        _write_json(path, [
            {"name": "some_other", "channel": "email", "body": "Hello", "body_type": "plain"},
        ])
        with pytest.raises(RuntimeError, match="Required system templates missing"):
            TemplateRegistry(str(path))

    def test_load_missing_name_field_raises(self, templates_dir):
        path = templates_dir / "no_name.json"
        _write_json(path, [
            {"channel": "email", "body": "Hello", "body_type": "plain"},
        ])
        with pytest.raises(RuntimeError, match="without 'name' field"):
            TemplateRegistry(str(path))

    def test_load_with_required_template_ok(self, templates_dir):
        path = templates_dir / "minimal.json"
        _write_json(path, MINIMAL_TEMPLATES)
        reg = TemplateRegistry(str(path))
        assert reg.get("follow_up_email_v1") is not None


class TestTemplateRegistryGetList:
    """Тесты get() и list()."""

    @pytest.fixture
    def registry(self, templates_dir):
        path = templates_dir / "templates.json"
        _write_json(path, FULL_TEMPLATES)
        return TemplateRegistry(str(path))

    def test_get_existing(self, registry):
        t = registry.get("cold_email_v1")
        assert t is not None
        assert t.name == "cold_email_v1"
        assert t.channel == "email"

    def test_get_nonexistent_returns_none(self, registry):
        assert registry.get("no_such_template") is None

    def test_list_all(self, registry):
        all_templates = registry.list()
        assert len(all_templates) == 4
        # Сортировка по имени
        names = [t.name for t in all_templates]
        assert names == sorted(names)

    def test_list_filter_by_channel(self, registry):
        email_templates = registry.list(channel="email")
        assert len(email_templates) == 3
        assert all(t.channel == "email" for t in email_templates)

        tg_templates = registry.list(channel="tg")
        assert len(tg_templates) == 1
        assert tg_templates[0].name == "tg_intro"

    def test_list_filter_no_match(self, registry):
        wa_templates = registry.list(channel="wa")
        assert len(wa_templates) == 0

    def test_json_path_property(self, registry, templates_dir):
        assert registry.json_path == templates_dir / "templates.json"


class TestTemplateRegistryReload:
    """Тесты hot reload."""

    def test_reload_picks_up_changes(self, templates_dir):
        path = templates_dir / "templates.json"
        _write_json(path, FULL_TEMPLATES)
        reg = TemplateRegistry(str(path))
        assert len(reg._templates) == 4

        # Добавляем новый шаблон в JSON
        updated = FULL_TEMPLATES + [
            {
                "name": "new_template",
                "channel": "email",
                "subject": "New",
                "body": "New body",
                "body_type": "plain",
                "description": "Added after initial load",
            }
        ]
        _write_json(path, updated)

        count = reg.reload()
        assert count == 5
        assert reg.get("new_template") is not None

    def test_reload_invalid_json_raises_but_keeps_old(self, templates_dir):
        path = templates_dir / "templates.json"
        _write_json(path, FULL_TEMPLATES)
        reg = TemplateRegistry(str(path))
        assert len(reg._templates) == 4

        # Пишем невалидный JSON
        path.write_text("broken{{{", encoding="utf-8")
        with pytest.raises(RuntimeError):
            reg.reload()

        # Старые шаблоны должны остаться
        assert len(reg._templates) == 4
        assert reg.get("cold_email_v1") is not None

    def test_reload_missing_required_raises_but_keeps_old(self, templates_dir):
        path = templates_dir / "templates.json"
        _write_json(path, FULL_TEMPLATES)
        reg = TemplateRegistry(str(path))

        # Убираем обязательный шаблон
        _write_json(path, [
            {"name": "some_other", "channel": "email", "body": "Hello", "body_type": "plain"},
        ])
        with pytest.raises(RuntimeError, match="Required system templates missing"):
            reg.reload()

        # Старые шаблоны на месте
        assert reg.get("follow_up_email_v1") is not None


class TestTemplateRegistryRepr:
    def test_repr(self, templates_dir):
        path = templates_dir / "templates.json"
        _write_json(path, FULL_TEMPLATES)
        reg = TemplateRegistry(str(path))
        r = repr(reg)
        assert "TemplateRegistry" in r
        assert "4" in r  # count
