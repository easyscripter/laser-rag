"""ChromaVectorBackend — synchronous VectorBackend backed by ChromaDB HTTP server.

One Chroma collection per tenant: ``corpus_{tenant_id}``.
Synchronous to match the VectorBackend Protocol (spec Phase 2).
"""

from __future__ import annotations

import chromadb
from chromadb import Collection

from app.core.config import get_settings
from app.domain.models import SearchHit


class ChromaVectorBackend:
    """VectorBackend implementation wrapping a single ChromaDB collection."""

    def __init__(self, collection: Collection) -> None:
        self._collection = collection

    def add(
        self,
        *,
        ids: list[str],
        embeddings: list[list[float]],
        documents: list[str],
        metadatas: list[dict[str, str]],
    ) -> None:
        """Upsert embedded chunks — upsert handles deterministic re-indexing."""
        self._collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
        )

    def query(
        self,
        *,
        embedding: list[float],
        n_results: int,
        where: dict[str, str] | None = None,
    ) -> list[SearchHit]:
        """Return nearest chunks as SearchHit objects."""
        kwargs: dict[str, object] = {
            "query_embeddings": [embedding],
            "n_results": n_results,
            "include": ["documents", "metadatas", "distances"],
        }
        if where:
            kwargs["where"] = where

        result = self._collection.query(**kwargs)

        ids: list[str] = result["ids"][0]
        documents: list[str] = result["documents"][0]
        metadatas: list[dict[str, str]] = result["metadatas"][0]
        distances: list[float] = result["distances"][0]

        return [
            SearchHit(
                chunk_id=chunk_id,
                doc_id=meta.get("doc_id", ""),
                text=text,
                distance=float(dist),
                metadata=meta,
            )
            for chunk_id, text, meta, dist in zip(ids, documents, metadatas, distances, strict=True)
        ]


def make_chroma_backend(tenant_id: str) -> ChromaVectorBackend:
    """Build a ChromaVectorBackend for the given tenant.

    Collection is created if it does not exist. Name: ``corpus_{tenant_id}``.
    Uses cosine distance to match MiniLM-L6-v2 training objective.
    """
    settings = get_settings()
    client = chromadb.HttpClient(host=settings.chroma_host, port=settings.chroma_port)
    collection = client.get_or_create_collection(
        name=f"corpus_{tenant_id}",
        metadata={"hnsw:space": "cosine"},
    )
    return ChromaVectorBackend(collection)
