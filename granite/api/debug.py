"""Debug API: manual IMAP inspection and reply processing.

Endpoints are protected by X-Admin-Token (same as admin.py).
Use ONLY for diagnosing reply/bounce tracking issues.
"""
import os

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from loguru import logger

from granite.api.deps import get_db
from granite.api.admin import _check_admin

__all__ = ["router"]

router = APIRouter()


@router.post("/debug/process-replies")
def debug_process_replies(
    request: Request,
    db: Session = Depends(get_db),
):
    """Вручную запустить process_replies() и вернуть детальный результат.

    Полезно, когда reply-статус не обновляется, и нужно проверить,
    видит ли IMAP ответные письма и находит ли совпадения по email.

    Returns:
        - imap_ok: bool (подключение к IMAP)
        - messages_found: int (сколько UNSEEN писем в INBOX)
        - processed: int (сколько обработано как reply)
        - messages: list[{subject, from, date}] (детали каждого письма)
        - error: str | None
    """
    from granite.email.imap_helpers import fetch_imap_messages
    from granite.email.process_replies import process_replies

    _check_admin(request)

    # 1. Проверка кред
    imap_user = os.environ.get("SMTP_USER", "")
    imap_pass = os.environ.get("IMAP_PASS", os.environ.get("SMTP_PASS", ""))
    if not imap_user or not imap_pass:
        return {
            "imap_ok": False,
            "messages_found": 0,
            "processed": 0,
            "messages": [],
            "error": "IMAP credentials not configured (SMTP_USER / IMAP_PASS)",
        }

    # 2. Fetch messages
    try:
        messages = fetch_imap_messages(mark_seen=False)
    except Exception as e:
        return {
            "imap_ok": False,
            "messages_found": 0,
            "processed": 0,
            "messages": [],
            "error": f"IMAP connection error: {e}",
        }

    if not messages:
        return {
            "imap_ok": True,
            "messages_found": 0,
            "processed": 0,
            "messages": [],
            "error": None,
        }

    # 3. Сохраняем детали писем ДО обработки
    msg_details = []
    for mid, msg in messages:
        msg_details.append({
            "mid": mid.decode(errors="replace") if isinstance(mid, bytes) else str(mid),
            "subject": msg.get("Subject", ""),
            "from": msg.get("From", ""),
            "date": str(msg.get("Date", "")),
            "message_id": msg.get("Message-ID", ""),
        })

    # 4. Запускаем process_replies
    try:
        processed = process_replies(db, messages=messages)
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"debug/process-replies: process_replies failed: {e}")
        return {
            "imap_ok": True,
            "messages_found": len(messages),
            "processed": 0,
            "messages": msg_details,
            "error": f"process_replies error: {e}",
        }

    return {
        "imap_ok": True,
        "messages_found": len(messages),
        "processed": processed,
        "messages": msg_details,
        "error": None,
    }


@router.get("/debug/imap-inbox")
def debug_imap_inbox(
    request: Request,
):
    """Показать непрочитанные письма в IMAP INBOX (без обработки).

    Полезно для проверки: доходят ли ответы, видны ли они IMAP,
    не помечены ли уже как Seen.

    Returns:
        - imap_ok: bool
        - messages: list[{subject, from, date, message_id}]
        - error: str | None
    """
    from granite.email.imap_helpers import fetch_imap_messages

    _check_admin(request)

    imap_user = os.environ.get("SMTP_USER", "")
    imap_pass = os.environ.get("IMAP_PASS", os.environ.get("SMTP_PASS", ""))
    if not imap_user or not imap_pass:
        return {
            "imap_ok": False,
            "messages": [],
            "error": "IMAP credentials not configured",
        }

    try:
        messages = fetch_imap_messages(mark_seen=False)
    except Exception as e:
        return {
            "imap_ok": False,
            "messages": [],
            "error": f"IMAP connection error: {e}",
        }

    msg_details = []
    for mid, msg in (messages or []):
        msg_details.append({
            "mid": mid.decode(errors="replace") if isinstance(mid, bytes) else str(mid),
            "subject": msg.get("Subject", ""),
            "from": msg.get("From", ""),
            "date": str(msg.get("Date", "")),
            "message_id": msg.get("Message-ID", ""),
        })

    return {
        "imap_ok": True,
        "messages_found": len(msg_details),
        "messages": msg_details,
        "error": None,
    }
