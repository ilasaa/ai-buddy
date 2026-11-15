from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Team, User
from app.models.adaptation import TeamObjective
from app.schemas.adaptation import (
    AgreementInput,
    GoalInput,
    ObjectiveInput,
    PlanInput,
    TaskInput,
    VerificationInput,
)
from app.services import adaptation as service
from app.services.auth import current_user

router = APIRouter(prefix="/adaptation", tags=["Персональная адаптация"])


@router.get("/interns")
def interns(actor: User = Depends(current_user), db: Session = Depends(get_db)):
    team = db.get(Team, actor.team_id)
    query = select(User).where(User.team_id == actor.team_id, User.role == "intern")
    if actor.role == "mentor":
        query = query.where(User.mentor_id == actor.id)
    elif actor.role != "manager" or team.leader_id != actor.id:
        raise HTTPException(403, "Раздел доступен руководителю и назначенному наставнику")
    return [dict(id=u.id, full_name=u.full_name) for u in db.scalars(query.order_by(User.id)).all()]


@router.get("/{intern_id}")
def get_plan(intern_id: int, actor: User = Depends(current_user), db: Session = Depends(get_db)):
    service.intern(db, actor, intern_id)
    return service.detail(db, intern_id)


@router.post("/{intern_id}/plan")
def save_plan(
    intern_id: int,
    body: PlanInput,
    actor: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    return service.save_plan(db, actor, intern_id, body)


@router.post("/{intern_id}/agreement")
def agreement(
    intern_id: int,
    body: AgreementInput,
    actor: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    return service.agreement(db, actor, intern_id, body)


@router.post("/{intern_id}/goals")
def goal(
    intern_id: int,
    body: GoalInput,
    actor: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    return service.add_goal(db, actor, intern_id, body)


@router.post("/{intern_id}/tasks")
def task(
    intern_id: int,
    body: TaskInput,
    actor: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    return service.add_task(db, actor, intern_id, body)


@router.post("/tasks/{task_id}/verification")
def verify(
    task_id: int,
    body: VerificationInput,
    actor: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    return service.verify(db, actor, task_id, body)


@router.post("/{intern_id}/objectives")
def objective(
    intern_id: int,
    body: ObjectiveInput,
    actor: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    target = service.intern(db, actor, intern_id, manage=True)
    if body.period_end < body.period_start or any(
        not k.strip() or len(k) > 1000 for k in body.key_results
    ):
        raise HTTPException(422, "Проверьте период и ключевые результаты")
    db.add(TeamObjective(team_id=target.team_id, **body.model_dump()))
    db.commit()
    return service.detail(db, intern_id)


@router.post("/{intern_id}/goals/{goal_id}/verify")
def verify_goal(
    intern_id: int,
    goal_id: int,
    body: VerificationInput,
    actor: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    from app.models import AdaptationGoal, OnboardingTask

    service.intern(db, actor, intern_id, manage=True)
    value = service.plan(db, intern_id, lock=True)
    goal = db.get(AdaptationGoal, goal_id)
    if not goal or goal.plan_id != value.id:
        raise HTTPException(404, "Цель не найдена")
    tasks = service.rows(db, OnboardingTask, OnboardingTask.goal_id == goal_id)
    if (
        value.status != "active"
        or body.action != "approve"
        or not body.evidence
        or not tasks
        or any(t.status != "done" for t in tasks)
    ):
        raise HTTPException(
            409, "Необходимы активный план, завершённые задачи и подтверждение критериев"
        )
    if goal.status == "achieved":
        return service.detail(db, intern_id)
    goal.status, goal.evidence, goal.verified_by = "achieved", body.evidence, actor.id
    service.event(db, value, actor, "goal_verified", body.evidence)
    db.commit()
    return service.detail(db, intern_id)


@router.patch("/{intern_id}/goals/{goal_id}")
def update_goal(
    intern_id: int,
    goal_id: int,
    body: GoalInput,
    actor: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    return service.update_goal(db, actor, intern_id, goal_id, body)


@router.patch("/{intern_id}/tasks/{task_id}")
def update_task(
    intern_id: int,
    task_id: int,
    body: TaskInput,
    actor: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    return service.update_task(db, actor, intern_id, task_id, body)


class QuestionInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    text: str = Field(min_length=3, max_length=5000)


@router.post("/{intern_id}/questions")
def question(
    intern_id: int,
    body: QuestionInput,
    actor: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    from app.models import MentorQuestion

    target = service.intern(db, actor, intern_id)
    if actor.id != target.id:
        raise HTTPException(403, "Обращение отправляет стажёр")
    mentor = db.get(User, target.mentor_id) if target.mentor_id else None
    if (
        not mentor
        or mentor.role != "mentor"
        or mentor.team_id != target.team_id
        or not mentor.is_active
    ):
        raise HTTPException(409, "Наставник не назначен. Обратитесь к руководителю")
    db.scalar(select(User).where(User.id == target.id).with_for_update())
    existing = db.scalar(
        select(MentorQuestion).where(
            MentorQuestion.intern_id == intern_id,
            MentorQuestion.question == body.text,
            MentorQuestion.answer.is_(None),
        )
    )
    if not existing:
        db.add(MentorQuestion(intern_id=target.id, mentor_id=mentor.id, question=body.text))
    db.commit()
    return service.detail(db, intern_id)


@router.post("/{intern_id}/questions/{question_id}/answer")
def answer(
    intern_id: int,
    question_id: int,
    body: QuestionInput,
    actor: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    from datetime import UTC, datetime

    from app.models import MentorQuestion

    service.intern(db, actor, intern_id)
    value = db.scalar(
        select(MentorQuestion)
        .where(MentorQuestion.id == question_id, MentorQuestion.intern_id == intern_id)
        .with_for_update()
    )
    if not value or actor.role != "mentor" or value.mentor_id != actor.id:
        raise HTTPException(404, "Обращение недоступно")
    if value.answer:
        raise HTTPException(409, "Обращение уже рассмотрено")
    value.answer, value.answered_by, value.answered_at = body.text, actor.id, datetime.now(UTC)
    db.commit()
    return service.detail(db, intern_id)
