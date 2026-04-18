"""SEED: стартовые шаблоны для холодного аутрича (ретушь памятников).

Шаблоны используют плейсхолдеры {from_name}, {city}, {company_name}, {website}.
Подстановка происходит автоматически через template.render().

Запуск: python -m scripts.seed_crm_templates
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from granite.database import Database, CrmTemplateRow
from loguru import logger

TEMPLATES = [
    {
        "name": "cold_email_1",
        "channel": "email",
        "subject": "Ретушь фото для памятников — быстро и качественно",
        "body": (
            "Добрый день!\n\n"
            "Меня зовут {from_name}, я занимаюсь AI-ретушью фотографий для гравировки на памятниках.\n\n"
            "Обычно ретушь занимает несколько часов — у меня результат готов за 10 минут.\n"
            "Принимаю фото любого качества: старые, помятые, низкое разрешение.\n\n"
            "Работаю с мастерскими по всей России. Первый портрет — бесплатно, чтобы вы могли "
            "оценить качество.\n\n"
            "Если актуально — напишите, пришлю примеры работ.\n\n"
            "С уважением,\n{from_name}"
        ),
        "description": "Первое холодное письмо. Короткое, с оффером бесплатного первого портрета.",
    },
    {
        "name": "follow_up_email",
        "channel": "email",
        "subject": "Re: Ретушь фото для памятников",
        "body": (
            "Добрый день!\n\n"
            "Писал вам несколько дней назад по теме ретуши фото для гравировки.\n\n"
            "Понимаю, что входящих сообщений много — просто хочу уточнить: актуально ли "
            "это направление для вашей мастерской?\n\n"
            "Если не нужно — скажите, больше не буду беспокоить.\n\n"
            "С уважением,\n{from_name}"
        ),
        "description": "Follow-up если не ответили на первое письмо.",
    },
    {
        "name": "tg_intro",
        "channel": "tg",
        "subject": "",
        "body": (
            "Добрый день! Меня зовут {from_name}, занимаюсь AI-ретушью фото для гравировки на "
            "памятниках. Результат за 10 минут, принимаю любое качество фото. "
            "Первый портрет бесплатно — если интересно, пришлю примеры?"
        ),
        "description": "Первое сообщение в Telegram. Без ссылок — только текст.",
    },
    {
        "name": "tg_follow_up",
        "channel": "tg",
        "subject": "",
        "body": (
            "Добрый день, писал раньше про ретушь фото для памятников. "
            "Просто хотел уточнить — актуально ли для вас?"
        ),
        "description": "Follow-up в TG если не ответили.",
    },
    {
        "name": "wa_intro",
        "channel": "wa",
        "subject": "",
        "body": (
            "Здравствуйте! Меня зовут {from_name}. Занимаюсь AI-ретушью фото для гравировки "
            "на памятниках — результат за 10 минут, любое качество фото. "
            "Первый портрет бесплатно. Интересно?"
        ),
        "description": "Первое сообщение в WhatsApp. Без ссылок.",
    },
    {
        "name": "wa_follow_up",
        "channel": "wa",
        "subject": "",
        "body": (
            "Добрый день, писал вам ранее про ретушь. Актуально?"
        ),
        "description": "Короткий follow-up в WA.",
    },
]


def _apply_templates(session) -> tuple[int, int]:
    """UPSERT шаблонов в переданную сессию. Возвращает (inserted, updated)."""
    inserted = 0
    updated = 0

    for t in TEMPLATES:
        existing = session.query(CrmTemplateRow).filter_by(name=t["name"]).first()
        if existing:
            existing.channel = t["channel"]
            existing.subject = t["subject"]
            existing.body = t["body"]
            existing.description = t.get("description", "")
            updated += 1
        else:
            session.add(CrmTemplateRow(**t))
            inserted += 1

    logger.info(
        f"SEED crm_templates: создано {inserted}, обновлено {updated}"
    )
    return inserted, updated


def seed_crm_templates():
    db = Database()
    with db.session_scope() as session:
        inserted, updated = _apply_templates(session)
    db.engine.dispose()
    return inserted + updated


if __name__ == "__main__":
    seed_crm_templates()
