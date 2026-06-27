"""Conversation + chat endpoints (spec §5, §6, §7).

``POST /conversations`` opens a session. ``POST /conversations/{id}/messages``
runs the conversational RAG flow and streams the answer back as Server-Sent
Events (``status`` → ``token`` → ``citations`` → ``done``).
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, status
from sse_starlette.sse import EventSourceResponse

from app.api.deps import get_chat_engine, get_conversation_repository, get_current_user
from app.auth.tokens import TokenClaims
from app.chat.engine import ChatEngine
from app.chat.repository import ConversationRepository
from app.core.logging import get_logger
from app.schemas.chat import (
    ConversationCreated,
    CreateConversationRequest,
    MessageRequest,
)

logger = get_logger(__name__)

router = APIRouter(tags=["chat"])


@router.post(
    "/conversations",
    status_code=status.HTTP_201_CREATED,
    response_model=ConversationCreated,
)
async def create_conversation(
    body: CreateConversationRequest,
    user: TokenClaims = Depends(get_current_user),
    repo: ConversationRepository = Depends(get_conversation_repository),
) -> ConversationCreated:
    """Open a new conversation owned by the authenticated user (spec §6)."""
    conversation = await repo.create(
        tenant_id=user.tenant_id, user_id=user.sub, title=body.title
    )
    logger.info("conversation.created", conversation_id=conversation.id)
    return ConversationCreated(conversation_id=conversation.id)


@router.post("/conversations/{conversation_id}/messages")
async def post_message(
    conversation_id: str,
    body: MessageRequest,
    user: TokenClaims = Depends(get_current_user),
    repo: ConversationRepository = Depends(get_conversation_repository),
    engine: ChatEngine = Depends(get_chat_engine),
) -> EventSourceResponse:
    """Run conversational RAG and stream the answer as SSE (spec §5, §7)."""
    conversation = await repo.get(conversation_id, tenant_id=user.tenant_id)
    if conversation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"unknown conversation: {conversation_id}",
        )

    async def event_stream() -> AsyncIterator[dict[str, str]]:
        async for event in engine.run(
            conversation=conversation, query=body.query, filters=body.filters
        ):
            yield {"event": event.event, "data": json.dumps(event.data, ensure_ascii=False)}

    return EventSourceResponse(event_stream())
