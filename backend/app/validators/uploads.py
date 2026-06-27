"""Upload validation (spec cross-cutting security: extension allowlist + size).

Pure request-validation helpers shared by the document endpoints. Each raises an
``HTTPException`` with the appropriate status code; the router stays declarative.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import HTTPException, status

from app.core.config import Settings


def validate_filename(filename: str | None) -> str:
    """Return a sanitized base filename; reject a missing/empty name."""
    name = Path(filename or "").name
    if not name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="missing filename"
        )
    return name


def validate_extension(filename: str, settings: Settings) -> str:
    """Return the lowercased extension if it is in the allowlist, else 415."""
    ext = Path(filename).suffix.lower().lstrip(".")
    if ext not in settings.allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"unsupported file type '.{ext}'; allowed: {settings.allowed_extensions}",
        )
    return ext


def ensure_within_size(written: int, *, max_bytes: int) -> None:
    """Reject an upload that has grown past the configured size limit (413)."""
    if written > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"file exceeds the {max_bytes // (1024 * 1024)} MB limit",
        )


def ensure_not_empty(written: int) -> None:
    """Reject an empty upload (400)."""
    if written == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="uploaded file is empty"
        )
