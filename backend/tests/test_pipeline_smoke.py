"""Smoke test: RAGPipeline.index end-to-end with mocked external deps (Phase 1).

No ChromaDB / LLM / Postgres — the vector store, embedder and LLM are fakes and
persistence is the in-memory DatabaseManager. Verifies the six stages wire
together and a document lands in the store with its chunks indexed.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from app.domain.chroma_indexer import ChromaIndexer
from app.domain.database_manager import InMemoryDatabaseManager
from app.domain.document_analyzer import DocumentAnalyzer
from app.domain.document_splitter import DocumentSplitter
from app.domain.metadata_extractor import MetadataExtractor
from app.domain.models import SearchHit
from app.domain.pipeline import RAGPipeline
from app.domain.text_extractor import TextExtractor
from app.errors.domain import DuplicateDocumentError


class FakeLLM:
    """Returns canned metadata JSON regardless of the prompt."""

    async def complete(self, prompt: str, *, task: str) -> str:
        return json.dumps(
            {
                "title": "Laser Cladding of Nickel Superalloys",
                "authors": ["A. Malyshev", "B. Solovyov"],
                "abstract": "A study of laser cladding.",
                "keywords": ["laser", "cladding"],
                "doi": None,
                "url": None,
                "year": 2025,
                "journal": "Journal of Surface Engineering",
            }
        )


class FakeEmbedder:
    """Deterministic fixed-dimension vectors keyed off text length."""

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[float(len(t) % 7), 1.0, 0.0] for t in texts]


class FakeVectorBackend:
    """In-memory vector store capturing everything written to it."""

    def __init__(self) -> None:
        self.ids: list[str] = []
        self.documents: list[str] = []

    def add(
        self,
        *,
        ids: list[str],
        embeddings: list[list[float]],
        documents: list[str],
        metadatas: list[dict[str, str]],
    ) -> None:
        self.ids.extend(ids)
        self.documents.extend(documents)

    def query(
        self,
        *,
        embedding: list[float],
        n_results: int,
        where: dict[str, str] | None = None,
    ) -> list[SearchHit]:
        return [
            SearchHit(chunk_id=cid, doc_id=cid.split(":")[0], text=doc, distance=0.1)
            for cid, doc in zip(self.ids[:n_results], self.documents, strict=False)
        ]


def _build_pipeline(database: InMemoryDatabaseManager) -> tuple[RAGPipeline, FakeVectorBackend]:
    backend = FakeVectorBackend()
    pipeline = RAGPipeline(
        extractor=TextExtractor(),
        analyzer=DocumentAnalyzer(),
        metadata_extractor=MetadataExtractor(FakeLLM()),
        splitter=DocumentSplitter(),
        indexer=ChromaIndexer(FakeEmbedder(), backend),
        database=database,
    )
    return pipeline, backend


def _sample_document(tmp_path: Path) -> Path:
    paragraphs = [
        "Laser cladding is an additive manufacturing process. " * 40,
        "It deposits metal powder onto a substrate. " * 40,
        "The resulting coating improves wear resistance. " * 40,
    ]
    doc = tmp_path / "laser_cladding_review.txt"
    doc.write_text("\n\n".join(paragraphs), encoding="utf-8")
    return doc


async def test_index_pipeline_persists_document_and_chunks(tmp_path: Path) -> None:
    database = InMemoryDatabaseManager()
    pipeline, backend = _build_pipeline(database)
    doc = _sample_document(tmp_path)

    result = await pipeline.index(doc, tenant_id="default")

    assert result.n_chunks > 0
    assert result.quality_score > 0.9  # clean ASCII text
    assert result.lang == "en"

    stored = database.get(result.doc_id)
    assert stored is not None
    assert stored.metadata.title == "Laser Cladding of Nickel Superalloys"
    assert len(stored.chunk_ids) == result.n_chunks
    assert len(backend.ids) == result.n_chunks  # every chunk reached the vector store


async def test_index_pipeline_rejects_duplicate(tmp_path: Path) -> None:
    database = InMemoryDatabaseManager()
    pipeline, _ = _build_pipeline(database)
    doc = _sample_document(tmp_path)

    await pipeline.index(doc, tenant_id="default")
    with pytest.raises(DuplicateDocumentError):
        await pipeline.index(doc, tenant_id="default")
