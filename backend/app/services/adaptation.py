from datetime import UTC, date, datetime

from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder
from sqlalchemy import select

from app.models import OnboardingTask, Team, User
from app.models.adaptation import (
    AdaptationGoal,
    AdaptationPlan,
    PlanAgreement,
    TaskVerification,
    TeamObjective,
)
from app.services.onboarding import overview


def intern(db, actor, intern_id, manage=False):
    target = db.get(User, intern_id)
    team = db.get(Team, actor.team_id)
    manager = actor.role == "manager" and team and team.leader_id == actor.id
    allowed = target and target.role == "intern" and target.team_id == actor.team_id
    allowed = allowed and (
        manager
        if manage
        else (
            manager
            or actor.id == target.id
            or (actor.role == "mentor" and target.mentor_id == actor.id)
        )
    )
    if not allowed:
        raise HTTPException(404, "Стажёр не найден или недоступен")
    return target


def plan(db, intern_id, lock=False):
    query = select(AdaptationPlan).where(AdaptationPlan.intern_id == intern_id)
    value = db.scalar(query.with_for_update() if lock else query)
    if not value:
        raise HTTPException(404, "План ещё не создан. Обсудите его с руководителем")
    return value


def version_check(value, version):
    if value.version != version:
        raise HTTPException(409, "План изменился. Обновите страницу")


def editable(value, version):
    version_check(value, version)
    if value.status != "draft":
        raise HTTPException(409, "Для изменений откройте новую версию черновика")


def rows(db, cls, condition):
    return db.scalars(select(cls).where(condition).order_by(cls.id)).all()


def serialize(item):
    return jsonable_encoder({c.name: getattr(item, c.name) for c in item.__table__.columns})


def detail(db, intern_id):
    value = db.scalar(select(AdaptationPlan).where(AdaptationPlan.intern_id == intern_id))
    tasks = overview(db, intern_id).model_dump(mode="json")
    goals = rows(db, AdaptationGoal, AdaptationGoal.plan_id == value.id) if value else []
    history = rows(db, PlanAgreement, PlanAgreement.plan_id == value.id) if value else []
    user = db.get(User, intern_id)
    from app.models import AccessRequest, MentorQuestion

    requests = rows(db, AccessRequest, AccessRequest.user_id == intern_id)
    from app.models import ChatConversation, ChatMessage

    answers = db.scalars(
        select(ChatMessage.sources)
        .join(ChatConversation)
        .where(ChatConversation.user_id == intern_id, ChatMessage.role == "assistant")
    ).all()
    durations = [(r.resolved_at - r.created_at).total_seconds() for r in requests if r.resolved_at]

    next_steps = []
    if not value or value.status != "active":
        next_steps.append("Обсудите и согласуйте актуальную версию плана с руководителем")
    for task in tasks["tasks"]:
        if task["status"] == "blocked":
            next_steps.append(f"Обсудите блокирующую проблему с наставником: {task['title']}")
        elif task["status"] == "submitted":
            next_steps.append(f"Ожидайте проверки: {task['title']}")
        elif task["status"] != "done":
            prefix = (
                "Просрочено: "
                if task["due_date"] and task["due_date"] < date.today().isoformat()
                else "Следующий шаг: "
            )
            next_steps.append(prefix + task["title"])
    for goal in goals:
        if not any(t["goal_id"] == goal.id for t in tasks["tasks"]):
            next_steps.append(f"Обсудите задачи для цели «{goal.title}» с руководителем")
    return dict(
        questions=[
            serialize(q) for q in rows(db, MentorQuestion, MentorQuestion.intern_id == intern_id)
        ],
        requests=[serialize(r) for r in requests],
        metrics=dict(
            submitted=sum(t["status"] == "submitted" for t in tasks["tasks"]),
            blocked=sum(t["status"] == "blocked" for t in tasks["tasks"]),
            overdue=sum(
                t["status"] != "done"
                and bool(t["due_date"])
                and t["due_date"] < date.today().isoformat()
                for t in tasks["tasks"]
            ),
            goals_achieved=sum(g.status == "achieved" for g in goals),
            requests_total=len(requests),
            requests_pending=sum(r.status == "pending" for r in requests),
            requests_approved=sum(r.status == "approved" for r in requests),
            requests_rejected=sum(r.status == "rejected" for r in requests),
            mean_decision_seconds=round(sum(durations) / len(durations), 1) if durations else None,
            assistant_answers=len(answers),
            answers_with_sources=sum(bool(s) for s in answers),
            sources_share=round(sum(bool(s) for s in answers) / len(answers) * 100)
            if answers
            else None,
        ),
        plan=serialize(value) if value else None,
        goals=[serialize(g) for g in goals],
        history=[serialize(h) for h in history],
        **tasks,
        next_steps=next_steps,
        objectives=[
            serialize(o) for o in rows(db, TeamObjective, TeamObjective.team_id == user.team_id)
        ],
        verifications=[
            serialize(v)
            for v in db.scalars(
                select(TaskVerification)
                .join(OnboardingTask)
                .where(OnboardingTask.user_id == intern_id)
                .order_by(TaskVerification.id)
            ).all()
        ],
    )


