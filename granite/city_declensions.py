"""City declensions — static nominative→locative lookup.

Loads data/city_declensions.json at first import (module-level singleton).
Provides get_locative(city) for template rendering.

Why a separate module, not inside TemplateRegistry:
  - TemplateRegistry is generic (any channel, any placeholders).
  - Declensions are domain-specific (Russian grammar) and only needed
    where render_kwargs are assembled (campaigns, replies, followups).
  - Keeping it separate means: no changes to templates.py,
    easy to test in isolation, easy to extend (other cases later).

Fallback: if city is not in the dictionary, returns the nominative form
unchanged. This is safe — "в Москва" is grammatically wrong but better
than crashing. New cities should be added to the JSON as they appear.
"""

import json
from pathlib import Path
from loguru import logger

# Module-level singleton — loaded once at first import
_DECLENSIONS: dict[str, str] | None = None
_JSON_PATH = Path(__file__).resolve().parent.parent / "data" / "city_declensions.json"


def _load() -> dict[str, str]:
    """Load city_declensions.json into memory."""
    global _DECLENSIONS
    if _DECLENSIONS is not None:
        return _DECLENSIONS

    if not _JSON_PATH.exists():
        logger.warning(f"city_declensions.json not found at {_JSON_PATH}")
        _DECLENSIONS = {}
        return _DECLENSIONS

    try:
        with open(_JSON_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            logger.error(f"city_declensions.json: expected dict, got {type(data).__name__}")
            _DECLENSIONS = {}
            return _DECLENSIONS
        _DECLENSIONS = data
        logger.info(f"CityDeclensions: loaded {len(_DECLENSIONS)} entries from {_JSON_PATH}")
    except (json.JSONDecodeError, OSError) as e:
        logger.error(f"Failed to load city_declensions.json: {e}")
        _DECLENSIONS = {}

    return _DECLENSIONS


def get_locative(city: str) -> str:
    """Return locative case for a city name (WITHOUT preposition).

    Examples:
        get_locative("Москва")    → "Москве"
        get_locative("Казань")    → "Казани"
        get_locative("Сочи")      → "Сочи"       (indeclinable)
        get_locative("Неизвест")  → "Неизвест"   (fallback to nominative)

    Usage in templates: "в {city_locative}" → "в Москве"
    """
    declensions = _load()
    if not city:
        return city
    return declensions.get(city, city)


def reload() -> int:
    """Force reload from JSON (for hot-reload without server restart).

    Returns: number of entries loaded.
    """
    global _DECLENSIONS
    _DECLENSIONS = None
    return len(_load())
