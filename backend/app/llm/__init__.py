"""LLM layer — ChatOpenAI factory and LLMClient implementation (Phase 3)."""

from __future__ import annotations

from app.core.config import Settings
from app.llm.client import LangChainLLMClient


def build_llm_client(settings: Settings) -> LangChainLLMClient:
    """Factory: construct a ready-to-use LangChainLLMClient from app settings."""
    return LangChainLLMClient(settings)


__all__ = ["LangChainLLMClient", "build_llm_client"]
