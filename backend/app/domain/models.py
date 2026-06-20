"""Domain value objects that cross module boundaries (spec §3.1, §8).

Pydantic models carry structured results (validation + serialization for the
later API/worker layers); frozen dataclasses carry lightweight internal
transport objects (chunks, hits).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from pydantic import BaseModel, Field

from app.domain.enums import DocumentType, Language


class ExtractionResult(BaseModel):
    """Output of TextExtractor (spec §4 stage 1)."""

    text: str
    sha256: str
    quality_score: float = Field(ge=0.0, le=1.0)
    n_pages: int = Field(ge=0)
    n_words: int = Field(ge=0)
    warning: str | None = None


class AnalysisResult(BaseModel):
    """Output of DocumentAnalyzer (spec §4 stage 2)."""

    doc_type: DocumentType
    lang: Language
    n_words: int = Field(ge=0)


class DocumentMetadata(BaseModel):
    """Bibliographic metadata extracted by the LLM (spec §3.1, §4 stage 3)."""

    title: str
    authors: list[str] = Field(default_factory=list)
    abstract: str | None = None
    keywords: list[str] = Field(default_factory=list)
    doi: str | None = None
    url: str | None = None
    year: int | None = None
    journal: str | None = None


@dataclass(frozen=True, slots=True)
class Chunk:
    """A text fragment produced by DocumentSplitter (spec §4 stage 4)."""

    index: int
    text: str
    n_words: int


@dataclass(frozen=True, slots=True)
class IndexedChunk:
    """A chunk after it has been embedded and written to the vector store."""

    chunk_id: str
    index: int
    n_words: int


@dataclass(frozen=True, slots=True)
class SearchHit:
    """A retrieval result from the vector store (spec §5 step 3)."""

    chunk_id: str
    doc_id: str
    text: str
    distance: float
    metadata: dict[str, str] = field(default_factory=dict)
