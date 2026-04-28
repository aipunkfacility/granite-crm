"""IMAP helpers — общие функции для process_bounces и process_replies.

Задача 19 (v13): вынести дублирующийся IMAP-код в отдельный модуль.

Функции:
    extract_email()       — извлечь email из "Имя <email>" или "email"
    extract_body()        — извлечь text/plain часть из email.message.Message
    is_bounce()           — определить, является ли письмо bounce (DSN)
    is_ooo()              — определить автоответчик (Out of Office)
    extract_bounced_email() — извлечь Final-Recipient из DSN-текста
    extract_dsn()         — извлечь DSN-код (5.x.x) из delivery-status
    fetch_imap_messages() — подключиться к IMAP и получить сообщения
"""
import imaplib
import email
import os
import re
from email.message import Message
from email.policy import default as default_policy
from typing import Optional

from loguru import logger

__all__ = [
    "extract_email",
    "extract_body",
    "is_bounce",
    "is_ooo",
    "extract_bounced_email",
    "extract_dsn",
    "fetch_imap_messages",
]


# ── Email extraction ──────────────────────────────────────

_EMAIL_RE = re.compile(r"<([^<>@\s]+@[^<>@\s]+)>|([^\s<>]+@[^\s<>]+)")


def extract_email(from_header: str) -> Optional[str]:
    """Извлечь email-адрес из заголовка From.

    Примеры:
        'Иван <ivan@mail.ru>' → 'ivan@mail.ru'
        'ivan@mail.ru'        → 'ivan@mail.ru'
        ''                    → None
    """
    if not from_header:
        return None
    m = _EMAIL_RE.search(from_header)
    if not m:
        return None
    return m.group(1) or m.group(2)


# ── Body extraction ───────────────────────────────────────

def extract_body(msg: Message) -> str:
    """Извлечь text/plain часть из email.message.Message.

    Для multipart-письма — ищет первую text/plain часть.
    Для простого письма — возвращает payload как строку.
    """
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            if content_type == "text/plain":
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    try:
                        return payload.decode(charset, errors="replace")
                    except (LookupError, UnicodeDecodeError):
                        return payload.decode("utf-8", errors="replace")
        # Fallback: первая текстовая часть
        for part in msg.walk():
            content_type = part.get_content_type()
            if content_type.startswith("text/"):
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    return payload.decode(charset, errors="replace")
        return ""
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            charset = msg.get_content_charset() or "utf-8"
            try:
                return payload.decode(charset, errors="replace")
            except (LookupError, UnicodeDecodeError):
                return payload.decode("utf-8", errors="replace")
        # Если payload — строка (не закодирована, например Message.set_payload)
        raw = msg.get_payload()
        if isinstance(raw, str):
            return raw
        return str(raw) if raw else ""


# ── Bounce detection ──────────────────────────────────────

def is_bounce(msg: Message) -> bool:
    """Определить, является ли письмо bounce (Delivery Status Notification).

    Признаки:
    - Content-Type: multipart/report; report-type=delivery-status
    - From содержит mailer-daemon / postmaster
    - Subject содержит "Delivery Status Notification" / "Undelivered" / "bounce"
    """
    # FIX P3-M1: убрана мёртвая переменная content_type
    lower_ct = (msg.get("Content-Type", "") or "").lower()

    # Стандартный DSN
    if "multipart/report" in lower_ct and "delivery-status" in lower_ct:
        return True

    # Проверяем по заголовкам
    from_header = (msg.get("From", "") or "").lower()
    subject = (msg.get("Subject", "") or "").lower()

    bounce_from = any(kw in from_header for kw in ("mailer-daemon", "postmaster", "mail delivery"))
    bounce_subject = any(kw in subject for kw in (
        "delivery status notification", "undelivered", "returned mail",
        "mail delivery failed", "failure notice", "delivery failure",
    ))

    return bounce_from or bounce_subject


# ── OOO detection ─────────────────────────────────────────

