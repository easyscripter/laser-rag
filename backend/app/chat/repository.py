"""Conversation/message persistence interface (spec §8).

The chat engine depends on this seam to load history and append turns; the
PostgreSQL implementation lives in ``app/db/conversation_repository.py``.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.chat.models import ConversationRecord, MessageRecord
from app.core.enums.chat import MessageRole


class ConversationRepository(ABC):
    """Create conversations and read/append their messages."""

    @abstractmethod
    async def create(
        self, *, tenant_id: str, user_id: str, title: str | None = None
    ) -> ConversationRecord:
        """Create and return a new conversation."""

    @abstractmethod
    async def get(self, conversation_id: str, *, tenant_id: str) -> ConversationRecord | None:
        """Return the conversation if it exists within ``tenant_id`` (else ``None``)."""

    @abstractmethod
    async def list_messages(self, conversation_id: str) -> list[MessageRecord]:
        """Return the conversation's messages in chronological order."""

    @abstractmethod
    async def add_message(
        self,
        *,
        conversation_id: str,
        role: MessageRole,
        content: str,
        citations_json: dict[str, object] | None = None,
    ) -> MessageRecord:
        """Append a message and return the persisted record (with its id)."""
