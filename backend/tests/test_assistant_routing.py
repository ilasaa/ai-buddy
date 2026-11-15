"""Regressions for novice-facing clarification and unrelated RAG conflicts."""

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import test_access
from pydantic import SecretStr

from app.core.config import settings
from app.schemas.assistant import Source
from app.services import assistant, llm, rag, tools

client = test_access.client
people = test_access.people


def messages(*texts):
    return [SimpleNamespace(role="user", content=text) for text in texts]


def review_hits():
    sources = [
        Source(document_id=1, chunk_id=i, title="Code Review", source="demo/review.md", score=0.9)
        for i in (1, 2)
    ]
    sources += [
        Source(
            document_id=2, chunk_id=3, title="Архив Code Review", source="demo/old.md", score=0.8
        ),
        Source(
            document_id=3, chunk_id=4, title="Адаптация", source="demo/onboarding.md", score=0.8
        ),
    ]
    fragments = [
        {
            "title": s.title,
            "content": "Правила ревью",
            "source": s.source,
            "metadata": {
                "conflict_group": "review",
                "rule": "Один" if s.document_id == 2 else "Два",
            }
            if s.document_id != 3
            else {},
        }
        for s in sources
    ]
    return sources, fragments


@pytest.mark.parametrize(
    "text,old,expected",
    [
        ("BACKEND, редактирование", ["Мне нужен доступ к Jira"], True),
        ("Редактирование", ["Мне нужен доступ к Jira", "BACKEND"], True),
        ("Как у нас проводят Code Review?", ["Создай заявку на Jira"], False),
        ("Сколько согласующих нужно?", ["Доступ к Jira"], False),
        ("Как настроить окружение?", ["Мне нужен доступ"], False),
        ("Какие задачи у меня остались?", ["Доступ к Jira"], False),
        ("Спасибо", ["Доступ к Jira"], False),
        ("Подготовь заявку Jira", ["Как проводят Code Review?"], True),
    ],
)
def test_topic_routing(text, old, expected):
    assert assistant.access_flow(text, messages(*old)) is expected


def test_access_retrieval_drops_review_and_renumbers():
    sources, fragments = review_hits()
    sources.append(
        Source(document_id=4, chunk_id=5, title="Jira", source="demo/jira.md", score=0.9)
    )
    fragments.append({"title": "Jira", "content": "Доступ к Jira", "source_number": 5})
    selected, contexts = rag.access_sources(sources, fragments, "Как получить доступ к Jira?")
    assert [s.document_id for s in selected] == [4]
    assert contexts[0]["source_number"] == 1


def test_conflict_is_relevant_and_deduplicated():
    sources, contexts = rag.conflict_evidence(*review_hits())
    assert len(sources) == len(contexts) == 2
    answer = assistant.conflict_reply(contexts, "Сколько согласующих нужно для Code Review?")
    assert answer.count("Code Review") == 3
    assert "[1]" in answer and "[2]" in answer and "[3]" not in answer
    assert "Адаптация" not in answer and "уточните у наставника" in answer
    assert assistant.conflict_reply(contexts, "Мне нужен Jira") is None


def test_clarification_is_not_replaced(monkeypatch):
    question = "К какому проекту нужен доступ и какие права нужны: просмотр или редактирование?"
    monkeypatch.setattr(llm, "complete", AsyncMock(return_value=llm.LLMResult(question)))
    result = asyncio.run(
        tools.run(None, None, [{"role": "user", "content": "Подготовь заявку на Jira"}])
    )
    assert result.content == question
    assert "LLM" not in result.content


def test_partial_tool_asks_only_missing_fields():
    result = tools.dispatch(None, None, "create_access_request", '{"resource":"jira"}')
    assert "проект" in result["error"] and "права" in result["error"]
    assert "причин" not in result["error"] and "read" not in result["error"]
    result = tools.dispatch(
        None, None, "create_access_request", '{"resource":"jira", "project_key":"BACKEND"}'
    )
    assert result["error"] == "Какие права нужны: просмотр или редактирование?"


def test_default_reason_visible_in_real_draft(client, db_session, people, monkeypatch):
    monkeypatch.setattr(settings, "llm_api_key", SecretStr("mock-only"))
    retrieval = AsyncMock(
        side_effect=AssertionError("Action must not retrieve unrelated documents")
    )
    monkeypatch.setattr(rag, "search", retrieval)
    call = {
        "name": "create_access_request",
        "arguments": json.dumps(
            {"resource": "jira", "project_key": "BACKEND", "permission": "write"}
        ),
    }
    provider = AsyncMock(return_value=llm.LLMResult("", tool_calls=[call]))
    monkeypatch.setattr(llm, "complete", provider)
    # Recover in the same conversation after an earlier confusing Code Review answer.
    cid = client.post("/assistant/conversations").json()["id"]
    from app.models import ChatMessage

    db_session.add(
        ChatMessage(conversation_id=cid, role="user", content="Как проводят Code Review?")
    )
    db_session.add(
        ChatMessage(
            conversation_id=cid,
            role="assistant",
            content="Обнаружено расхождение в инструкциях Code Review",
        )
    )
    db_session.flush()
    response = client.post(
        "/assistant/chat",
        json={"message": "Подготовь заявку Jira, BACKEND, редактирование", "conversation_id": cid},
    )
    assert response.status_code == 200, response.text
    assert "Черновик" in response.json()["message"]["content"]
    assert not response.json()["message"]["sources"]
    proposal = client.get("/assistant/actions").json()[0]
    assert proposal["parameters"]["justification"] == "Работа над задачами стажировки"
    assert client.get("/access-requests").json() == []
    assert client.post(f"/assistant/actions/{proposal['id']}/confirm").json()["status"] == "pending"
    retrieval.assert_not_called()
    assert not any("Обнаружено расхождение" in m["content"] for m in provider.call_args.args[0])


def test_access_howto_ignores_irrelevant_conflict(client, monkeypatch):
    monkeypatch.setattr(settings, "llm_api_key", SecretStr("mock-only"))
    monkeypatch.setattr(rag, "search", lambda *_: review_hits())
    question = "К какому проекту нужен доступ и какие права нужны?"
    provider = AsyncMock(return_value=llm.LLMResult(question))
    monkeypatch.setattr(llm, "complete", provider)
    response = client.post("/assistant/chat", json={"message": "Как получить доступ к Jira?"})
    assert response.status_code == 200, response.text
    assert response.json()["message"]["content"] == question
    assert not response.json()["message"]["sources"]
    provider.assert_awaited_once()
    assert "Code Review" not in provider.call_args.args[0][1]["content"]


@pytest.mark.parametrize(
    "arguments,expected",
    [
        ('{"resource":"jira","permission":"admin"}', "Повышенные права"),
        ('{"resource":"unknown"}', "К какому сервису"),
        ('{"project_key":"bad space"}', "Уточните код проекта"),
    ],
)
def test_tool_validation_uses_plain_language(arguments, expected):
    assert expected in tools.dispatch(None, None, "create_access_request", arguments)["error"]


def test_status_without_tool_does_not_reuse_model_answer(monkeypatch):
    monkeypatch.setattr(
        llm, "complete", AsyncMock(return_value=llm.LLMResult("Ваша заявка согласована"))
    )
    result = asyncio.run(
        tools.run(None, None, [{"role": "user", "content": "Какой статус моей заявки?"}])
    )
    assert "не удалось проверить" in result.content and "Мои заявки" in result.content
    assert "согласована" not in result.content
