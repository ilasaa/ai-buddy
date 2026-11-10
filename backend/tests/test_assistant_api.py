from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import func, select

from app.core.config import settings
from app.db.session import get_db
from app.main import app
from app.models import ChatMessage, ChatUsage, Team, User
from app.schemas.assistant import Source
from app.services import llm, rag
from app.services.auth import current_user

HEADERS = {"Origin": "http://localhost:5173", "X-Requested-With": "AI-buddy"}


@pytest.fixture
def chat_client(db_session, monkeypatch):
    team = Team(name="Chat team")
    db_session.add(team)
    db_session.flush()
    user = User(
        full_name="Synthetic Intern", email="chat@example.test", role="intern", team_id=team.id
    )
    other = User(full_name="Other", email="other-chat@example.test", role="intern", team_id=team.id)
    db_session.add_all([user, other])
    db_session.flush()
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[current_user] = lambda: user
    monkeypatch.setattr(settings, "deepseek_api_key", SecretStr("synthetic-key-not-sent"))
    mock = AsyncMock(return_value=llm.LLMResult("Синтетический тестовый ответ", 20, 10))
    monkeypatch.setattr(llm, "complete", mock)
    with TestClient(app, headers=HEADERS) as client:
        yield client, user, other, mock
    app.dependency_overrides.clear()


def test_chat_personal_history(chat_client, db_session):
    client, user, other, mock = chat_client
    response = client.post("/assistant/chat", json={"message": "Какие задачи у меня остались?"})
    assert response.status_code == 200, response.text
    result = response.json()
    cid = result["conversation_id"]
    assert result["rag_used"] is False
    assert (
        client.get(f"/assistant/conversations/{cid}").json()[1]["content"]
        == "Синтетический тестовый ответ"
    )
    prompt = str(mock.call_args.args[0])
    assert "Synthetic Intern" in prompt and "Chat team" in prompt and "progress" in prompt
    assert "password_hash" not in prompt and "email" not in prompt
    assert client.get("/assistant/conversations").json()[0]["id"] == cid
    assert (
        client.post(
            "/assistant/chat", json={"message": "Спасибо", "conversation_id": cid}
        ).status_code
        == 200
    )
    assert len(client.get(f"/assistant/conversations/{cid}").json()) == 4
    app.dependency_overrides[current_user] = lambda: other
    assert client.get(f"/assistant/conversations/{cid}").status_code == 404
    assert (
        client.post(
            "/assistant/chat", json={"message": "Привет", "conversation_id": cid}
        ).status_code
        == 404
    )
    assert client.get("/assistant/conversations").json() == []


def test_new_conversation(chat_client):
    client, *_ = chat_client
    result = client.post("/assistant/conversations")
    assert result.status_code == 201
    assert client.get("/assistant/conversations/" + str(result.json()["id"])).json() == []


def test_chat_rag(chat_client, monkeypatch):
    client, user, other, mock = chat_client
    source = Source(
        document_id=1, chunk_id=2, title="Demo instruction", source="demo/gitlab.md", score=0.9
    )

    def retrieval(*_):
        return [source], [{"content": "Synthetic instruction", "source_number": 1}]

    monkeypatch.setattr(rag, "search", retrieval)
    response = client.post("/assistant/chat", json={"message": "Как получить доступ к GitLab?"})
    assert response.status_code == 200, response.text
    assert response.json()["rag_used"] is True
    assert response.json()["message"]["sources"][0]["title"] == "Demo instruction"
    assert "Synthetic instruction" in str(mock.call_args.args)


def test_chat_limits_and_errors(chat_client, db_session, monkeypatch):
    client, user, other, mock = chat_client
    monkeypatch.setattr(settings, "chat_daily_limit", 1)
    assert client.post("/assistant/chat", json={"message": "Привет"}).status_code == 200
    assert client.post("/assistant/chat", json={"message": "Привет"}).status_code == 429
    assert client.post("/assistant/chat", json={"message": "   "}).status_code == 422
    assert (
        client.post("/assistant/chat", json={"message": "Hi", "user_id": other.id}).status_code
        == 422
    )
    monkeypatch.setattr(settings, "deepseek_api_key", SecretStr(""))
    assert client.post("/assistant/chat", json={"message": "Привет"}).status_code == 503


def test_failed_answer_not_saved(chat_client, db_session):
    from fastapi import HTTPException

    client, user, other, mock = chat_client
    mock.side_effect = HTTPException(504, "Тайм-аут")
    assert client.post("/assistant/chat", json={"message": "Привет"}).status_code == 504
    assert db_session.scalar(select(func.count()).select_from(ChatMessage)) == 0
    assert (
        db_session.scalar(
            select(func.count()).select_from(ChatUsage).where(ChatUsage.user_id == user.id)
        )
        == 1
    )


def test_anonymous_chat():
    with TestClient(app, headers=HEADERS) as client:
        assert client.post("/assistant/chat", json={"message": "Привет"}).status_code == 401
        assert client.get("/assistant/conversations").status_code == 401
        assert client.get("/knowledge").status_code == 401
