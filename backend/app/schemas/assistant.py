from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.config import settings


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message: str = Field(min_length=1, max_length=10000)
    conversation_id: int | None = Field(default=None, gt=0)

    @field_validator("message")
    @classmethod
    def validate_message(cls, value):
        value = value.strip()
        if not value or len(value) > settings.chat_max_message_chars:
            raise ValueError("Сообщение пустое или превышает лимит длины")
        return value


class Source(BaseModel):
    document_id: int
    chunk_id: int
    title: str
    source: str
    score: float


class MessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    role: Literal["user", "assistant"]
    content: str
    created_at: datetime
    sources: list[Source] = []


class ConversationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    created_at: datetime
    updated_at: datetime


class ChatResponse(BaseModel):
    conversation_id: int
    message: MessageResponse
    prompt_tokens: int
    completion_tokens: int
    rag_used: bool


class DocumentResponse(BaseModel):
    id: int
    title: str
    source: str
    is_public: bool
    content: str
