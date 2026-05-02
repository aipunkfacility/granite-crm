"""Replies API: отправка reply из шаблона на карточке компании.

Phase 4: Post-reply кнопки. Позволяет оператору быстро ответить
на входящее письмо, выбрав один из playbook-шаблонов:
«Цена», «Примеры», «Сроки», «Есть подрядчик», «Отказ».

Два эндпоинта:
1. POST /companies/{id}/reply/preview — превью без отправки
2. POST /companies/{id}/reply         — отправка reply

Логика:
- Находит email компании (первый из списка)
- Рендерит шаблон с плейсхолдерами {company_name}, {city}, etc.
- Добавляет "Re: " к теме, если есть предыдущее входящее письмо
- Отправляет через EmailSender
- Логирует исходящее касание (CrmTouchRow)
- Обновляет метрики контакта (email_sent_count, funnel_stage)
"""
import os
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from granite.api.deps import get_db
from granite.api.schemas import (
    SendReplyRequest, PreviewReplyRequest, OkResponse, OkWithIdResponse,
)
from granite.database import (
    CompanyRow, EnrichedCompanyRow, CrmContactRow,
    CrmTouchRow, CrmEmailLogRow,
)
from granite.api.stage_transitions import apply_outgoing_touch
from loguru import logger

__all__ = ["router"]

router = APIRouter()


def _get_reply_context(company: CompanyRow, contact: CrmContactRow | None) -> dict:
    """Собрать контекст для рендеринга шаблона reply.

    P4R-M12: Убран неиспользуемый параметр enriched.
    """
    from granite.constants import get_sender_field
    from_name = get_sender_field("from_name")
    city = company.city or ""
    from granite.city_declensions import get_locative
    return {
        "from_name": from_name,
        "whatsapp_number": get_sender_field("whatsapp"),
        "telegram_link": get_sender_field("telegram"),
        "city": city,
        "city_locative": get_locative(city),
        "company_name": company.name_best or "",
        "website": company.website or "",
        "contact_name": "",
        "phone": (company.phones or [""])[0] if company.phones else "",
        "unsubscribe_url": "",  # Заполняется в send_reply при наличии contact
    }


def _get_last_incoming_subject(company_id: int, db: Session) -> str | None:
    """Найти тему последнего входящего письма от компании."""
    last_incoming = (
        db.query(CrmTouchRow)
        .filter_by(company_id=company_id, direction="incoming", channel="email")
        .order_by(CrmTouchRow.created_at.desc())
        .first()
    )
    if last_incoming and last_incoming.subject:
        subject = last_incoming.subject
        # Если тема уже начинается с Re: — не добавляем ещё
        if not subject.lower().startswith("re:"):
            return f"Re: {subject}"
        return subject
    return None


# P4R-M9: Общий хелпер валидации для preview и send reply.
# Ранее логика дублировалась между двумя эндпоинтами.
def _validate_reply_context(company_id: int, template_name: str, request: Request, db: Session):
    """Общая валидация для preview и send reply.

    Проверяет: существование компании, наличие email, существование
    шаблона (из TemplateRegistry), тип шаблона (email).

    Returns: (company, template, emails, contact)
    """
    company = db.get(CompanyRow, company_id)
    if not company:
        raise HTTPException(404, "Company not found")

    emails = company.emails or []
    if not emails:
        raise HTTPException(400, "У компании нет email-адреса для отправки reply")

    template = request.app.state.template_registry.get(template_name)
    if not template:
        raise HTTPException(404, f"Template '{template_name}' not found")

    if template.channel != "email":
        raise HTTPException(400, f"Template '{template_name}' is not an email template")

    contact = db.get(CrmContactRow, company_id)

    return company, template, emails, contact


def _mask_email(email: str) -> str:
    """P4R-M8: Маскировать email для логов (152-ФЗ/GDPR)."""
    if "@" not in email:
        return "***"
    local, domain = email.rsplit("@", 1)
    return f"{local[:2]}***@{domain}"


