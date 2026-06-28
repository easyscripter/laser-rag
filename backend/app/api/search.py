"""Semantic and metadata search endpoints (spec §6).

``POST /search`` runs the same cross-lingual retrieval pipeline as the chat
engine (detect language → translate → per-language query → merge/dedup/rank)
but returns ranked fragments directly instead of generating an answer.

``POST /search/metadata`` filters the relational ``documents`` table by
metadata fields (``lang``, ``type``, ``year``) and returns the matching
document list without any vector search.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import (
    get_current_user,
    get_document_repository,
    get_llm_client,
    get_retriever,
    get_tenant_id,
)
from app.auth.tokens import TokenClaims
from app.chat.retrieval import merge_dedup_rank
from app.core.constants import LLM_TASK_TRANSLATION
from app.db.document_repository import PostgreSQLDocumentRepository
from app.domain.chroma_indexer import ChromaIndexer
from app.domain.constants import RETRIEVAL_TOP_K
from app.domain.language import LANGUAGE_NAMES, detect_language, other_language
from app.llm.client import LangChainLLMClient
from app.prompts.chat import TRANSLATE_PROMPT
from app.schemas.documents import DocumentOut
from app.schemas.search import (
    MetadataSearchResponse,
    SearchHitOut,
    SearchMetadataRequest,
    SearchRequest,
    SearchResponse,
)

router = APIRouter(tags=["search"])


@router.post("/search", response_model=SearchResponse)
async def search(
    body: SearchRequest,
    retriever: ChromaIndexer = Depends(get_retriever),
    llm: LangChainLLMClient = Depends(get_llm_client),
    _: TokenClaims = Depends(get_current_user),
) -> SearchResponse:
    """Cross-lingual semantic search — returns ranked fragments (spec §6).

    Mirrors the retrieval step of the chat engine (spec §5 steps 1-4):
    detect the query language, translate to the complementary language, run
    both queries against the per-tenant Chroma collection, then merge/dedup/rank.
    No LLM answer generation is performed.
    """
    lang = detect_language(body.query)
    raw_translation = await llm.complete(
        TRANSLATE_PROMPT.format(
            target_language=LANGUAGE_NAMES[other_language(lang)],
            query=body.query,
        ),
        task=LLM_TASK_TRANSLATION,
    )
    translated = raw_translation.strip() or body.query

    hits = retriever.query(body.query, n_results=RETRIEVAL_TOP_K, where=body.filters)
    hits += retriever.query(translated, n_results=RETRIEVAL_TOP_K, where=body.filters)
    ranked = merge_dedup_rank(hits, limit=RETRIEVAL_TOP_K)

    return SearchResponse(
        hits=[
            SearchHitOut(
                chunk_id=h.chunk_id,
                doc_id=h.doc_id,
                text=h.text,
                distance=h.distance,
                metadata=h.metadata,
            )
            for h in ranked
        ]
    )


@router.post("/search/metadata", response_model=MetadataSearchResponse)
async def search_metadata(
    body: SearchMetadataRequest,
    tenant_id: str = Depends(get_tenant_id),
    repo: PostgreSQLDocumentRepository = Depends(get_document_repository),
) -> MetadataSearchResponse:
    """Metadata-filter search over the documents table (spec §6).

    Recognised filter keys: ``lang`` (``"en"``/``"ru"``), ``type``
    (``"article"``/``"review"``/``"monograph"``/``"thesis"``), ``year``
    (four-digit integer as a string).  Unknown keys are silently ignored.
    """
    records = await repo.filter_by_metadata(tenant_id=tenant_id, filters=body.filters)
    return MetadataSearchResponse(documents=[DocumentOut.from_record(r) for r in records])
