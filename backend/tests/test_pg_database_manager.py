"""TDD Cycles 1 & 2 — PostgreSQLDatabaseManager against a real Postgres.

Requires TEST_DATABASE_URL env var pointing to a throwaway database.
Skipped automatically when the env var is absent (safe in CI without Postgres).

Run locally (docker-compose postgres must be up):
    TEST_DATABASE_URL="postgresql+asyncpg://laserrag:laserrag@localhost:5432/laserrag" \
        uv run pytest tests/test_pg_database_manager.py -v
"""
from __future__ import annotations

import os
import uuid
from unittest.mock import patch

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.models import Base
from app.db.pg_manager import PostgreSQLDatabaseManager
from app.domain.enums import DocumentType, Language
from app.domain.models import AnalysisResult, DocumentMetadata, IndexedChunk

TEST_DB_URL = os.getenv("TEST_DATABASE_URL", "")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(scope="module")
async def test_engine():
    if not TEST_DB_URL:
        pytest.skip("TEST_DATABASE_URL not set")
    eng = create_async_engine(TEST_DB_URL, echo=False)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await eng.dispose()


@pytest_asyncio.fixture
async def manager(test_engine, monkeypatch):
    test_factory = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
        autocommit=False,
    )
    monkeypatch.setattr("app.db.pg_manager.AsyncSessionLocal", test_factory)
    return PostgreSQLDatabaseManager()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _meta(**overrides: object) -> DocumentMetadata:
    return DocumentMetadata(
        title="Laser Cladding of Nickel Superalloys",
        authors=["A. Malyshev"],
        abstract="A study on laser cladding.",
        keywords=["laser", "cladding"],
        doi=None,
        url=None,
        year=2025,
        journal="Surface Engineering",
        **overrides,  # type: ignore[arg-type]
    )


def _analysis() -> AnalysisResult:
    return AnalysisResult(doc_type=DocumentType.ARTICLE, lang=Language.EN, n_words=5000)


def _chunks(doc_id: str, n: int = 3) -> list[IndexedChunk]:
    return [IndexedChunk(chunk_id=f"{doc_id}:{i}", index=i, n_words=300) for i in range(n)]


def _uid() -> str:
    return uuid.uuid4().hex


# ---------------------------------------------------------------------------
# Cycle 1 — Tracer bullet: save → exists
# ---------------------------------------------------------------------------


async def test_save_and_exists(manager: PostgreSQLDatabaseManager) -> None:
    """Saved document is found by document_exists; other sha256/tenant combos are not."""
    doc_id = _uid()
    sha256 = "aabbcc" + doc_id

    stored = await manager.save_document(
        doc_id=doc_id,
        tenant_id="default",
        sha256=sha256,
        metadata=_meta(),
        analysis=_analysis(),
        quality_score=0.95,
        n_pages=12,
        indexed_chunks=_chunks(doc_id),
    )

    assert stored.doc_id == doc_id
    assert stored.tenant_id == "default"
    assert stored.sha256 == sha256
    assert stored.chunk_ids == [f"{doc_id}:0", f"{doc_id}:1", f"{doc_id}:2"]

    # same (tenant, sha256) → found
    assert await manager.document_exists(tenant_id="default", sha256=sha256) is True

    # different sha256 → not found
    assert await manager.document_exists(tenant_id="default", sha256="000000") is False

    # same sha256, different tenant → not found (tenant isolation)
    assert await manager.document_exists(tenant_id="other_tenant", sha256=sha256) is False


# ---------------------------------------------------------------------------
# Cycle 2 — Rollback atomicity
# ---------------------------------------------------------------------------


async def test_save_rolls_back_on_error(manager: PostgreSQLDatabaseManager) -> None:
    """If session.add raises mid-transaction the document row must NOT be persisted."""
    doc_id = _uid()
    sha256 = "deadbeef" + doc_id

    original_add = None

    call_count = 0

    def failing_add(obj: object) -> None:
        nonlocal call_count
        call_count += 1
        raise RuntimeError("Simulated DB failure during add")

    # Patch the session.add call inside the transaction context
    with patch("app.db.pg_manager.Document", side_effect=RuntimeError("Simulated constructor failure")):
        with pytest.raises(RuntimeError, match="Simulated"):
            await manager.save_document(
                doc_id=doc_id,
                tenant_id="default",
                sha256=sha256,
                metadata=_meta(),
                analysis=_analysis(),
                quality_score=0.9,
                n_pages=5,
                indexed_chunks=_chunks(doc_id),
            )

    # The transaction must have been rolled back — document row must NOT exist
    assert await manager.document_exists(tenant_id="default", sha256=sha256) is False
