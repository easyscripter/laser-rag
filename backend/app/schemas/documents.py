"""Request/response DTOs for document indexing and job status (spec §6)."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.core.constants import FIRST_STAGE, LAST_STAGE
from app.core.enums.jobs import JobStatus
from app.queue.jobs import IndexJob


class UploadAccepted(BaseModel):
    """202 response for ``POST /documents`` (spec §6)."""

    job_id: str
    doc_id: str


class JobStatusResponse(BaseModel):
    """``GET /jobs/{job_id}`` payload (spec §6)."""

    job_id: str
    doc_id: str
    stage: int = Field(ge=FIRST_STAGE, le=LAST_STAGE)
    stage_name: str
    status: JobStatus
    quality_score: float | None = None
    warning: str | None = None
    error: str | None = None

    @classmethod
    def from_job(cls, job: IndexJob) -> JobStatusResponse:
        return cls(
            job_id=job.job_id,
            doc_id=job.doc_id,
            stage=job.stage,
            stage_name=job.stage_name,
            status=job.status,
            quality_score=job.quality_score,
            warning=job.warning,
            error=job.error,
        )


class RetryRequest(BaseModel):
    """Body for ``POST /jobs/{job_id}/retry`` — resume from this stage (spec §4)."""

    from_stage: int = Field(default=FIRST_STAGE, ge=FIRST_STAGE, le=LAST_STAGE)
