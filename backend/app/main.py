"""LaserRAG FastAPI application entrypoint."""

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from arq import create_pool
from arq.connections import RedisSettings
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.auth import router as auth_router
from app.api.documents import router as documents_router
from app.api.jobs import router as jobs_router
from app.core.config import get_settings
from app.core.constants import API_V1_PREFIX, APP_NAME
from app.core.logging import configure_logging, get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    settings = get_settings()
    app.state.arq_pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
    logger.info("startup", app=APP_NAME, version=__version__)
    yield
    await app.state.arq_pool.aclose()
    logger.info("shutdown", app=APP_NAME)


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=APP_NAME,
        version=__version__,
        lifespan=lifespan,
        docs_url=f"{API_V1_PREFIX}/docs",
        openapi_url=f"{API_V1_PREFIX}/openapi.json",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def security_headers(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    @app.get(f"{API_V1_PREFIX}/health", tags=["health"])
    async def health() -> dict[str, str]:
        return {"status": "ok", "app": APP_NAME, "version": __version__}

    app.include_router(auth_router, prefix=API_V1_PREFIX)
    app.include_router(documents_router, prefix=API_V1_PREFIX)
    app.include_router(jobs_router, prefix=API_V1_PREFIX)

    return app


app = create_app()
