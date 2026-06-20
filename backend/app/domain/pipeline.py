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
from app.domain.database_manager import DatabaseManager
from app.domain.document_analyzer import DocumentAnalyzer
from app.domain.document_splitter import DocumentSplitter
from app.domain.metadata_extractor import MetadataExtractor
from app.domain.models import SearchHit
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

    async def index(self, path: str | Path, *, tenant_id: str) -> IndexResult:
        """Run the six indexing stages and return a summary (spec §4)."""
        file_path = Path(path)

        # Stage 1 — extract text + content hash.
        extraction = self._extractor.extract(file_path)
        if await self._database.document_exists(
            tenant_id=tenant_id, sha256=extraction.sha256
        ):
            raise DuplicateDocumentError(extraction.sha256)

        # Stage 2 — classify type + language.
        analysis = self._analyzer.analyze(extraction.text)

        # Stage 3 — bibliographic metadata (LLM, with filename fallback).
        metadata = await self._metadata_extractor.extract(
            extraction.text,
            doc_type=analysis.doc_type,
            filename=file_path.name,
        )

        # Stage 4 — chunk the text.
        chunks = self._splitter.split(extraction.text)

        # Stage 5 — embed + store vectors.
        doc_id = uuid.uuid4().hex
        indexed_chunks = self._indexer.index(
            doc_id,
            chunks,
            metadata=metadata,
            lang=analysis.lang.value,
            doc_type=analysis.doc_type.value,
        )

        # Stage 6 — persist relational rows atomically.
        await self._database.save_document(
            doc_id=doc_id,
            tenant_id=tenant_id,
            sha256=extraction.sha256,
            metadata=metadata,
            analysis=analysis,
            quality_score=extraction.quality_score,
            n_pages=extraction.n_pages,
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
