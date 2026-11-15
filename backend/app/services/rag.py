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
    # Include all accessible variants of a known demo conflict, even outside top_k.
    groups = {
        d.document_metadata.get("conflict_group")
        for _, d, _ in rows
        if getattr(d, "document_metadata", None) and d.document_metadata.get("conflict_group")
    }
    if groups:
        variants = db.execute(
            select(KnowledgeChunk, KnowledgeDocument, distance.label("distance"))
            .join(KnowledgeDocument, KnowledgeChunk.document_id == KnowledgeDocument.id)
            .where(
                access_filter(team_id),
                KnowledgeDocument.embedding_model == settings.embedding_model,
                KnowledgeDocument.document_metadata["conflict_group"].as_string().in_(groups),
            )
            .order_by(KnowledgeDocument.id, KnowledgeChunk.id)
        ).all()
        seen = {c.id for c, _, _ in variants}
        rows = variants + [(c, d, score) for c, d, score in rows if c.id not in seen]
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
                metadata=getattr(document, "document_metadata", {}) or {},
            )
        )
        contexts.append(
            {
                "source_number": len(sources),
                "title": document.title,
                "content": content,
                "metadata": getattr(document, "document_metadata", {}) or {},
                "source": document.source,
            }
        )
    return sources, contexts


def conflict(contexts):
    groups = {}
    for item in contexts:
        meta = item.get("metadata", {})
        if meta.get("conflict_group") and meta.get("rule"):
            groups.setdefault(meta["conflict_group"], set()).add(meta["rule"])
    return any(len(rules) > 1 for rules in groups.values())


def access_sources(sources, contexts, question):
    """Drop unrelated retrieval hits and renumber retained citations together."""
    lower = question.lower()
    resources = [name for name in ("jira", "confluence", "gitlab") if name in lower]
    selected_sources, selected_contexts = [], []
    for source, item in zip(sources, contexts, strict=True):
        if item.get("metadata", {}).get("conflict_group"):
            continue
        content = (
            source.title
            + " "
            + source.source
            + " "
            + " ".join(str(item.get(key, "")) for key in ("title", "content", "source"))
        ).lower()
        if resources and not any(name in content for name in resources):
            continue
        selected_sources.append(source)
        selected_contexts.append(item | {"source_number": len(selected_sources)})
    return selected_sources, selected_contexts


def conflict_evidence(sources, contexts):
    groups = {}
    for item in contexts:
        meta = item.get("metadata", {})
        if meta.get("conflict_group") and meta.get("rule"):
            groups.setdefault(meta["conflict_group"], set()).add(meta["rule"])
    conflicting = {group for group, rules in groups.items() if len(rules) > 1}
    if not conflicting:
        return sources, contexts
    kept_sources, kept_contexts, seen = [], [], set()
    for source, item in zip(sources, contexts, strict=True):
        if item.get("metadata", {}).get("conflict_group") not in conflicting:
            continue
        if source.document_id in seen:
            continue
        seen.add(source.document_id)
        kept_sources.append(source)
        kept_contexts.append(item | {"source_number": len(kept_sources)})
    return kept_sources, kept_contexts
