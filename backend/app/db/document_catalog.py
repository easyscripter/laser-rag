"""PostgreSQL implementation of the DocumentCatalog seam (spec §5 step 6, §7)."""

from __future__ import annotations

from sqlalchemy import select

from app.chat.models import DocumentRef
from app.db.models import Document
from app.db.session import AsyncSessionLocal


class PostgreSQLDocumentCatalog:
    """Reads bibliographic fields from the documents table for citations."""

    async def get_by_ids(
        self, *, tenant_id: str, doc_ids: list[str]
    ) -> dict[str, DocumentRef]:
        if not doc_ids:
            return {}
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Document).where(
                    Document.tenant_id == tenant_id,
                    Document.id.in_(doc_ids),
                )
            )
            return {
                row.id: DocumentRef(
                    doc_id=row.id,
                    title=row.title,
                    authors=list(row.authors),
                    year=row.year,
                    journal=row.journal,
                    doi=row.doi,
                    url=row.url,
                )
                for row in result.scalars()
            }
