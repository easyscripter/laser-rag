"""Phase 6 — ChatEngine conversational RAG flow (spec §5, §7).

Behavior is driven through the public ``run`` async generator with in-test fakes
for the LLM, retriever, document catalog and conversation repository — no real
OpenAI/Chroma/Postgres. Focus: event order, citation numbering, the
rewritten-vs-original query split, condense skipping, and history summarization.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import AsyncIterator
from datetime import UTC, datetime

from app.chat.engine import ChatEngine
from app.chat.events import ChatEvent
from app.chat.models import ConversationRecord, DocumentRef, MessageRecord
from app.chat.repository import ConversationRepository
from app.chat.retrieval import merge_dedup_rank
from app.core.constants import (
    LLM_TASK_CONDENSE,
    LLM_TASK_SUMMARY,
    SSE_EVENT_CITATIONS,
    SSE_EVENT_DONE,
    SSE_EVENT_STATUS,
    SSE_EVENT_TOKEN,
)
from app.core.enums.chat import MessageRole
from app.domain.models import SearchHit


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class _FakeLLM:
    def __init__(self, *, tokens: tuple[str, ...] = ("Hello", " world")) -> None:
        self.complete_calls: list[tuple[str, str]] = []
        self.stream_prompts: list[str] = []
        self._tokens = tokens

    async def complete(self, prompt: str, *, task: str) -> str:
        self.complete_calls.append((task, prompt))
        if task == LLM_TASK_CONDENSE:
            return "REWRITTEN QUERY"
        if task == LLM_TASK_SUMMARY:
            return "SUMMARY OF OLD TURNS"
        return "TRANSLATED"  # translation task

    async def stream(self, prompt: str, *, task: str) -> AsyncIterator[str]:
        self.stream_prompts.append(prompt)
        for tok in self._tokens:
            yield tok


class _FakeRetriever:
    def __init__(self, results: dict[str, list[SearchHit]]) -> None:
        self.queries: list[str] = []
        self._results = results

    def query(
        self, text: str, *, n_results: int = 10, where: dict[str, str] | None = None
    ) -> list[SearchHit]:
        self.queries.append(text)
        return list(self._results.get(text, []))


class _FakeCatalog:
    def __init__(self, refs: dict[str, DocumentRef]) -> None:
        self._refs = refs

    async def get_by_ids(
        self, *, tenant_id: str, doc_ids: list[str]
    ) -> dict[str, DocumentRef]:
        return {d: self._refs[d] for d in doc_ids if d in self._refs}


class _FakeRepo(ConversationRepository):
    def __init__(self) -> None:
        self.conversations: dict[str, ConversationRecord] = {}
        self.messages: dict[str, list[MessageRecord]] = defaultdict(list)
        self._seq = 0

    async def create(
        self, *, tenant_id: str, user_id: str, title: str | None = None
    ) -> ConversationRecord:
        cid = f"c{len(self.conversations) + 1}"
        rec = ConversationRecord(id=cid, tenant_id=tenant_id, user_id=user_id, title=title)
        self.conversations[cid] = rec
        return rec

    async def get(
        self, conversation_id: str, *, tenant_id: str
    ) -> ConversationRecord | None:
        rec = self.conversations.get(conversation_id)
        return rec if rec is not None and rec.tenant_id == tenant_id else None

    async def list_messages(self, conversation_id: str) -> list[MessageRecord]:
        return list(self.messages[conversation_id])

    async def add_message(
        self,
        *,
        conversation_id: str,
        role: MessageRole,
        content: str,
        citations_json: dict[str, object] | None = None,
    ) -> MessageRecord:
        self._seq += 1
        rec = MessageRecord(
            id=f"m{self._seq}",
            conversation_id=conversation_id,
            role=role,
            content=content,
            created_at=datetime.now(UTC),
            citations_json=citations_json,
        )
        self.messages[conversation_id].append(rec)
        return rec


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _hit(chunk_id: str, doc_id: str, distance: float, text: str = "frag") -> SearchHit:
    return SearchHit(
        chunk_id=chunk_id,
        doc_id=doc_id,
        text=text,
        distance=distance,
        metadata={"title": f"meta-{doc_id}", "authors": "X, Y"},
    )


def _ref(doc_id: str) -> DocumentRef:
    return DocumentRef(
        doc_id=doc_id, title=f"Title {doc_id}", authors=["A. Author"], year=2025,
        journal="J", doi=None, url=None,
    )


def _engine(llm: _FakeLLM, retriever: _FakeRetriever, repo: _FakeRepo, *, window: int = 8) -> ChatEngine:
    return ChatEngine(
        llm=llm,
        retriever=retriever,
        catalog=_FakeCatalog({"A": _ref("A"), "B": _ref("B"), "C": _ref("C")}),
        repository=repo,
        history_window=window,
    )


async def _collect(engine: ChatEngine, conversation: ConversationRecord, query: str) -> list[ChatEvent]:
    return [e async for e in engine.run(conversation=conversation, query=query)]


# ---------------------------------------------------------------------------
# Cycle 1 — pure merge/dedup/rank
# ---------------------------------------------------------------------------


def test_merge_dedup_rank_dedups_by_chunk_keeps_min_distance_and_orders() -> None:
    merged = merge_dedup_rank(
        [_hit("a0", "A", 0.4), _hit("b0", "B", 0.2), _hit("a0", "A", 0.1)],
        limit=10,
    )
    assert [h.chunk_id for h in merged] == ["a0", "b0"]  # a0 kept at 0.1, before b0
    assert merged[0].distance == 0.1


def test_merge_dedup_rank_caps_to_limit() -> None:
    hits = [_hit(f"c{i}", "A", 0.1 * i) for i in range(5)]
    assert len(merge_dedup_rank(hits, limit=3)) == 3


# ---------------------------------------------------------------------------
# Cycle 2 — happy-path event order + citations
# ---------------------------------------------------------------------------


async def test_run_emits_events_in_spec_order_with_numbered_citations() -> None:
    llm = _FakeLLM(tokens=("Ans", "wer"))
    retriever = _FakeRetriever(
        {
            "What is cladding?": [_hit("a0", "A", 0.2), _hit("b0", "B", 0.3)],
            "TRANSLATED": [_hit("a0", "A", 0.1), _hit("c0", "C", 0.25)],
        }
    )
    repo = _FakeRepo()
    conv = await repo.create(tenant_id="default", user_id="u1")
    engine = _engine(llm, retriever, repo)

    events = await _collect(engine, conv, "What is cladding?")

    names = [e.event for e in events]
    assert names[0] == SSE_EVENT_STATUS and events[0].data == {"stage": "retrieving"}
    assert names[1] == SSE_EVENT_STATUS and events[1].data == {"stage": "generating"}
    assert names[2] == SSE_EVENT_TOKEN and names[3] == SSE_EVENT_TOKEN
    assert names[-2] == SSE_EVENT_CITATIONS
    assert names[-1] == SSE_EVENT_DONE

    citations = events[-2].data
    assert isinstance(citations, list)
    # merged order by distance: A@0.1, C@0.25, B@0.3 → numbered 1,2,3
    assert [(c["n"], c["doc_id"]) for c in citations] == [(1, "A"), (2, "C"), (3, "B")]
    assert citations[0]["chunk_ids"] == ["a0"]
    assert citations[0]["title"] == "Title A"  # from catalog, not chroma metadata


async def test_run_persists_user_then_assistant_with_citations() -> None:
    llm = _FakeLLM(tokens=("Hi",))
    retriever = _FakeRetriever({"Q": [_hit("a0", "A", 0.1)], "TRANSLATED": []})
    repo = _FakeRepo()
    conv = await repo.create(tenant_id="default", user_id="u1")
    engine = _engine(llm, retriever, repo)

    events = await _collect(engine, conv, "Q")

    stored = repo.messages[conv.id]
    assert [m.role for m in stored] == [MessageRole.USER, MessageRole.ASSISTANT]
    assert stored[0].content == "Q"
    assert stored[1].content == "Hi"
    assert stored[1].citations_json is not None and "citations" in stored[1].citations_json
    assert events[-1].data == {"message_id": stored[1].id}


# ---------------------------------------------------------------------------
# Cycle 3 — rewritten query for retrieval, original for generation
# ---------------------------------------------------------------------------


async def test_retrieval_uses_rewritten_query_generation_uses_original() -> None:
    llm = _FakeLLM(tokens=("x",))
    retriever = _FakeRetriever({"REWRITTEN QUERY": [_hit("a0", "A", 0.1)], "TRANSLATED": []})
    repo = _FakeRepo()
    conv = await repo.create(tenant_id="default", user_id="u1")
    # prior turns → history is non-empty → condense runs
    await repo.add_message(conversation_id=conv.id, role=MessageRole.USER, content="earlier q")
    await repo.add_message(conversation_id=conv.id, role=MessageRole.ASSISTANT, content="earlier a")
    engine = _engine(llm, retriever, repo)

    await _collect(engine, conv, "ORIGINAL FOLLOWUP")

    # retrieval issued the rewritten (condensed) query, not the raw follow-up
    assert "REWRITTEN QUERY" in retriever.queries
    assert "ORIGINAL FOLLOWUP" not in retriever.queries
    assert any(task == LLM_TASK_CONDENSE for task, _ in llm.complete_calls)
    # generation prompt carries the ORIGINAL question, not the rewrite
    gen_prompt = llm.stream_prompts[0]
    assert "ORIGINAL FOLLOWUP" in gen_prompt
    assert "REWRITTEN QUERY" not in gen_prompt


async def test_no_history_skips_condense_and_retrieves_with_original() -> None:
    llm = _FakeLLM(tokens=("x",))
    retriever = _FakeRetriever({"FIRST QUESTION": [_hit("a0", "A", 0.1)], "TRANSLATED": []})
    repo = _FakeRepo()
    conv = await repo.create(tenant_id="default", user_id="u1")
    engine = _engine(llm, retriever, repo)

    await _collect(engine, conv, "FIRST QUESTION")

    assert "FIRST QUESTION" in retriever.queries
    assert all(task != LLM_TASK_CONDENSE for task, _ in llm.complete_calls)


# ---------------------------------------------------------------------------
# Cycle 4 — history overflow is summarized
# ---------------------------------------------------------------------------


async def test_history_overflow_is_summarized() -> None:
    llm = _FakeLLM(tokens=("x",))
    retriever = _FakeRetriever({"REWRITTEN QUERY": [], "TRANSLATED": []})
    repo = _FakeRepo()
    conv = await repo.create(tenant_id="default", user_id="u1")
    for i in range(6):  # window=2 → 4 older messages overflow
        await repo.add_message(conversation_id=conv.id, role=MessageRole.USER, content=f"m{i}")
    engine = _engine(llm, retriever, repo, window=2)

    await _collect(engine, conv, "new question")

    assert any(task == LLM_TASK_SUMMARY for task, _ in llm.complete_calls)
