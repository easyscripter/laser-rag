"""PostgreSQL repository for document CRUD operations (Phase 7, spec §6).

Provides list, get, delete and metadata-filter queries over the ``documents``
table.  Chroma vector clean-up (delete by chunk IDs) is handled separately in
the API layer so this module stays free of vector-store concerns.
"""

from __future__ import annotations

import contextlib
from dataclasses import dataclass, field

from sqlalchemy import delete as sa_delete
from sqlalchemy import select

from app.db.models import Document
from app.db.session import AsyncSessionLocal


@dataclass(frozen=True, slots=True)
class DocumentRecord:
    """Internal data-transfer object for a single document row (Phase 7)."""

    id: str
    title: str
    authors: list[str]
    year: int | None
    doc_type: str
    lang: str
    quality_score: float
    abstract: str | None
    chunk_ids: list[str] = field(default_factory=list)

    @property
    def n_chunks(self) -> int:
        return len(self.chunk_ids)


def _to_record(row: Document) -> DocumentRecord:
    return DocumentRecord(
        id=row.id,
        title=row.title,
        authors=list(row.authors),
        year=row.year,
        doc_type=row.doc_type,
        lang=row.lang,
        quality_score=row.quality_score,
        abstract=row.abstract,
        chunk_ids=list(row.chunk_ids),
    )


class PostgreSQLDocumentRepository:
    """Async document repository backed by SQLAlchemy + PostgreSQL."""

    async def list_all(self, *, tenant_id: str) -> list[DocumentRecord]:
        """Return all documents for the tenant, newest first."""
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Document)
                .where(Document.tenant_id == tenant_id)
                .order_by(Document.created_at.desc())
            )
            return [_to_record(row) for row in result.scalars()]

    async def get(self, doc_id: str, *, tenant_id: str) -> DocumentRecord | None:
        """Return a single document, or ``None`` if not found / not owned by tenant."""
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Document).where(
                    Document.id == doc_id,
                    Document.tenant_id == tenant_id,
                )
            )
            row = result.scalar_one_or_none()
            return _to_record(row) if row is not None else None

    async def delete(self, doc_id: str, *, tenant_id: str) -> None:
        """Delete the document row and its citations (CASCADE).

        The caller is responsible for verifying existence before calling this.
        """
        async with AsyncSessionLocal() as session, session.begin():
            await session.execute(
                sa_delete(Document).where(
                    Document.id == doc_id,
                    Document.tenant_id == tenant_id,
                )
            )

    async def filter_by_metadata(
        self, *, tenant_id: str, filters: dict[str, str]
    ) -> list[DocumentRecord]:
        """Return documents matching the supplied metadata filters.

        Recognised keys: ``lang``, ``type``, ``year``.
        Unknown keys are silently ignored (no SQL injection risk — only known
        columns are touched; Pydantic validated the incoming dict).
        """
        stmt = (
            select(Document)
            .where(Document.tenant_id == tenant_id)
            .order_by(Document.created_at.desc())
        )
        if lang := filters.get("lang"):
            stmt = stmt.where(Document.lang == lang)
        if doc_type := filters.get("type"):
            stmt = stmt.where(Document.doc_type == doc_type)
        if year_str := filters.get("year"):
            with contextlib.suppress(ValueError):
                stmt = stmt.where(Document.year == int(year_str))

        async with AsyncSessionLocal() as session:
            result = await session.execute(stmt)
            return [_to_record(row) for row in result.scalars()]
