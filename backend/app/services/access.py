"""Transactional demo adapter. No external access is granted by approval."""

from datetime import UTC, datetime, timedelta
from typing import Protocol
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import AccessRequest, AccessRequestEvent, ActionProposal, User
from app.schemas.access import AccessArguments

DEMO_TEAM = "Backend · Demo"
DEMO_PROJECT = "BACKEND"


def policy_context(user: User):
    allowed = user.is_active and user.role == "intern" and user.team.name == DEMO_TEAM
    return {
        "can_prepare": allowed,
        "projects": [DEMO_PROJECT] if allowed else [],
        "resources": ["jira", "confluence", "gitlab"] if allowed else [],
        "permissions": {"read": "просмотр", "write": "редактирование"},
        "default_justification": "Работа над задачами стажировки",
        "steps": "Уточнить сервис, проект и права; подготовить черновик; пользователь подтверждает кнопкой; заявка ожидает согласования. Согласование не выдаёт реальный доступ.",
    }


def policy(user: User, args: AccessArguments):
    if user.role != "intern" or not user.is_active:
        raise HTTPException(403, "Заявки доступны активным стажёрам")
    if args.task_id is not None:
        from sqlalchemy.orm import object_session

        from app.models import OnboardingTask

        task = object_session(user).get(OnboardingTask, args.task_id)
        if not task or task.user_id != user.id:
            raise HTTPException(404, "Задача недоступна")
        if task.verification_type == "request" and task.request_resource != args.resource:
            raise HTTPException(422, "Ресурс заявки не соответствует условию задачи")
    # Explicit synthetic policy; never infer project membership from LLM or RAG.
    if user.team.name != DEMO_TEAM or args.project_key != DEMO_PROJECT:
        raise HTTPException(
            403, "В демополитике разрешён только проект BACKEND команды Backend · Demo"
        )


def approver(db: Session, user: User, resource: str):
    if user.role != "intern" or not user.is_active:
        return None
    candidate = db.get(User, user.mentor_id) if user.mentor_id else None
    return (
        candidate.id
        if (
            candidate
            and candidate.is_active
            and candidate.role == "mentor"
            and candidate.team_id == user.team_id
            and candidate.id != user.id
        )
        else None
    )


def serialize(item: AccessRequest):
    return {
        key: getattr(item, key)
        for key in (
            "id",
            "task_id",
            "user_id",
            "team_id",
            "resource",
            "project_key",
            "permission",
            "justification",
            "status",
            "approver_id",
            "created_at",
            "updated_at",
            "resolved_at",
        )
    } | {"routing": "assigned" if item.approver_id else "awaiting_routing"}


def visible(db: Session, user: User, item: AccessRequest):
    if item.user_id == user.id:
        return True
    owner = db.get(User, item.user_id)
    if not owner or owner.team_id != user.team_id or item.team_id != user.team_id:
        return False
    if user.role == "mentor":
        return owner.role == "intern" and owner.mentor_id == user.id
    return False


def get_request(db: Session, user: User, request_id: int, lock=False):
    query = select(AccessRequest).where(AccessRequest.id == request_id)
    item = db.scalar(query.with_for_update() if lock else query)
    if not item or not visible(db, user, item):
        raise HTTPException(404, "Заявка не найдена")
    return item


def requests(db: Session, user: User, own=False):
    query = select(AccessRequest).where(AccessRequest.team_id == user.team_id)
    if own or user.role == "intern":
        query = select(AccessRequest).where(AccessRequest.user_id == user.id)
    return [
        serialize(item)
        for item in db.scalars(query.order_by(AccessRequest.id.desc())).all()
        if visible(db, user, item)
    ]


def prepare(db: Session, user: User, args: AccessArguments, conversation_id=None):
    policy(user, args)
    db.execute(select(func.pg_advisory_xact_lock(18429, user.id)))
    existing = db.scalar(
        select(ActionProposal)
        .where(
            ActionProposal.user_id == user.id,
            ActionProposal.state == "prepared",
            ActionProposal.expires_at > datetime.now(UTC),
            ActionProposal.parameters == args.model_dump(),
            ActionProposal.team_id == user.team_id,
        )
        .order_by(ActionProposal.created_at.desc())
    )
    if existing:
        return existing
    item = ActionProposal(
        id=str(uuid4()),
        user_id=user.id,
        team_id=user.team_id,
        parameters=args.model_dump(),
        conversation_id=conversation_id,
        expires_at=datetime.now(UTC) + timedelta(minutes=10),
    )
    db.add(item)
    db.flush()
    return item


