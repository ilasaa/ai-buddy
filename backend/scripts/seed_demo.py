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
        people = {}
        for role, name in [
            ("manager", "Анна Петрова"),
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
        team.leader_id = people["manager"].id
        people["intern"].mentor_id = people["mentor"].id
        titles = [
            "Ознакомиться с компанией",
            "Познакомиться с наставником",
            "Изучить правила команды",
            "Получить доступ к GitLab",
            "Настроить рабочее окружение",
            "Ознакомиться с архитектурой проекта",
            "Выполнить первую задачу",
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
                    status="done" if i < 3 else "in_progress" if i == 3 else "todo",
                    completed_at=datetime.now(UTC) if i < 3 else None,
                    due_date=date.today() + timedelta(days=i - 2),
                )
            )
    print("Демонстрационные записи готовы. Пароли существующих аккаунтов не изменены.")


if __name__ == "__main__":
    seed()