def event(db, value, actor, action, comment=""):
    snapshot = detail(db, value.intern_id)
    snapshot.pop("history", None)
    db.add(
        PlanAgreement(
            plan_id=value.id,
            actor_id=actor.id,
            actor_role=actor.role,
            version=value.version,
            action=action,
            comment=comment,
            snapshot=snapshot,
        )
    )
    value.updated_at = datetime.now(UTC)


def save_plan(db, actor, intern_id, body):
    intern(db, actor, intern_id, manage=True)
    # Lock the intern as well: two first-time creates cannot race.
    db.scalar(select(User).where(User.id == intern_id).with_for_update())
    value = db.scalar(
        select(AdaptationPlan).where(AdaptationPlan.intern_id == intern_id).with_for_update()
    )
    data = body.model_dump(exclude={"version"})
    if value:
        editable(value, body.version)
        children = rows(db, AdaptationGoal, AdaptationGoal.plan_id == value.id)
        linked_tasks = (
            db.scalars(
                select(OnboardingTask).where(OnboardingTask.goal_id.in_([g.id for g in children]))
            ).all()
            if children
            else []
        )
        if any(not body.start_date <= g.target_date <= body.target_date for g in children) or any(
            t.due_date and not body.start_date <= t.due_date <= body.target_date
            for t in linked_tasks
        ):
            raise HTTPException(422, "Период плана должен включать сроки целей и задач")
        value.manager_id = actor.id
        value.version += 1
        for key, val in data.items():
            setattr(value, key, val)
    else:
        if body.version != 0:
            raise HTTPException(409, "Обновите страницу")
        value = AdaptationPlan(intern_id=intern_id, manager_id=actor.id, **data)
        db.add(value)
    db.flush()
    event(db, value, actor, "draft_saved")
    db.commit()
    return detail(db, intern_id)


def agreement(db, actor, intern_id, body):
    intern(db, actor, intern_id, manage=body.action in ("send", "revise"))
    value = plan(db, intern_id, lock=True)
    version_check(value, body.version)
    if body.action == "send":
        editable(value, body.version)
        if not rows(db, AdaptationGoal, AdaptationGoal.plan_id == value.id):
            raise HTTPException(409, "Добавьте хотя бы одну цель с критериями")
        value.status = "pending_agreement"
    elif body.action == "agree":
        if actor.id != intern_id:
            raise HTTPException(403, "План согласует сам стажёр")
        if value.status == "active":
            return detail(db, intern_id)
        if value.status != "pending_agreement":
            raise HTTPException(409, "План не ожидает согласования")
        value.status = "active"
        value.agreed_at = datetime.now(UTC)
    elif body.action == "revise":
        if value.status not in ("active", "pending_agreement"):
            raise HTTPException(409, "План уже находится в черновике")
        event(db, value, actor, "previous_version")
        value.version += 1
        for goal in rows(db, AdaptationGoal, AdaptationGoal.plan_id == value.id):
            goal.status, goal.evidence, goal.verified_by = "active", None, None
        value.status = "draft"
        value.agreed_at = None
    elif not body.comment:
        raise HTTPException(422, "Введите комментарий")
    event(db, value, actor, body.action, body.comment)
    db.commit()
    return detail(db, intern_id)


def add_goal(db, actor, intern_id, body):
    intern(db, actor, intern_id, manage=True)
    value = plan(db, intern_id, lock=True)
    editable(value, body.version)
    if not value.start_date <= body.target_date <= value.target_date:
        raise HTTPException(422, "Срок цели должен входить в период плана")
    db.add(AdaptationGoal(plan_id=value.id, **body.model_dump(exclude={"version"})))
    value.version += 1
    db.flush()
    event(db, value, actor, "goal_added")
    db.commit()
    return detail(db, intern_id)


def add_task(db, actor, intern_id, body):
    target = intern(db, actor, intern_id, manage=True)
    value = plan(db, intern_id, lock=True)
    editable(value, body.version)
    goal = db.get(AdaptationGoal, body.goal_id)
    if not goal or goal.plan_id != value.id:
        raise HTTPException(404, "Цель недоступна")
    if not value.start_date <= body.due_date <= min(value.target_date, goal.target_date):
        raise HTTPException(422, "Срок задачи должен входить в период плана")
    validate_quiz(db, body)
    db.add(
        OnboardingTask(
            user_id=intern_id,
            reviewer_id=target.mentor_id if body.verification_type == "review" else None,
            **body.model_dump(exclude={"version"}),
        )
    )
    value.version += 1
    db.flush()
    event(db, value, actor, "task_added")
    db.commit()
    return detail(db, intern_id)


