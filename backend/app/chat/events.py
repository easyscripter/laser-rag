"""SSE event objects for the chat stream (spec §7).

The engine yields :class:`ChatEvent`s; the API layer serializes ``data`` to JSON
and relays them as Server-Sent Events.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.chat.models import Citation
from app.core.constants import (
    SSE_EVENT_CITATIONS,
    SSE_EVENT_DONE,
    SSE_EVENT_STATUS,
    SSE_EVENT_TOKEN,
)

EventData = dict[str, object] | list[dict[str, object]]


@dataclass(frozen=True, slots=True)
class ChatEvent:
    """A named SSE event with a JSON-serializable payload."""

    event: str
    data: EventData


def status_event(stage: str) -> ChatEvent:
    return ChatEvent(event=SSE_EVENT_STATUS, data={"stage": stage})


def token_event(text: str) -> ChatEvent:
    return ChatEvent(event=SSE_EVENT_TOKEN, data={"text": text})


def citations_event(citations: list[Citation]) -> ChatEvent:
    return ChatEvent(
        event=SSE_EVENT_CITATIONS,
        data=[c.model_dump() for c in citations],
    )


def done_event(message_id: str) -> ChatEvent:
    return ChatEvent(event=SSE_EVENT_DONE, data={"message_id": message_id})
