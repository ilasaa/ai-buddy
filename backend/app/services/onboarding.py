from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import OnboardingTask
from app.schemas.dashboard import OnboardingResponse, TaskResponse


def overview(db: Session, user_id: int):
    tasks = db.scalars(
        select(OnboardingTask)
        .where(OnboardingTask.user_id == user_id)
        .order_by(OnboardingTask.due_date.asc().nullslast(), OnboardingTask.id)
    ).all()
    completed = sum(task.status == "done" for task in tasks)
    return OnboardingResponse(
        tasks=[TaskResponse.model_validate(task) for task in tasks],
        completed=completed,
        total=len(tasks),
        percent=round(completed / len(tasks) * 100) if tasks else 0,
    )


def change_status(db: Session, user_id: int, task_id: int, status: str):
    task = db.scalar(
        select(OnboardingTask)
        .where(OnboardingTask.id == task_id, OnboardingTask.user_id == user_id)
        .with_for_update()
    )
    if not task:
        raise HTTPException(404, "Задача не найдена")
    if task.status != status:
        task.status = status
        task.completed_at = datetime.now(UTC) if status == "done" else None
    db.commit()
    db.refresh(task)
    return task
