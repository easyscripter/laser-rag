"""Job status + retry endpoints (spec §4, §6).

``GET /jobs/{job_id}`` is the indexing progress poll. ``POST /jobs/{job_id}/retry``
re-enqueues a job from a chosen stage, reusing the artifacts already stored for
the earlier stages (the §4 "Retry from stage N" action).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_current_user, get_job_store, get_task_queue, require_curator
from app.auth.tokens import TokenClaims
from app.core.logging import get_logger
from app.queue.queue import TaskQueue
from app.queue.store import JobStore
from app.schemas.documents import JobStatusResponse, RetryRequest, UploadAccepted

logger = get_logger(__name__)

router = APIRouter(tags=["jobs"])


async def _load_job(job_id: str, store: JobStore) -> JobStatusResponse:
    job = await store.get(job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"unknown job: {job_id}"
        )
    return JobStatusResponse.from_job(job)


@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job(
    job_id: str,
    store: JobStore = Depends(get_job_store),
    _: TokenClaims = Depends(get_current_user),
) -> JobStatusResponse:
    """Return the current stage/status of an indexing job (spec §6)."""
    return await _load_job(job_id, store)


@router.post(
    "/jobs/{job_id}/retry",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=UploadAccepted,
)
async def retry_job(
    job_id: str,
    body: RetryRequest,
    store: JobStore = Depends(get_job_store),
    queue: TaskQueue = Depends(get_task_queue),
    _: TokenClaims = Depends(require_curator),
) -> UploadAccepted:
    """Re-enqueue ``job_id`` from ``from_stage``, reusing earlier artifacts (spec §4).

    Curator-only: re-indexing is a curation action (spec §11).
    """
    job = await store.get(job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"unknown job: {job_id}"
        )

    await queue.enqueue_index(job_id, from_stage=body.from_stage)
    logger.info("job.retry", job_id=job_id, from_stage=body.from_stage)
    return UploadAccepted(job_id=job.job_id, doc_id=job.doc_id)
