import json
import logging
import os
import random
import smtplib
import uuid
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_DIR = os.path.join(BASE_DIR, "db")
CRM_DIR = BASE_DIR

# Ensure db directory exists
os.makedirs(DB_DIR, exist_ok=True)

with open(os.path.join(BASE_DIR, "config.json"), "r", encoding="utf-8") as f:
    config = json.load(f)

with open(os.path.join(BASE_DIR, config["template_file"]), "r", encoding="utf-8") as f:
    template_html = f.read()

jobs: dict[str, dict] = {}

app = FastAPI(title="Email Sender Server")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routes FIRST, then static files
# (so API endpoints aren't caught by static file middleware)


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


def send_single_email(recipient_email: str, html_body: str) -> tuple[bool, str, str]:
    try:
        msg = MIMEMultipart("alternative")
        msg["From"] = config["sender_email"]
        msg["To"] = recipient_email
        msg["Subject"] = config["email_subject"]
        msg.attach(MIMEText(html_body, "html"))

        logger.info(f"Connecting to SMTP {config['smtp_server']}:{config['smtp_port']}")
        server = smtplib.SMTP(config["smtp_server"], config["smtp_port"], timeout=30)
        server.starttls()
        server.login(config["sender_email"], config["sender_password"])
        server.sendmail(config["sender_email"], recipient_email, msg.as_string())
        server.quit()
        
        logger.info(f"Email sent successfully to {recipient_email}")
        return True, "", ""
    except Exception as e:
        logger.error(f"Failed to send email to {recipient_email}: {e}")
        return False, str(e), classify_error(e)


async def process_batch(job_id: str, contacts: list[BatchContact], html: str):
    job = jobs[job_id]
    for contact in contacts:
        if job.get("cancelled"):
            job["status"] = "cancelled"
            return

        success, error, error_type = send_single_email(contact.email, html)
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

        if contact != contacts[-1]:
            delay = random.randint(config["delay_min"], config["delay_max"])
            import asyncio

            await asyncio.sleep(delay)

    job["status"] = "completed"


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "server": "email-sender",
        "timestamp": datetime.now().isoformat(),
    }


@app.post("/send/single")
async def send_single(body: SingleEmail):
    request_id = str(uuid.uuid4())[:8]
    html = body.html or template_html
    success, error, error_type = send_single_email(body.email, html)
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
    import asyncio

    asyncio.create_task(process_batch(job_id, body.contacts, html))
    return {
        "job_id": job_id,
        "total": len(body.contacts),
        "status": "started",
    }


@app.get("/send/status/{job_id}")
async def job_status(job_id: str):
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
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    jobs[job_id]["cancelled"] = True
    return {"status": "cancelled"}


@app.get("/template")
async def get_template():
    return {"html": template_html}


@app.post("/template")
async def update_template(body: TemplateUpdate):
    global template_html
    template_html = body.html
    with open(
        os.path.join(BASE_DIR, config["template_file"]), "w", encoding="utf-8"
    ) as f:
        f.write(body.html)
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
        return {"files": files}
    except Exception as e:
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
        raise HTTPException(status_code=500, detail=f"Invalid JSON: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/db/{filename}")
async def write_db_file(filename: str, request: Request):
    """Write a JSON file to crm/db/ directory."""
    if not filename.endswith(".json"):
        raise HTTPException(status_code=400, detail="Only .json files allowed")

    # Security: prevent path traversal
    safe_name = os.path.basename(filename)
    filepath = os.path.join(DB_DIR, safe_name)

    try:
        body = await request.json()
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(body, f, ensure_ascii=False, indent=2)
        return {"success": True, "file": safe_name, "size": os.path.getsize(filepath)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/db/{filename}")
async def delete_db_file(filename: str):
    """Delete a JSON file from crm/db/ directory."""
    if not filename.endswith(".json"):
        raise HTTPException(status_code=400, detail="Only .json files allowed")

    safe_name = os.path.basename(filename)
    filepath = os.path.join(DB_DIR, safe_name)

    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="File not found")

    try:
        os.remove(filepath)
        return {"success": True, "file": safe_name}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)

# Serve CRM static files from root (after API routes)
app.mount("/", StaticFiles(directory=CRM_DIR, html=True), name="root")
