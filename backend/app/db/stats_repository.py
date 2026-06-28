"""PostgreSQL repository for aggregate statistics (Phase 7, spec §6).

All queries are scoped to a single tenant so the ``/stats`` endpoint only
ever sees the caller's own data (spec §11 multi-tenancy seam).
"""

from __future__ import annotations

from sqlalchemy import func, select

from app.db.models import Conversation, Document, Message
from app.db.session import AsyncSessionLocal


class PostgreSQLStatsRepository:
    """Aggregates tenant-scoped counts for the ``GET /stats`` endpoint."""

    async def document_count(self, *, tenant_id: str) -> int:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(func.count(Document.id)).where(Document.tenant_id == tenant_id)
            )
            raw = result.scalar_one_or_none()
            return int(raw) if raw is not None else 0

    async def chunk_count(self, *, tenant_id: str) -> int:
        """Sum ``jsonb_array_length(chunk_ids)`` across all documents for the tenant."""
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(
                    func.coalesce(
                        func.sum(func.jsonb_array_length(Document.chunk_ids)), 0
                    )
                ).where(Document.tenant_id == tenant_id)
            )
            raw = result.scalar_one_or_none()
            return int(raw) if raw is not None else 0

    async def conversation_count(self, *, tenant_id: str) -> int:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(func.count(Conversation.id)).where(
                    Conversation.tenant_id == tenant_id
                )
            )
            raw = result.scalar_one_or_none()
            return int(raw) if raw is not None else 0

    async def message_count(self, *, tenant_id: str) -> int:
        """Count messages in all conversations owned by this tenant."""
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(func.count(Message.id))
                .join(Conversation, Message.conversation_id == Conversation.id)
                .where(Conversation.tenant_id == tenant_id)
            )
            raw = result.scalar_one_or_none()
            return int(raw) if raw is not None else 0
