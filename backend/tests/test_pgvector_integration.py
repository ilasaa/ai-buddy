"""Run against ai_buddy_test after installing pgvector and upgrading to head."""

import pytest
from sqlalchemy import inspect
from test_ai_services import FakeEncoder

from app.core.config import settings
from app.models import KnowledgeChunk, KnowledgeDocument, Team
from app.services.rag import search


@pytest.mark.pgvector
def test_postgres_cosine_acl_and_document(db_session, monkeypatch):
    if not inspect(db_session.bind).has_table("knowledge_chunks"):
        pytest.skip("Нужны pgvector и миграция e4a81c093bd2 в ai_buddy_test")
    monkeypatch.setattr(settings, "rag_min_score", 0.8)
    own, foreign = Team(name="RAG test own"), Team(name="RAG test foreign")
    db_session.add_all([own, foreign])
    db_session.flush()
    docs = [
        KnowledgeDocument(
            title="Allowed",
            source="test/allowed",
            content_hash="a" * 64,
            embedding_model=settings.embedding_model,
            team_id=own.id,
            is_public=False,
        ),
        KnowledgeDocument(
            title="Forbidden",
            source="test/forbidden",
            content_hash="b" * 64,
            embedding_model=settings.embedding_model,
            team_id=foreign.id,
            is_public=False,
        ),
        KnowledgeDocument(
            title="Unrelated",
            source="test/unrelated",
            content_hash="c" * 64,
            embedding_model=settings.embedding_model,
            is_public=True,
        ),
    ]
    db_session.add_all(docs)
    db_session.flush()
    vectors = [[1.0] + [0.0] * 383, [1.0] + [0.0] * 383, [0.0, 1.0] + [0.0] * 382]
    for doc, vector in zip(docs, vectors, strict=True):
        db_session.add(
            KnowledgeChunk(document_id=doc.id, chunk_index=0, content=doc.title, embedding=vector)
        )
    db_session.flush()
    sources, contexts = search(db_session, own.id, "query", FakeEncoder())
    assert [source.title for source in sources] == ["Allowed"]
    assert contexts[0]["content"] == "Allowed"
