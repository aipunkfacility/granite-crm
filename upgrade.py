import os

path_v6 = r'f:\Dev\Projects\GRANITE\granite-crm-db\docs\backend-dev-plan-v6.md'
path_v7 = r'f:\Dev\Projects\GRANITE\granite-crm-db\docs\backend-dev-plan-v7.md'

with open(path_v6, 'r', encoding='utf-8') as f:
    text = f.read()

# 1. Header
text = text.replace('Backend Development Plan v6', 'Backend Development Plan v7')
text = text.replace('Изменения v5→v6: Исправлена двойная сериализация JSON, дополнены схемы и тесты (по v5-critique). (2 критических, 4 высоких, 5 средних, 2 низких).', 'Изменения v6→v7: Исправлены 5 архитектурных уязвимостей по итогам ревью (datetime в Pydantic, json_extract, каскад при переименовании шаблона, heartbeat для stale-check, фикс утечки сессии в seed).')

# 2. schemas.py due_date
text = text.replace('due_date: Optional[str] = None', 'due_date: Optional[datetime] = None')
text = text.replace('class UpdateTaskRequest(BaseModel):', 'from datetime import datetime\n\nclass UpdateTaskRequest(BaseModel):')

# 3. Tasks - Create Task
text = text.replace('''    # FIX 1.3: парсинг ISO 8601 строки в datetime для Column(DateTime)
    due_date = None
    if data.due_date:
        try:
            due_date = dt.fromisoformat(data.due_date)
        except ValueError:
            raise HTTPException(400, f"Invalid due_date: {data.due_date}")''', '''    # FIX v7-1.3: due_date теперь datetime в Pydantic. Парсинг автоматический.
    due_date = data.due_date''')

# 4. Tasks - Update task
text = text.replace('''    if key == "due_date":
        if value is not None:
            try:
                task.due_date = datetime.fromisoformat(value)
            except ValueError:
                from fastapi import HTTPException
                raise HTTPException(400, f"Invalid due_date: {value}")
        else:
            task.due_date = None''', '''    if key == "due_date":
        task.due_date = value''')

# 5. Templates (cascade update)
text = text.replace('''    if "name" in updates and updates["name"] != t.name:
        dup = db.query(CrmTemplateRow).filter_by(name=updates["name"]).first()
        if dup:
            raise HTTPException(409, f"Template name '{updates['name']}' already taken")''', '''    if "name" in updates and updates["name"] != t.name:
        dup = db.query(CrmTemplateRow).filter_by(name=updates["name"]).first()
        if dup:
            raise HTTPException(409, f"Template name '{updates['name']}' already taken")
        
        # FIX v7-1.1: Каскадное обновление в кампаниях
        from sqlalchemy import text as sa_text
        db.execute(sa_text(
            "UPDATE crm_email_campaigns SET template_name = :new_name WHERE template_name = :old_name"
        ), {"new_name": updates["name"], "old_name": t.name})''')

# 6. JSON Extract
text = text.replace('''has_whatsapp: Optional[int] = Query(None)
if has_whatsapp == 1:
    # Есть WhatsApp с непустым значением: "whatsapp":"7900..."
    q = q.filter(
        EnrichedCompanyRow.messengers.cast(String).like('%"whatsapp":"%')
    )
elif has_whatsapp == 0:
    # Нет ключа whatsapp ИЛИ значение пустое/null
    q = q.filter(
        ~EnrichedCompanyRow.messengers.cast(String).like('%"whatsapp":"%')
    )

has_telegram: Optional[int] = Query(None)
if has_telegram == 1:
    q = q.filter(
        EnrichedCompanyRow.messengers.cast(String).like('%"telegram":"%')
    )
elif has_telegram == 0:
    q = q.filter(
        ~EnrichedCompanyRow.messengers.cast(String).like('%"telegram":"%')
    )''', '''from sqlalchemy import text as sa_text

has_whatsapp: Optional[int] = Query(None)
if has_whatsapp == 1:
    # FIX v7-1.4: Используется json_extract (SQLite 3.43+)
    q = q.filter(sa_text("json_extract(messengers, '$.whatsapp') IS NOT NULL AND json_extract(messengers, '$.whatsapp') != ''"))
elif has_whatsapp == 0:
    q = q.filter(sa_text("json_extract(messengers, '$.whatsapp') IS NULL OR json_extract(messengers, '$.whatsapp') = ''"))

has_telegram: Optional[int] = Query(None)
if has_telegram == 1:
    q = q.filter(sa_text("json_extract(messengers, '$.telegram') IS NOT NULL AND json_extract(messengers, '$.telegram') != ''"))
elif has_telegram == 0:
    q = q.filter(sa_text("json_extract(messengers, '$.telegram') IS NULL OR json_extract(messengers, '$.telegram') = ''"))''')

