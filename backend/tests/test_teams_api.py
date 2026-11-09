from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.db.session import get_db
from app.models import Team


def test_get_teams(db_session: Session):
    team = Team(
        name="Backend Test Team",
        description="Тестовая команда",
    )

    db_session.add(team)
    db_session.flush()

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as client:
            response = client.get("/teams")

        assert response.status_code == 200

        data = response.json()

        assert any(
            item["id"] == team.id
            and item["name"] == "Backend Test Team"
            for item in data
        )

    finally:
        app.dependency_overrides.pop(get_db, None)