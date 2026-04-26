"""Unsubscribe эндпоинт — отписка от email-рассылки."""
import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from granite.api.deps import get_db
from granite.database import CrmContactRow, CrmTouchRow
from granite.api.helpers import cancel_followup_tasks

__all__ = ["router"]

router = APIRouter()

_UNSUBSCRIBE_PAGE = """<!DOCTYPE html>
<html><body style="font-family:sans-serif;max-width:500px;margin:60px auto;text-align:center">
<h2>RetouchGrav</h2>
<p>{msg}</p>
{extra}
</body></html>"""


def ensure_unsubscribe_token(contact: CrmContactRow, db: Session) -> str:
    """Гарантировать наличие unsubscribe_token у контакта."""
    if not contact.unsubscribe_token:
        contact.unsubscribe_token = secrets.token_hex(16)
        db.flush()
    return contact.unsubscribe_token


@router.get("/unsubscribe/{token}", response_class=HTMLResponse)
def unsubscribe_page(token: str, db: Session = Depends(get_db)):
    """Страница подтверждения отписки. НЕ отписывает при GET —
    защита от префетча почтовыми клиентами."""
    contact = db.query(CrmContactRow).filter_by(unsubscribe_token=token).first()
    if not contact:
        raise HTTPException(404, "Ссылка недействительна")

    if contact.stop_automation:
        return _UNSUBSCRIBE_PAGE.format(
            msg="Вы уже отписаны. Писем больше не будет.",
            extra="",
        )

    return _UNSUBSCRIBE_PAGE.format(
        msg="Подтвердите отписку от рассылки RetouchGrav.",
        extra=f'''
        <form method="POST" action="/api/v1/unsubscribe/{token}">
          <button type="submit" style="padding:10px 24px;font-size:16px;cursor:pointer">
            Отписаться
          </button>
        </form>''',
    )


@router.post("/unsubscribe/{token}", response_class=HTMLResponse)
def unsubscribe_confirm(token: str, db: Session = Depends(get_db)):
    """Собственно отписка — только POST."""
    contact = db.query(CrmContactRow).filter_by(unsubscribe_token=token).first()
    if not contact:
        raise HTTPException(404, "Ссылка недействительна")

    if contact.stop_automation:
        return _UNSUBSCRIBE_PAGE.format(msg="Вы уже отписаны.", extra="")

    contact.stop_automation = True
    contact.funnel_stage = "not_interested"
    contact.updated_at = datetime.now(timezone.utc)

    # Отменить pending follow-up задачи
    cancel_followup_tasks(contact.company_id, "not_interested", db)

    db.add(CrmTouchRow(
        company_id=contact.company_id,
        channel="email",
        direction="incoming",
        subject="Отписка",
        body="unsubscribe_link",
    ))

    return _UNSUBSCRIBE_PAGE.format(
        msg="Вы успешно отписаны. Больше писем не будет.",
        extra="",
    )
