"""StageRunner: the 6-stage indexing job runner with retry-from-stage (Phase 4).

Exercises observable job behaviour through the public ``run`` interface with
fake external deps (no Redis / Chroma / LLM / Postgres). Verifies the stage
progression, failure handling, and that a retry resumes from stored artifacts
instead of recomputing earlier stages.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.core.enums.jobs import JobStatus
from app.domain.chroma_indexer import ChromaIndexer
from app.domain.database_manager import InMemoryDatabaseManager
from app.domain.document_analyzer import DocumentAnalyzer
from app.domain.document_splitter import DocumentSplitter
from app.domain.metadata_extractor import MetadataExtractor
from app.domain.models import SearchHit
from app.domain.pipeline import RAGPipeline
from app.domain.text_extractor import TextExtractor
from app.queue.jobs import IndexJob
from app.queue.runner import StageRunner
from app.queue.store import InMemoryJobStore


class FakeLLM:
    async def complete(self, prompt: str, *, task: str) -> str:
        return json.dumps({"title": "Laser Cladding", "authors": ["A. B."], "year": 2025})


class CountingEmbedder:
    """Deterministic embedder that counts how many times it runs (spy for recompute)."""

    def __init__(self) -> None:
        self.calls = 0

    def embed(self, texts: list[str]) -> list[list[float]]:
        self.calls += 1
        return [[float(len(t) % 7), 1.0, 0.0] for t in texts]


class FakeVectorBackend:
    def __init__(self, *, fail_times: int = 0) -> None:
        self.ids: list[str] = []
        self._fail_times = fail_times
        self.add_attempts = 0

    def add(self, *, ids, embeddings, documents, metadatas) -> None:  # type: ignore[no-untyped-def]
        self.add_attempts += 1
        if self.add_attempts <= self._fail_times:
            raise RuntimeError("vector backend unavailable")
        self.ids.extend(ids)

    def query(self, *, embedding, n_results, where=None) -> list[SearchHit]:  # type: ignore[no-untyped-def]
        return []


def _build(
    database: InMemoryDatabaseManager,
    backend: FakeVectorBackend,
    embedder: CountingEmbedder,
) -> StageRunner:
    pipeline = RAGPipeline(
        extractor=TextExtractor(),
        analyzer=DocumentAnalyzer(),
        metadata_extractor=MetadataExtractor(FakeLLM()),
        splitter=DocumentSplitter(),
        indexer=ChromaIndexer(embedder, backend),
        database=database,
    )
    return StageRunner(pipeline=pipeline)


def _sample_doc(tmp_path: Path) -> Path:
    doc = tmp_path / "laser_cladding_review.txt"
    doc.write_text("Laser cladding is additive manufacturing. " * 200, encoding="utf-8")
    return doc


async def _enqueue(store: InMemoryJobStore, doc: Path) -> IndexJob:
    job = IndexJob(
        job_id="job-1",
        doc_id="doc-1",
        tenant_id="default",
        filename=doc.name,
        file_path=str(doc),
    )
    await store.save(job)
    return job


async def test_runs_all_six_stages_to_completion(tmp_path: Path) -> None:
    store = InMemoryJobStore()
    database = InMemoryDatabaseManager()
    backend = FakeVectorBackend()
    await _enqueue(store, _sample_doc(tmp_path))
    runner = _build(database, backend, CountingEmbedder())

    job = await runner.run("job-1", store=store)

    assert job.status is JobStatus.COMPLETED
    assert job.stage == 6
    assert job.stage_name == "persist"
    assert job.quality_score is not None and job.quality_score > 0.9
    assert database.get("doc-1") is not None  # stage 6 persisted
    assert len(backend.ids) > 0  # stage 5 wrote vectors


async def test_failed_stage_stops_pipeline(tmp_path: Path) -> None:
    store = InMemoryJobStore()
    database = InMemoryDatabaseManager()
    backend = FakeVectorBackend(fail_times=1)  # stage 5 fails
    await _enqueue(store, _sample_doc(tmp_path))
    runner = _build(database, backend, CountingEmbedder())

    job = await runner.run("job-1", store=store)

    assert job.status is JobStatus.FAILED
    assert job.stage == 5
    assert job.error is not None
    assert database.get("doc-1") is None  # stage 6 never ran


async def test_retry_resumes_from_stage_without_recomputing(tmp_path: Path) -> None:
    store = InMemoryJobStore()
    database = InMemoryDatabaseManager()
    backend = FakeVectorBackend(fail_times=1)  # stage 5 fails once
    embedder = CountingEmbedder()
    await _enqueue(store, _sample_doc(tmp_path))
    runner = _build(database, backend, embedder)

    failed = await runner.run("job-1", store=store)
    assert failed.status is JobStatus.FAILED and failed.stage == 5
    embed_calls_after_first = embedder.calls

    resumed = await runner.run("job-1", store=store, from_stage=5)

    assert resumed.status is JobStatus.COMPLETED
    assert resumed.stage == 6
    assert database.get("doc-1") is not None
    # Stages 1-4 reused stored artifacts: only stage 5's re-embed added calls.
    assert embedder.calls == embed_calls_after_first + 1


async def test_duplicate_document_fails_at_stage_one(tmp_path: Path) -> None:
    store = InMemoryJobStore()
    database = InMemoryDatabaseManager()
    doc = _sample_doc(tmp_path)
    # Pre-index the same content so the dedup check trips.
    first = _build(database, FakeVectorBackend(), CountingEmbedder())
    await _enqueue(store, doc)
    await first.run("job-1", store=store)

    second_job = IndexJob(
        job_id="job-2",
        doc_id="doc-2",
        tenant_id="default",
        filename=doc.name,
        file_path=str(doc),
    )
    await store.save(second_job)
    runner = _build(database, FakeVectorBackend(), CountingEmbedder())

    job = await runner.run("job-2", store=store)

    assert job.status is JobStatus.FAILED
    assert job.stage == 1
    assert job.error is not None and "duplicate" in job.error.lower()
