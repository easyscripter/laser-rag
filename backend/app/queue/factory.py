"""Wiring for the async indexing path (spec §4).

Builds a :class:`~app.domain.pipeline.RAGPipeline` from the real Phase 2/3
collaborators (sentence-transformers + ChromaDB + Postgres + the LLM client) for
a given tenant. Kept out of the domain layer so the pipeline stays mock-friendly.
"""

from __future__ import annotations

from app.core.config import get_settings
from app.db.chroma_backend import make_chroma_backend
from app.db.embedder import SentenceTransformerEmbedder
from app.db.pg_manager import PostgreSQLDatabaseManager
from app.domain.chroma_indexer import ChromaIndexer
from app.domain.document_analyzer import DocumentAnalyzer
from app.domain.document_splitter import DocumentSplitter
from app.domain.metadata_extractor import MetadataExtractor
from app.domain.pipeline import RAGPipeline
from app.domain.text_extractor import TextExtractor
from app.llm import build_llm_client
from app.queue.runner import StageRunner


def build_pipeline(tenant_id: str) -> RAGPipeline:
    """Construct a production RAGPipeline for ``tenant_id`` (per-tenant collection)."""
    settings = get_settings()
    return RAGPipeline(
        extractor=TextExtractor(),
        analyzer=DocumentAnalyzer(),
        metadata_extractor=MetadataExtractor(build_llm_client(settings)),
        splitter=DocumentSplitter(),
        indexer=ChromaIndexer(
            SentenceTransformerEmbedder(), make_chroma_backend(tenant_id)
        ),
        database=PostgreSQLDatabaseManager(),
    )


def build_runner(tenant_id: str) -> StageRunner:
    """Construct a StageRunner over a production pipeline for ``tenant_id``."""
    return StageRunner(pipeline=build_pipeline(tenant_id))
