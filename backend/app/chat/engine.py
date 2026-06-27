"""ChatEngine — conversational RAG orchestration (spec §5, §7).

Runs the query flow and yields SSE events as it goes:

  0. condense the follow-up into a standalone query (only when history exists)
  1. detect the query language; 2. translate it to the other language
  3. retrieve per language; 4. merge + dedup + rank
  5. stream a grounded answer (ORIGINAL query + history); 6. emit citations

Retrieval uses the *rewritten* query; generation uses the *original* query plus
history (spec §5). Collaborators arrive pre-built so the engine stays testable.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from app.chat.catalog import DocumentCatalog
from app.chat.events import (
    ChatEvent,
    citations_event,
    done_event,
    status_event,
    token_event,
)
from app.chat.history import HistoryContext, build_history
from app.chat.models import Citation, ConversationRecord, DocumentRef
from app.chat.repository import ConversationRepository
from app.chat.retrieval import (
    Retriever,
    SourceGroup,
    group_sources,
    merge_dedup_rank,
    render_sources_block,
)
from app.core.constants import (
    LLM_TASK_CONDENSE,
    LLM_TASK_GENERATION,
    LLM_TASK_TRANSLATION,
    SSE_STAGE_GENERATING,
    SSE_STAGE_RETRIEVING,
)
from app.core.enums.chat import MessageRole
from app.domain.constants import RETRIEVAL_TOP_K
from app.domain.enums import Language
from app.domain.language import LANGUAGE_NAMES, detect_language, other_language
from app.domain.models import SearchHit
from app.domain.protocols import LLMClient
from app.prompts.chat import ANSWER_PROMPT, CONDENSE_PROMPT, TRANSLATE_PROMPT


class ChatEngine:
    """Coordinates condense, cross-lingual retrieval, and streamed generation."""

    def __init__(
        self,
        *,
        llm: LLMClient,
        retriever: Retriever,
        catalog: DocumentCatalog,
        repository: ConversationRepository,
        history_window: int,
    ) -> None:
        self._llm = llm
        self._retriever = retriever
        self._catalog = catalog
        self._repository = repository
        self._history_window = history_window

    async def run(
        self,
        *,
        conversation: ConversationRecord,
        query: str,
        filters: dict[str, str] | None = None,
    ) -> AsyncIterator[ChatEvent]:
        """Drive the query flow for ``query`` and yield SSE events (spec §5, §7)."""
        history = await build_history(
            await self._repository.list_messages(conversation.id),
            window=self._history_window,
            llm=self._llm,
        )
        standalone = await self._condense(history, query)

        yield status_event(SSE_STAGE_RETRIEVING)
        ranked = await self._retrieve(standalone, filters)
        groups = group_sources(ranked)
        citations = await self._build_citations(conversation.tenant_id, groups)

        # Persist the user turn before generating (so the turn is durable even if
        # generation is interrupted).
        await self._repository.add_message(
            conversation_id=conversation.id, role=MessageRole.USER, content=query
        )

        yield status_event(SSE_STAGE_GENERATING)
        prompt = ANSWER_PROMPT.format(
            history_block=self._history_block(history),
            sources=render_sources_block(ranked, groups),
            question=query,  # generation uses the ORIGINAL query (spec §5)
        )
        answer_parts: list[str] = []
        async for delta in self._llm.stream(prompt, task=LLM_TASK_GENERATION):
            answer_parts.append(delta)
            yield token_event(delta)

        message = await self._repository.add_message(
            conversation_id=conversation.id,
            role=MessageRole.ASSISTANT,
            content="".join(answer_parts),
            citations_json={"citations": [c.model_dump() for c in citations]},
        )

        yield citations_event(citations)
        yield done_event(message.id)

    # --- steps -------------------------------------------------------------

    async def _condense(self, history: HistoryContext, query: str) -> str:
        """Rewrite the follow-up into a standalone query — only when history exists."""
        if history.is_empty:
            return query
        rewritten = await self._llm.complete(
            CONDENSE_PROMPT.format(history=history.render(), question=query),
            task=LLM_TASK_CONDENSE,
        )
        return rewritten.strip() or query

    async def _retrieve(
        self, standalone: str, filters: dict[str, str] | None
    ) -> list[SearchHit]:
        lang = detect_language(standalone)
        translated = await self._translate(standalone, other_language(lang))
        hits = self._retriever.query(standalone, n_results=RETRIEVAL_TOP_K, where=filters)
        hits += self._retriever.query(translated, n_results=RETRIEVAL_TOP_K, where=filters)
        return merge_dedup_rank(hits, limit=RETRIEVAL_TOP_K)

    async def _translate(self, text: str, target: Language) -> str:
        translated = await self._llm.complete(
            TRANSLATE_PROMPT.format(target_language=LANGUAGE_NAMES[target], query=text),
            task=LLM_TASK_TRANSLATION,
        )
        return translated.strip() or text

    async def _build_citations(
        self, tenant_id: str, groups: list[SourceGroup]
    ) -> list[Citation]:
        refs = await self._catalog.get_by_ids(
            tenant_id=tenant_id, doc_ids=[g.doc_id for g in groups]
        )
        return [self._citation_for(g, refs.get(g.doc_id)) for g in groups]

    def _citation_for(self, group: SourceGroup, ref: DocumentRef | None) -> Citation:
        chunk_ids = [h.chunk_id for h in group.hits]
        if ref is not None:
            return Citation(
                n=group.n,
                doc_id=group.doc_id,
                title=ref.title,
                authors=ref.authors,
                year=ref.year,
                journal=ref.journal,
                doi=ref.doi,
                url=ref.url,
                chunk_ids=chunk_ids,
            )
        # Fallback to the metadata carried on the hit when the doc row is missing.
        meta = group.hits[0].metadata
        authors = [a.strip() for a in meta.get("authors", "").split(",") if a.strip()]
        return Citation(
            n=group.n,
            doc_id=group.doc_id,
            title=meta.get("title", ""),
            authors=authors,
            chunk_ids=chunk_ids,
        )

    def _history_block(self, history: HistoryContext) -> str:
        if history.is_empty:
            return ""
        return f"--- CONVERSATION SO FAR ---\n{history.render()}\n\n"
