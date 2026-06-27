"""arq worker — runs the 6-stage indexing pipeline in the background (spec §4).

The ``index_document`` task is a thin shell: it loads the job from Redis and hands
it to :class:`~app.queue.runner.StageRunner`, which owns the stage logic and the
retry-from-stage behaviour. arq retries (crashes/transient errors) are separate
from the user-driven "retry from stage N" exposed via ``POST /jobs/{id}/retry``.
"""

from __future__ import annotations

from typing import Any, ClassVar

from arq.connections import RedisSettings

from app.core.config import get_settings
from app.core.constants import FIRST_STAGE
from app.core.logging import configure_logging, get_logger
from app.queue.factory import build_runner
from app.queue.queue import INDEX_TASK
from app.queue.store import RedisJobStore

logger = get_logger(__name__)


async def index_document(
    ctx: dict[str, Any], job_id: str, *, from_stage: int = FIRST_STAGE
) -> str:
    """Run (or resume) the indexing job identified by ``job_id``."""
    store = RedisJobStore(ctx["redis"])
    job = await store.get(job_id)
    if job is None:
        logger.warning("index.job_missing", job_id=job_id)
        return "missing"

    logger.info("index.start", job_id=job_id, doc_id=job.doc_id, from_stage=from_stage)
    runner = build_runner(job.tenant_id)
    result = await runner.run(job_id, store=store, from_stage=from_stage)
    logger.info(
        "index.finished", job_id=job_id, status=result.status, stage=result.stage
    )
    return result.status


async def startup(_: dict[str, object]) -> None:
    configure_logging()
    logger.info("worker.startup")


async def shutdown(_: dict[str, object]) -> None:
    logger.info("worker.shutdown")


# arq looks up the task by its function name; keep it aligned with INDEX_TASK.
assert index_document.__name__ == INDEX_TASK


class WorkerSettings:
    functions: ClassVar[list[object]] = [index_document]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
