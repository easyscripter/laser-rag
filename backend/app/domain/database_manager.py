"""DatabaseManager — relational persistence interface (spec §3.1, §4 stage 6).

Defines the atomic "save a document with its citations and keywords" contract.
The real async-SQLAlchemy/PostgreSQL implementation lands in Phase 2 and must run
the write inside a single transaction (rollback on any error, spec §4 stage 6).
``InMemoryDatabaseManager`` is a lightweight stand-in for the Phase 1 smoke test.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from app.domain.models import AnalysisResult, DocumentMetadata, IndexedChunk


@dataclass(frozen=True, slots=True)
class StoredDocument:
    """Everything persisted for one document (spec §8 documents/keywords)."""

    doc_id: str
    tenant_id: str
    sha256: str
    metadata: DocumentMetadata
    analysis: AnalysisResult
    quality_score: float
    n_pages: int
    chunk_ids: list[str] = field(default_factory=list)


class DatabaseManager(ABC):
    """Atomic persistence of a document and its derived rows."""

    @abstractmethod
    async def document_exists(self, *, tenant_id: str, sha256: str) -> bool:
        """Return whether a document with this content hash already exists (dedup)."""

    @abstractmethod
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
        """Persist document + keywords + chunk links atomically; rollback on error."""


class InMemoryDatabaseManager(DatabaseManager):
    """Non-durable implementation for tests — commits atomically into a dict."""

    def __init__(self) -> None:
        self._by_id: dict[str, StoredDocument] = {}
        self._hashes: dict[str, set[str]] = {}  # tenant_id → {sha256}

    async def document_exists(self, *, tenant_id: str, sha256: str) -> bool:
        return sha256 in self._hashes.get(tenant_id, set())

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
        record = StoredDocument(
            doc_id=doc_id,
            tenant_id=tenant_id,
            sha256=sha256,
            metadata=metadata,
            analysis=analysis,
            quality_score=quality_score,
            n_pages=n_pages,
            chunk_ids=[c.chunk_id for c in indexed_chunks],
        )
        # Single atomic commit: build the record fully, then publish both indexes.
        self._by_id[doc_id] = record
        self._hashes.setdefault(tenant_id, set()).add(sha256)
        return record

    def get(self, doc_id: str) -> StoredDocument | None:
        return self._by_id.get(doc_id)
