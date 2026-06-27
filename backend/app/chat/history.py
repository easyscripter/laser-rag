"""Conversation history window (spec §5 — last N turns, summarize on overflow)."""

from __future__ import annotations

from dataclasses import dataclass

from app.chat.models import MessageRecord
from app.core.constants import LLM_TASK_SUMMARY
from app.domain.protocols import LLMClient
from app.prompts.chat import SUMMARY_PROMPT


def _render_messages(messages: list[MessageRecord]) -> str:
    return "\n".join(f"{m.role.value.capitalize()}: {m.content}" for m in messages)


@dataclass(frozen=True, slots=True)
class HistoryContext:
    """The history fed to condense/generation: a summary of old turns + recent turns."""

    summary: str | None
    recent: list[MessageRecord]

    @property
    def is_empty(self) -> bool:
        return self.summary is None and not self.recent

    def render(self) -> str:
        """Render history as plain text for prompts (summary first, then turns)."""
        parts: list[str] = []
        if self.summary:
            parts.append(f"Summary of earlier conversation: {self.summary}")
        if self.recent:
            parts.append(_render_messages(self.recent))
        return "\n".join(parts)


async def build_history(
    messages: list[MessageRecord], *, window: int, llm: LLMClient
) -> HistoryContext:
    """Keep the last ``window`` messages; summarize anything older via the LLM."""
    if len(messages) <= window:
        return HistoryContext(summary=None, recent=messages)
    overflow = messages[:-window]
    recent = messages[-window:]
    summary = await llm.complete(
        SUMMARY_PROMPT.format(history=_render_messages(overflow)), task=LLM_TASK_SUMMARY
    )
    return HistoryContext(summary=summary.strip(), recent=recent)
