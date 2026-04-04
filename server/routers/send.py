import uuid
import asyncio
import json
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from server.models import BatchEmail, SingleEmail
from server.services.batch import jobs, process_batch, _jobs_lock

router = APIRouter(prefix="/send", tags=["send"])


@router.post("/single")
async def send_single(body: SingleEmail):
    from server.config import template_html
    from server.services.email import send_single_email as send_email

    request_id = str(uuid.uuid4())[:8]
    html = body.html or template_html
    success, error, error_type = await send_email(body.email, html)

    if success:
        return {"success": True, "message": "Sent", "request_id": request_id}
    return {
        "success": False,
        "error": error,
        "error_type": error_type,
        "request_id": request_id,
    }


@router.post("/batch")
async def send_batch(body: BatchEmail):
    from server.config import template_html

    job_id = str(uuid.uuid4())
    html = body.html or template_html

    async with _jobs_lock:
        jobs[job_id] = {
            "total": len(body.contacts),
            "sent": 0,
            "failed": 0,
            "status": "started",
            "results": [],
            "cancelled": False,
            "queue": asyncio.Queue(),
        }

    asyncio.create_task(process_batch(job_id, body.contacts, html))

    return {
        "job_id": job_id,
        "total": len(body.contacts),
        "status": "started",
    }


@router.get("/status/{job_id}")
async def job_status(job_id: str):
    async with _jobs_lock:
        if job_id not in jobs:
            raise HTTPException(status_code=404, detail="Job not found")

        job = dict(jobs[job_id])

    return {
        "job_id": job_id,
        "total": job["total"],
        "sent": job["sent"],
        "failed": job["failed"],
        "status": job["status"],
        "results": job["results"],
    }


@router.post("/cancel/{job_id}")
async def cancel_job(job_id: str):
    async with _jobs_lock:
        if job_id not in jobs:
            raise HTTPException(status_code=404, detail="Job not found")

        jobs[job_id]["cancelled"] = True

    return {"status": "cancelled"}


async def _sse_generator(job_id: str):
    async with _jobs_lock:
        if job_id not in jobs:
            return
        queue = jobs[job_id]["queue"]

    try:
        while True:
            item = await queue.get()
            if item is None:
                break

            event_type = item.get("event", "message")
            data = json.dumps(item, ensure_ascii=False)

            if event_type == "done":
                yield f"event: {event_type}\ndata: {data}\n\n"
                break

            yield f"event: {event_type}\ndata: {data}\n\n"
    except asyncio.CancelledError:
        pass


@router.get("/stream/{job_id}")
async def job_stream(job_id: str):
    async with _jobs_lock:
        if job_id not in jobs:
            raise HTTPException(status_code=404, detail="Job not found")

        job = dict(jobs[job_id])

    initial = json.dumps(
        {
            "event": "init",
            "job_id": job_id,
            "total": job["total"],
            "sent": job["sent"],
            "failed": job["failed"],
            "status": job["status"],
            "results": job["results"],
        },
        ensure_ascii=False,
    )

    async def event_stream():
        yield f"event: init\ndata: {initial}\n\n"
        async for chunk in _sse_generator(job_id):
            yield chunk

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
