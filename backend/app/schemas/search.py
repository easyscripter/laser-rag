"""Request/response DTOs for semantic and metadata search (spec §6)."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.documents import DocumentOut


class SearchRequest(BaseModel):
    """Body for ``POST /search`` — semantic power-search (spec §6)."""

    query: str = Field(min_length=1)
    filters: dict[str, str] | None = None


class SearchMetadataRequest(BaseModel):
    """Body for ``POST /search/metadata`` — metadata-filter search (spec §6)."""

    filters: dict[str, str] = Field(default_factory=dict)


class SearchHitOut(BaseModel):
    """A single ranked fragment returned by ``POST /search``."""

    chunk_id: str
    doc_id: str
    text: str
    distance: float
    metadata: dict[str, str] = Field(default_factory=dict)


class SearchResponse(BaseModel):
    """``POST /search`` payload — ranked fragment list."""

    hits: list[SearchHitOut] = Field(default_factory=list)


class MetadataSearchResponse(BaseModel):
    """``POST /search/metadata`` payload — filtered document list."""

    documents: list[DocumentOut] = Field(default_factory=list)