class CorporateAccessAdapter(Protocol):
    def create(self, db: Session, user: User, proposal: ActionProposal) -> AccessRequest: ...


class DemoCorporateAccessAdapter:
    def create(self, db: Session, user: User, proposal: ActionProposal):
        args = AccessArguments.model_validate(proposal.parameters)
        item = AccessRequest(
            proposal_id=proposal.id,
            user_id=user.id,
            team_id=user.team_id,
            **args.model_dump(),
            approver_id=approver(db, user, args.resource),
        )
        db.add(item)
        db.flush()
        db.add(
            AccessRequestEvent(
                request_id=item.id,
                actor_id=user.id,
                event_type="created",
                comment="Ожидает согласования"
                if item.approver_id
                else "Ожидает маршрутизации: согласующий не назначен",
            )
        )
        return item


adapter: CorporateAccessAdapter = DemoCorporateAccessAdapter()


def proposal_for(db: Session, user: User, proposal_id: str):
    item = db.scalar(
        select(ActionProposal)
        .where(ActionProposal.id == proposal_id, ActionProposal.user_id == user.id)
        .with_for_update()
    )
    if not item:
        raise HTTPException(404, "Черновик не найден")
    return item


def confirm(db: Session, user: User, proposal_id: str):
    # Serializes *all* confirmations of this owner, including distinct identical proposals.
    db.execute(select(func.pg_advisory_xact_lock(18429, user.id)))
    db.refresh(user)
    item = proposal_for(db, user, proposal_id)
    policy(user, AccessArguments.model_validate(item.parameters))
    if item.team_id != user.team_id:
        raise HTTPException(409, "Команда изменилась. Подготовьте новый черновик")
    if item.state == "confirmed":
        result = db.scalar(select(AccessRequest).where(AccessRequest.proposal_id == item.id))
        complete_request_task(db, user, result)
        return result
    if item.state != "prepared" or item.expires_at <= datetime.now(UTC):
        raise HTTPException(409, "Черновик отменён или истёк. Подготовьте новый")
    duplicate = db.scalar(
        select(AccessRequest)
        .where(
            AccessRequest.user_id == user.id,
            AccessRequest.resource == item.parameters["resource"],
            AccessRequest.project_key == item.parameters["project_key"],
            AccessRequest.permission == item.parameters["permission"],
            AccessRequest.status.in_(["pending", "approved"]),
        )
        .order_by(AccessRequest.id.desc())
    )
    if duplicate:
        raise HTTPException(409, f"Такая заявка уже существует: №{duplicate.id}")
    result = adapter.create(db, user, item)
    complete_request_task(db, user, result)
    item.state = "confirmed"
    db.flush()
    return result


def cancel(db: Session, user: User, proposal_id: str):
    item = proposal_for(db, user, proposal_id)
    if item.state == "confirmed":
        raise HTTPException(409, "Заявка уже создана")
    item.state = "cancelled"
    return {"state": item.state}


def decide(db: Session, user: User, request_id: int, status: str, comment: str):
    item = get_request(db, user, request_id, lock=True)
    db.refresh(user)
    if not user.is_active or not visible(db, user, item):
        raise HTTPException(404, "Заявка не найдена")
    owner = db.get(User, item.user_id)
    if (
        user.id == owner.id
        or item.approver_id != user.id
        or approver(db, owner, item.resource) != user.id
    ):
        raise HTTPException(403, "Вы не назначены согласующим")
    if item.status != "pending":
        raise HTTPException(409, "Заявка уже рассмотрена")
    item.status = status
    item.resolved_at = item.updated_at = datetime.now(UTC)
    db.add(
        AccessRequestEvent(request_id=item.id, actor_id=user.id, event_type=status, comment=comment)
    )
    db.flush()
    return item


def complete_request_task(db, user, request):
    from app.models import OnboardingTask, TaskVerification

    if request.task_id is None:
        return
    task = db.scalar(
        select(OnboardingTask)
        .where(OnboardingTask.id == request.task_id, OnboardingTask.user_id == user.id)
        .with_for_update()
    )
    if not task or task.verification_type != "request" or task.status == "done":
        return
    if task.request_resource != request.resource:
        raise HTTPException(409, "Условие задачи изменилось. Подготовьте заявку заново")
    task.status = "done"
    task.completed_at = task.verified_at = datetime.now(UTC)
    task.evidence = (
        f"Заявка №{request.id} отправлена: {request.resource}. Выдача доступа не подтверждена."
    )
    db.add(
        TaskVerification(
            task_id=task.id,
            actor_id=user.id,
            action="request_created",
            evidence=task.evidence,
            comment="Условие задачи — отправка заявки — выполнено backend",
        )
    )
