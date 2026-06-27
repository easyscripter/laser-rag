"""LangChain-backed LLMClient implementation (Phase 3).

Implements the LLMClient Protocol from app.domain.protocols via ChatOpenAI.
Task labels select the model tier; the final attempt always falls back to
model_fallback. Raises LLMClientError after MAX_ATTEMPTS consecutive failures.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI

from app.core.config import Settings
from app.core.constants import (
    LLM_TASK_CONDENSE,
    LLM_TASK_GENERATION,
    LLM_TASK_SUMMARY,
    LLM_TASK_TRANSLATION,
)
from app.errors.domain import LLMClientError

MAX_ATTEMPTS: int = 3

# Tasks served by the fast model (generation, translation, condense, summary,
# article metadata). Monograph metadata uses the long-context model; anything
# unrecognized falls back to the reserve model.
_FAST_TASKS: frozenset[str] = frozenset(
    {
        "metadata_fast",
        LLM_TASK_GENERATION,
        LLM_TASK_TRANSLATION,
        LLM_TASK_CONDENSE,
        LLM_TASK_SUMMARY,
    }
)


class LangChainLLMClient:
    """Implements LLMClient Protocol using LangChain's ChatOpenAI.

    Routing:
      metadata_fast  → settings.model_fast
      metadata_long  → settings.model_long_ctx
      (anything else) → settings.model_fallback

    Retry: MAX_ATTEMPTS total. The last attempt always uses model_fallback.
    Raises LLMClientError if every attempt raises an exception.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def complete(self, prompt: str, *, task: str) -> str:
        last_exc: Exception = RuntimeError("no attempts made")
        for attempt in range(MAX_ATTEMPTS):
            model = self._model_for(task, attempt)
            chat = ChatOpenAI(
                model=model,
                base_url=self._settings.llm_base_url,
                api_key=self._settings.llm_api_key,
            )
            try:
                result = await chat.ainvoke([HumanMessage(content=prompt)])
                return str(result.content)
            except Exception as exc:
                last_exc = exc
        raise LLMClientError(
            f"LLM failed after {MAX_ATTEMPTS} attempts: {last_exc}"
        ) from last_exc

    async def stream(self, prompt: str, *, task: str) -> AsyncIterator[str]:
        """Stream the completion as text deltas (spec §7). Single attempt, no fallback.

        Streaming powers the live SSE answer; retry/fallback would replay tokens
        the client has already received, so generation uses one attempt only.
        """
        chat = ChatOpenAI(
            model=self._model_for(task, 0),
            base_url=self._settings.llm_base_url,
            api_key=self._settings.llm_api_key,
            streaming=True,
        )
        async for chunk in chat.astream([HumanMessage(content=prompt)]):
            text = str(chunk.content)
            if text:
                yield text

    def _model_for(self, task: str, attempt: int) -> str:
        if attempt == MAX_ATTEMPTS - 1:
            return self._settings.model_fallback
        if task == "metadata_long":
            return self._settings.model_long_ctx
        if task in _FAST_TASKS:
            return self._settings.model_fast
        return self._settings.model_fallback