# 7. Seed CRM
text = text.replace('''def seed_crm_templates(session=None):
    """Создать/обновить CRM шаблоны. Если session=None — использует Database()."""
    from granite.database import CrmTemplateRow, Database

    if session is None:
        db = Database()
        session = db.session_scope().__enter__()

    created = 0
    updated = 0
    for tpl in TEMPLATES:''', '''def seed_crm_templates(session=None):
    """Создать/обновить CRM шаблоны. Если session=None — использует Database()."""
    from granite.database import Database

    # FIX v7-1.5: Правильное управление сессией через with
    if session is None:
        db = Database()
        with db.session_scope() as s:
            return _do_seed(s)
    return _do_seed(session)

def _do_seed(session):
    from granite.database import CrmTemplateRow
    from loguru import logger
    from datetime import datetime, timezone

    created = 0
    updated = 0
    for tpl in TEMPLATES:''')

text = text.replace('''    session.commit()
    logger.info(f"SEED crm_templates: создано {created}, обновлено {updated}")
    return created''', '''    # сессия коммитится на уровне caller-а
    logger.info(f"SEED crm_templates: создано {created}, обновлено {updated}")
    return created''')

# 8. heartbeat updated_at
text = text.replace('''        # FIX 1.2: CrmEmailCampaignRow не имеет updated_at.
        # Используем started_at (когда рассылка реально началась) или created_at.
        last_activity = c.started_at or c.created_at''', '''        # FIX v7-1.2: Stale check должен использовать updated_at (heartbeat).
        # Подразумевается, что в Шаге 1 добавлена миграция с updated_at для CrmEmailCampaignRow.
        last_activity = c.updated_at or c.started_at or c.created_at''')

text = text.replace('''        "completed_at": c.completed_at.isoformat() if c.completed_at else None,''', '''        "completed_at": c.completed_at.isoformat() if c.completed_at else None,
        "updated_at": c.updated_at.isoformat() if getattr(c, 'updated_at', None) else None,  # FIX v7-1.2''')

# Add history V6 -> V7
history_entry = '''### v6 → v7 (5 критических архитектурных правок по ревью)

| FIX | Что | Где | Критичность |
|-----|-----|-----|-------------|
| 1.1 | Отсутствие каскада при переименовании шаблона → `UPDATE crm_email_campaigns` | Шаг 2, templates.py | 🔴 Критический |
| 1.2 | Ложноположительный сброс долгих рассылок → смотрим на `updated_at` (heartbeat) | Шаг 15, campaigns.py | 🔴 Критический |
| 1.3 | Ручной парсинг дат → `due_date: Optional[datetime]` в Pydantic | Шаг 1 и 5, schemas.py | 🟡 Высокий |
| 1.4 | SQLite `LIKE` хрупок к пробелам в JSON → `json_extract()` (доступен с Python 3.12) | Шаг 10, companies.py | 🟡 Высокий |
| 1.5 | Вызов `session_scope().__enter__()` без гарантии `__exit__()` → `with` и `_do_seed` | Шаг 12, seed_crm_templates.py | 🟡 Высокий |

'''
text = text.replace('## История изменений\n\n### v4 → v5', '## История изменений\n\n' + history_entry + '### v4 → v5')

with open(path_v7, 'w', encoding='utf-8') as f:
    f.write(text)

print("v7 generated.")
