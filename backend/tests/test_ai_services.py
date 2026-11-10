import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import httpx
import numpy as np
import pytest
from fastapi import HTTPException
from openai import APIConnectionError, APIStatusError, APITimeoutError, RateLimitError
from pydantic import SecretStr, ValidationError
from sqlalchemy.dialects import postgresql

from app.core.config import settings
from app.schemas.assistant import ChatRequest
from app.services import assistant, embeddings, llm, rag
from app.services.knowledge import chunk_markdown


def test_validation_and_intents():
    for message in ["", "   ", "x" * (settings.chat_max_message_chars + 1)]:
        with pytest.raises(ValidationError):
            ChatRequest(message=message)
    with pytest.raises(ValidationError):
        ChatRequest(message="hello", user_id=4)
    assert ChatRequest(message=" hello ").message == "hello"
    assert assistant.intent("Какие задачи у меня остались?") == "personal"
    assert assistant.intent("Привет! Чем ты можешь помочь?") == "general"
    assert assistant.intent("Как получить доступ к GitLab?") == "corporate"
    assert assistant.intent("Что такое Python?") == "general"


def test_llm_missing_key(monkeypatch):
    monkeypatch.setattr(settings, "deepseek_api_key", SecretStr(""))
    with pytest.raises(HTTPException) as e:
        llm.client()
    assert e.value.status_code == 503


def mock_llm(monkeypatch, result=None, error=None):
    create = AsyncMock(return_value=result, side_effect=error)
    client = MagicMock()
    client.chat.completions.create = create
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    monkeypatch.setattr(llm, "client", lambda: client)
    return create


def test_llm_request(monkeypatch):
    monkeypatch.setattr(settings, "deepseek_model", "configured-test-model")
    result = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="Ответ"))],
        usage=SimpleNamespace(prompt_tokens=20, completion_tokens=10),
    )
    create = mock_llm(monkeypatch, result)
    answer = asyncio.run(llm.complete([{"role": "user", "content": "Привет"}]))
    assert answer == llm.LLMResult("Ответ", 20, 10)
    assert create.call_args.kwargs["model"] == "configured-test-model"
    assert create.call_args.kwargs["max_tokens"] == settings.llm_max_tokens
    assert create.call_args.kwargs["extra_body"]["thinking"]["type"] == "disabled"


@pytest.mark.parametrize(
    "kind,status",
    [("timeout", 504), ("rate", 429), ("connection", 502), ("api", 502), ("empty", 502)],
)
def test_llm_errors(monkeypatch, kind, status):
    req = httpx.Request("POST", "https://example.invalid")
    response = httpx.Response(429, request=req)
    errors = {
        "timeout": APITimeoutError(req),
        "rate": RateLimitError("redacted", response=response, body=None),
        "connection": APIConnectionError(request=req),
        "api": APIStatusError("redacted", response=response, body=None),
    }
    mock_llm(monkeypatch, SimpleNamespace(choices=[]), errors.get(kind))
    with pytest.raises(HTTPException) as e:
        asyncio.run(llm.complete([]))
    assert e.value.status_code == status
    assert "redacted" not in e.value.detail


class FakeEncoder:
    def __init__(self):
        self.calls = []

    def tokens(self, text):
        return list(text.encode())

    def decode(self, tokens):
        return bytes(tokens).decode(errors="ignore")

    def encode(self, texts, kind):
        self.calls.append((texts, kind))
        return [[1.0] + [0.0] * 383 for _ in texts]


def test_chunking():
    encoder = FakeEncoder()
    chunks = chunk_markdown(
        "# Header\n\n"
        + ("Sentence one. Sentence two. " * 200)
        + "\n\n## Second\n\nAnother paragraph.",
        encoder,
    )
    assert len(chunks) > 3
    assert all(len(encoder.tokens(chunk)) <= 320 for chunk in chunks)
    assert all(chunk for chunk in chunks)
    assert any("Second" in chunk for chunk in chunks)
    assert chunk_markdown("   ", encoder) == []


def test_embedding_prefixes_and_dimensions(monkeypatch):
    fake = MagicMock()
    fake.tokenizer.encode = lambda text, **kwargs: list(range(len(text)))
    fake.encode.return_value = np.ones((1, 384)) / np.sqrt(384)
    monkeypatch.setattr(embeddings, "load_model", lambda *_: fake)
    provider = embeddings.Embeddings()
    assert len(provider.encode([" test "], "query")[0]) == 384
    assert fake.encode.call_args.args[0] == ["query: test"]
    provider.encode(["document"], "passage")
    assert fake.encode.call_args.args[0] == ["passage: document"]
    with pytest.raises(ValueError):
        provider.encode(["x"], "invalid")
    with pytest.raises(ValueError):
        provider.encode(["x" * 600], "query")
    fake.encode.return_value = np.zeros((1, 3))
    with pytest.raises(ValueError):
        provider.encode(["x"], "query")


def test_model_cached(monkeypatch):
    import sys

    factory = MagicMock(return_value=object())
    monkeypatch.setitem(
        sys.modules, "sentence_transformers", SimpleNamespace(SentenceTransformer=factory)
    )
    embeddings.load_model.cache_clear()
    assert embeddings.load_model("synthetic-model", True) is embeddings.load_model(
        "synthetic-model", True
    )
    assert factory.call_count == 1
    embeddings.load_model.cache_clear()


def test_rag_sql_acl_and_sources(monkeypatch):
    monkeypatch.setattr(settings, "rag_min_score", 0.8)
    chunk = SimpleNamespace(id=3, content="Instruction")
    doc = SimpleNamespace(id=2, title="Document", source="demo/doc.md")
    db = MagicMock()
    db.execute.return_value.all.return_value = [(chunk, doc, 0.1)]
    sources, context = rag.search(db, 42, "question", FakeEncoder())
    assert sources[0].score == 0.9 and context[0]["content"] == "Instruction"
    sql = str(db.execute.call_args.args[0].compile(dialect=postgresql.dialect()))
    assert "knowledge_documents.team_id" in sql and "is_public IS true" in sql
    assert "<=>" in sql and "LIMIT" in sql and "WHERE" in sql
    db.execute.return_value.all.return_value = []
    assert rag.search(db, 42, "missing", FakeEncoder()) == ([], [])


def test_rag_unavailable(monkeypatch):
    monkeypatch.setattr(settings, "rag_min_score", None)
    with pytest.raises(HTTPException) as e:
        rag.search(MagicMock(), 1, "x", FakeEncoder())
    assert e.value.status_code == 503
    monkeypatch.setattr(settings, "rag_min_score", 0.8)
    encoder = FakeEncoder()
    encoder.encode = MagicMock(side_effect=RuntimeError())
    with pytest.raises(HTTPException) as e:
        rag.search(MagicMock(), 1, "x", encoder)
    assert e.value.status_code == 503
