"""Seed email templates from data/email_templates.json.

Задача 12 (impl): INSERT-only. Существующие шаблоны НЕ обновляются —
immutable-подход: если шаблон используется в отправленных письмах,
его содержимое не должно меняться.

Запуск:
  uv run python -m scripts.seed_templates
"""
import json
import os
import sys

# Добавляем корень проекта в путь для импорта
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from loguru import logger


def seed_templates(db_path: str | None = None) -> int:
    """Загрузить шаблоны из JSON в БД. INSERT-only — пропускает существующие.

    Returns:
        Количество добавленных шаблонов.
    """
    from granite.database import Database, CrmTemplateRow

    # Находим JSON-файл
    json_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "data", "email_templates.json"
    )
    if not os.path.exists(json_path):
        logger.error(f"Templates JSON not found: {json_path}")
        return 0

    with open(json_path, "r", encoding="utf-8") as f:
        templates = json.load(f)

    db = Database(db_path=db_path)
    session = db.SessionLocal()
    added = 0

    try:
        for tpl in templates:
            existing = session.query(CrmTemplateRow).filter_by(name=tpl["name"]).first()
            if existing:
                logger.debug(f"Template '{tpl['name']}' already exists (id={existing.id}), skipping")
                continue

            new_tpl = CrmTemplateRow(
                name=tpl["name"],
                channel=tpl["channel"],
                subject=tpl.get("subject", ""),
                body=tpl["body"],
                body_type=tpl.get("body_type", "plain"),
                description=tpl.get("description", ""),
            )
            session.add(new_tpl)
            added += 1
            logger.info(f"Added template: '{tpl['name']}'")

        session.commit()
        logger.info(f"Seed complete: {added} new templates added, "
                     f"{len(templates) - added} already existed")
    except Exception as e:
        session.rollback()
        logger.error(f"Seed failed: {e}")
        raise
    finally:
        session.close()
        db.engine.dispose()

    return added


if __name__ == "__main__":
    count = seed_templates()
    print(f"Added {count} templates")
