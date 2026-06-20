"""ChromaIndexer — embed chunks and run filtered vector search (spec §4 stage 5).

Wraps an injected ``Embedder`` (MiniLM-384) and ``VectorBackend`` (ChromaDB in
Phase 2). Each stored record carries metadata so retrieval can filter by
type/lang/title/authors (spec §3.1, §8). Chunk IDs are ``{doc_id}:{index}`` so a
document's vectors can be located and replaced deterministically.
"""

from __future__ import annotations

from app.domain.constants import RETRIEVAL_TOP_K
from app.domain.models import Chunk, DocumentMetadata, IndexedChunk, SearchHit
from app.domain.protocols import Embedder, VectorBackend


class ChromaIndexer:
    """Embeds document chunks and stores/queries them in a vector backend."""

    def __init__(self, embedder: Embedder, backend: VectorBackend) -> None:
        self._embedder = embedder
        self._backend = backend

    def index(
        self,
        doc_id: str,
        chunks: list[Chunk],
        *,
        metadata: DocumentMetadata,
        lang: str,
        doc_type: str,
    ) -> list[IndexedChunk]:
        """Embed ``chunks`` and upsert them with filterable metadata."""
        if not chunks:
            return []

        ids = [self._chunk_id(doc_id, c.index) for c in chunks]
        documents = [c.text for c in chunks]
        embeddings = self._embedder.embed(documents)
        base_meta = self._base_metadata(doc_id, metadata, lang=lang, doc_type=doc_type)
        metadatas = [{**base_meta, "chunk_id": cid} for cid in ids]

        self._backend.add(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
        )
        return [
            IndexedChunk(chunk_id=cid, index=c.index, n_words=c.n_words)
            for cid, c in zip(ids, chunks, strict=True)
        ]

    def query(
        self,
        text: str,
        *,
        n_results: int = RETRIEVAL_TOP_K,
        where: dict[str, str] | None = None,
    ) -> list[SearchHit]:
        """Embed ``text`` and return the nearest chunks, optionally filtered."""
        embedding = self._embedder.embed([text])[0]
        return self._backend.query(
            embedding=embedding,
            n_results=n_results,
            where=where,
        )

    def _chunk_id(self, doc_id: str, index: int) -> str:
        return f"{doc_id}:{index}"

    def _base_metadata(
        self,
        doc_id: str,
        metadata: DocumentMetadata,
        *,
        lang: str,
        doc_type: str,
    ) -> dict[str, str]:
        # Chroma metadata values must be scalars — join authors into one string.
        return {
            "doc_id": doc_id,
            "title": metadata.title,
            "authors": ", ".join(metadata.authors),
            "lang": lang,
            "type": doc_type,
        }
