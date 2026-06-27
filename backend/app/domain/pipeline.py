"""RAGPipeline — orchestrates the domain modules (spec §3.1, §4, §5).

Two modes:
  * ``index(path, …)`` runs the six indexing stages in order, each stage's output
    feeding the next (spec §4): extract → analyze → metadata → split → vector
    index → relational persist.
  * ``search(query, …)`` is retrieval-only here — it returns ranked chunks.
    Answer generation (condense + 5-step search + LLM, spec §5) is wired in
    Phase 6; this method is the retrieval seam it will build on.

The pipeline owns no I/O of its own — every external concern arrives as an
already-constructed collaborator, so it stays unit-testable with mocks.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path

from app.domain.chroma_indexer import ChromaIndexer
from app.domain.constants import RETRIEVAL_TOP_K
from app.domain.database_manager import DatabaseManager, StoredDocument
from app.domain.document_analyzer import DocumentAnalyzer
from app.domain.document_splitter import DocumentSplitter
from app.domain.enums import DocumentType
from app.domain.metadata_extractor import MetadataExtractor
from app.domain.models import (
    AnalysisResult,
    Chunk,
    DocumentMetadata,
    ExtractionResult,
    IndexedChunk,
    SearchHit,
)
from app.domain.text_extractor import TextExtractor
from app.errors.domain import DuplicateDocumentError


@dataclass(frozen=True, slots=True)
class IndexResult:
    """Summary of a completed indexing run (drives the §4 job status later)."""

    doc_id: str
    n_chunks: int
    quality_score: float
    doc_type: str
    lang: str
    warning: str | None = None


class RAGPipeline:
    """Coordinates extraction, analysis, indexing and persistence."""

    def __init__(
        self,
        *,
        extractor: TextExtractor,
        analyzer: DocumentAnalyzer,
        metadata_extractor: MetadataExtractor,
        splitter: DocumentSplitter,
        indexer: ChromaIndexer,
        database: DatabaseManager,
    ) -> None:
        self._extractor = extractor
        self._analyzer = analyzer
        self._metadata_extractor = metadata_extractor
        self._splitter = splitter
        self._indexer = indexer
        self._database = database

    async def index(
        self, path: str | Path, *, tenant_id: str, doc_id: str | None = None
    ) -> IndexResult:
        """Run the six indexing stages in order and return a summary (spec §4).

        Synchronous in-process path (used by the smoke test). The async worker
        runs the same stage methods one at a time, persisting each stage's output
        so a job can be retried from any stage (``StageRunner``, Phase 4).
        """
        file_path = Path(path)
        doc_id = doc_id or uuid.uuid4().hex

        extraction = self.extract(file_path)  # Stage 1
        if await self.is_duplicate(tenant_id=tenant_id, sha256=extraction.sha256):
            raise DuplicateDocumentError(extraction.sha256)
        analysis = self.analyze(extraction.text)  # Stage 2
        metadata = await self.extract_metadata(  # Stage 3
            extraction.text, doc_type=analysis.doc_type, filename=file_path.name
        )
        chunks = self.split(extraction.text)  # Stage 4
        indexed_chunks = self.index_vectors(  # Stage 5
            doc_id, chunks, metadata=metadata, analysis=analysis
        )
        await self.persist(  # Stage 6
            doc_id=doc_id,
            tenant_id=tenant_id,
            extraction=extraction,
            analysis=analysis,
            metadata=metadata,
            indexed_chunks=indexed_chunks,
        )

        return IndexResult(
            doc_id=doc_id,
            n_chunks=len(indexed_chunks),
            quality_score=extraction.quality_score,
            doc_type=analysis.doc_type.value,
            lang=analysis.lang.value,
            warning=extraction.warning,
        )

    # --- Individual stages (spec §4) — shared by index() and the async worker ---

    def extract(self, path: str | Path) -> ExtractionResult:
        """Stage 1 — normalized text, SHA-256 and quality score."""
        return self._extractor.extract(Path(path))

    async def is_duplicate(self, *, tenant_id: str, sha256: str) -> bool:
        """SHA-256 dedup check against already-indexed documents (spec §8)."""
        return await self._database.document_exists(tenant_id=tenant_id, sha256=sha256)

    def analyze(self, text: str) -> AnalysisResult:
        """Stage 2 — document type (by size) and language (by char mix)."""
        return self._analyzer.analyze(text)

    async def extract_metadata(
        self, text: str, *, doc_type: DocumentType, filename: str
    ) -> DocumentMetadata:
        """Stage 3 — bibliographic metadata (LLM, with filename fallback)."""
        return await self._metadata_extractor.extract(text, doc_type=doc_type, filename=filename)

    def split(self, text: str) -> list[Chunk]:
        """Stage 4 — chunk into 800-word fragments with 150-word overlap."""
        return self._splitter.split(text)

    def index_vectors(
        self,
        doc_id: str,
        chunks: list[Chunk],
        *,
        metadata: DocumentMetadata,
        analysis: AnalysisResult,
    ) -> list[IndexedChunk]:
        """Stage 5 — embed chunks and upsert them into the vector store."""
        return self._indexer.index(
            doc_id,
            chunks,
            metadata=metadata,
            lang=analysis.lang.value,
            doc_type=analysis.doc_type.value,
        )

    async def persist(
        self,
        *,
        doc_id: str,
        tenant_id: str,
        extraction: ExtractionResult,
        analysis: AnalysisResult,
        metadata: DocumentMetadata,
        indexed_chunks: list[IndexedChunk],
    ) -> StoredDocument:
        """Stage 6 — persist relational rows atomically (rollback on error)."""
        return await self._database.save_document(
            doc_id=doc_id,
            tenant_id=tenant_id,
            sha256=extraction.sha256,
            metadata=metadata,
            analysis=analysis,
            quality_score=extraction.quality_score,
            n_pages=extraction.n_pages,
            indexed_chunks=indexed_chunks,
        )

    def search(
        self,
        query: str,
        *,
        n_results: int = RETRIEVAL_TOP_K,
        where: dict[str, str] | None = None,
    ) -> list[SearchHit]:
        """Retrieve the chunks most relevant to ``query`` (filtered, ranked).

        TODO(Phase 6): wrap this with condense + language-split retrieval + LLM
        answer generation (spec §5). For now it exposes raw retrieval only.
        """
        return self._indexer.query(query, n_results=n_results, where=where)
