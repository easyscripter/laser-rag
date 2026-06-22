"""PostgreSQL implementation of DatabaseManager (spec §4 stage 6).

All writes in save_document run inside a single BEGIN/COMMIT transaction.
Any exception triggers automatic ROLLBACK via the async context manager.
"""
from __future__ import annotations

from sqlalchemy import select

from app.db.models import Document
from app.db.session import AsyncSessionLocal
from app.domain.database_manager import DatabaseManager, StoredDocument
from app.domain.models import AnalysisResult, DocumentMetadata, IndexedChunk


class PostgreSQLDatabaseManager(DatabaseManager):
    """Concrete DatabaseManager backed by async SQLAlchemy + PostgreSQL."""

    async def document_exists(self, *, tenant_id: str, sha256: str) -> bool:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Document.id).where(
                    Document.tenant_id == tenant_id,
                    Document.sha256 == sha256,
                )
            )
            return result.scalar_one_or_none() is not None

    async def save_document(
        self,
        *,
        doc_id: str,
        tenant_id: str,
        sha256: str,
        metadata: DocumentMetadata,
        analysis: AnalysisResult,
        quality_score: float,
        n_pages: int,
        indexed_chunks: list[IndexedChunk],
    ) -> StoredDocument:
        chunk_ids = [c.chunk_id for c in indexed_chunks]

        async with AsyncSessionLocal() as session, session.begin():  # single atomic transaction
            session.add(
                Document(
                    id=doc_id,
                    tenant_id=tenant_id,
                    sha256=sha256,
                    title=metadata.title,
                    authors=metadata.authors,
                    abstract=metadata.abstract,
                    doi=metadata.doi,
                    url=metadata.url,
                    year=metadata.year,
                    journal=metadata.journal,
                    doc_type=analysis.doc_type.value,
                    lang=analysis.lang.value,
                    quality_score=quality_score,
                    n_pages=n_pages,
                    n_words=analysis.n_words,
                    keywords=metadata.keywords,
                    chunk_ids=chunk_ids,
                )
            )

        return StoredDocument(
            doc_id=doc_id,
            tenant_id=tenant_id,
            sha256=sha256,
            metadata=metadata,
            analysis=analysis,
            quality_score=quality_score,
            n_pages=n_pages,
            chunk_ids=chunk_ids,
        )
