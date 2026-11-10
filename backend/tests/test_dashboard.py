from datetime import UTC, datetime, timedelta

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.db.session import get_db
from app.main import app
from app.models import OnboardingTask, Team, User
from app.services.auth import COOKIE, passwords

HEADERS = {"Origin": "http://localhost:5173", "X-Requested-With": "AI-buddy"}


@pytest.fixture
def accounts(db_session):
    team = Team(name="Dashboard test")
    other = Team(name="Other dashboard test")
    db_session.add_all([team, other])
    db_session.flush()
    users = {}
    hashed = passwords.hash("Synthetic-password-123")
    for role in ["intern", "mentor", "manager"]:
        user = User(
            full_name=f"Test {role}",
            email=f"{role}@dashboard.example",
            role=role,
            team_id=team.id,
            password_hash=hashed,
        )
        db_session.add(user)
        users[role] = user
    foreign = User(
        full_name="Other intern",
        email="other@dashboard.example",
        role="intern",
        team_id=other.id,
        password_hash=hashed,
    )
    db_session.add(foreign)
    db_session.flush()
    users["intern"].mentor_id = users["mentor"].id
    own_task = OnboardingTask(user_id=users["intern"].id, title="Own task")
    foreign_task = OnboardingTask(user_id=foreign.id, title="Foreign task")
    db_session.add_all([own_task, foreign_task])
    db_session.flush()
    return users, own_task, foreign_task, other


@pytest.fixture
def client(db_session, monkeypatch):
    monkeypatch.setattr(
        settings, "jwt_secret", "test-only-signing-secret-with-at-least-32-characters"
    )
    app.dependency_overrides[get_db] = lambda: db_session
    with TestClient(app, headers=HEADERS) as client:
        yield client
    app.dependency_overrides.clear()


def login(client, role="intern", password="Synthetic-password-123"):
    return client.post(
        "/auth/login", json={"email": f"{role}@dashboard.example", "password": password}
    )


def test_login_me_logout(client, accounts):
    response = login(client)
    assert response.status_code == 200
    assert "HttpOnly" in response.headers["set-cookie"]
    assert "SameSite=lax" in response.headers["set-cookie"]
    assert "password_hash" not in response.text
    profile = client.get("/auth/me").json()
    assert profile["role"] == "intern"
    assert profile["mentor"]["full_name"] == "Test mentor"
    assert client.post("/auth/logout").status_code == 204
    assert client.get("/auth/me").status_code == 401


@pytest.mark.parametrize("role,password", [("intern", "wrong"), ("missing", "wrong")])
def test_bad_credentials(client, accounts, role, password):
    assert login(client, role, password).status_code == 401


def test_inactive_and_legacy(client, accounts, db_session):
    user = accounts[0]["intern"]
    user.is_active = False
    db_session.flush()
    assert login(client).status_code == 403
    user.is_active = True
    user.password_hash = None
    db_session.flush()
    assert login(client).status_code == 401


@pytest.mark.parametrize("path", ["/auth/me", "/teams", "/teams/1", "/users/me/onboarding"])
def test_private(client, path):
    assert client.get(path).status_code == 401


def test_expired_and_malformed(client, accounts):
    client.cookies.set(
        COOKIE,
        jwt.encode(
            {
                "sub": str(accounts[0]["intern"].id),
                "iat": datetime.now(UTC) - timedelta(hours=2),
                "exp": datetime.now(UTC) - timedelta(hours=1),
            },
            settings.jwt_secret,
            algorithm="HS256",
        ),
    )
    assert client.get("/auth/me").status_code == 401
    client.cookies.set(COOKIE, "broken")
    assert client.get("/auth/me").status_code == 401


def test_session_disabled_user(client, accounts, db_session):
    login(client)
    accounts[0]["intern"].is_active = False
    db_session.flush()
    assert client.get("/auth/me").status_code == 401


