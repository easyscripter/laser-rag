"""Value objects for the chat layer (spec §5, §7, §8).

Frozen dataclasses carry internal transport (conversation/message rows, the
document reference used to build a citation); the pydantic ``Citation`` is the
wire shape streamed in the SSE ``citations`` event.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from pydantic import BaseModel, Field

from app.core.enums.chat import MessageRole


@dataclass(frozen=True, slots=True)
class ConversationRecord:
    """A chat session (spec §8 conversations)."""

    id: str
    tenant_id: str
    user_id: str
    title: str | None = None


@dataclass(frozen=True, slots=True)
class MessageRecord:
    """A single turn in a conversation (spec §8 messages)."""

    id: str
    conversation_id: str
    role: MessageRole
    content: str
    created_at: datetime
    citations_json: dict[str, object] | None = None


@dataclass(frozen=True, slots=True)
class DocumentRef:
    """Bibliographic fields needed to render a citation (spec §7)."""

    doc_id: str
    title: str
    authors: list[str] = field(default_factory=list)
    year: int | None = None
    journal: str | None = None
    doi: str | None = None
    url: str | None = None


class Citation(BaseModel):
    """One numbered source in the SSE ``citations`` payload (spec §7)."""

    n: int = Field(ge=1)
    doc_id: str
    title: str
    authors: list[str] = Field(default_factory=list)
    year: int | None = None
    journal: str | None = None
    doi: str | None = None
    url: str | None = None
    chunk_ids: list[str] = Field(default_factory=list)
