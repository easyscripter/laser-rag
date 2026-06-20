"""Injected-dependency interfaces for the domain layer.

The domain modules never import concrete LLM / vector-store clients. They depend
on these Protocols, and other layers supply real implementations or mocks.
Structural typing keeps the seam loose — no base classes to inherit.

TEMPORARY (Phase 1): real implementations are wired in later —
  * ``Embedder`` / ``VectorBackend`` → sentence-transformers + ChromaDB (Phase 2)
  * ``LLMClient``                     → ChatOpenAI factory (Phase 3)
Until then tests inject mocks.
"""

from __future__ import annotations

from typing import Protocol

from app.domain.models import SearchHit


class LLMClient(Protocol):
    """Minimal async text-completion interface (real impl: llm/ factory, Phase 3)."""

    async def complete(self, prompt: str, *, task: str) -> str:
        """Return the model's completion for ``prompt``.

        ``task`` selects the model tier downstream (e.g. ``"metadata"``); the
        domain layer treats it as an opaque label.
        """
        ...


class Embedder(Protocol):
    """Sentence-embedding interface (real impl: sentence-transformers, Phase 2)."""

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return one dense vector per input text."""
        ...


class VectorBackend(Protocol):
    """Vector-store interface (real impl: ChromaDB client, Phase 2)."""

    def add(
        self,
        *,
        ids: list[str],
        embeddings: list[list[float]],
        documents: list[str],
        metadatas: list[dict[str, str]],
    ) -> None:
        """Upsert embedded chunks into the collection."""
        ...

    def query(
        self,
        *,
        embedding: list[float],
        n_results: int,
        where: dict[str, str] | None = None,
    ) -> list[SearchHit]:
        """Return the nearest chunks, optionally filtered by metadata."""
        ...
