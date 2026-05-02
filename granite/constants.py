"""Общие константы проекта Granite CRM.

Домены классифицируются по назначению:
- MESSENGER_DOMAINS — соцсети/мессенджеры, не являются «сайтом компании»
- NON_NETWORK_DOMAINS — крупные площадки, не являются «сетью» филиалов
- SPAM_DOMAINS — известные агрегаторы-спам
"""

import os

import yaml


def _load_sender_config() -> dict:
    """Загрузить секцию sender из config.yaml (кэшируется при первом вызове)."""
    if _load_sender_config._cache is not None:
        return _load_sender_config._cache
    try:
        config_path = os.environ.get("GRANITE_CONFIG", "config.yaml")
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        _load_sender_config._cache = config.get("sender", {})
    except Exception:
        _load_sender_config._cache = {}
    return _load_sender_config._cache


_load_sender_config._cache = None


def get_sender_field(key: str, default: str = "") -> str:
    """Получить поле из секции sender конфига, с fallback на env.

    Приоритет: config.yaml sender.KEY → env KEY → default.
    """
    cfg = _load_sender_config()
    env_key = key.upper()  # whatsapp → WHATSAPP, from_name → FROM_NAME
    return cfg.get(key) or os.environ.get(env_key, default)

MESSENGER_DOMAINS: frozenset[str] = frozenset({
    "vk.com", "vk.link", "vkontakte.ru",
    "t.me", "telegram.me", "telegram.org",
    "wa.me", "api.whatsapp.com",
    "ok.ru", "odnoklassniki.ru",
    "instagram.com", "facebook.com",
    "youtube.com", "youtu.be",
})

NON_NETWORK_DOMAINS: frozenset[str] = frozenset({
    "vk.com", "vk.link", "vkontakte.ru",
    "t.me", "telegram.me", "telegram.org",
    "wa.me", "api.whatsapp.com",
    "ok.ru", "odnoklassniki.ru",
    "youtube.com", "youtu.be",
    "yandex.ru", "google.com",
    "2gis.ru", "avito.ru",
    "instagram.com", "facebook.com",
})

SPAM_DOMAINS: frozenset[str] = frozenset({
    "uslugio.com", "zoon.ru", "jsprav.ru", "yell.ru",
    "orgpage.ru", "spravka-inform.ru", "2gis.ru",
    "vmkros.ru", "exkluziv-granit.ru", "gravestone.ru",
    "katangranit.ru", "grandmonument.ru", "rting.ru",
    "altai-offroad.ru", "nikapamyatniki.ru", "памятники-цены.рф",
})
