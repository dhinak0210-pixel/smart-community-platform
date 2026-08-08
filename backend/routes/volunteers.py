"""Volunteer task management and assignment endpoints."""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import select

from backend.database import get_db
from backend.models.user import User, UserRole
from backend.models.volunteer import VolunteerTask, TaskStatus
from backend.models.issue import Issue
from backend.utils.auth import get_current_user
from pydantic import BaseModel, ConfigDict
from datetime import datetime

router = APIRouter(prefix="/volunteers", tags=["Volunteer Tasks"])


class VolunteerTaskCreate(BaseModel):
    title: str
    description: str
    issue_id: int


class VolunteerTaskResponse(BaseModel):
    id: int
    title: str
    description: str
    status: TaskStatus
    issue_id: int
    volunteer_id: Optional[int] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


@router.get("/tasks", response_model=List[VolunteerTaskResponse])
def list_volunteer_tasks(
    status_filter: Optional[TaskStatus] = None,
    db: Session = Depends(get_db)
):
    """List open or assigned volunteer tasks."""
    stmt = select(VolunteerTask)
    if status_filter:
        stmt = stmt.where(VolunteerTask.status == status_filter)
    tasks = db.execute(stmt.order_by(VolunteerTask.created_at.desc())).scalars().all()
    return list(tasks)


@router.post("/tasks", response_model=VolunteerTaskResponse, status_code=status.HTTP_201_CREATED)
def create_volunteer_task(
    task_in: VolunteerTaskCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new volunteer task linked to an issue (Authorities / Admins only)."""
    if current_user.role not in [UserRole.AUTHORITY, UserRole.ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only authorities or admins can create volunteer tasks."
        )

    issue = db.execute(select(Issue).where(Issue.id == task_in.issue_id)).scalar_one_or_none()
    if not issue:
        raise HTTPException(status_code=404, detail="Linked issue not found.")

    task = VolunteerTask(
        title=task_in.title,
        description=task_in.description,
        issue_id=task_in.issue_id,
        status=TaskStatus.OPEN,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


@router.post("/tasks/{task_id}/assign", response_model=VolunteerTaskResponse)
@router.post("/tasks/{task_id}/claim", response_model=VolunteerTaskResponse)
def assign_volunteer_task(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Volunteer assigns themselves to an open task."""
    task = db.execute(select(VolunteerTask).where(VolunteerTask.id == task_id)).scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found.")

    if task.status != TaskStatus.OPEN:
        raise HTTPException(status_code=400, detail="Task is no longer open for assignment.")

    task.volunteer_id = current_user.id
    task.status = TaskStatus.ASSIGNED
    db.commit()
    db.refresh(task)
    return task


@router.post("/tasks/{task_id}/complete", response_model=VolunteerTaskResponse)
def complete_volunteer_task(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Mark assigned volunteer task as completed."""
    task = db.execute(select(VolunteerTask).where(VolunteerTask.id == task_id)).scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found.")

    if task.volunteer_id != current_user.id and current_user.role not in [UserRole.AUTHORITY, UserRole.ADMIN]:
        raise HTTPException(status_code=403, detail="Not authorized to complete this task.")

    task.status = TaskStatus.COMPLETED
    db.commit()
    db.refresh(task)
    return task
