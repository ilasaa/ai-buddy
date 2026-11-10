from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from test_ai_services import FakeEncoder

from app.models import KnowledgeChunk, KnowledgeDocument, Team, User
from app.services.knowledge import get_document, index_file


@pytest.fixture
def knowledge_db():
    # Unit tests for atomic indexing need no downloaded model or pgvector server.
    # Exact cosine SQL and PostgreSQL integration are tested separately.
    engine = create_engine("sqlite://")
    for table in [
        Team.__table__,
        User.__table__,
        KnowledgeDocument.__table__,
        KnowledgeChunk.__table__,
    ]:
        table.create(engine)
    with Session(engine) as db:
        team = Team(name="Backend · Demo")
        db.add(team)
        db.commit()
        yield db, team.id
    engine.dispose()


def write_document(root: Path, content="First sentence.", scope="public"):
    path = root / "demo.md"
    path.write_text(f"---\ntitle: Test document\nscope: {scope}\n---\n# Header\n\n{content}")
    return path


def test_index_idempotency_and_update(knowledge_db, tmp_path):
    db, team_id = knowledge_db
    path = write_document(tmp_path)
    encoder = FakeEncoder()
    assert index_file(db, path, tmp_path, encoder)[0] == "indexed"
    db.commit()
    assert index_file(db, path, tmp_path, encoder) == ("unchanged", 0)
    assert len(encoder.calls) == 1
    document = db.scalar(select(KnowledgeDocument))
    assert document.is_public
    assert get_document(db, team_id, document.id)["content"].endswith("First sentence.")
    write_document(tmp_path, "Updated content.", "team:Backend · Demo")
    assert index_file(db, path, tmp_path, encoder)[0] == "indexed"
    db.commit()
    assert len(db.scalars(select(KnowledgeDocument)).all()) == 1
    assert len(db.scalars(select(KnowledgeChunk)).all()) == 1
    assert not document.is_public
    with pytest.raises(HTTPException):
        get_document(db, team_id + 10, document.id)


def test_index_error_preserves_existing(knowledge_db, tmp_path):
    db, team_id = knowledge_db
    path = write_document(tmp_path)
    index_file(db, path, tmp_path, FakeEncoder())
    db.commit()
    original = db.scalar(select(KnowledgeDocument)).content_hash
    db.rollback()
    write_document(tmp_path, "Changed content.")
    encoder = FakeEncoder()
    encoder.encode = MagicMock(side_effect=RuntimeError("Failed"))
    with pytest.raises(RuntimeError), db.begin():
        index_file(db, path, tmp_path, encoder)
    assert db.scalar(select(KnowledgeDocument)).content_hash == original
    assert len(db.scalars(select(KnowledgeChunk)).all()) == 1


@pytest.mark.parametrize(
    "raw",
    [
        "bad",
        "---\ntitle: test\nscope: unknown\n---\ntext",
        "---\ntitle: test\nscope: team:Missing\n---\ntext",
        "---\ntitle: test\nscope: public\n---\n",
    ],
)
def test_invalid_documents(knowledge_db, tmp_path, raw):
    db, _ = knowledge_db
    path = tmp_path / "bad.md"
    path.write_text(raw)
    with pytest.raises(ValueError):
        index_file(db, path, tmp_path, FakeEncoder())


def test_document_not_found(knowledge_db):
    db, team_id = knowledge_db
    with pytest.raises(HTTPException) as e:
        get_document(db, team_id, 100)
    assert e.value.status_code == 404


def test_sources_hidden_when_access_revoked(monkeypatch):
    from datetime import UTC, datetime

    from app.services.assistant import history

    db = MagicMock()
    db.scalar.return_value = SimpleNamespace(id=1, user_id=1)
    message = SimpleNamespace(
        id=1,
        role="assistant",
        content="Restricted contents",
        created_at=datetime.now(UTC),
        sources=[
            {
                "document_id": 9,
                "chunk_id": 1,
                "title": "Restricted",
                "source": "hidden.md",
                "score": 0.9,
            }
        ],
    )
    db.scalars.return_value.all.side_effect = [[message], []]
    result = history(db, SimpleNamespace(id=1, team_id=2), 1)
    assert result[0].content == "Ответ скрыт: доступ к источникам изменился."
    assert result[0].sources == []


def test_knowledge_api_scope(knowledge_db, tmp_path):
    from app.api.knowledge import list_documents, read_document

    db, team_id = knowledge_db
    path = write_document(tmp_path, scope="team:Backend · Demo")
    index_file(db, path, tmp_path, FakeEncoder())
    db.commit()
    own = SimpleNamespace(team_id=team_id)
    foreign = SimpleNamespace(team_id=team_id + 10)
    result = list_documents(user=own, db=db)
    assert len(result) == 1
    assert list_documents(user=foreign, db=db) == []
    assert read_document(result[0].id, user=own, db=db)["title"] == "Test document"
    with pytest.raises(HTTPException) as e:
        read_document(result[0].id, user=foreign, db=db)
    assert e.value.status_code == 404


def test_intro_is_not_isolated_from_review_rules():
    from app.services.knowledge import chunk_markdown

    text = "# Code Review\n\nСинтетическая инструкция.\n\n## Подготовка\n\nСоздайте merge request после тестов.\n\n## Проверка\n\nПолучите одобрение ревьюера."
    chunks = chunk_markdown(text, FakeEncoder())
    assert all("merge request" in chunk or "ревьюера" in chunk for chunk in chunks)
    assert all("Code Review" in chunk for chunk in chunks)
