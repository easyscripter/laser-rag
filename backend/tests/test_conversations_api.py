"""Phase 6 — conversations + chat SSE endpoints (spec §6, §7).

TestClient with in-memory fakes (no lifespan/Redis/Chroma/Postgres): the chat
engine and conversation repository are swapped via dependency_overrides, and the
current user is a reader (chat is reader-capable).
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime

import pytest
from app.api.deps import get_chat_engine, get_conversation_repository, get_current_user
from app.auth.tokens import TokenClaims
from app.chat.events import (
    ChatEvent,
    citations_event,
    done_event,
    status_event,
    token_event,
)
from app.chat.models import Citation, ConversationRecord, MessageRecord
from app.chat.repository import ConversationRepository
from app.core.constants import TOKEN_TYPE_ACCESS
from app.core.enums.auth import Role
from app.core.enums.chat import MessageRole
from app.main import create_app
from fastapi.testclient import TestClient


class _FakeRepo(ConversationRepository):
    def __init__(self) -> None:
        self.conversations: dict[str, ConversationRecord] = {}
        self.messages: dict[str, list[MessageRecord]] = defaultdict(list)

    def seed(self, conv: ConversationRecord) -> None:
        self.conversations[conv.id] = conv

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
        rec = MessageRecord(
            id="m1", conversation_id=conversation_id, role=role, content=content,
            created_at=datetime.now(UTC), citations_json=citations_json,
        )
        self.messages[conversation_id].append(rec)
        return rec


class _FakeEngine:
    async def run(
        self,
        *,
        conversation: ConversationRecord,
        query: str,
        filters: dict[str, str] | None = None,
    ) -> AsyncIterator[ChatEvent]:
        yield status_event("retrieving")
        yield status_event("generating")
        yield token_event("Hello")
        yield citations_event(
            [Citation(n=1, doc_id="d1", title="T", authors=["A"], chunk_ids=["d1:0"])]
        )
        yield done_event("m1")


def _reader() -> TokenClaims:
    return TokenClaims(
        sub="u-rdr", username="rdr", role=Role.READER, tenant_id="default",
        type=TOKEN_TYPE_ACCESS,
    )


@pytest.fixture
def repo() -> _FakeRepo:
    return _FakeRepo()


@pytest.fixture
def client(repo: _FakeRepo) -> Iterator[TestClient]:
    app = create_app()
    app.dependency_overrides[get_conversation_repository] = lambda: repo
    app.dependency_overrides[get_chat_engine] = _FakeEngine
    app.dependency_overrides[get_current_user] = _reader
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_create_conversation_returns_201_with_id(client: TestClient, repo: _FakeRepo) -> None:
    resp = client.post("/api/v1/conversations", json={"title": "Cladding chat"})

    assert resp.status_code == 201
    cid = resp.json()["conversation_id"]
    assert cid in repo.conversations
    assert repo.conversations[cid].user_id == "u-rdr"


def test_post_message_streams_sse_events_in_order(client: TestClient, repo: _FakeRepo) -> None:
    repo.seed(ConversationRecord(id="c1", tenant_id="default", user_id="u-rdr"))

    resp = client.post(
        "/api/v1/conversations/c1/messages", json={"query": "What is cladding?"}
    )

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")
    body = resp.text
    # events arrive in the spec order
    order = [
        body.index("event: status"),
        body.index("event: token"),
        body.index("event: citations"),
        body.index("event: done"),
    ]
    assert order == sorted(order)
    assert '"stage": "retrieving"' in body
    assert '"message_id": "m1"' in body


def test_post_message_unknown_conversation_returns_404(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/conversations/missing/messages", json={"query": "hi"}
    )
    assert resp.status_code == 404


def test_chat_endpoints_require_auth(repo: _FakeRepo) -> None:
    app = create_app()
    app.dependency_overrides[get_conversation_repository] = lambda: repo
    app.dependency_overrides[get_chat_engine] = _FakeEngine
    # no get_current_user override → real bearer extraction runs
    client = TestClient(app)
    assert client.post("/api/v1/conversations", json={}).status_code == 401
    assert client.post(
        "/api/v1/conversations/c1/messages", json={"query": "hi"}
    ).status_code == 401
