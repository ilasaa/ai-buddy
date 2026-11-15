"""Run from backend: python -m scripts.seed_demo (synthetic local data only)."""

import os
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models import OnboardingTask, Team, User
from app.services.auth import passwords


def seed():
    password = os.environ.get("DEMO_PASSWORD", "")
    if len(password) < 12:
        raise SystemExit("Установите DEMO_PASSWORD длиной не менее 12 символов")
    with SessionLocal.begin() as db:
        team = db.scalar(select(Team).where(Team.name == "Backend · Demo"))
        if not team:
            team = Team(
                name="Backend · Demo",
                description="Синтетическая команда локального прототипа. Не данные Авито.",
            )
            db.add(team)
            db.flush()
        if not db.scalar(select(Team).where(Team.name == "Analytics · Demo")):
            db.add(
                Team(
                    name="Analytics · Demo",
                    description="Синтетическая команда для проверки доступа к RAG",
                )
            )
            db.flush()
        people = {}
        for role, name in [
            ("mentor", "Дмитрий Смирнов"),
            ("intern", "Алексей Иванов"),
        ]:
            email = f"{role}@ai-buddy.example"
            user = db.scalar(select(User).where(User.email == email))
            if user and user.team_id != team.id:
                raise SystemExit(f"Конфликт demo email: {email}; данные не изменены")
            if not user:
                user = User(
                    full_name=name,
                    email=email,
                    role=role,
                    team_id=team.id,
                    password_hash=passwords.hash(password),
                    internship_started_at=date.today() - timedelta(days=6)
                    if role == "intern"
                    else None,
                )
                db.add(user)
                db.flush()
            people[role] = user
        team.leader_id = people["mentor"].id
        people["intern"].mentor_id = people["mentor"].id
        titles = [
            "Ознакомиться с компанией",
            "Познакомиться с наставником",
            "Изучить правила команды",
            "Получить доступ к GitLab",
            "Настроить рабочее окружение",
            "Ознакомиться с архитектурой проекта",
            "Выполнить первую задачу",
            "Оформить доступ к Jira через AI-buddy",
        ]
        for i, title in enumerate(titles):
            if db.scalar(
                select(OnboardingTask.id).where(
                    OnboardingTask.user_id == people["intern"].id, OnboardingTask.title == title
                )
            ):
                continue
            db.add(
                OnboardingTask(
                    user_id=people["intern"].id,
                    title=title,
                    description="Демонстрационная задача адаптации. Результат обсудите с наставником.",
                    verification_type="request" if i == 7 else "self",
                    request_resource="jira" if i == 7 else None,
                    status="done" if i < 3 else "in_progress" if i == 3 else "todo",
                    completed_at=datetime.now(UTC) if i < 3 else None,
                    due_date=date.today() + timedelta(days=i - 2),
                )
            )
        from scripts.quiz_data import seed_quizzes

        seed_quizzes(db)
        seed_adaptation(db, people, team, password)
    print("Демонстрационные записи готовы. Пароли существующих аккаунтов не изменены.")


