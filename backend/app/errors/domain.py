"""Domain-layer exceptions (spec §3.1)."""

from __future__ import annotations


class DomainError(Exception):
    """Base class for all domain-layer errors."""


class UnsupportedFormatError(DomainError):
    """Raised when a file extension is outside the supported allowlist."""


class MetadataExtractionError(DomainError):
    """Raised when the LLM fails to yield valid metadata after all retries."""


class DuplicateDocumentError(DomainError):
    """Raised when a document with the same content hash is already indexed (§8 dedup)."""
