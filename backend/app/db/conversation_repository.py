"""PostgreSQL implementation of ConversationRepository (spec §8)."""

from __future__ import annotations

from sqlalchemy import select

from app.chat.models import ConversationRecord, MessageRecord
from app.chat.repository import ConversationRepository
from app.core.enums.chat import MessageRole
from app.db.models import Conversation, Message
from app.db.session import AsyncSessionLocal


def _to_message(row: Message) -> MessageRecord:
    return MessageRecord(
        id=row.id,
        conversation_id=row.conversation_id,
        role=MessageRole(row.role),
        content=row.content,
        created_at=row.created_at,
        citations_json=row.citations_json,
    )


def _to_conversation(row: Conversation) -> ConversationRecord:
    return ConversationRecord(
        id=row.id, tenant_id=row.tenant_id, user_id=row.user_id, title=row.title
    )


class PostgreSQLConversationRepository(ConversationRepository):
    """Concrete ConversationRepository backed by async SQLAlchemy + PostgreSQL."""

    async def create(
        self, *, tenant_id: str, user_id: str, title: str | None = None
    ) -> ConversationRecord:
        async with AsyncSessionLocal() as session, session.begin():
            row = Conversation(tenant_id=tenant_id, user_id=user_id, title=title)
            session.add(row)
            await session.flush()
            return _to_conversation(row)

    async def get(
        self, conversation_id: str, *, tenant_id: str
    ) -> ConversationRecord | None:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Conversation).where(
                    Conversation.id == conversation_id,
                    Conversation.tenant_id == tenant_id,
                )
            )
            row = result.scalar_one_or_none()
            return _to_conversation(row) if row is not None else None

    async def list_messages(self, conversation_id: str) -> list[MessageRecord]:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Message)
                .where(Message.conversation_id == conversation_id)
                .order_by(Message.created_at, Message.id)
            )
            return [_to_message(row) for row in result.scalars()]

    async def add_message(
        self,
        *,
        conversation_id: str,
        role: MessageRole,
        content: str,
        citations_json: dict[str, object] | None = None,
    ) -> MessageRecord:
        async with AsyncSessionLocal() as session, session.begin():
            row = Message(
                conversation_id=conversation_id,
                role=role.value,
                content=content,
                citations_json=citations_json,
            )
            session.add(row)
            await session.flush()
            return _to_message(row)
