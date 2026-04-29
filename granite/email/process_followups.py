"""Follow-up executor — отправка писем по созревшим задачам.

Задача 11: process_followups() находит созревшие CrmTaskRow
(task_type='follow_up', status='pending', due_date < now)
и отправляет follow-up письмо через EmailSender.

Тема письма: Re: {original_subject} — извлекается из последнего
исходящего CrmTouchRow для компании.
"""
import re
from datetime import datetime, timezone
from loguru import logger

from granite.email.sender import EmailSender

__all__ = ["process_followups"]

# Максимальное число попыток отправки, после которого задача → failed
_MAX_RETRIES = 3

# Парсим retry_count из description: "[retry:2]"
_RETRY_RE = re.compile(r"\[retry:(\d+)\]")


def _get_retry_count(task) -> int:
    """Извлечь счётчик попыток из task.description."""
    if not task.description:
        return 0
    m = _RETRY_RE.search(task.description)
    return int(m.group(1)) if m else 0


def _set_retry_count(task, count: int) -> None:
    """Записать счётчик попыток в task.description."""
    old = task.description or ""
    # Удалить старый маркер
    new = _RETRY_RE.sub("", old).strip()
    new = f"[retry:{count}] {new}" if new else f"[retry:{count}]"
    task.description = new


def process_followups(db_session) -> int:
    """Обработать созревшие follow-up задачи.

    Для каждой задачи:
    1. Найти компанию, контакт, последний исходящий touch.
    2. Рендерить follow-up шаблон.
    3. Отправить письмо через EmailSender.
    4. Пометить задачу как done.

    FIX P3-H1: commit-per-task — коммит после каждой задачи,
    чтобы не потерять уже обработанные при сбое.

    FIX P3-H2: лимит повторных попыток — после 3 неудачных
    отправок задача переходит в status="failed".

    Returns:
        Количество отправленных follow-up писем.
    """
    from granite.database import (
        CrmTaskRow, CrmContactRow, CrmTouchRow,
        CompanyRow, CrmEmailLogRow,
    )
    from granite.templates import TemplateRegistry

    now = datetime.now(timezone.utc)

    # Найти созревшие задачи
    tasks = (
        db_session.query(CrmTaskRow)
        .filter(
            CrmTaskRow.task_type == "follow_up",
            CrmTaskRow.status == "pending",
            CrmTaskRow.due_date.isnot(None),
            CrmTaskRow.due_date <= now,
        )
        .all()
    )

    if not tasks:
        logger.debug("process_followups: no due follow-up tasks")
        return 0

    # Загрузить follow-up шаблон из TemplateRegistry
    # NOTE: process_followups вызывается через CLI/CRON, без request.
    # Используем TemplateRegistry напрямую с путём по умолчанию.
    try:
        registry = TemplateRegistry()
    except FileNotFoundError:
        logger.warning("process_followups: email_templates.json not found, skipping")
        return 0
    template = registry.get("follow_up_email_v1")
    if not template:
        logger.warning("process_followups: template 'follow_up_email_v1' not found, skipping")
        return 0

    sender = EmailSender()
    sent_count = 0

    for task in tasks:
        try:
            company = db_session.get(CompanyRow, task.company_id)
            if not company:
                logger.warning(f"task_id={task.id}: company_id={task.company_id} not found")
                task.status = "done"
                task.completed_at = now
                db_session.commit()
                continue

            # Найти email компании
            emails = company.emails or []
            if not emails:
                logger.warning(f"task_id={task.id}: no email for company_id={task.company_id}")
                task.status = "done"
                task.completed_at = now
                db_session.commit()
                continue

            email_to = emails[0].lower().strip()

            # Найти контакт
            contact = db_session.query(CrmContactRow).filter_by(
                company_id=task.company_id
            ).first()

            # Проверить stop_automation
            if contact and contact.stop_automation:
                logger.info(f"task_id={task.id}: stop_automation=1, cancelling")
                task.status = "cancelled"
                task.completed_at = now
                db_session.commit()
                continue

            # Найти последний исходящий touch для извлечения темы
            last_touch = (
                db_session.query(CrmTouchRow)
                .filter_by(company_id=task.company_id, direction="outgoing")
                .order_by(CrmTouchRow.created_at.desc())
                .first()
            )
            original_subject = last_touch.subject if last_touch else ""

            # Рендерить тему: Re: {original_subject}
            followup_subject = f"Re: {original_subject}" if original_subject else "Re: follow-up"

            # Рендерить тело шаблона
            from_name = sender.from_name
            city = company.city or ""
            unsubscribe_url = ""
            if contact and contact.unsubscribe_token:
                unsubscribe_url = f"{sender.base_url}/api/v1/unsubscribe/{contact.unsubscribe_token}"

            render_kwargs = {
                "from_name": from_name,
                "city": city,
                "company_name": company.name_best or "",
                "original_subject": original_subject,
                "unsubscribe_url": unsubscribe_url,
            }

            rendered_body = template.render(**render_kwargs)

            # Отправить письмо
            tracking_id = sender.send(
                company_id=task.company_id,
                email_to=email_to,
                subject=followup_subject,
                body_text=rendered_body,
                template_name=template.name,
                rendered_body=rendered_body,  # plain text для истории
                db_session=db_session,
            )

            if tracking_id:
                # Записать touch
                db_session.add(CrmTouchRow(
                    company_id=task.company_id,
                    channel="email",
                    direction="outgoing",
                    subject=followup_subject,
                    body=f"[tracking_id={tracking_id}] [follow-up]",
                ))

                # Обновить метрики контакта
                if contact:
                    from granite.api.stage_transitions import apply_outgoing_touch
                    apply_outgoing_touch(contact, "email")

                task.status = "done"
                task.completed_at = now
                sent_count += 1
                logger.info(
                    f"task_id={task.id}: follow-up sent to {email_to} "
                    f"(subject={followup_subject!r})"
                )
            else:
                # FIX P3-H2: ошибка отправки — инкремент retry_count
                retry_count = _get_retry_count(task) + 1
                if retry_count >= _MAX_RETRIES:
                    task.status = "failed"
                    task.completed_at = now
                    _set_retry_count(task, retry_count)
                    logger.warning(
                        f"task_id={task.id}: follow-up failed after {retry_count} "
                        f"attempts to {email_to}, marking as failed"
                    )
                else:
                    _set_retry_count(task, retry_count)
                    logger.warning(
                        f"task_id={task.id}: follow-up send failed to {email_to} "
                        f"(attempt {retry_count}/{_MAX_RETRIES})"
                    )

        except Exception as e:
            logger.error(f"task_id={task.id}: error processing follow-up: {e}")
            db_session.commit()
            continue

        # FIX P3-H1: commit-per-task
        db_session.commit()

    return sent_count
