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
    if status in ("submitted", "changes_requested") or (
        status == "done" and task.verification_type != "self"
    ):
        raise HTTPException(
            409, "Используйте отправку результата и проверку уполномоченным пользователем"
        )
    if task.status == "submitted" and task.status != status:
        raise HTTPException(409, "Задача ожидает проверки")
    if task.status == "done" and task.verification_type != "self" and status != "done":
        raise HTTPException(
            409, "Подтверждённый результат пересматривает руководитель через новую версию"
        )
    if task.status != status:
        from app.models import AdaptationGoal, TaskVerification

        goal = db.get(AdaptationGoal, task.goal_id) if task.goal_id else None
        if goal and goal.status == "achieved":
            raise HTTPException(409, "Цель уже подтверждена. Обсудите пересмотр с руководителем")
        db.add(
            TaskVerification(
                task_id=task.id,
                actor_id=user_id,
                action="self_done" if status == "done" else status,
                evidence=task.evidence or "",
                comment="Самостоятельное изменение статуса",
            )
        )
        task.verified_at = datetime.now(UTC) if status == "done" else None
        task.status = status
        task.completed_at = datetime.now(UTC) if status == "done" else None
    db.commit()
    db.refresh(task)
    return task
