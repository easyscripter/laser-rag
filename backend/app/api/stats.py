"""System statistics endpoint (spec §6).

``GET /stats`` returns per-tenant aggregate counts of documents, vector chunks,
conversations and messages.  Reader access is sufficient — no data mutation.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_stats_repository, get_tenant_id
from app.db.stats_repository import PostgreSQLStatsRepository
from app.schemas.stats import StatsResponse

router = APIRouter(tags=["stats"])


@router.get("/stats", response_model=StatsResponse)
async def get_stats(
    tenant_id: str = Depends(get_tenant_id),
    stats_repo: PostgreSQLStatsRepository = Depends(get_stats_repository),
) -> StatsResponse:
    """Return per-tenant aggregate statistics (spec §6).

    All counts are scoped to the authenticated tenant so no cross-tenant
    data leaks (spec §11).
    """
    return StatsResponse(
        documents=await stats_repo.document_count(tenant_id=tenant_id),
        chunks=await stats_repo.chunk_count(tenant_id=tenant_id),
        conversations=await stats_repo.conversation_count(tenant_id=tenant_id),
        messages=await stats_repo.message_count(tenant_id=tenant_id),
    )
