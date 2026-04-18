"""Tasks API: создание и управление задачами follow-up."""
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from granite.api.deps import get_db
from granite.api.schemas import (
    CreateTaskRequest, UpdateTaskRequest,
    OkWithIdResponse, OkResponse,
    TaskDetailResponse, PaginatedResponse,
)
from granite.database import CrmTaskRow, CompanyRow

__all__ = ["router"]

router = APIRouter()


@router.post("/companies/{company_id}/tasks", response_model=OkWithIdResponse, status_code=201)
def create_task(company_id: int, data: CreateTaskRequest, db: Session = Depends(get_db)):
    """Создать задачу для компании."""
    # FIX K5: При ошибке парсинга due_date возвращаем 422,
    # а не молча создаём задачу с due_date=None.
    due_date = None
    if data.due_date:
        try:
            due_date = datetime.fromisoformat(data.due_date)
        except ValueError as exc:
            raise HTTPException(
                422,
                f"Invalid due_date format: {exc}. Expected ISO 8601, e.g. 2026-05-01T12:00",
            )

    # FIX H6: Проверяем существование компании перед созданием задачи.
    company = db.get(CompanyRow, company_id)
    if not company:
        raise HTTPException(404, "Company not found")

    task = CrmTaskRow(
        company_id=company_id,
        title=data.title,
        description=data.description,
        due_date=due_date,
        priority=data.priority,
        task_type=data.task_type,
    )
    db.add(task)
    db.flush()
    return OkWithIdResponse(ok=True, id=task.id)


@router.get("/tasks", response_model=PaginatedResponse)
def list_tasks(
    db: Session = Depends(get_db),
    status: Optional[str] = None,
    priority: Optional[str] = None,
    company_id: Optional[int] = None,
    task_type: Optional[str] = None,
    include_unlinked: bool = False,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
):
    """Список задач с фильтрами. По умолчанию — только привязанные к компании."""
    q = (
        db.query(CrmTaskRow, CompanyRow)
        .outerjoin(CompanyRow, CrmTaskRow.company_id == CompanyRow.id)
    )
    if not include_unlinked:
        q = q.filter(CrmTaskRow.company_id.isnot(None))
    if status:
        q = q.filter(CrmTaskRow.status == status)
    if priority:
        q = q.filter(CrmTaskRow.priority == priority)
    if company_id:
        q = q.filter(CrmTaskRow.company_id == company_id)
    if task_type:
        q = q.filter(CrmTaskRow.task_type == task_type)
    q = q.order_by(CrmTaskRow.due_date.asc().nullslast(), CrmTaskRow.created_at.asc())

    total = q.count()
    rows = q.offset((page - 1) * per_page).limit(per_page).all()

    return {
        "items": [
            {
                "id": t.id,
                "company_id": t.company_id,
                "company_name": c.name_best if c else None,
                "company_city": c.city if c else None,
                "title": t.title,
                "task_type": t.task_type,
                "priority": t.priority,
                "status": t.status,
                "due_date": t.due_date.isoformat() if t.due_date else None,
                "created_at": t.created_at.isoformat() if t.created_at else None,
            }
            for t, c in rows
        ],
        "total": total,
        "page": page,
        "per_page": per_page,
    }


@router.get("/companies/{company_id}/tasks", response_model=list[TaskDetailResponse])
def list_company_tasks(
    company_id: int,
    db: Session = Depends(get_db),
    status: Optional[str] = None,
):
    """Задачи конкретной компании."""
    company = db.get(CompanyRow, company_id)
    if not company:
        raise HTTPException(404, "Company not found")

    q = db.query(CrmTaskRow).filter_by(company_id=company_id)
    if status:
        q = q.filter_by(status=status)
    tasks = q.order_by(CrmTaskRow.due_date.asc().nullslast()).all()

    return [
        {
            "id": t.id,
            "title": t.title,
            "task_type": t.task_type,
            "priority": t.priority,
            "status": t.status,
            "due_date": t.due_date.isoformat() if t.due_date else None,
            "created_at": t.created_at.isoformat() if t.created_at else None,
        }
        for t in tasks
    ]


@router.patch("/tasks/{task_id}", response_model=OkResponse)
def update_task(task_id: int, data: UpdateTaskRequest, db: Session = Depends(get_db)):
    """Обновить задачу (статус, приоритет)."""
    task = db.get(CrmTaskRow, task_id)
    if not task:
        raise HTTPException(404, "Task not found")

    updates = data.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(task, key, value)

    if data.status == "done":
        task.completed_at = datetime.now(timezone.utc)

    return OkResponse(ok=True)


@router.delete("/tasks/{task_id}", response_model=OkResponse)
def delete_task(task_id: int, db: Session = Depends(get_db)):
    """Удалить задачу."""
    task = db.get(CrmTaskRow, task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    db.delete(task)
    db.flush()
    return OkResponse(ok=True)
