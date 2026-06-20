"""arq worker entrypoint."""

from typing import ClassVar

from arq.connections import RedisSettings

from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger

logger = get_logger(__name__)


async def startup(_: dict[str, object]) -> None:
    configure_logging()
    logger.info("worker.startup")


async def shutdown(_: dict[str, object]) -> None:
    logger.info("worker.shutdown")


class WorkerSettings:
    functions: ClassVar[list[object]] = []
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
