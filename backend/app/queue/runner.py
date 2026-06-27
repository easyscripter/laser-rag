"""StageRunner — drives the six indexing stages with retry-from-stage (spec §4).

Each stage's output is stored on the job before the next stage runs, so a failed
job can be retried from any stage N: stages < N reuse the persisted artifacts
instead of recomputing. The runner is pure orchestration over an injected
:class:`~app.domain.pipeline.RAGPipeline`; the arq worker is a thin shell on top.
"""

from __future__ import annotations

from typing import TypeVar

from app.core.constants import FIRST_STAGE, LAST_STAGE
from app.core.enums.jobs import JobStatus
from app.domain.pipeline import RAGPipeline
from app.errors.domain import DuplicateDocumentError
from app.queue.jobs import IndexJob
from app.queue.store import JobStore

T = TypeVar("T")


class StageRunner:
    """Runs an :class:`IndexJob` through stages 1..6, persisting progress."""

    def __init__(self, *, pipeline: RAGPipeline) -> None:
        self._pipeline = pipeline

    async def run(
        self, job_id: str, *, store: JobStore, from_stage: int = FIRST_STAGE
    ) -> IndexJob:
        """Run stages ``from_stage``..6, updating ``store`` as each stage finishes."""
        job = await store.get(job_id)
        if job is None:
            raise KeyError(f"unknown job: {job_id}")

        job.error = None
        start = max(from_stage, FIRST_STAGE)
        try:
            for stage in range(start, LAST_STAGE + 1):
                job.stage = stage
                job.status = JobStatus.RUNNING
                await store.save(job)
                await self._run_stage(stage, job)
                await store.save(job)
            job.status = JobStatus.COMPLETED
        except DuplicateDocumentError:
            job.status = JobStatus.FAILED
            job.error = "duplicate document — already indexed"
        except Exception as exc:  # any stage failure marks the whole job failed
            job.status = JobStatus.FAILED
            job.error = str(exc)
        await store.save(job)
        return job

    async def _run_stage(self, stage: int, job: IndexJob) -> None:
        art = job.artifacts
        p = self._pipeline

        if stage == 1:
            extraction = p.extract(job.file_path)
            art.extraction = extraction
            job.quality_score = extraction.quality_score
            job.warning = extraction.warning
            if await p.is_duplicate(tenant_id=job.tenant_id, sha256=extraction.sha256):
                raise DuplicateDocumentError(extraction.sha256)
        elif stage == 2:
            art.analysis = p.analyze(self._require(art.extraction, "extraction").text)
        elif stage == 3:
            extraction = self._require(art.extraction, "extraction")
            analysis = self._require(art.analysis, "analysis")
            art.metadata = await p.extract_metadata(
                extraction.text, doc_type=analysis.doc_type, filename=job.filename
            )
        elif stage == 4:
            art.chunks = p.split(self._require(art.extraction, "extraction").text)
        elif stage == 5:
            art.indexed_chunks = p.index_vectors(
                job.doc_id,
                self._require(art.chunks, "chunks"),
                metadata=self._require(art.metadata, "metadata"),
                analysis=self._require(art.analysis, "analysis"),
            )
        elif stage == 6:
            await p.persist(
                doc_id=job.doc_id,
                tenant_id=job.tenant_id,
                extraction=self._require(art.extraction, "extraction"),
                analysis=self._require(art.analysis, "analysis"),
                metadata=self._require(art.metadata, "metadata"),
                indexed_chunks=self._require(art.indexed_chunks, "indexed_chunks"),
            )

    @staticmethod
    def _require(value: T | None, name: str) -> T:
        """Return a prerequisite artifact, failing clearly if a resume is incoherent."""
        if value is None:
            raise ValueError(f"cannot resume: missing artifact '{name}' from an earlier stage")
        return value
