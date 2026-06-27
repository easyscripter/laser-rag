"""FastAPI dependencies for the API layer (spec §6, §11).

Job state and the task queue ride on the arq Redis pool created in the app
lifespan (``app.state.arq_pool`` — ``ArqRedis`` is a ``redis.asyncio.Redis``).
Authentication resolves the current user from the bearer access token; role
guards and the active ``tenant_id`` both derive from that token. Overriding any
of these in tests swaps in fakes.
"""

from __future__ import annotations

from collections.abc import Callable

from arq.connections import ArqRedis
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.auth.repository import UserRepository
from app.auth.service import AuthService
from app.auth.tokens import TokenClaims, TokenError, decode_token
from app.chat.engine import ChatEngine
from app.chat.factory import build_chat_engine
from app.chat.repository import ConversationRepository
from app.core.config import Settings, get_settings
from app.core.constants import TOKEN_TYPE_ACCESS
from app.core.enums.auth import Role
from app.db.conversation_repository import PostgreSQLConversationRepository
from app.db.user_repository import PostgreSQLUserRepository
from app.queue.queue import ArqTaskQueue, TaskQueue
from app.queue.store import JobStore, RedisJobStore

_bearer = HTTPBearer(auto_error=False)
_UNAUTHENTICATED = {"WWW-Authenticate": "Bearer"}


def _arq_pool(request: Request) -> ArqRedis:
    pool: ArqRedis | None = getattr(request.app.state, "arq_pool", None)
    if pool is None:  # pragma: no cover - lifespan guarantees this in production
        raise RuntimeError("arq pool is not initialized")
    return pool


def get_job_store(request: Request) -> JobStore:
    return RedisJobStore(_arq_pool(request))


def get_task_queue(request: Request) -> TaskQueue:
    return ArqTaskQueue(_arq_pool(request))


def get_app_settings() -> Settings:
    return get_settings()


def get_user_repository() -> UserRepository:
    return PostgreSQLUserRepository()


def get_auth_service(
    repository: UserRepository = Depends(get_user_repository),
) -> AuthService:
    return AuthService(repository)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> TokenClaims:
    """Resolve the authenticated user from the bearer access token (401 otherwise)."""
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing bearer token",
            headers=_UNAUTHENTICATED,
        )
    try:
        return decode_token(credentials.credentials, expected_type=TOKEN_TYPE_ACCESS)
    except TokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers=_UNAUTHENTICATED,
        ) from exc


def require_role(*roles: Role) -> Callable[[TokenClaims], TokenClaims]:
    """Build a dependency that admits only the given role(s) (403 otherwise)."""

    def _guard(user: TokenClaims = Depends(get_current_user)) -> TokenClaims:
        if user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="insufficient role",
            )
        return user

    return _guard


require_curator = require_role(Role.CURATOR)


def get_tenant_id(user: TokenClaims = Depends(get_current_user)) -> str:
    """The active tenant is taken from the authenticated user's token (spec §11)."""
    return user.tenant_id


def get_conversation_repository() -> ConversationRepository:
    return PostgreSQLConversationRepository()


def get_chat_engine(user: TokenClaims = Depends(get_current_user)) -> ChatEngine:
    """Build a per-tenant chat engine for the authenticated user (spec §5)."""
    return build_chat_engine(user.tenant_id)