def test_tasks_and_progress(client, accounts, db_session):
    login(client)
    task = accounts[1]
    assert client.get("/users/me/onboarding").json()["percent"] == 0
    for status, percent in [("in_progress", 0), ("done", 100), ("done", 100), ("todo", 0)]:
        response = client.patch(f"/users/me/onboarding/{task.id}", json={"status": status})
        assert response.status_code == 200
        assert bool(response.json()["completed_at"]) == (status == "done")
        result = client.get("/users/me/onboarding").json()
        assert result["percent"] == percent
        assert result["total"] == 1
    db_session.expire_all()
    assert db_session.get(OnboardingTask, task.id).status == "todo"


def test_foreign_and_invalid_task(client, accounts):
    login(client)
    assert (
        client.patch(f"/users/me/onboarding/{accounts[2].id}", json={"status": "done"}).status_code
        == 404
    )
    assert client.patch("/users/me/onboarding/9999999", json={"status": "done"}).status_code == 404
    assert (
        client.patch(
            f"/users/me/onboarding/{accounts[1].id}", json={"status": "invalid"}
        ).status_code
        == 422
    )
    assert (
        client.patch(
            f"/users/me/onboarding/{accounts[1].id}", json={"status": "done", "user_id": 1}
        ).status_code
        == 422
    )


@pytest.mark.parametrize("role", ["mentor", "manager"])
def test_role_boundaries(client, accounts, role):
    assert login(client, role).json()["role"] == role
    assert client.get("/users/me/onboarding").status_code == 403
    assert (
        client.patch(f"/users/me/onboarding/{accounts[1].id}", json={"status": "done"}).status_code
        == 403
    )
    assert client.get(f"/teams/{accounts[3].id}").status_code == 404
    teams = client.get("/teams").json()
    assert len(teams) == 1 and teams[0]["id"] == accounts[0][role].team_id


def test_team_and_mentor_scope(client, accounts, db_session):
    login(client)
    user = accounts[0]["intern"]
    assert client.get(f"/teams/{user.team_id}").status_code == 200
    assert client.get("/teams/999999").status_code == 404
    accounts[0]["mentor"].team_id = accounts[3].id
    db_session.flush()
    assert client.get("/auth/me").json()["mentor"] is None
    user.mentor_id = None
    db_session.flush()
    assert client.get("/auth/me").json()["mentor"] is None


@pytest.mark.parametrize(
    "headers",
    [
        {"Origin": "https://evil.example", "X-Requested-With": "AI-buddy"},
        {"Origin": "http://localhost:5173"},
        {"X-Requested-With": "AI-buddy"},
        {},
    ],
)
def test_csrf(accounts, headers):
    with TestClient(app) as client:
        assert (
            client.post(
                "/auth/login", json={"email": "test", "password": "test"}, headers=headers
            ).status_code
            == 403
        )


@pytest.mark.parametrize(
    "status,completed", [("invalid", None), ("done", None), ("todo", datetime.now(UTC))]
)
def test_task_constraints(db_session, accounts, status, completed):
    db_session.add(
        OnboardingTask(
            user_id=accounts[0]["intern"].id, title="Invalid", status=status, completed_at=completed
        )
    )
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_task_fk(db_session):
    db_session.add(OnboardingTask(user_id=-1, title="Missing owner"))
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_password_and_defaults(accounts):
    user = accounts[0]["intern"]
    assert user.password_hash.startswith("$argon2")
    assert user.is_active is True
    assert user.created_at.tzinfo is not None
    assert accounts[1].user == user


def test_empty_onboarding(client, accounts, db_session):
    db_session.delete(accounts[1])
    db_session.flush()
    login(client)
    result = client.get("/users/me/onboarding").json()
    assert result == {"tasks": [], "completed": 0, "total": 0, "percent": 0}


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_missing_signing_secret(client, accounts, monkeypatch):
    monkeypatch.setattr(settings, "jwt_secret", "")
    assert login(client).status_code == 503


def test_invalid_hash_and_role(client, accounts, db_session):
    user = accounts[0]["intern"]
    user.password_hash = "invalid-hash"
    db_session.flush()
    assert login(client).status_code == 401
    user.password_hash = passwords.hash("Synthetic-password-123")
    db_session.flush()
    assert login(client).status_code == 200
    user.role = "unsupported"
    db_session.flush()
    assert client.get("/auth/me").status_code == 403
    assert login(client).status_code == 403
