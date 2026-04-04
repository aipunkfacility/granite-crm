import asyncio
import logging
import random
import smtplib
from datetime import datetime

from server.config import config, JOB_CLEANUP_INTERVAL, JOB_RETENTION_SECONDS
from server.models import BatchContact
from server.services.email import classify_error

logger = logging.getLogger(__name__)

jobs: dict[str, dict] = {}
_jobs_lock = asyncio.Lock()


async def process_batch(job_id: str, contacts: list[BatchContact], html: str):
    async with _jobs_lock:
        job = jobs[job_id]
        job["started_at"] = datetime.now().isoformat()

    smtp_timeout = config.get("smtp_timeout", 30)
    total = len(contacts)

    try:
        logger.info(f"Connecting to SMTP {config['smtp_server']}:{config['smtp_port']}")
        server = smtplib.SMTP(
            config["smtp_server"], config["smtp_port"], timeout=smtp_timeout
        )
        server.starttls()
        server.login(config["sender_email"], config["sender_password"])
    except Exception as e:
        logger.error(f"SMTP connection failed: {e}")
        async with _jobs_lock:
            for contact in contacts:
                job["results"].append(
                    {
                        "email": contact.email,
                        "success": False,
                        "error": str(e),
                        "error_type": classify_error(e),
                    }
                )
                job["failed"] += 1
            job["status"] = "completed"
            job["completed_at"] = datetime.now().isoformat()
        return

    for i, contact in enumerate(contacts):
        async with _jobs_lock:
            is_cancelled = job.get("cancelled")
            if is_cancelled:
                job["status"] = "cancelled"
                job["completed_at"] = datetime.now().isoformat()

        if is_cancelled:
            logger.info(f"Job {job_id} cancelled after {job['sent']}/{total}")
            try:
                server.quit()
            except Exception as e:
                logger.warning(f"Error quitting SMTP server: {e}")
            return

        try:
            from email.mime.multipart import MIMEMultipart
            from email.mime.text import MIMEText

            msg = MIMEMultipart("alternative")
            msg["From"] = config["sender_email"]
            msg["To"] = contact.email
            msg["Subject"] = config["email_subject"]
            msg.attach(MIMEText(html, "html"))

            server.sendmail(config["sender_email"], contact.email, msg.as_string())
            logger.info(f"Email sent to {contact.email}")

            async with _jobs_lock:
                job["results"].append(
                    {
                        "email": contact.email,
                        "success": True,
                        "error": "",
                        "error_type": "",
                    }
                )
                job["sent"] += 1

        except Exception as e:
            logger.error(f"Failed to send email to {contact.email}: {e}")

            async with _jobs_lock:
                job["results"].append(
                    {
                        "email": contact.email,
                        "success": False,
                        "error": str(e),
                        "error_type": classify_error(e),
                    }
                )
                job["failed"] += 1

        await asyncio.sleep(0)

        if i < total - 1 and not job.get("cancelled"):
            delay = random.randint(
                config.get("delay_min", 20), config.get("delay_max", 30)
            )
            await asyncio.sleep(delay)

    try:
        server.quit()
    except Exception as e:
        logger.warning(f"Error quitting SMTP server: {e}")

    async with _jobs_lock:
        job["status"] = "completed"
        job["completed_at"] = datetime.now().isoformat()
    logger.info(f"Job {job_id} completed: {job['sent']} sent, {job['failed']} failed")


async def cleanup_old_jobs():
    while True:
        await asyncio.sleep(JOB_CLEANUP_INTERVAL)

        now = datetime.now()
        cutoff = now.timestamp() - JOB_RETENTION_SECONDS

        async with _jobs_lock:
            to_remove = []
            for job_id, job in jobs.items():
                if job.get("status") in ("completed", "cancelled"):
                    completed_at = job.get("completed_at")
                    if completed_at:
                        try:
                            completed_time = datetime.fromisoformat(completed_at)
                            if completed_time.timestamp() < cutoff:
                                to_remove.append(job_id)
                        except Exception as e:
                            logger.warning(f"Error parsing completed_at timestamp: {e}")

            for job_id in to_remove:
                del jobs[job_id]
                logger.debug(f"Cleaned up old job: {job_id}")

        if to_remove:
            logger.info(f"Cleaned up {len(to_remove)} old jobs")


def start_cleanup_task():
    """Start the cleanup task - call this after app is created."""
    import asyncio

    asyncio.create_task(cleanup_old_jobs())
