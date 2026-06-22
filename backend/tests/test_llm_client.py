"""TDD tests for LangChainLLMClient — Phase 3.

Cycles:
  1. Task→model routing (metadata_fast/long, unknown → fallback)
  2. Retry on transport failure — returns on eventual success
  3. All attempts exhausted → LLMClientError; final attempt uses model_fallback
  4. MetadataExtractor integration smoke with LangChainLLMClient
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.core.config import Settings
from app.domain.enums import DocumentType
from app.domain.metadata_extractor import MetadataExtractor
from app.errors.domain import LLMClientError
from app.llm.client import LangChainLLMClient

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _settings() -> Settings:
    return Settings(
        llm_api_key="test-key",
        llm_base_url="http://test-llm/v1",
        model_fast="fast-model",
        model_long_ctx="long-model",
        model_fallback="fallback-model",
    )


def _ai_message(content: str) -> MagicMock:
    msg = MagicMock()
    msg.content = content
    return msg


# ---------------------------------------------------------------------------
# Cycle 1 — task→model routing
# ---------------------------------------------------------------------------


@patch("app.llm.client.ChatOpenAI")
async def test_routes_metadata_fast_to_fast_model(mock_cls: MagicMock) -> None:
    mock_inst = MagicMock()
    mock_inst.ainvoke = AsyncMock(return_value=_ai_message("response"))
    mock_cls.return_value = mock_inst

    client = LangChainLLMClient(_settings())
    result = await client.complete("prompt", task="metadata_fast")

    assert result == "response"
    assert mock_cls.call_args.kwargs["model"] == "fast-model"


@patch("app.llm.client.ChatOpenAI")
async def test_routes_metadata_long_to_long_ctx_model(mock_cls: MagicMock) -> None:
    mock_inst = MagicMock()
    mock_inst.ainvoke = AsyncMock(return_value=_ai_message("response"))
    mock_cls.return_value = mock_inst

    client = LangChainLLMClient(_settings())
    await client.complete("prompt", task="metadata_long")

    assert mock_cls.call_args.kwargs["model"] == "long-model"


@patch("app.llm.client.ChatOpenAI")
async def test_unknown_task_uses_fallback_model(mock_cls: MagicMock) -> None:
    mock_inst = MagicMock()
    mock_inst.ainvoke = AsyncMock(return_value=_ai_message("response"))
    mock_cls.return_value = mock_inst

    client = LangChainLLMClient(_settings())
    await client.complete("prompt", task="unknown_task")

    assert mock_cls.call_args.kwargs["model"] == "fallback-model"


# ---------------------------------------------------------------------------
# Cycle 2 — retry on transport failure
# ---------------------------------------------------------------------------


@patch("app.llm.client.ChatOpenAI")
async def test_retries_on_failure_returns_on_success(mock_cls: MagicMock) -> None:
    mock_inst = MagicMock()
    mock_inst.ainvoke = AsyncMock(
        side_effect=[Exception("timeout"), Exception("timeout"), _ai_message("ok")]
    )
    mock_cls.return_value = mock_inst

    result = await LangChainLLMClient(_settings()).complete("p", task="metadata_fast")

    assert result == "ok"
    assert mock_inst.ainvoke.call_count == 3


# ---------------------------------------------------------------------------
# Cycle 3 — exhausted retries
# ---------------------------------------------------------------------------


@patch("app.llm.client.ChatOpenAI")
async def test_final_attempt_uses_fallback_model(mock_cls: MagicMock) -> None:
    """Third (last) attempt must always route to model_fallback regardless of task."""
    models: list[str] = []

    def factory(**kwargs: object) -> MagicMock:
        models.append(str(kwargs.get("model", "")))
        inst = MagicMock()
        inst.ainvoke = AsyncMock(side_effect=Exception("fail"))
        return inst

    mock_cls.side_effect = factory

    with pytest.raises(LLMClientError):
        await LangChainLLMClient(_settings()).complete("p", task="metadata_fast")

    assert len(models) == 3
    assert models[-1] == "fallback-model"


@patch("app.llm.client.ChatOpenAI")
async def test_raises_llm_client_error_after_all_attempts_fail(mock_cls: MagicMock) -> None:
    mock_inst = MagicMock()
    mock_inst.ainvoke = AsyncMock(side_effect=Exception("API down"))
    mock_cls.return_value = mock_inst

    with pytest.raises(LLMClientError, match="3 attempts"):
        await LangChainLLMClient(_settings()).complete("p", task="metadata_fast")

    assert mock_inst.ainvoke.call_count == 3


# ---------------------------------------------------------------------------
# Cycle 4 — MetadataExtractor integration smoke
# ---------------------------------------------------------------------------


@patch("app.llm.client.ChatOpenAI")
async def test_metadata_extractor_wired_with_langchain_client(mock_cls: MagicMock) -> None:
    """LangChainLLMClient satisfies LLMClient Protocol — MetadataExtractor accepts it."""
    metadata_json = json.dumps(
        {
            "title": "Laser Cladding Study",
            "authors": ["A. Petrov"],
            "abstract": "Abstract text.",
            "keywords": ["laser", "cladding"],
            "doi": None,
            "url": None,
            "year": 2024,
            "journal": "Surface Engineering",
        }
    )
    mock_inst = MagicMock()
    mock_inst.ainvoke = AsyncMock(return_value=_ai_message(metadata_json))
    mock_cls.return_value = mock_inst

    client = LangChainLLMClient(_settings())
    extractor = MetadataExtractor(client)
    result = await extractor.extract(
        "Some document text about laser cladding.",
        doc_type=DocumentType.ARTICLE,
        filename="study.pdf",
    )

    assert result.title == "Laser Cladding Study"
    assert result.authors == ["A. Petrov"]
    assert result.year == 2024
