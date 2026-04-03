import asyncio
import json
import logging
import os
import random
import shutil
import smtplib
import uuid
from datetime import datetime

# Load .env file if exists
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass  # python-dotenv not installed
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from logging.handlers import RotatingFileHandler
from contextlib import asynccontextmanager
from typing import Optional

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# ===== LOGGING SETUP =====
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_DIR = os.path.join(BASE_DIR, "db")
LOGS_DIR = os.path.join(BASE_DIR, "logs")
BACKUP_DIR = os.path.join(BASE_DIR, "backups")
CRM_DIR = BASE_DIR

# Ensure directories exist
os.makedirs(DB_DIR, exist_ok=True)
os.makedirs(LOGS_DIR, exist_ok=True)
os.makedirs(BACKUP_DIR, exist_ok=True)

# Logging to both console and file
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Console handler
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_format = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
console_handler.setFormatter(console_format)

# File handler with rotation (5MB max, keep 5 backups)
file_handler = RotatingFileHandler(
    os.path.join(LOGS_DIR, "crm_server.log"),
    maxBytes=5 * 1024 * 1024,
    backupCount=5,
    encoding="utf-8",
)
file_handler.setLevel(logging.INFO)
file_format = logging.Formatter("%(asctime)s - %(levelname)s - %(name)s - %(message)s")
file_handler.setFormatter(file_format)

logger.addHandler(console_handler)
logger.addHandler(file_handler)

logger.info("Server starting up...")


# ===== CONFIG LOADING =====
def load_config():
    """Load config from file, with env var overrides for sensitive data."""
    config_path = os.path.join(BASE_DIR, "config.json")

    if not os.path.exists(config_path):
        raise FileNotFoundError(
            f"config.json not found at {config_path}. "
            "Create it from config.example.json"
        )

    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    # Override password from environment variable if set
    env_password = os.environ.get("GMAIL_APP_PASSWORD")
    if env_password:
        config["sender_password"] = env_password
        logger.info("Using GMAIL_APP_PASSWORD from environment")

    # Validate required fields
    required = ["sender_email", "sender_password", "smtp_server", "smtp_port"]
    missing = [k for k in required if not config.get(k)]
    if missing:
        raise ValueError(f"Missing required config fields: {missing}")

    return config


config = load_config()

# Load email template
template_path = os.path.join(
    BASE_DIR, config.get("template_file", "email_template.html")
)
if not os.path.exists(template_path):
    logger.warning(f"Template file not found: {template_path}, using empty template")
    template_html = ""
else:
    with open(template_path, "r", encoding="utf-8") as f:
        template_html = f.read()

jobs: dict[str, dict] = {}


