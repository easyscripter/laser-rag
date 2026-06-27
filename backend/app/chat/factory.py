"""Wiring for the conversational RAG path (spec §5).

Builds a :class:`~app.chat.engine.ChatEngine` from the real collaborators
(LLM client + per-tenant Chroma retriever + Postgres catalog/repository). Kept
out of the engine so the engine stays mock-friendly.
"""

from __future__ import annotations

from app.chat.engine import ChatEngine
from app.core.config import get_settings
from app.db.chroma_backend import make_chroma_backend
from app.db.conversation_repository import PostgreSQLConversationRepository
from app.db.document_catalog import PostgreSQLDocumentCatalog
from app.db.embedder import SentenceTransformerEmbedder
from app.domain.chroma_indexer import ChromaIndexer
from app.llm import build_llm_client


def build_chat_engine(tenant_id: str) -> ChatEngine:
    """Construct a production ChatEngine for ``tenant_id`` (per-tenant collection)."""
    settings = get_settings()
    return ChatEngine(
        llm=build_llm_client(settings),
        retriever=ChromaIndexer(
            SentenceTransformerEmbedder(), make_chroma_backend(tenant_id)
        ),
        catalog=PostgreSQLDocumentCatalog(),
        repository=PostgreSQLConversationRepository(),
        history_window=settings.chat_history_window,
    )
