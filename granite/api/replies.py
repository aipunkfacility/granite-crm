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

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from granite.api.deps import get_db
from granite.api.schemas import (
    SendReplyRequest, PreviewReplyRequest, OkResponse, OkWithIdResponse,
)
from granite.database import (
    CompanyRow, EnrichedCompanyRow, CrmContactRow,
    CrmTouchRow, CrmEmailLogRow, CrmTemplateRow,
)
from granite.api.stage_transitions import apply_outgoing_touch
from loguru import logger

__all__ = ["router"]

router = APIRouter()


def _get_reply_context(company: CompanyRow, enriched: EnrichedCompanyRow | None,
                       contact: CrmContactRow | None) -> dict:
    """Собрать контекст для рендеринга шаблона reply."""
    from_name = os.environ.get("FROM_NAME", "")
    return {
        "from_name": from_name,
        "city": company.city or "",
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


@router.post("/companies/{company_id}/reply/preview")
def preview_reply(
    company_id: int,
    data: PreviewReplyRequest,
    db: Session = Depends(get_db),
):
    """Предпросмотр reply из шаблона (без отправки).

    Возвращает отрендеренный subject и body для превью на карточке компании.
    """
    company = db.get(CompanyRow, company_id)
    if not company:
        raise HTTPException(404, "Company not found")

    # Проверяем email
    emails = company.emails or []
    if not emails:
        raise HTTPException(400, "У компании нет email-адреса для отправки reply")

    # Проверяем шаблон
    template = db.query(CrmTemplateRow).filter_by(name=data.template_name).first()
    if not template:
        raise HTTPException(404, f"Template '{data.template_name}' not found")

    if template.channel != "email":
        raise HTTPException(400, f"Template '{data.template_name}' is not an email template")

    enriched = db.get(EnrichedCompanyRow, company_id)
    contact = db.get(CrmContactRow, company_id)

    render_kwargs = _get_reply_context(company, enriched, contact)

    # Тема: если есть входящее письмо — "Re: исходная тема", иначе — из шаблона
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
    }


@router.post("/companies/{company_id}/reply", response_model=OkWithIdResponse)
def send_reply(
    company_id: int,
    data: SendReplyRequest,
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
    company = db.get(CompanyRow, company_id)
    if not company:
        raise HTTPException(404, "Company not found")

    # Проверяем email
    emails = company.emails or []
    if not emails:
        raise HTTPException(400, "У компании нет email-адреса для отправки reply")
    email_to = emails[0].lower().strip()

    # Проверяем шаблон
    template = db.query(CrmTemplateRow).filter_by(name=data.template_name).first()
    if not template:
        raise HTTPException(404, f"Template '{data.template_name}' not found")

    if template.channel != "email":
        raise HTTPException(400, f"Template '{data.template_name}' is not an email template")

    enriched = db.get(EnrichedCompanyRow, company_id)
    contact = db.get(CrmContactRow, company_id)

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

    render_kwargs = _get_reply_context(company, enriched, contact)

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
    from granite.email.sender import EmailSender
    sender = EmailSender()

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
            template_id=template.id,
            db_session=db,
        )
    else:
        tracking_id = sender.send(
            company_id=company_id,
            email_to=email_to,
            subject=subject,
            body_text=rendered,
            template_name=template.name,
            template_id=template.id,
            db_session=db,
        )

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

    logger.info(
        f"Reply sent: company={company_id} template={data.template_name} "
        f"to={email_to} tracking={tracking_id}"
    )

    return OkWithIdResponse(ok=True, id=touch.id)
