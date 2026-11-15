"""Прикладные интеграционные сценарии на отдельной PostgreSQL-базе."""

import json
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.session import get_db
from app.main import app
from app.models import (
    AdaptationPlan,
    OnboardingTask,
    PlanAgreement,
    TaskVerification,
    Team,
    User,
)
from app.services import access, tools
from app.services.auth import current_user

HEADERS = {"Origin": "http://localhost:5173", "X-Requested-With": "AI-buddy"}


@pytest.fixture
def scenario(db_session):
    db = db_session
    team = Team(name="Adaptation test")
    other = Team(name="Adaptation foreign")
    db.add_all([team, other])
    db.flush()
    people = {}
    for key, role, team_id in [
        ("manager", "mentor", team.id),
        ("mentor", "mentor", team.id),
        ("intern", "intern", team.id),
        ("outsider", "mentor", other.id),
        ("stranger", "mentor", team.id),
    ]:
        person = User(full_name=key, email=f"{key}@adaptation.test", role=role, team_id=team_id)
        db.add(person)
        people[key] = person
    db.flush()
    people["manager"] = people["mentor"]
    team.leader_id = people["mentor"].id
    people["intern"].mentor_id = people["mentor"].id
    db.flush()
    app.dependency_overrides[get_db] = lambda: db

    def as_role(role):
        app.dependency_overrides[current_user] = lambda: people[role]

    as_role("manager")
    with TestClient(app, headers=HEADERS) as client:
        yield client, people, as_role
    app.dependency_overrides.clear()


def create(client, people):
    i = people["intern"].id
    start = date.today()
    end = start + timedelta(days=90)
    r = client.post(
        f"/adaptation/{i}/plan",
        json={
            "title": "План Backend",
            "expectations": "Самостоятельная инженерная работа",
            "start_date": str(start),
            "target_date": str(end),
        },
    )
    assert r.status_code == 200, r.text
    version = r.json()["plan"]["version"]
    r = client.post(
        f"/adaptation/{i}/goals",
        json={
            "title": "Освоить окружение",
            "success_criteria": "Запуск сервиса и зелёные тесты",
            "target_date": str(end),
            "version": version,
        },
    )
    assert r.status_code == 200, r.text
    goal = r.json()["goals"][0]["id"]
    version = r.json()["plan"]["version"]
    for kind in ["self", "review"]:
        r = client.post(
            f"/adaptation/{i}/tasks",
            json={
                "title": f"Задача {kind}",
                "goal_id": goal,
                "due_date": str(end),
                "verification_type": kind,
                "version": version,
            },
        )
        assert r.status_code == 200, r.text
        version = r.json()["plan"]["version"]
    return i, version, r.json()


def test_plan_agreement_revision_and_persistence(scenario, db_session):
    c, p, as_role = scenario
    i, v, d = create(c, p)
    assert len(d["tasks"]) == 2 and d["tasks"][0]["goal_id"] == d["goals"][0]["id"]
    assert (
        c.post(f"/adaptation/{i}/agreement", json={"action": "agree", "version": v}).status_code
        == 403
    )
    assert (
        c.post(f"/adaptation/{i}/agreement", json={"action": "send", "version": v}).status_code
        == 200
    )
    as_role("intern")
    assert (
        c.post(
            f"/adaptation/{i}/agreement",
            json={"action": "comment", "comment": "Нужен доступ", "version": v},
        ).status_code
        == 200
    )
    assert (
        c.post(f"/adaptation/{i}/agreement", json={"action": "agree", "version": v}).json()["plan"][
            "status"
        ]
        == "active"
    )
    assert (
        c.post(f"/adaptation/{i}/agreement", json={"action": "agree", "version": v}).status_code
        == 200
    )
    as_role("manager")
    assert (
        c.post(
            f"/adaptation/{i}/goals",
            json={
                "title": "Новая цель",
                "success_criteria": "Критерии",
                "target_date": d["plan"]["target_date"],
                "version": v,
            },
        ).status_code
        == 409
    )
    r = c.post(f"/adaptation/{i}/agreement", json={"action": "revise", "version": v})
    assert r.status_code == 200
    assert r.json()["plan"]["version"] == v + 1 and r.json()["plan"]["status"] == "draft"
    as_role("intern")
    assert (
        c.post(f"/adaptation/{i}/agreement", json={"action": "agree", "version": v}).status_code
        == 409
    )
    db_session.expire_all()
    assert db_session.scalar(select(AdaptationPlan)).version == v + 1
    assert any(
        h.snapshot["plan"]["status"] == "active"
        for h in db_session.scalars(select(PlanAgreement)).all()
    )


