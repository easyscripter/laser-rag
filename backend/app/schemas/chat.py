"""Request/response DTOs for conversations and chat (spec §6, §7)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class CreateConversationRequest(BaseModel):
    """Body for ``POST /conversations``."""

    title: str | None = Field(default=None, max_length=512)


class ConversationCreated(BaseModel):
    """``POST /conversations`` payload (spec §6)."""

    conversation_id: str


class MessageRequest(BaseModel):
    """Body for ``POST /conversations/{id}/messages`` (spec §6, §7)."""

    query: str = Field(min_length=1)
    filters: dict[str, str] | None = None


class MessageOut(BaseModel):
    """A single turn inside ``GET /conversations/{id}`` (spec §6)."""

    id: str
    role: str
    content: str
    created_at: datetime
    citations_json: dict[str, object] | None = None


class ConversationHistoryResponse(BaseModel):
    """``GET /conversations/{id}`` payload — full message history (spec §6)."""

    conversation_id: str
    title: str | None = None
    messages: list[MessageOut] = Field(default_factory=list)
