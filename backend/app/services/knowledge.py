import hashlib
import re
from datetime import UTC, datetime
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import delete, or_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import KnowledgeChunk, KnowledgeDocument, Team
from app.services.embeddings import provider


def access_filter(team_id: int):
    return or_(KnowledgeDocument.is_public.is_(True), KnowledgeDocument.team_id == team_id)


def get_document(db: Session, team_id: int, document_id: int):
    document = db.scalar(
        select(KnowledgeDocument).where(KnowledgeDocument.id == document_id, access_filter(team_id))
    )
    if not document:
        raise HTTPException(404, "Документ не найден")
    chunks = db.scalars(
        select(KnowledgeChunk)
        .where(KnowledgeChunk.document_id == document.id)
        .order_by(KnowledgeChunk.chunk_index)
    ).all()
    return {
        "id": document.id,
        "title": document.title,
        "source": document.source,
        "is_public": document.is_public,
        "metadata": document.document_metadata,
        "content": "\n\n".join(c.content for c in chunks),
    }


def chunk_markdown(text: str, encoder=provider, limit=320, overlap=40) -> list[str]:
    """Token-aware paragraphs/sentences; headings included in every related chunk."""
    title = ""
    section = ""
    buffer = ""
    result = []
    previous_section = None
    for block in re.split(r"\n\s*\n", text.strip()):
        if block.startswith("#"):
            heading, _, block = block.partition("\n")
            heading = encoder.decode(encoder.tokens(heading)[:40])
            if heading.startswith("# "):
                title = heading
            else:
                section = heading
        for sentence in re.split(r"(?<=[.!?])\s+", block):
            if not sentence.strip():
                continue
            parts = encoder.tokens(sentence)
            while parts:
                part = encoder.decode(parts[: limit - 100])
                parts = parts[limit - 100 :]
                prefix = "\n".join(filter(None, (title, section)))
                addition = (
                    section + "\n" if section and section != previous_section else ""
                ) + part
                candidate = (
                    (buffer + "\n" + addition).strip() if buffer else (prefix + "\n" + part).strip()
                )
                if len(encoder.tokens(candidate)) > limit:
                    if buffer:
                        result.append(buffer.strip())
                    tail = encoder.decode(encoder.tokens(buffer)[-overlap:]) if buffer else ""
                    buffer = (prefix + "\n" + tail + "\n" + part).strip()
                    if len(encoder.tokens(buffer)) > limit:
                        buffer = (prefix + "\n" + part).strip()
                else:
                    buffer = candidate
                previous_section = section
    if buffer:
        result.append(buffer.strip())
    return result


def index_file(db: Session, path: Path, root: Path, encoder=provider):
    """Caller commits per file; exceptions roll back this entire document."""
    raw = path.read_text(encoding="utf-8")
    lines = raw.splitlines()
    if len(lines) < 4 or lines[0] != "---" or "---" not in lines[1:]:
        raise ValueError("Необходимы метаданные scope/title в Markdown")
    boundary = lines.index("---", 1)
    meta = dict(line.split(":", 1) for line in lines[1:boundary])
    meta = {k.strip(): v.strip() for k, v in meta.items()}
    scope = meta.get("scope")
    team_id = None
    if scope != "public":
        if not scope or not scope.startswith("team:"):
            raise ValueError("Неизвестная область доступа")
        team_id = db.scalar(select(Team.id).where(Team.name == scope[5:]))
        if not team_id:
            raise ValueError("Команда документа не найдена; сначала выполните seed")
    source = path.relative_to(root).as_posix()
    # Include encoder identity and chunking version so changing either reindexes.
    digest = hashlib.sha256((raw + settings.embedding_model + ":chunks-v2").encode()).hexdigest()
    document = db.scalar(
        select(KnowledgeDocument).where(KnowledgeDocument.source == source).with_for_update()
    )
    if document and document.content_hash == digest and document.team_id == team_id:
        return "unchanged", 0
    chunks = chunk_markdown("\n".join(lines[boundary + 1 :]), encoder)
    if not chunks:
        raise ValueError("Пустой документ")
    vectors = encoder.encode(chunks, "passage")
    if len(vectors) != len(chunks):
        raise ValueError("Не все фрагменты получили embedding")
    if not document:
        document = KnowledgeDocument(source=source)
        db.add(document)
    document.document_metadata = {
        key: meta[key] for key in ("reviewed_on", "scope", "conflict_group", "rule") if key in meta
    }
    document.title = meta["title"]
    document.content_hash = digest
    document.embedding_model = settings.embedding_model
    document.team_id = team_id
    document.is_public = scope == "public"
    document.updated_at = datetime.now(UTC)
    db.flush()
    db.execute(delete(KnowledgeChunk).where(KnowledgeChunk.document_id == document.id))
    db.add_all(
        [
            KnowledgeChunk(
                document_id=document.id, chunk_index=i, content=content, embedding=vector
            )
            for i, (content, vector) in enumerate(zip(chunks, vectors, strict=True))
        ]
    )
    db.flush()
    return "indexed", len(chunks)
