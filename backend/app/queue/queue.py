"""Task queue seam (spec §4): enqueue indexing jobs onto arq.

The :class:`TaskQueue` protocol keeps the API layer independent of arq, so the
endpoints can be tested with a fake. :class:`ArqTaskQueue` wraps a real arq pool.
"""

from __future__ import annotations

from typing import Protocol

from arq.connections import ArqRedis

from app.core.constants import FIRST_STAGE

INDEX_TASK = "index_document"


class TaskQueue(Protocol):
    """Enqueues indexing work for the worker."""

    async def enqueue_index(self, job_id: str, *, from_stage: int = FIRST_STAGE) -> None:
        """Schedule (or reschedule) the worker to run ``job_id`` from ``from_stage``."""
        ...


class ArqTaskQueue:
    """TaskQueue backed by an arq Redis pool."""

    def __init__(self, pool: ArqRedis) -> None:
        self._pool = pool

    async def enqueue_index(self, job_id: str, *, from_stage: int = FIRST_STAGE) -> None:
        await self._pool.enqueue_job(INDEX_TASK, job_id, from_stage=from_stage)
