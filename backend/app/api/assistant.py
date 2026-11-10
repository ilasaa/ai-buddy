from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.db.session import get_db
from app.models import ChatConversation, User
from app.schemas.assistant import ChatRequest, ChatResponse, ConversationResponse, MessageResponse
from app.services import assistant
from app.services.auth import current_user

router = APIRouter(prefix="/assistant", tags=["Assistant"])


@router.get("/conversations", response_model=list[ConversationResponse])
def list_conversations(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return db.scalars(
        select(ChatConversation)
        .where(ChatConversation.user_id == user.id)
        .order_by(ChatConversation.updated_at.desc())
        .limit(100)
    ).all()


@router.post("/conversations", response_model=ConversationResponse, status_code=201)
def create_conversation(user: User = Depends(current_user), db: Session = Depends(get_db)):
    item = ChatConversation(user_id=user.id, title="Новый диалог")
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.get("/conversations/{conversation_id}", response_model=list[MessageResponse])
def get_history(
    conversation_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    return assistant.history(db, user, conversation_id)


@router.post("/chat", response_model=ChatResponse)
async def send_message(
    body: ChatRequest, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    # CPU embeddings and synchronous SQL run off the event loop; the LLM call is async.
    # Run the orchestration in a worker with its own event loop, keeping one SQL
    # session/connection for the entire operation and session advisory lock.
    import asyncio

    return await run_in_threadpool(
        lambda: asyncio.run(assistant.chat(db, user, body.message, body.conversation_id))
    )