_OOO_PATTERNS = re.compile(
    r"автоответ|auto.repl|out\s+of\s+office|ooo[:\s]|vacation|нет\s+на\s+месте",
    re.IGNORECASE,
)


def is_ooo(msg: Message) -> bool:
    """Определить автоответчик (Out of Office / автоответ).

    Проверяет Subject и常见 автоответ-паттерны.
    """
    subject = msg.get("Subject", "") or ""
    if _OOO_PATTERNS.search(subject):
        return True

    # Также проверяем заголовок Auto-Submitted (RFC 3834)
    auto_submitted = msg.get("Auto-Submitted", "") or ""
    if auto_submitted.lower().startswith("auto-replied"):
        return True

    return False


# ── DSN extraction ────────────────────────────────────────

_FINAL_RECIPIENT_RE = re.compile(
    r"Final-Recipient:\s*rfc822;\s*(\S+)", re.IGNORECASE
)
_DSN_CODE_RE = re.compile(
    r"Diagnostic-Code:\s*smtp;\s*(\d+\.\d+\.\d+)", re.IGNORECASE
)


def extract_bounced_email(dsn_text: str) -> Optional[str]:
    """Извлечь Final-Recipient из DSN-текста.

    Пример:
        'Final-Recipient: rfc822; user_unknown@example.com'
        → 'user_unknown@example.com'
    """
    m = _FINAL_RECIPIENT_RE.search(dsn_text)
    return m.group(1) if m else None


def extract_dsn(dsn_text: str) -> Optional[str]:
    """Извлечь DSN-код (5.x.x) из delivery-status текста.

    Пример:
        'Diagnostic-Code: smtp; 5.1.1 User unknown'
        → '5.1.1'
    """
    m = _DSN_CODE_RE.search(dsn_text)
    return m.group(1) if m else None


# ── IMAP connection ───────────────────────────────────────

def fetch_imap_messages(
    folder: str = "INBOX",
    search_criteria: str = "UNSEEN",
    limit: int = 100,
    mark_seen: bool = False,
) -> list[tuple[bytes, Message]]:
    """Подключиться к IMAP и получить сообщения.

    Args:
        folder: IMAP-папка (INBOX по умолчанию).
        search_criteria: критерий поиска (UNSEEN — непрочитанные).
        limit: максимум сообщений.
        mark_seen: помечать как прочитанные.

    Returns:
        Список кортежей (message_id_bytes, email.message.Message).

    Raises:
        Exception: при ошибке подключения (ловится в вызывающем коде).
    """
    imap_host = os.environ.get("IMAP_HOST", "imap.gmail.com")
    imap_port = int(os.environ.get("IMAP_PORT", "993"))
    imap_user = os.environ.get("SMTP_USER", "")
    imap_pass = os.environ.get("IMAP_PASS", os.environ.get("SMTP_PASS", ""))

    if not imap_user or not imap_pass:
        logger.warning("IMAP credentials not configured (SMTP_USER / IMAP_PASS)")
        return []

    conn = imaplib.IMAP4_SSL(imap_host, imap_port)
    try:
        conn.login(imap_user, imap_pass)
        conn.select(folder)

        status, data = conn.search(None, search_criteria)
        if status != "OK":
            return []

        message_ids = data[0].split()
        if not message_ids:
            return []

        # Ограничиваем количество
        message_ids = message_ids[-limit:]

        results = []
        for mid in message_ids:
            # FIX P3-M2: убрана мёртвая переменная fetch_flag
            if not mark_seen:
                # BODY.PEEK — не меняет флаг \Seen
                status, msg_data = conn.fetch(mid, "(BODY.PEEK[])")
            else:
                status, msg_data = conn.fetch(mid, "(RFC822)")

            if status != "OK":
                continue

            for response_part in msg_data:
                if isinstance(response_part, tuple):
                    raw_email = response_part[1]
                    msg = email.message_from_bytes(raw_email, policy=default_policy)
                    results.append((mid, msg))
                    break

        return results
    finally:
        try:
            conn.close()
            conn.logout()
        except Exception:
            pass