@router.post("/companies/{company_id}/reply/preview")
def preview_reply(
    company_id: int,
    data: PreviewReplyRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Предпросмотр reply из шаблона (без отправки).

    Возвращает отрендеренный subject и body для превью на карточке компании.

    P4R-M10: Проверяет stop_automation — если установлен, возвращает предупреждение.
    """
    # P4R-M9: Общая валидация
    company, template, emails, contact = _validate_reply_context(company_id, data.template_name, request, db)

    # P4R-M10: Проверяем stop_automation — preview показываем, но с предупреждением
    stop_automation_warning = None
    if contact and contact.stop_automation:
        stop_automation_warning = (
            "Автоматизация остановлена для этой компании (stop_automation=True). "
            "Отправка reply будет заблокирована, пока флаг не снят."
        )

    render_kwargs = _get_reply_context(company, contact)

    # Тема: если есть входящее письмо — "Re: исходящая тема", иначе — из шаблона
    last_subject = _get_last_incoming_subject(company_id, db)
    if last_subject:
        subject = last_subject
    else:
        subject = template.render_subject(**render_kwargs)

    body = template.render(**render_kwargs)

    return {
        "company_id": company_id,
        "email_to": emails[0],
        "template_name": template.name,
        "subject": subject,
        "body": body,
        "body_type": template.body_type,
        "stop_automation_warning": stop_automation_warning,  # P4R-M10
    }


@router.post("/companies/{company_id}/reply", response_model=OkWithIdResponse)
def send_reply(
    company_id: int,
    data: SendReplyRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Отправить reply из шаблона на входящее письмо компании.

    Phase 4: Блокер для post-reply кнопок на карточке компании.

    Логика:
    1. Проверяет существование компании и email
    2. Рендерит шаблон reply с плейсхолдерами
    3. Определяет тему (Re: входящее или из шаблона)
    4. Отправляет через EmailSender
    5. Логирует исходящее касание + email_log
    6. Обновляет метрики контакта
    7. Отменяет follow-up задачу (если есть)
    """
    # P4R-M9: Общая валидация
    company, template, emails, contact = _validate_reply_context(company_id, data.template_name, request, db)
    email_to = emails[0].lower().strip()

    # Создаём контакт, если его нет
    if not contact:
        contact = CrmContactRow(company_id=company_id)
        db.add(contact)
        db.flush()

    # Проверяем stop_automation
    if contact.stop_automation:
        raise HTTPException(
            409,
            "Автоматизация остановлена для этой компании (stop_automation=True). "
            "Снимите флаг, чтобы отправить reply."
        )

    render_kwargs = _get_reply_context(company, contact)

    # Тема: subject_override > Re: входящее > из шаблона
    if data.subject_override:
        subject = data.subject_override
    else:
        last_subject = _get_last_incoming_subject(company_id, db)
        if last_subject:
            subject = last_subject
        else:
            subject = template.render_subject(**render_kwargs)

    # Рендерим тело
    rendered = template.render(**render_kwargs)

    # Отправляем через EmailSender
    # P4R-M11: Ловим исключения SMTP → HTTPException 502
    from granite.email.sender import EmailSender
    sender = EmailSender()

    try:
        if template.body_type == "html":
            from granite.utils import html_to_plain_text
            body_text = html_to_plain_text(rendered)
            tracking_id = sender.send(
                company_id=company_id,
                email_to=email_to,
                subject=subject,
                body_text=body_text,
                body_html=rendered,
                template_name=template.name,
                rendered_body=body_text,  # plain text для истории
                db_session=db,
            )
        else:
            tracking_id = sender.send(
                company_id=company_id,
                email_to=email_to,
                subject=subject,
                body_text=rendered,
                template_name=template.name,
                rendered_body=rendered,  # plain text для истории
                db_session=db,
            )
    except Exception as exc:
        logger.error(f"SMTP error sending reply: company={company_id} template={data.template_name}: {exc}")
        raise HTTPException(502, f"Ошибка отправки email (SMTP): {exc}")

    if not tracking_id:
        raise HTTPException(500, "Не удалось отправить reply. Проверьте SMTP настройки.")

    # Логируем исходящее касание — сохраняем отрендеренное тело письма
    touch = CrmTouchRow(
        company_id=company_id,
        channel="email",
        direction="outgoing",
        subject=subject,
        body=rendered,
        note=f"reply_template={data.template_name} tracking_id={tracking_id}",
    )
    db.add(touch)

    # Обновляем метрики контакта
    apply_outgoing_touch(contact, "email")
    contact.updated_at = datetime.now(timezone.utc)

    # Отменяем follow-up задачи (reply = оператор уже ответил)
    from granite.api.helpers import cancel_followup_tasks
    cancel_followup_tasks(company_id, "replied", db)

    db.flush()

    # P4R-M8: Маскируем email в логе
    logger.info(
        f"Reply sent: company={company_id} template={data.template_name} "
        f"to={_mask_email(email_to)} tracking={tracking_id}"
    )

    return OkWithIdResponse(ok=True, id=touch.id)