def test_task_review_return_and_progress(scenario, db_session):
    c, p, as_role = scenario
    i, v, d = create(c, p)
    own, review = d["tasks"]
    as_role("intern")
    assert (
        c.patch(f"/users/me/onboarding/{review['id']}", json={"status": "done"}).status_code == 409
    )
    assert (
        c.post(
            f"/adaptation/tasks/{review['id']}/verification", json={"action": "submit"}
        ).status_code
        == 422
    )
    assert (
        c.post(
            f"/adaptation/tasks/{own['id']}/verification",
            json={"action": "submit", "evidence": "Прочитал инструкцию"},
        ).json()["completed"]
        == 1
    )
    assert (
        c.post(
            f"/adaptation/tasks/{review['id']}/verification",
            json={"action": "submit", "evidence": "MR с тестами"},
        ).json()["tasks"][1]["status"]
        == "submitted"
    )
    assert (
        c.patch(f"/users/me/onboarding/{review['id']}", json={"status": "todo"}).status_code == 409
    )
    assert (
        c.post(
            f"/adaptation/tasks/{review['id']}/verification", json={"action": "approve"}
        ).status_code
        == 403
    )
    as_role("mentor")
    assert (
        c.post(
            f"/adaptation/tasks/{review['id']}/verification", json={"action": "reject"}
        ).status_code
        == 422
    )
    assert (
        c.post(
            f"/adaptation/tasks/{review['id']}/verification",
            json={"action": "reject", "comment": "Добавьте тесты"},
        ).json()["tasks"][1]["status"]
        == "changes_requested"
    )
    as_role("intern")
    c.post(
        f"/adaptation/tasks/{review['id']}/verification",
        json={"action": "submit", "evidence": "MR v2 с тестами"},
    )
    as_role("mentor")
    r = c.post(
        f"/adaptation/tasks/{review['id']}/verification",
        json={"action": "approve", "comment": "Проверено"},
    )
    assert r.json()["percent"] == 100
    assert (
        c.post(
            f"/adaptation/tasks/{review['id']}/verification", json={"action": "approve"}
        ).status_code
        == 409
    )
    db_session.expire_all()
    assert db_session.get(OnboardingTask, review["id"]).completed_at is not None
    assert len(db_session.scalars(select(TaskVerification)).all()) == 5


def test_permissions_tools_and_validation(scenario, db_session):
    c, p, as_role = scenario
    i, v, d = create(c, p)
    for role in ["outsider", "stranger"]:
        as_role(role)
        assert c.get(f"/adaptation/{i}").status_code == 404
    as_role("mentor")
    assert c.get("/adaptation/interns").json()[0]["id"] == i
    assert (
        c.post(f"/adaptation/{i}/agreement", json={"action": "revise", "version": v}).status_code
        == 409
    )
    as_role("manager")
    assert c.get("/adaptation/interns").status_code == 200
    assert (
        c.post(f"/adaptation/{i}/agreement", json={"action": "comment", "version": v}).status_code
        == 422
    )
    assert (
        c.post(f"/adaptation/{i}/agreement", json={"action": "send", "version": 999}).status_code
        == 409
    )
    assert (
        c.post(
            f"/adaptation/{i}/objectives",
            json={
                "title": "Надёжность сервиса",
                "key_results": ["Зелёный CI"],
                "period_start": str(date.today()),
                "period_end": str(date.today() + timedelta(days=10)),
            },
        ).status_code
        == 200
    )
    for name in [
        "get_my_adaptation_plan",
        "get_my_goals",
        "get_my_progress",
        "get_next_steps",
        "get_my_team_objectives",
    ]:
        result = tools.dispatch(db_session, p["intern"], name, "{}")
        assert "Освоить окружение" in json.dumps(result, ensure_ascii=False)
        assert "Ожидания наставника" in tools.render(result)
    as_role("intern")
    assert c.get("/adaptation/interns").status_code == 403
    assert tools.dispatch(db_session, p["mentor"], "get_next_steps", "{}").get("error")


