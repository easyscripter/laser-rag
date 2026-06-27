"""Job state persistence (spec §4).

The job record is small and ephemeral, so it lives in Redis (the same instance
arq uses) under ``job:{job_id}``. The :class:`JobStore` protocol keeps the runner
and API decoupled from Redis; :class:`InMemoryJobStore` backs the tests.
"""

from __future__ import annotations

from typing import Protocol

from redis.asyncio import Redis

from app.queue.jobs import IndexJob

JOB_KEY_PREFIX = "job:"
# Jobs are progress trackers, not durable records — expire a day after the last update.
JOB_TTL_SECONDS = 60 * 60 * 24


class JobStore(Protocol):
    """Persists and retrieves :class:`IndexJob` records."""

    async def save(self, job: IndexJob) -> None:
        """Create or overwrite the job record (bumps ``updated_at``)."""
        ...

    async def get(self, job_id: str) -> IndexJob | None:
        """Return the job, or ``None`` if it is unknown/expired."""
        ...


class InMemoryJobStore:
    """Non-durable JobStore for tests — stores a copy keyed by job_id."""

    def __init__(self) -> None:
        self._jobs: dict[str, str] = {}

    async def save(self, job: IndexJob) -> None:
        job.touch()
        self._jobs[job.job_id] = job.model_dump_json()

    async def get(self, job_id: str) -> IndexJob | None:
        raw = self._jobs.get(job_id)
        return IndexJob.model_validate_json(raw) if raw is not None else None


class RedisJobStore:
    """JobStore backed by Redis (``job:{job_id}`` → JSON, TTL refreshed on save)."""

    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    def _key(self, job_id: str) -> str:
        return f"{JOB_KEY_PREFIX}{job_id}"

    async def save(self, job: IndexJob) -> None:
        job.touch()
        await self._redis.set(
            self._key(job.job_id), job.model_dump_json(), ex=JOB_TTL_SECONDS
        )

    async def get(self, job_id: str) -> IndexJob | None:
        raw = await self._redis.get(self._key(job_id))
        if raw is None:
            return None
        if isinstance(raw, bytes):
            raw = raw.decode()
        return IndexJob.model_validate_json(raw)
