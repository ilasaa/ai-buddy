from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import KnowledgeDocument, User
from app.schemas.assistant import DocumentResponse
from app.services.auth import current_user
from app.services.knowledge import access_filter, get_document

router = APIRouter(prefix="/knowledge", tags=["Knowledge"])


@router.get("", response_model=list[DocumentResponse])
def list_documents(user: User = Depends(current_user), db: Session = Depends(get_db)):
    documents = db.scalars(
        select(KnowledgeDocument)
        .where(access_filter(user.team_id))
        .order_by(KnowledgeDocument.title)
    ).all()
    return [
        DocumentResponse(id=d.id, title=d.title, source=d.source, is_public=d.is_public, content="")
        for d in documents
    ]


@router.get("/{document_id}", response_model=DocumentResponse)
def read_document(
    document_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    return get_document(db, user.team_id, document_id)
