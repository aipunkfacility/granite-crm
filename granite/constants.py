"""Общие константы проекта Granite CRM.

Домены классифицируются по назначению:
- MESSENGER_DOMAINS — соцсети/мессенджеры, не являются «сайтом компании»
- NON_NETWORK_DOMAINS — крупные площадки, не являются «сетью» филиалов
- SPAM_DOMAINS — известные агрегаторы-спам
"""

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
