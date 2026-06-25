# granite/api/network_toggles.py
"""API для управления тогглами email в сетях."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from granite.api.deps import get_db
from granite.api.schemas import OkResponse
from granite.database import NetworkRow, NetworkEmailToggleRow

router = APIRouter()


class ToggleEmailRequest(BaseModel):
    email: str = Field(..., description="Email для тоггла")
    is_disabled: bool = Field(True, description="True=отключен, False=включен")
    reason: str = Field("", description="Причина отключения")


class NetworkEmailWithStatus(BaseModel):
    email: str
    is_disabled: bool
    reason: str = ""
    sent_count: int = 0
    last_sent_at: str | None = None
    badge: str = ""  # "sent" | "bounced" | "disabled" | ""


@router.get("/networks/{network_id}/emails", response_model=list[NetworkEmailWithStatus])
def list_network_emails(
    network_id: int,
    db: Session = Depends(get_db),
):
    """Вернуть email сети со статусами и бейджами."""
    from granite.database import CompanyEmailRow, CrmEmailLogRow

    nw = db.get(NetworkRow, network_id)
    if not nw:
        raise HTTPException(404, "Network not found")

    emails = nw.emails or []

    toggles = {}
    for t in db.query(NetworkEmailToggleRow).filter(
        NetworkEmailToggleRow.network_id == network_id
    ).all():
        toggles[t.email.lower()] = t

    result = []
    for email in emails:
        email_lower = email.lower()
        toggle = toggles.get(email_lower)

        ce = db.query(CompanyEmailRow).filter(
            CompanyEmailRow.email == email_lower,
        ).first()
        sent_count = ce.sent_count if ce else 0
        last_sent_at = ce.last_sent_at.isoformat() if ce and ce.last_sent_at else None

        badge = ""
        if toggle and toggle.is_disabled:
            badge = "disabled"
        elif sent_count > 0:
            last_log = db.query(CrmEmailLogRow).filter(
                CrmEmailLogRow.email_to == email_lower,
            ).order_by(CrmEmailLogRow.created_at.desc()).first()
            if last_log:
                badge = "bounced" if last_log.status == "bounced" else "sent"
            else:
                badge = "sent"

        result.append(NetworkEmailWithStatus(
            email=email,
            is_disabled=toggle.is_disabled if toggle else False,
            reason=toggle.reason if toggle else "",
            sent_count=sent_count,
            last_sent_at=last_sent_at,
            badge=badge,
        ))

    return result


@router.post("/networks/{network_id}/emails/toggle", response_model=OkResponse)
def toggle_email(
    network_id: int,
    body: ToggleEmailRequest,
    db: Session = Depends(get_db),
):
    """Включить/отключить email в сети."""
    nw = db.get(NetworkRow, network_id)
    if not nw:
        raise HTTPException(404, "Network not found")

    email_lower = body.email.lower().strip()

    # Валидация: email должен быть в списке emails сети
    network_emails_lower = {e.lower() for e in (nw.emails or [])}
    if email_lower not in network_emails_lower:
        raise HTTPException(400, f"Email {email_lower} не найден в сети {nw.name}")

    existing = db.query(NetworkEmailToggleRow).filter(
        NetworkEmailToggleRow.network_id == network_id,
        NetworkEmailToggleRow.email == email_lower,
    ).first()

    if existing:
        existing.is_disabled = body.is_disabled
        existing.reason = body.reason
    else:
        db.add(NetworkEmailToggleRow(
            network_id=network_id,
            email=email_lower,
            is_disabled=body.is_disabled,
            reason=body.reason,
        ))

    db.flush()
    action = "отключен" if body.is_disabled else "включен"
    return {"ok": True, "message": f"Email {email_lower} {action}"}