# ===== LIFESPAN HANDLER =====
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start background tasks on startup, cleanup on shutdown."""
    # Start cleanup task
    cleanup_task = asyncio.create_task(cleanup_old_jobs())
    logger.info("Started job cleanup background task")

    yield  # App is running

    # Cleanup on shutdown
    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass
    logger.info("Shutdown complete")


app = FastAPI(title="Email Sender Server", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ===== PYDANTIC MODELS =====


class SingleEmail(BaseModel):
    email: str
    name: str
    html: Optional[str] = None


class BatchContact(BaseModel):
    id: Optional[str] = None
    email: str
    name: str


class BatchEmail(BaseModel):
    contacts: list[BatchContact]
    html: Optional[str] = None


class TemplateUpdate(BaseModel):
    html: str


# ===== HELPER FUNCTIONS =====


def classify_error(e: Exception) -> str:
    """Classify email sending error for better user feedback."""
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


async def send_single_email(
    recipient_email: str, html_body: str
) -> tuple[bool, str, str]:
    """
    Send a single email via SMTP.
    Returns (success, error_message, error_type).
    """
    results = await send_emails_batch([recipient_email], html_body)
    return results[0]


async def send_emails_batch(
    recipient_emails: list[str], html_body: str
) -> list[tuple[bool, str, str]]:
    """
    Send multiple emails with one SMTP connection (connection pooling).
    Returns list of (success, error_message, error_type).
    """
    results = []

    if not recipient_emails:
        return results

    smtp_timeout = config.get("smtp_timeout", 30)

    try:
        logger.info(f"Connecting to SMTP {config['smtp_server']}:{config['smtp_port']}")

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
                logger.info(f"Email sent to {recipient_email}")
                results.append((True, "", ""))

            except Exception as e:
                logger.error(f"Failed to send email to {recipient_email}: {e}")
                results.append((False, str(e), classify_error(e)))

            # Delay between emails (except for last one)
            if i < len(recipient_emails) - 1:
                delay = random.randint(
                    config.get("delay_min", 20), config.get("delay_max", 30)
                )
                await asyncio.sleep(delay)

        server.quit()
        logger.info(f"SMTP connection closed after {len(recipient_emails)} emails")

    except Exception as e:
        logger.error(f"SMTP connection failed: {e}")
        # All emails failed due to connection error
        results = [(False, str(e), classify_error(e)) for _ in recipient_emails]

    return results


def validate_json_data(data) -> tuple[bool, str]:
    """
    Validate JSON data before saving.
    Returns (is_valid, error_message).
    """
    # Accept both arrays and objects
    if not isinstance(data, (dict, list)):
        return False, "Root must be an object or array"

    # Check for reasonable size (prevent DoS)
    data_str = json.dumps(data)
    max_size = config.get("max_json_size", 10 * 1024 * 1024)  # 10MB default
    if len(data_str) > max_size:
        return False, f"Data too large: {len(data_str)} bytes (max: {max_size})"

    return True, ""


def create_backup(filepath: str) -> Optional[str]:
    """
    Create a backup of file before overwriting.
    Returns backup path or None if no file existed.
    """
    if not os.path.exists(filepath):
        return None

    # Create backup with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = os.path.basename(filepath)
    backup_name = f"{filename}.{timestamp}.bak"
    backup_path = os.path.join(BACKUP_DIR, backup_name)

    shutil.copy2(filepath, backup_path)
    logger.info(f"Created backup: {backup_path}")

    # Clean old backups (keep last 10 per file)
    cleanup_old_backups(filename)

    return backup_path


def cleanup_old_backups(filename: str, keep: int = 10):
    """Remove old backups, keeping only the most recent ones."""
    pattern = f"{filename}."
    backups = []

    for f in os.listdir(BACKUP_DIR):
        if f.startswith(pattern) and f.endswith(".bak"):
            full_path = os.path.join(BACKUP_DIR, f)
            backups.append((full_path, os.path.getmtime(full_path)))

    # Sort by modification time, newest first
    backups.sort(key=lambda x: x[1], reverse=True)

    # Remove old ones
    for path, _ in backups[keep:]:
        try:
            os.remove(path)
            logger.debug(f"Removed old backup: {path}")
        except Exception as e:
            logger.warning(f"Failed to remove old backup {path}: {e}")


def find_backup(filename: str) -> Optional[str]:
    """Find the most recent backup for a file."""
    pattern = f"{filename}."
    backups = []

    for f in os.listdir(BACKUP_DIR):
        if f.startswith(pattern) and f.endswith(".bak"):
            full_path = os.path.join(BACKUP_DIR, f)
            backups.append((full_path, os.path.getmtime(full_path)))

    if not backups:
        return None

    # Return most recent
    backups.sort(key=lambda x: x[1], reverse=True)
    return backups[0][0]


# ===== BATCH PROCESSING =====


async def process_batch(job_id: str, contacts: list[BatchContact], html: str):
    """Process batch email sending in background with connection pooling."""
    job = jobs[job_id]
    job["started_at"] = datetime.now().isoformat()

    # Extract emails
    emails = [c.email for c in contacts]

    # Send all emails with one SMTP connection
    results = await send_emails_batch(emails, html)

    # Process results
    for i, contact in enumerate(contacts):
        success, error, error_type = results[i]

        job["results"].append(
            {
                "email": contact.email,
                "success": success,
                "error": error,
                "error_type": error_type,
            }
        )

        if success:
            job["sent"] += 1
        else:
            job["failed"] += 1

    job["status"] = "completed"
    job["completed_at"] = datetime.now().isoformat()
    logger.info(f"Job {job_id} completed: {job['sent']} sent, {job['failed']} failed")


async def cleanup_old_jobs():
    """Remove completed/cancelled jobs older than 1 hour to prevent memory leak."""
    while True:
        await asyncio.sleep(3600)  # Check every hour

        now = datetime.now()
        cutoff = now.timestamp() - 3600  # 1 hour ago

        to_remove = []
        for job_id, job in jobs.items():
            if job.get("status") in ("completed", "cancelled"):
                # Check if we have completion timestamp
                completed_at = job.get("completed_at")
                if completed_at:
                    try:
                        completed_time = datetime.fromisoformat(completed_at)
                        if completed_time.timestamp() < cutoff:
                            to_remove.append(job_id)
                    except:
                        pass

        for job_id in to_remove:
            del jobs[job_id]
            logger.debug(f"Cleaned up old job: {job_id}")

        if to_remove:
            logger.info(f"Cleaned up {len(to_remove)} old jobs")


# ===== API ENDPOINTS =====


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "ok",
        "server": "email-sender",
        "timestamp": datetime.now().isoformat(),
        "db_files": len([f for f in os.listdir(DB_DIR) if f.endswith(".json")]),
    }


@app.post("/send/single")
async def send_single(body: SingleEmail):
    """Send a single email."""
    request_id = str(uuid.uuid4())[:8]
    html = body.html or template_html
    success, error, error_type = await send_single_email(body.email, html)

    if success:
        return {"success": True, "message": "Sent", "request_id": request_id}
    return {
        "success": False,
        "error": error,
        "error_type": error_type,
        "request_id": request_id,
    }


@app.post("/send/batch")
async def send_batch(body: BatchEmail):
    """Start a batch email job."""
    import asyncio

    job_id = str(uuid.uuid4())
    html = body.html or template_html

    jobs[job_id] = {
        "total": len(body.contacts),
        "sent": 0,
        "failed": 0,
        "status": "started",
        "results": [],
        "cancelled": False,
    }

    asyncio.create_task(process_batch(job_id, body.contacts, html))
    logger.info(f"Started batch job {job_id} with {len(body.contacts)} recipients")

    return {
        "job_id": job_id,
        "total": len(body.contacts),
        "status": "started",
    }


@app.get("/send/status/{job_id}")
async def job_status(job_id: str):
    """Get status of a batch job."""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    job = jobs[job_id]
    return {
        "job_id": job_id,
        "total": job["total"],
        "sent": job["sent"],
        "failed": job["failed"],
        "status": job["status"],
        "results": job["results"],
    }


@app.post("/send/cancel/{job_id}")
async def cancel_job(job_id: str):
    """Cancel a running batch job."""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    jobs[job_id]["cancelled"] = True
    logger.info(f"Job {job_id} marked for cancellation")
    return {"status": "cancelled"}


@app.get("/template")
async def get_template():
    """Get the current email template."""
    return {"html": template_html}


@app.post("/template")
async def update_template(body: TemplateUpdate):
    """Update the email template."""
    global template_html
    template_html = body.html

    template_path = os.path.join(
        BASE_DIR, config.get("template_file", "email_template.html")
    )
    with open(template_path, "w", encoding="utf-8") as f:
        f.write(body.html)

    logger.info("Email template updated")
    return {"success": True, "message": "Template updated"}


# ===== DB ENDPOINTS =====


@app.get("/db/list")
async def list_db_files():
    """List all JSON files in crm/db/ directory."""
    try:
        files = []
        for f in os.listdir(DB_DIR):
            if f.endswith(".json"):
                path = os.path.join(DB_DIR, f)
                stat = os.stat(path)
                files.append(
                    {
                        "name": f,
                        "size": stat.st_size,
                        "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    }
                )

        # Sort by modification time, newest first
        files.sort(key=lambda x: x["modified"], reverse=True)
        return {"files": files}

    except Exception as e:
        logger.error(f"Failed to list DB files: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/db/{filename}")
async def read_db_file(filename: str):
    """Read a JSON file from crm/db/ directory."""
    if not filename.endswith(".json"):
        raise HTTPException(status_code=400, detail="Only .json files allowed")

    # Security: prevent path traversal
    safe_name = os.path.basename(filename)
    filepath = os.path.join(DB_DIR, safe_name)

    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="File not found")

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data

    except json.JSONDecodeError as e:
        # Try to find backup
        backup_path = find_backup(safe_name)
        if backup_path:
            logger.warning(
                f"JSON corrupted for {safe_name}, backup available at {backup_path}"
            )
            raise HTTPException(
                status_code=500,
                detail=f"Invalid JSON: {e}. Backup available: {os.path.basename(backup_path)}",
            )
        raise HTTPException(status_code=500, detail=f"Invalid JSON: {e}")

    except Exception as e:
        logger.error(f"Failed to read {safe_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/db/{filename}")
async def write_db_file(filename: str, request: Request):
    """Write a JSON file to crm/db/ directory with backup and validation."""
    if not filename.endswith(".json"):
        raise HTTPException(status_code=400, detail="Only .json files allowed")

    # Security: prevent path traversal
    safe_name = os.path.basename(filename)
    filepath = os.path.join(DB_DIR, safe_name)

    try:
        body = await request.json()

        # Validate JSON data
        is_valid, error_msg = validate_json_data(body)
        if not is_valid:
            raise HTTPException(
                status_code=400, detail=f"Validation failed: {error_msg}"
            )

        # Check if content unchanged (skip write entirely)
        if os.path.exists(filepath):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    existing = json.load(f)
                if existing == body:
                    logger.info(f"Skipped {safe_name}: content unchanged")
                    return {"success": True, "file": safe_name, "unchanged": True}
            except:
                pass

        # Create backup before overwriting
        backup_path = create_backup(filepath)
        if backup_path:
            logger.info(f"Backup created: {os.path.basename(backup_path)}")

        # Write atomically: write to temp file first, then rename
        temp_path = filepath + ".tmp"
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(body, f, ensure_ascii=False, indent=2)

        # Atomic rename
        os.replace(temp_path, filepath)

        logger.info(f"Saved {safe_name} ({os.path.getsize(filepath)} bytes)")
        return {
            "success": True,
            "file": safe_name,
            "size": os.path.getsize(filepath),
            "backup": os.path.basename(backup_path) if backup_path else None,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to write {safe_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/db/{filename}")
async def delete_db_file(filename: str):
    """Delete a JSON file from crm/db/ directory (with backup)."""
    if not filename.endswith(".json"):
        raise HTTPException(status_code=400, detail="Only .json files allowed")

    safe_name = os.path.basename(filename)
    filepath = os.path.join(DB_DIR, safe_name)

    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="File not found")

    try:
        # Create backup before deleting
        backup_path = create_backup(filepath)
        os.remove(filepath)

        logger.info(f"Deleted {safe_name}, backup at {backup_path}")
        return {
            "success": True,
            "file": safe_name,
            "backup": os.path.basename(backup_path) if backup_path else None,
        }

    except Exception as e:
        logger.error(f"Failed to delete {safe_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/db/{filename}/backups")
async def list_backups(filename: str):
    """List available backups for a file."""
    if not filename.endswith(".json"):
        raise HTTPException(status_code=400, detail="Only .json files allowed")

    safe_name = os.path.basename(filename)
    pattern = f"{safe_name}."
    backups = []

    for f in os.listdir(BACKUP_DIR):
        if f.startswith(pattern) and f.endswith(".bak"):
            full_path = os.path.join(BACKUP_DIR, f)
            stat = os.stat(full_path)
            backups.append(
                {
                    "name": f,
                    "size": stat.st_size,
                    "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                }
            )

    backups.sort(key=lambda x: x["modified"], reverse=True)
    return {"file": safe_name, "backups": backups}


@app.get("/backups")
async def list_all_backups():
    """List all available backups."""
    backups = []

    for f in os.listdir(BACKUP_DIR):
        if f.endswith(".bak"):
            full_path = os.path.join(BACKUP_DIR, f)
            stat = os.stat(full_path)
            # Extract original filename and timestamp
            # Format: filename.json.YYYYMMDD_HHMMSS.bak
            backups.append(
                {
                    "name": f,
                    "size": stat.st_size,
                    "created": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                }
            )

    # Sort by creation time, newest first
    backups.sort(key=lambda x: x["created"], reverse=True)
    return {"backups": backups}


@app.post("/restore/{backup_name}")
async def restore_from_backup(backup_name: str):
    """Restore a JSON file from a backup."""
    # Security: prevent path traversal
    safe_name = os.path.basename(backup_name)
    backup_path = os.path.join(BACKUP_DIR, safe_name)

    if not os.path.exists(backup_path):
        raise HTTPException(status_code=404, detail=f"Backup not found: {safe_name}")

    # Extract original filename from backup name
    # Format: filename.json.YYYYMMDD_HHMMSS.bak
    if not safe_name.endswith(".bak"):
        raise HTTPException(status_code=400, detail="Invalid backup filename")

    # Read backup content
    try:
        with open(backup_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        logger.info(f"Restored from backup: {safe_name}")
        return {
            "success": True,
            "backup": safe_name,
            "contacts": data if isinstance(data, list) else [data],
        }

    except json.JSONDecodeError as e:
        raise HTTPException(status_code=500, detail=f"Invalid JSON in backup: {e}")
    except Exception as e:
        logger.error(f"Failed to restore from {safe_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/db/{filename}/restore")
async def restore_backup(filename: str):
    """Restore a file from its most recent backup."""
    if not filename.endswith(".json"):
        raise HTTPException(status_code=400, detail="Only .json files allowed")

    safe_name = os.path.basename(filename)
    backup_path = find_backup(safe_name)

    if not backup_path:
        raise HTTPException(status_code=404, detail="No backup found")

    filepath = os.path.join(DB_DIR, safe_name)

    try:
        # Backup current file if it exists
        if os.path.exists(filepath):
            create_backup(filepath)

        shutil.copy2(backup_path, filepath)
        logger.info(f"Restored {safe_name} from {backup_path}")

        return {
            "success": True,
            "file": safe_name,
            "restored_from": os.path.basename(backup_path),
        }

    except Exception as e:
        logger.error(f"Failed to restore {safe_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ===== MAIN =====

if __name__ == "__main__":
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)

# Serve CRM static files from root (after API routes)
app.mount("/", StaticFiles(directory=CRM_DIR, html=True), name="root")
