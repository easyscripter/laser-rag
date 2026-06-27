"""Retrieval merge/dedup/rank + source numbering (spec §5 steps 3-5).

Pure helpers over :class:`~app.domain.models.SearchHit`, kept separate from the
engine so the ranking and citation-numbering rules are independently testable.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Protocol

from app.domain.constants import RETRIEVAL_TOP_K
from app.domain.models import SearchHit


class Retriever(Protocol):
    """Vector retrieval seam (real impl: :class:`~app.domain.chroma_indexer.ChromaIndexer`)."""

    def query(
        self, text: str, *, n_results: int = RETRIEVAL_TOP_K, where: dict[str, str] | None = None
    ) -> list[SearchHit]:
        """Return the nearest chunks to ``text``, optionally metadata-filtered."""
        ...


@dataclass(frozen=True, slots=True)
class SourceGroup:
    """A cited document: its assigned number and the hits that backed it."""

    n: int
    doc_id: str
    hits: list[SearchHit]


def merge_dedup_rank(hits: Iterable[SearchHit], *, limit: int = RETRIEVAL_TOP_K) -> list[SearchHit]:
    """Merge per-language results: dedup by chunk_id (min distance), rank, cap.

    A chunk surfaced by both language queries is kept once at its best (smallest)
    distance; results are then ordered by ascending distance and truncated.
    """
    best: dict[str, SearchHit] = {}
    for hit in hits:
        existing = best.get(hit.chunk_id)
        if existing is None or hit.distance < existing.distance:
            best[hit.chunk_id] = hit
    ranked = sorted(best.values(), key=lambda h: h.distance)
    return ranked[:limit]


def group_sources(ranked: list[SearchHit]) -> list[SourceGroup]:
    """Group ranked hits by document in first-seen order, numbering from 1."""
    order: list[str] = []
    by_doc: dict[str, list[SearchHit]] = {}
    for hit in ranked:
        if hit.doc_id not in by_doc:
            order.append(hit.doc_id)
            by_doc[hit.doc_id] = []
        by_doc[hit.doc_id].append(hit)
    return [
        SourceGroup(n=i, doc_id=doc_id, hits=by_doc[doc_id])
        for i, doc_id in enumerate(order, start=1)
    ]


def render_sources_block(ranked: list[SearchHit], groups: list[SourceGroup]) -> str:
    """Render the numbered context block fed to the generator ([n] per fragment)."""
    numbering = {g.doc_id: g.n for g in groups}
    return "\n\n".join(f"[{numbering[hit.doc_id]}] {hit.text}" for hit in ranked)
