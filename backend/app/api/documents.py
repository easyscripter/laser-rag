"""Document indexing and management endpoints (spec §4, §6).

``POST /documents`` validates and stores the upload, registers a queued job and
hands it to the worker, returning 202 immediately.  Indexing happens out of band;
the client polls ``GET /jobs/{job_id}``.

Phase 7 additions:
  ``GET /documents``            — list all indexed documents for the tenant.
  ``GET /documents/{id}/summary`` — per-document summary (stored abstract).
  ``DELETE /documents/{id}``    — remove from PostgreSQL and Chroma (curator-only).
"""

from __future__ import annotations

import uuid
from pathlib import Path

import anyio
from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status

from app.api.deps import (
    get_app_settings,
    get_chroma_backend,
    get_document_repository,
    get_job_store,
    get_task_queue,
    get_tenant_id,
    require_curator,
)
from app.auth.tokens import TokenClaims
from app.core.config import Settings
from app.core.constants import UPLOAD_READ_CHUNK_BYTES
from app.core.logging import get_logger
from app.db.chroma_backend import ChromaVectorBackend
from app.db.document_repository import PostgreSQLDocumentRepository
from app.queue.jobs import IndexJob
from app.queue.queue import TaskQueue
from app.queue.store import JobStore
from app.schemas.documents import DocumentOut, DocumentSummaryResponse, UploadAccepted
from app.validators.uploads import (
    ensure_not_empty,
    ensure_within_size,
    validate_extension,
    validate_filename,
)

logger = get_logger(__name__)

router = APIRouter(tags=["documents"])


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


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
    _: TokenClaims = Depends(require_curator),
) -> UploadAccepted:
    """Accept a document, queue it for indexing, return 202 with job + doc ids.

    Curator-only: ingesting documents is a curation action (spec §11).
    """
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


@router.get("/documents", response_model=list[DocumentOut])
async def list_documents(
    tenant_id: str = Depends(get_tenant_id),
    repo: PostgreSQLDocumentRepository = Depends(get_document_repository),
) -> list[DocumentOut]:
    """Return all indexed documents for the authenticated tenant (spec §6)."""
    records = await repo.list_all(tenant_id=tenant_id)
    return [DocumentOut.from_record(r) for r in records]


@router.get(
    "/documents/{doc_id}/summary",
    response_model=DocumentSummaryResponse,
)
async def get_document_summary(
    doc_id: str,
    tenant_id: str = Depends(get_tenant_id),
    repo: PostgreSQLDocumentRepository = Depends(get_document_repository),
) -> DocumentSummaryResponse:
    """Return the stored abstract as the document summary (spec §6).

    The abstract was extracted by the LLM during indexing stage 3.  Returns
    ``null`` for ``summary`` when no abstract was extracted.
    """
    record = await repo.get(doc_id, tenant_id=tenant_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"unknown document: {doc_id}",
        )
    return DocumentSummaryResponse(
        doc_id=record.id,
        title=record.title,
        summary=record.abstract,
    )


@router.delete("/documents/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    doc_id: str,
    tenant_id: str = Depends(get_tenant_id),
    repo: PostgreSQLDocumentRepository = Depends(get_document_repository),
    chroma: ChromaVectorBackend = Depends(get_chroma_backend),
    _: TokenClaims = Depends(require_curator),
) -> Response:
    """Delete a document from both Chroma and PostgreSQL (curator-only, spec §6).

    Chroma chunks are removed first; then the relational row is deleted
    (CASCADE removes citations).  Returns 204 on success, 404 if not found.
    """
    record = await repo.get(doc_id, tenant_id=tenant_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"unknown document: {doc_id}",
        )

    # Remove vector chunks before the DB row so we never have orphaned vectors.
    chroma.delete_by_ids(record.chunk_ids)

    await repo.delete(doc_id, tenant_id=tenant_id)
    logger.info("document.deleted", doc_id=doc_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
