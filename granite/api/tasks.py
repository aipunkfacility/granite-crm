"""Tasks API: создание и управление задачами follow-up."""
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from granite.api.deps import get_db
from granite.database import CrmTaskRow

__all__ = ["router"]

router = APIRouter()


@router.post("/companies/{company_id}/tasks")
def create_task(company_id: int, data: dict, db: Session = Depends(get_db)):
    """Создать задачу для компании."""
    due_date = None
    if data.get("due_date"):
        try:
            due_date = datetime.fromisoformat(data["due_date"])
        except ValueError:
            pass

    task = CrmTaskRow(
        company_id=company_id,
        title=data.get("title", "Follow-up"),
        description=data.get("description", ""),
        due_date=due_date,
        priority=data.get("priority", "normal"),
        task_type=data.get("task_type", "follow_up"),
    )
    db.add(task)
    db.flush()
    return {"ok": True, "task_id": task.id}


@router.get("/tasks")
def list_tasks(
    db: Session = Depends(get_db),
    status: Optional[str] = None,
    priority: Optional[str] = None,
    company_id: Optional[int] = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
):
    """Список задач с фильтрами. По умолчанию — только привязанные к компании."""
    q = db.query(CrmTaskRow).filter(CrmTaskRow.company_id.isnot(None))
    if status:
        q = q.filter_by(status=status)
    if priority:
        q = q.filter_by(priority=priority)
    if company_id:
        q = q.filter_by(company_id=company_id)
    q = q.order_by(CrmTaskRow.due_date.asc().nullslast(), CrmTaskRow.created_at.asc())

    total = q.count()
    tasks = q.offset((page - 1) * per_page).limit(per_page).all()

    return {
        "items": [
            {
                "id": t.id,
                "company_id": t.company_id,
                "title": t.title,
                "task_type": t.task_type,
                "priority": t.priority,
                "status": t.status,
                "due_date": t.due_date.isoformat() if t.due_date else None,
                "created_at": t.created_at.isoformat() if t.created_at else None,
            }
            for t in tasks
        ],
        "total": total,
        "page": page,
        "per_page": per_page,
    }


@router.patch("/tasks/{task_id}")
def update_task(task_id: int, data: dict, db: Session = Depends(get_db)):
    """Обновить задачу (статус, приоритет)."""
    task = db.get(CrmTaskRow, task_id)
    if not task:
        raise HTTPException(404, "Task not found")

    for key in ("status", "priority", "title"):
        if key in data:
            setattr(task, key, data[key])

    if data.get("status") == "done":
        task.completed_at = datetime.now(timezone.utc)

    return {"ok": True}
