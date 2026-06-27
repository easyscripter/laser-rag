"""Chat enumerations (spec §8 messages)."""

from __future__ import annotations

from enum import StrEnum


class MessageRole(StrEnum):
    """Author of a chat message."""

    USER = "user"
    ASSISTANT = "assistant"
