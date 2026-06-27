"""Document catalog seam — bibliographic lookup for citations (spec §5 step 6, §7).

Retrieval gives us ``doc_id``s; the SSE ``citations`` event needs full
bibliographic fields (title/authors/year/journal/doi/url) from the relational
store. The chat engine depends on this Protocol; the PostgreSQL implementation
lives in ``app/db/document_catalog.py``.
"""

from __future__ import annotations

from typing import Protocol

from app.chat.models import DocumentRef


class DocumentCatalog(Protocol):
    """Read-side lookup of document bibliographic data by id."""

    async def get_by_ids(
        self, *, tenant_id: str, doc_ids: list[str]
    ) -> dict[str, DocumentRef]:
        """Return a ``{doc_id: DocumentRef}`` map for the ids that exist."""
        ...
