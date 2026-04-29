"""Template registry — JSON as single source of truth.

Loads templates from data/email_templates.json into memory at startup.
No DB reads for template content — only template_name in logs.
"""

import html as _html_module
import json
import re as _re
from dataclasses import dataclass, field
from pathlib import Path
from loguru import logger


@dataclass
class EmailTemplate:
    """Шаблон письма из JSON."""
    name: str
    channel: str          # "email" | "tg" | "wa"
    subject: str
    body: str
    body_type: str        # "plain" | "html"
    description: str = ""

    def render(self, **kwargs) -> str:
        """Подставить значения в плейсхолдеры шаблона.

        Безопасность: используется str.replace() (литеральная подстановка подстроки),
        НЕ str.format() или eval(). Инъекция невозможна.

        Для HTML-шаблонов (body_type='html') значения экранируются через html.escape()
        для предотвращения XSS.
        """
        result = self.body
        for key, value in kwargs.items():
            safe_value = _html_module.escape(str(value)) if self.body_type == "html" else str(value)
            result = result.replace(f"{{{key}}}", safe_value)
        leftovers = _re.findall(r'\{(\w+)\}', result)
        if leftovers:
            logger.warning(f"Template '{self.name}': unfilled placeholders: {leftovers}")
        return result

    def render_subject(self, **kwargs) -> str:
        """Подставить значения в тему письма.

        Subject — всегда plain text (RFC 2047), экранирование не требуется
        даже для HTML-шаблонов.
        """
        if not self.subject:
            return ""
        result = self.subject
        for key, value in kwargs.items():
            result = result.replace(f"{{{key}}}", str(value))
        return result

    def __repr__(self):
        return f"<EmailTemplate(name={self.name!r}, channel={self.channel!r}, body_type={self.body_type!r})>"


class TemplateRegistry:
    """Загрузка шаблонов из JSON. Инжектируется через app.state.template_registry."""

    # Системные шаблоны, обязательные для работы приложения
    _REQUIRED_TEMPLATES = ["follow_up_email_v1"]

    def __init__(self, json_path: str = "data/email_templates.json"):
        self._json_path = Path(json_path)
        self._templates: dict[str, EmailTemplate] = {}
        self._load()

    def _load(self) -> None:
        """Загрузить шаблоны из JSON-файла."""
        if not self._json_path.exists():
            raise FileNotFoundError(f"Template file not found: {self._json_path}")

        try:
            with open(self._json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Invalid JSON in {self._json_path}: {e}") from e

        if not isinstance(data, list):
            raise RuntimeError(f"Expected JSON array in {self._json_path}, got {type(data).__name__}")

        templates: dict[str, EmailTemplate] = {}
        names_seen: set[str] = set()

        for item in data:
            name = item.get("name")
            if not name:
                raise RuntimeError(f"Template without 'name' field in {self._json_path}")

            if name in names_seen:
                raise RuntimeError(f"Duplicate template name '{name}' in {self._json_path}")
            names_seen.add(name)

            templates[name] = EmailTemplate(
                name=name,
                channel=item.get("channel", "email"),
                subject=item.get("subject", ""),
                body=item.get("body", ""),
                body_type=item.get("body_type", "plain"),
                description=item.get("description", ""),
            )

        # Валидация системных шаблонов
        missing = [t for t in self._REQUIRED_TEMPLATES if t not in templates]
        if missing:
            raise RuntimeError(
                f"Required system templates missing in {self._json_path}: {missing}. "
                f"Application cannot start without them."
            )

        self._templates = templates
        logger.info(f"TemplateRegistry: loaded {len(self._templates)} templates from {self._json_path}")

    def get(self, name: str) -> EmailTemplate | None:
        """Получить шаблон по имени или None."""
        return self._templates.get(name)

    def list(self, channel: str | None = None) -> list[EmailTemplate]:
        """Список шаблонов, опционально отфильтрованный по каналу."""
        templates = list(self._templates.values())
        if channel:
            templates = [t for t in templates if t.channel == channel]
        return sorted(templates, key=lambda t: t.name)

    def reload(self) -> int:
        """Перезагрузить шаблоны из JSON (hot reload без рестарта сервера).

        Returns: количество загруженных шаблонов.
        Raises: RuntimeError / FileNotFoundError при невалидном JSON.
        """
        self._load()
        return len(self._templates)

    @property
    def json_path(self) -> Path:
        return self._json_path

    def __repr__(self):
        return f"<TemplateRegistry(path={self._json_path}, count={len(self._templates)})>"
