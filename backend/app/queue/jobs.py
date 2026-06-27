"""Indexing job state model (spec §4).

A job advances through six stages; the output of each stage is captured in
:class:`JobArtifacts` so the worker can resume from any stage on retry. The whole
record serializes to JSON for the Redis-backed :class:`~app.queue.store.JobStore`.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.core.constants import FIRST_STAGE, STAGE_NAMES
from app.core.enums.jobs import JobStatus
from app.core.time import utcnow
from app.domain.models import (
    AnalysisResult,
    Chunk,
    DocumentMetadata,
    ExtractionResult,
    IndexedChunk,
)


def stage_name(stage: int) -> str:
    """Human-readable name for a stage number (spec §4 / §6 ``stage_name``)."""
    return STAGE_NAMES.get(stage, "unknown")


class JobArtifacts(BaseModel):
    """Per-stage outputs persisted so a job can resume from any stage."""

    extraction: ExtractionResult | None = None  # stage 1
    analysis: AnalysisResult | None = None  # stage 2
    metadata: DocumentMetadata | None = None  # stage 3
    chunks: list[Chunk] | None = None  # stage 4
    indexed_chunks: list[IndexedChunk] | None = None  # stage 5


class IndexJob(BaseModel):
    """A single document-indexing job and its progress (spec §4, §6)."""

    job_id: str
    doc_id: str
    tenant_id: str
    filename: str
    file_path: str

    stage: int = FIRST_STAGE
    status: JobStatus = JobStatus.QUEUED
    quality_score: float | None = None
    warning: str | None = None
    error: str | None = None

    artifacts: JobArtifacts = Field(default_factory=JobArtifacts)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)

    @property
    def stage_name(self) -> str:
        return stage_name(self.stage)

    def touch(self) -> None:
        self.updated_at = utcnow()
