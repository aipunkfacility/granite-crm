import asyncio
import logging
import random
import smtplib
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from server.config import config

logger = logging.getLogger(__name__)


def classify_error(e: Exception) -> str:
    msg = str(e).lower()
    if any(
        kw in msg for kw in ("smtp", "mail", "recipient", "sender", "auth", "login")
    ):
        return "smtp_error"
    if any(kw in msg for kw in ("connection", "timeout", "refused", "network")):
        return "connection_error"
    if "@" not in msg or "invalid" in msg:
        return "invalid_email"
    return "unknown_error"


def _send_batch_sync(
    recipient_emails: list[str], html_body: str
) -> list[tuple[bool, str, str]]:
    """Синхронная отправка через smtplib. Вызывается в отдельном потоке."""
    results = []
    smtp_timeout = config.get("smtp_timeout", 30)

    try:
        logger.info(
            "Connecting to SMTP %s:%s", config["smtp_server"], config["smtp_port"]
        )
        server = smtplib.SMTP(
            config["smtp_server"], config["smtp_port"], timeout=smtp_timeout
        )
        server.starttls()
        server.login(config["sender_email"], config["sender_password"])

        for i, recipient_email in enumerate(recipient_emails):
            try:
                msg = MIMEMultipart("alternative")
                msg["From"] = config["sender_email"]
                msg["To"] = recipient_email
                msg["Subject"] = config["email_subject"]
                msg.attach(MIMEText(html_body, "html"))

                server.sendmail(
                    config["sender_email"], recipient_email, msg.as_string()
                )
                logger.info("Email sent to %s", recipient_email)
                results.append((True, "", ""))

            except Exception as e:
                logger.error("Failed to send email to %s: %s", recipient_email, e)
                results.append((False, str(e), classify_error(e)))

            if i < len(recipient_emails) - 1:
                delay = random.randint(
                    config.get("delay_min", 20), config.get("delay_max", 30)
                )
                time.sleep(delay)

        server.quit()
        logger.info("SMTP connection closed after %d emails", len(recipient_emails))

    except Exception as e:
        logger.error("SMTP connection failed: %s", e)
        results = [(False, str(e), classify_error(e)) for _ in recipient_emails]

    return results


async def send_single_email(
    recipient_email: str, html_body: str
) -> tuple[bool, str, str]:
    results = await send_emails_batch([recipient_email], html_body)
    return results[0]


async def send_emails_batch(
    recipient_emails: list[str], html_body: str
) -> list[tuple[bool, str, str]]:
    """Асинхронная обёртка: запускает блокирующую SMTP-отправку в пуле потоков."""
    if not recipient_emails:
        return []

    loop = asyncio.get_event_loop()
    results = await loop.run_in_executor(
        None, _send_batch_sync, recipient_emails, html_body
    )
    return results
