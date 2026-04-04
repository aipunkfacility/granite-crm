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
_sentinel = object()


async def process_batch(job_id: str, contacts: list[BatchContact], html: str):
    from server.services.email import send_single_email
    
    async with _jobs_lock:
        if job_id not in jobs:
            return
        job = jobs[job_id]
        job["started_at"] = datetime.now().isoformat()

    total = len(contacts)
    for i, contact in enumerate(contacts):
        async with _jobs_lock:
            if job.get("cancelled"):
                job["status"] = "cancelled"
                job["completed_at"] = datetime.now().isoformat()
                try:
                    job["queue"].put_nowait({"event": "done", "status": "cancelled", "sent": job["sent"], "failed": job["failed"], "total": total})
                except Exception: pass
                return

        # Отправка письма через неблокирующий сервис
        success, error, error_type = await send_single_email(contact.email, html)
        
        async with _jobs_lock:
            # Обновление состояния джоба
            job["results"].append({
                "email": contact.email,
                "success": success,
                "error": error,
                "error_type": error_type,
            })
            if success:
                job["sent"] += 1
            else:
                job["failed"] += 1
                
            sent = job["sent"]
            failed = job["failed"]

        # Отправка события в SSE
        try:
            job["queue"].put_nowait({
                "event": "result",
                "email": contact.email,
                "success": success,
                "error": error,
                "error_type": error_type,
                "sent": sent,
                "failed": failed,
                "total": total,
            })
        except Exception: pass

        # Задержка между письмами (не блокирует цикл сервера)
        if i < total - 1:
            delay = random.randint(config.get("delay_min", 20), config.get("delay_max", 30))
            await asyncio.sleep(delay)

    try:
        server.quit()
    except Exception as e:
        logger.warning(f"Error quitting SMTP server: {e}")

    async with _jobs_lock:
        job["status"] = "completed"
        job["completed_at"] = datetime.now().isoformat()
        final_sent = job["sent"]
        final_failed = job["failed"]
        final_total = job["total"]
    logger.info(
        "Job %s completed: %d sent, %d failed", job_id, final_sent, final_failed
    )

    try:
        job["queue"].put_nowait(
            {
                "event": "done",
                "status": "completed",
                "sent": final_sent,
                "failed": final_failed,
                "total": final_total,
            }
        )
    except Exception:
        pass


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
                            logger.warning(
                                "Error parsing completed_at timestamp: %s", e
                            )

            for job_id in to_remove:
                del jobs[job_id]
                logger.debug("Cleaned up old job: %s", job_id)

        if to_remove:
            logger.info("Cleaned up %d old jobs", len(to_remove))


def start_cleanup_task():
    """Start the cleanup task - call this after app is created."""
    import asyncio

    asyncio.create_task(cleanup_old_jobs())