def verify(db, actor, task_id, body):
    task = db.scalar(select(OnboardingTask).where(OnboardingTask.id == task_id).with_for_update())
    if not task:
        raise HTTPException(404, "Задача не найдена")
    target = intern(db, actor, task.user_id)
    if task.verification_type == "quiz":
        raise HTTPException(409, "Пройдите мини-тест для подтверждения задачи")
    if body.action == "submit":
        if actor.id != task.user_id:
            raise HTTPException(403, "Результат отправляет стажёр")
        if task.status in ("submitted", "done"):
            raise HTTPException(409, "Результат уже отправлен")
        if not body.evidence:
            raise HTTPException(422, "Приложите результат выполнения")
        task.evidence = body.evidence
        task.submitted_at = datetime.now(UTC)
        task.status = "done" if task.verification_type == "self" else "submitted"
        if task.status == "done":
            task.completed_at = task.verified_at = datetime.now(UTC)
    else:
        if actor.id == target.id or (
            actor.role == "mentor" and task.reviewer_id not in (None, actor.id)
        ):
            raise HTTPException(403, "Проверяющий не назначен")
        if task.verification_type != "review" or task.status != "submitted":
            raise HTTPException(409, "Задача не ожидает проверки")
        if body.action == "reject" and not body.comment:
            raise HTTPException(422, "Укажите замечания")
        task.status = "done" if body.action == "approve" else "changes_requested"
        task.completed_at = task.verified_at = (
            datetime.now(UTC) if body.action == "approve" else None
        )
        task.review_comment = body.comment
    db.add(
        TaskVerification(
            task_id=task.id,
            actor_id=actor.id,
            action=body.action,
            evidence=body.evidence or task.evidence or "",
            comment=body.comment,
        )
    )
    db.commit()
    return detail(db, task.user_id)


def update_goal(db, actor, intern_id, goal_id, body):
    intern(db, actor, intern_id, manage=True)
    value = plan(db, intern_id, lock=True)
    editable(value, body.version)
    goal = db.get(AdaptationGoal, goal_id)
    if not goal or goal.plan_id != value.id:
        raise HTTPException(404, "Цель недоступна")
    if not value.start_date <= body.target_date <= value.target_date:
        raise HTTPException(422, "Срок цели должен входить в период плана")
    if any(
        t.due_date and t.due_date > body.target_date
        for t in rows(db, OnboardingTask, OnboardingTask.goal_id == goal.id)
    ):
        raise HTTPException(422, "Срок цели не может быть раньше связанных задач")
    for key, val in body.model_dump(exclude={"version"}).items():
        setattr(goal, key, val)
    goal.status, goal.evidence, goal.verified_by = "active", None, None
    value.version += 1
    db.flush()
    event(db, value, actor, "goal_updated")
    db.commit()
    return detail(db, intern_id)


def update_task(db, actor, intern_id, task_id, body):
    target = intern(db, actor, intern_id, manage=True)
    value = plan(db, intern_id, lock=True)
    editable(value, body.version)
    validate_quiz(db, body)
    task = db.scalar(
        select(OnboardingTask)
        .where(OnboardingTask.id == task_id, OnboardingTask.user_id == intern_id)
        .with_for_update()
    )
    goal = db.get(AdaptationGoal, body.goal_id)
    if not task or not goal or goal.plan_id != value.id:
        raise HTTPException(404, "Задача или цель недоступна")
    if not value.start_date <= body.due_date <= min(value.target_date, goal.target_date):
        raise HTTPException(422, "Срок задачи должен входить в период плана")
    if task.status == "submitted":
        raise HTTPException(409, "Сначала рассмотрите отправленный результат")
    if any(
        getattr(task, key) != getattr(body, key)
        for key in ("title", "description", "goal_id", "verification_type", "quiz_id")
    ):
        task.status, task.completed_at, task.verified_at = "todo", None, None
        task.evidence, task.review_comment, task.submitted_at = None, None, None
    for key, val in body.model_dump(exclude={"version"}).items():
        setattr(task, key, val)
    task.reviewer_id = target.mentor_id if task.verification_type == "review" else None
    goal.status, goal.evidence, goal.verified_by = "active", None, None
    value.version += 1
    db.flush()
    event(db, value, actor, "task_updated")
    db.commit()
    return detail(db, intern_id)


def validate_quiz(db, body):
    from app.models import KnowledgeQuiz

    if (body.verification_type == "quiz") != (body.quiz_id is not None):
        raise HTTPException(422, "Для типа мини-тест укажите тест; для других типов тест не нужен")
    if body.quiz_id and not db.get(KnowledgeQuiz, body.quiz_id):
        raise HTTPException(404, "Мини-тест не найден")
