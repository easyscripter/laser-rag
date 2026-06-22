"""LangChain-backed LLMClient implementation (Phase 3).

Implements the LLMClient Protocol from app.domain.protocols via ChatOpenAI.
Task labels select the model tier; the final attempt always falls back to
model_fallback. Raises LLMClientError after MAX_ATTEMPTS consecutive failures.
"""

from __future__ import annotations

from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI

from app.core.config import Settings
from app.errors.domain import LLMClientError

MAX_ATTEMPTS: int = 3


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

    def _model_for(self, task: str, attempt: int) -> str:
        if attempt == MAX_ATTEMPTS - 1:
            return self._settings.model_fallback
        if task == "metadata_fast":
            return self._settings.model_fast
        if task == "metadata_long":
            return self._settings.model_long_ctx
        return self._settings.model_fallback
