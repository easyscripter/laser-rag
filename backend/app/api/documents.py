"""Document indexing endpoints (spec §4, §6).

``POST /documents`` validates and stores the upload, registers a queued job and
hands it to the worker, returning 202 immediately. Indexing happens out of band;
the client polls ``GET /jobs/{job_id}``.
"""

from __future__ import annotations

import uuid
from pathlib import Path

import anyio
from fastapi import APIRouter, Depends, File, UploadFile, status

from app.api.deps import get_app_settings, get_job_store, get_task_queue, get_tenant_id
from app.core.config import Settings
from app.core.constants import UPLOAD_READ_CHUNK_BYTES
from app.core.logging import get_logger
from app.queue.jobs import IndexJob
from app.queue.queue import TaskQueue
from app.queue.store import JobStore
from app.schemas.documents import UploadAccepted
from app.validators.uploads import (
    ensure_not_empty,
    ensure_within_size,
    validate_extension,
    validate_filename,
)

logger = get_logger(__name__)

router = APIRouter(tags=["documents"])


def _persist(dest: Path, data: bytes) -> None:
    """Blocking write of the validated bytes to disk (run off the event loop)."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)


async def _store_upload(upload: UploadFile, dest: Path, *, max_bytes: int) -> None:
    """Read the upload (enforcing the size limit) and persist it to ``dest``."""
    chunks: list[bytes] = []
    written = 0
    while chunk := await upload.read(UPLOAD_READ_CHUNK_BYTES):
        written += len(chunk)
        ensure_within_size(written, max_bytes=max_bytes)
        chunks.append(chunk)
    ensure_not_empty(written)
    await anyio.to_thread.run_sync(_persist, dest, b"".join(chunks))


@router.post(
    "/documents",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=UploadAccepted,
)
async def upload_document(
    file: UploadFile = File(...),
    settings: Settings = Depends(get_app_settings),
    tenant_id: str = Depends(get_tenant_id),
    store: JobStore = Depends(get_job_store),
    queue: TaskQueue = Depends(get_task_queue),
) -> UploadAccepted:
    """Accept a document, queue it for indexing, return 202 with job + doc ids."""
    filename = validate_filename(file.filename)
    ext = validate_extension(filename, settings)

    doc_id = uuid.uuid4().hex
    job_id = uuid.uuid4().hex
    dest = Path(settings.upload_dir) / f"{doc_id}.{ext}"
    await _store_upload(file, dest, max_bytes=settings.max_upload_mb * 1024 * 1024)

    job = IndexJob(
        job_id=job_id,
        doc_id=doc_id,
        tenant_id=tenant_id,
        filename=filename,
        file_path=str(dest),
    )
    await store.save(job)
    await queue.enqueue_index(job_id)

    logger.info("document.queued", job_id=job_id, doc_id=doc_id, filename=filename)
    return UploadAccepted(job_id=job_id, doc_id=doc_id)
