from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import KnowledgeChunk, KnowledgeDocument
from app.schemas.assistant import Source
from app.services.embeddings import provider
from app.services.knowledge import access_filter


def search(db: Session, team_id: int, question: str, encoder=provider):
    if settings.rag_min_score is None:
        raise HTTPException(503, "База знаний требует индексации и калибровки поиска.")
    try:
        query = encoder.decode(encoder.tokens(question)[:470])
        vector = encoder.encode([query], "query")[0]
    except Exception:
        raise HTTPException(
            503, "Локальная embedding-модель недоступна. Обратитесь к администратору."
        ) from None
    distance = KnowledgeChunk.embedding.cosine_distance(vector)
    statement = (
        select(KnowledgeChunk, KnowledgeDocument, distance.label("distance"))
        .join(KnowledgeDocument, KnowledgeChunk.document_id == KnowledgeDocument.id)
        .where(
            access_filter(team_id),
            KnowledgeDocument.embedding_model == settings.embedding_model,
            distance <= 1 - settings.rag_min_score,
        )
        .order_by(distance, KnowledgeChunk.id)
        .limit(settings.rag_top_k)
    )
    rows = db.execute(statement).all()
    sources, contexts = [], []
    remaining = settings.rag_context_chars
    for chunk, document, score in rows:
        content = chunk.content[:remaining]
        if not content:
            break
        remaining -= len(content)
        sources.append(
            Source(
                document_id=document.id,
                chunk_id=chunk.id,
                title=document.title,
                source=document.source,
                score=round(1 - float(score), 4),
            )
        )
        contexts.append(
            {"source_number": len(sources), "title": document.title, "content": content}
        )
    return sources, contexts