def test_edit_goal_task_verify_criteria_and_quiz(scenario, db_session):
    from app.models import KnowledgeQuiz, QuizAttempt
    from scripts.quiz_data import seed_quizzes

    c, p, as_role = scenario
    i, v, d = create(c, p)
    goal = d["goals"][0]
    task = d["tasks"][0]
    body = {
        "title": "Уточнённая цель",
        "success_criteria": "Запуск и тесты",
        "target_date": d["plan"]["target_date"],
        "version": v,
    }
    r = c.patch(f"/adaptation/{i}/goals/{goal['id']}", json=body)
    assert r.status_code == 200, r.text
    v = r.json()["plan"]["version"]
    assert c.patch(f"/adaptation/{i}/goals/{goal['id']}", json=body).status_code == 409
    seed_quizzes(db_session)
    quiz = db_session.scalar(select(KnowledgeQuiz).where(KnowledgeQuiz.slug == "code-review"))
    r = c.patch(
        f"/adaptation/{i}/tasks/{task['id']}",
        json={
            "title": "Мини-тест ревью",
            "goal_id": goal["id"],
            "due_date": d["plan"]["target_date"],
            "verification_type": "quiz",
            "quiz_id": quiz.id,
            "version": v,
        },
    )
    assert r.status_code == 200, r.text
    v = r.json()["plan"]["version"]
    assert c.get("/quizzes").status_code == 200
    as_role("intern")
    quiz_response = c.get(f"/quizzes/tasks/{task['id']}")
    assert (
        quiz_response.status_code == 200
        and "correct" not in quiz_response.text
        and "explanation" not in quiz_response.text
    )
    assert c.patch(f"/users/me/onboarding/{task['id']}", json={"status": "done"}).status_code == 409
    assert (
        c.post(
            f"/adaptation/tasks/{task['id']}/verification",
            json={"action": "submit", "evidence": "Обойти тест"},
        ).status_code
        == 409
    )
    assert c.post(f"/quizzes/tasks/{task['id']}", json={"answers": [4]}).status_code == 422
    failed = c.post(f"/quizzes/tasks/{task['id']}", json={"answers": [1, 0, 2]})
    assert not failed.json()["passed"]
    assert all(f["explanation"] for f in failed.json()["feedback"])
    passed = c.post(f"/quizzes/tasks/{task['id']}", json={"answers": [0, 1, 0]})
    assert passed.json()["passed"]
    assert c.post(f"/quizzes/tasks/{task['id']}", json={"answers": [0, 1, 0]}).status_code == 409
    assert len(c.get(f"/quizzes/tasks/{task['id']}").json()["attempts"]) == 2
    as_role("stranger")
    assert c.get(f"/quizzes/tasks/{task['id']}").status_code == 404
    assert db_session.scalar(select(QuizAttempt).where(QuizAttempt.passed.is_(True))) is not None
    as_role("manager")
    c.post(f"/adaptation/{i}/agreement", json={"action": "send", "version": v})
    as_role("intern")
    c.post(f"/adaptation/{i}/agreement", json={"action": "agree", "version": v})
    review = d["tasks"][1]
    c.post(
        f"/adaptation/tasks/{review['id']}/verification",
        json={"action": "submit", "evidence": "MR и CI"},
    )
    as_role("manager")
    assert (
        c.post(
            f"/adaptation/{i}/goals/{goal['id']}/verify",
            json={"action": "approve", "evidence": "Все критерии проверены"},
        ).status_code
        == 409
    )
    c.post(f"/adaptation/tasks/{review['id']}/verification", json={"action": "approve"})
    r = c.post(
        f"/adaptation/{i}/goals/{goal['id']}/verify",
        json={"action": "approve", "evidence": "Проверены запуск, тесты и процесс"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["goals"][0]["status"] == "achieved"
    assert r.json()["metrics"]["goals_achieved"] == 1


def test_access_request_link_to_owned_task(scenario, db_session):
    c, p, as_role = scenario
    i, v, d = create(c, p)
    team = db_session.get(Team, p["intern"].team_id)
    team.name = access.DEMO_TEAM
    db_session.flush()
    as_role("intern")
    args = {
        "resource": "gitlab",
        "project_key": "BACKEND",
        "permission": "read",
        "justification": "Для настройки окружения",
        "task_id": d["tasks"][0]["id"],
    }
    r = c.post("/assistant/actions/prepare", json=args)
    assert r.status_code == 200, r.text
    pid = r.json()["id"]
    r = c.post(f"/assistant/actions/{pid}/confirm")
    assert r.status_code == 200, r.text
    assert r.json()["task_id"] == d["tasks"][0]["id"]
    assert r.json()["status"] == "pending"
    assert db_session.get(OnboardingTask, args["task_id"]).status == "todo"
    assert c.post(f"/assistant/actions/{pid}/confirm").json()["id"] == r.json()["id"]
    assert c.post("/assistant/actions/prepare", json=args | {"task_id": 999999}).status_code == 404
    as_role("manager")
    assert (
        c.post(
            f"/access-requests/{r.json()['id']}/approve", json={"comment": "Согласовано"}
        ).status_code
        == 200
    )
    assert db_session.get(OnboardingTask, args["task_id"]).status == "todo"


def test_mentor_question_escalation_and_authorization(scenario):
    c, p, as_role = scenario
    i = p["intern"].id
    as_role("intern")
    r = c.post(f"/adaptation/{i}/questions", json={"text": "Не получается запустить сервис"})
    assert r.status_code == 200, r.text
    q = r.json()["questions"][0]["id"]
    assert (
        len(
            c.post(
                f"/adaptation/{i}/questions", json={"text": "Не получается запустить сервис"}
            ).json()["questions"]
        )
        == 1
    )
    assert (
        c.post(f"/adaptation/{i}/questions/{q}/answer", json={"text": "Сам себе ответ"}).status_code
        == 404
    )
    as_role("stranger")
    assert (
        c.post(f"/adaptation/{i}/questions/{q}/answer", json={"text": "Чужой ответ"}).status_code
        == 404
    )
    as_role("mentor")
    r = c.post(
        f"/adaptation/{i}/questions/{q}/answer", json={"text": "Проверим конфигурацию вместе"}
    )
    assert (
        r.status_code == 200
        and r.json()["questions"][0]["answer"] == "Проверим конфигурацию вместе"
    )
    assert (
        c.post(f"/adaptation/{i}/questions/{q}/answer", json={"text": "Другой ответ"}).status_code
        == 409
    )


def test_deadlines_empty_plan_and_invalid_quiz(scenario):
    c, p, as_role = scenario
    i, v, d = create(c, p)
    assert (
        c.post(
            f"/adaptation/{i}/plan",
            json={
                "title": "План",
                "expectations": "Новые ожидания",
                "start_date": d["plan"]["start_date"],
                "target_date": d["plan"]["start_date"],
                "version": v,
            },
        ).status_code
        == 422
    )
    assert (
        c.post(
            f"/adaptation/{i}/tasks",
            json={
                "title": "Новый тест",
                "goal_id": d["goals"][0]["id"],
                "due_date": d["plan"]["target_date"],
                "verification_type": "quiz",
                "version": v,
            },
        ).status_code
        == 422
    )
    assert (
        c.post(
            f"/adaptation/{i}/tasks",
            json={
                "title": "Новый тест",
                "goal_id": d["goals"][0]["id"],
                "due_date": d["plan"]["target_date"],
                "verification_type": "quiz",
                "quiz_id": 999999,
                "version": v,
            },
        ).status_code
        == 404
    )


def test_llm_generic_key_and_current_plan_context(scenario, monkeypatch):
    from unittest.mock import AsyncMock

    from pydantic import SecretStr

    from app.core.config import settings
    from app.services import llm

    c, p, as_role = scenario
    i, v, d = create(c, p)
    c.post(f"/adaptation/{i}/agreement", json={"action": "send", "version": v})
    as_role("intern")
    c.post(f"/adaptation/{i}/agreement", json={"action": "agree", "version": v})
    monkeypatch.setattr(settings, "llm_api_key", SecretStr("mock-only-generic-key"))
    monkeypatch.setattr(settings, "deepseek_api_key", SecretStr(""))
    mock = AsyncMock(return_value=llm.LLMResult("Ожидания из персонального плана"))
    monkeypatch.setattr(llm, "complete", mock)
    r = c.post("/assistant/chat", json={"message": "Что от меня ожидает руководитель?"})
    assert r.status_code == 200, r.text
    prompt = str(mock.call_args.args[0])
    assert (
        "Самостоятельная инженерная работа" in prompt and "Запуск сервиса и зелёные тесты" in prompt
    )
    assert "mock-only-generic-key" not in prompt and "password_hash" not in prompt
    overview = c.get(f"/adaptation/{i}").json()
    assert overview["metrics"]["assistant_answers"] == 1
    assert overview["metrics"]["sources_share"] == 0


def test_request_task_completes_only_on_confirmed_submission(scenario, db_session):
    c, p, as_role = scenario
    i, v, d = create(c, p)
    team = db_session.get(Team, p["intern"].team_id)
    team.name = access.DEMO_TEAM
    db_session.flush()
    r = c.post(
        f"/adaptation/{i}/tasks",
        json={
            "title": "Отправить заявку в Jira",
            "goal_id": d["goals"][0]["id"],
            "due_date": d["plan"]["target_date"],
            "verification_type": "request",
            "request_resource": "jira",
            "version": v,
        },
    )
    assert r.status_code == 200, r.text
    task = next(t for t in r.json()["tasks"] if t["verification_type"] == "request")
    as_role("intern")
    assert (
        c.patch(f"/users/me/onboarding/{task['id']}", json={"status": "in_progress"}).status_code
        == 200
    )
    assert c.patch(f"/users/me/onboarding/{task['id']}", json={"status": "done"}).status_code == 409
    assert (
        c.post(
            f"/adaptation/tasks/{task['id']}/verification",
            json={"action": "submit", "evidence": "Пытаюсь закрыть вручную"},
        ).status_code
        == 409
    )
    args = {
        "resource": "jira",
        "project_key": "BACKEND",
        "permission": "read",
        "justification": "Для выполнения задачи",
        "task_id": task["id"],
    }
    assert (
        c.post("/assistant/actions/prepare", json=args | {"resource": "gitlab"}).status_code == 422
    )
    draft = c.post("/assistant/actions/prepare", json=args)
    assert draft.status_code == 200, draft.text
    assert db_session.get(OnboardingTask, task["id"]).status == "in_progress"
    pid = draft.json()["id"]
    r = c.post(f"/assistant/actions/{pid}/confirm")
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "pending" and r.json()["approver_id"] == p["mentor"].id
    db_session.expire_all()
    saved = db_session.get(OnboardingTask, task["id"])
    assert saved.status == "done" and saved.completed_at and str(r.json()["id"]) in saved.evidence
    assert "Выдача доступа не подтверждена" in saved.evidence
    assert c.post(f"/assistant/actions/{pid}/confirm").json()["id"] == r.json()["id"]
    history = db_session.scalars(
        select(TaskVerification).where(
            TaskVerification.task_id == task["id"], TaskVerification.action == "request_created"
        )
    ).all()
    assert len(history) == 1
