"""SentenceTransformerEmbedder — local MiniLM-384 Embedder (spec Phase 2).

Implements the Embedder Protocol (synchronous). Model is lazy-loaded on first
call to avoid import-time GPU/CPU initialization cost.
"""
from __future__ import annotations

from functools import cached_property

from sentence_transformers import SentenceTransformer

from app.core.config import get_settings


class SentenceTransformerEmbedder:
    """Embedder backed by a local sentence-transformers model (default: all-MiniLM-L6-v2)."""

    def __init__(self, model_name: str | None = None) -> None:
        self._model_name = model_name or get_settings().embed_model

    @cached_property
    def _model(self) -> SentenceTransformer:
        return SentenceTransformer(self._model_name)  # type: ignore[no-any-return]

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return one 384-dimensional vector per input text."""
        if not texts:
            return []
        vectors = self._model.encode(texts, convert_to_numpy=True)
        return [v.tolist() for v in vectors]
