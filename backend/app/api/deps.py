"""FastAPI dependencies for the indexing API (spec §6).

Job state and the task queue both ride on the arq Redis pool created in the app
lifespan (``app.state.arq_pool`` — ``ArqRedis`` is a ``redis.asyncio.Redis``).
Overriding these in tests swaps in in-memory fakes.
"""

from __future__ import annotations

from arq.connections import ArqRedis
from fastapi import Request

from app.core.config import Settings, get_settings
from app.queue.queue import ArqTaskQueue, TaskQueue
from app.queue.store import JobStore, RedisJobStore


def _arq_pool(request: Request) -> ArqRedis:
    pool: ArqRedis | None = getattr(request.app.state, "arq_pool", None)
    if pool is None:  # pragma: no cover - lifespan guarantees this in production
        raise RuntimeError("arq pool is not initialized")
    return pool


def get_job_store(request: Request) -> JobStore:
    return RedisJobStore(_arq_pool(request))


def get_task_queue(request: Request) -> TaskQueue:
    return ArqTaskQueue(_arq_pool(request))


def get_tenant_id() -> str:
    """Resolve the active tenant. Until auth (Phase 5) this is the default tenant."""
    return get_settings().default_tenant_id


def get_app_settings() -> Settings:
    return get_settings()