def seed_adaptation(db, people, team, password):
    from app.models import (
        AdaptationGoal,
        AdaptationPlan,
        PlanAgreement,
        TaskVerification,
        TeamObjective,
    )
    from app.services.adaptation import detail

    # Separate ready profile: never pre-complete the newcomer used for the full demo.
    for email, name in [
        ("intern-new@ai-buddy.example", "Новый стажёр"),
        ("intern-ready@ai-buddy.example", "Стажёр — обзор прогресса"),
    ]:
        if not db.scalar(select(User).where(User.email == email)):
            db.add(
                User(
                    full_name=name,
                    email=email,
                    role="intern",
                    team_id=team.id,
                    mentor_id=people["mentor"].id,
                    internship_started_at=date.today(),
                    password_hash=passwords.hash(password),
                )
            )
    db.flush()
    ready = db.scalar(select(User).where(User.email == "intern-ready@ai-buddy.example"))
    if not db.scalar(select(AdaptationPlan).where(AdaptationPlan.intern_id == ready.id)):
        plan = AdaptationPlan(
            intern_id=ready.id,
            mentor_id=people["mentor"].id,
            title="Синтетический Backend-план",
            expectations="Самостоятельно выполнять согласованные инженерные задачи и своевременно сообщать о блокировках.",
            start_date=date.today() - timedelta(days=10),
            target_date=date.today() + timedelta(days=90),
            status="active",
            agreed_at=datetime.now(UTC),
        )
        db.add(plan)
        db.flush()
        goals = []
        for title, criteria in [
            (
                "Освоить рабочее окружение",
                "Получены доступы, настроено окружение, локально запущен сервис",
            ),
            (
                "Выполнить первую самостоятельную инженерную задачу",
                "Требования изучены, решение и тесты прошли Code Review",
            ),
            (
                "Освоить процессы командной разработки",
                "Понимает Git workflow, трекер задач и отправку изменений на ревью",
            ),
        ]:
            goal = AdaptationGoal(
                plan_id=plan.id,
                title=title,
                success_criteria=criteria,
                target_date=plan.target_date,
            )
            db.add(goal)
            goals.append(goal)
        db.flush()
        titles = [
            "Познакомиться с командой",
            "Прочитать правила коммуникации",
            "Настроить окружение",
            "Отправить заявку на доступ к Jira",
            "Получить доступ к GitLab",
            "Запустить сервис локально",
            "Изучить требования первой задачи",
            "Написать тесты первой задачи",
            "Пройти Code Review",
            "Изучить Git workflow",
        ]
        for index, title in enumerate(titles):
            status = (
                "done"
                if index < 2
                else "submitted"
                if index == 2
                else "blocked"
                if index == 3
                else "todo"
            )
            review = index in (2, 5, 7, 8)
            from app.models import KnowledgeQuiz

            quiz = (
                db.scalar(select(KnowledgeQuiz).where(KnowledgeQuiz.slug == "git-workflow"))
                if index == 9
                else None
            )
            task = OnboardingTask(
                user_id=ready.id,
                title=title,
                goal_id=goals[0 if index < 6 else 1 if index < 9 else 2].id,
                verification_type="request"
                if index == 3
                else "quiz"
                if quiz
                else "review"
                if review
                else "self",
                request_resource="jira" if index == 3 else None,
                quiz_id=quiz.id if quiz else None,
                reviewer_id=people["mentor"].id if review else None,
                status=status,
                due_date=date.today() + timedelta(days=index - 4),
                completed_at=datetime.now(UTC) if status == "done" else None,
                submitted_at=datetime.now(UTC) if status == "submitted" else None,
                evidence="Синтетический результат: сервис запускается, приложен учебный MR"
                if status == "submitted"
                else None,
                description="Синтетическая задача прототипа, не официальный чек-лист Авито",
            )
            db.add(task)
            db.flush()
            if status == "submitted":
                db.add(
                    TaskVerification(
                        task_id=task.id,
                        actor_id=ready.id,
                        action="submit",
                        evidence=task.evidence,
                        comment="Демонстрационные данные",
                    )
                )
        db.flush()
        snapshot = detail(db, ready.id)
        snapshot.pop("history", None)
        db.add(
            PlanAgreement(
                plan_id=plan.id,
                actor_id=people["mentor"].id,
                version=1,
                actor_role="mentor",
                action="synthetic_seed",
                comment="Заранее подготовленное синтетическое состояние для обзора. Полный сценарий — intern-new.",
                snapshot=snapshot,
            )
        )
    from app.models import AccessRequest
    from app.schemas.access import AccessArguments
    from app.services import access

    if not db.scalar(select(AccessRequest).where(AccessRequest.user_id == ready.id)):
        access_task = db.scalar(
            select(OnboardingTask).where(
                OnboardingTask.user_id == ready.id,
                OnboardingTask.title == "Отправить заявку на доступ к Jira",
            )
        )
        proposal = access.prepare(
            db,
            ready,
            AccessArguments(
                resource="jira",
                project_key="BACKEND",
                permission="read",
                justification="Синтетическая заявка профиля обзора прогресса",
                task_id=access_task.id if access_task else None,
            ),
        )
        access.confirm(db, ready, proposal.id)
    if not db.scalar(select(TeamObjective).where(TeamObjective.team_id == team.id)):
        db.add(
            TeamObjective(
                team_id=team.id,
                title="Улучшить качество и надёжность демонстрационного backend-сервиса",
                key_results=[
                    "Проверки критических сценариев",
                    "Успешный CI",
                    "Устранены согласованные дефекты",
                ],
                period_start=date.today(),
                period_end=date.today() + timedelta(days=90),
            )
        )


if __name__ == "__main__":
    seed()
