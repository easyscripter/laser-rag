"""Request/response DTOs for the system stats endpoint (spec §6)."""

from __future__ import annotations

from pydantic import BaseModel


class StatsResponse(BaseModel):
    """``GET /stats`` payload — per-tenant aggregate counts."""

    documents: int
    chunks: int
    conversations: int
    messages: int
