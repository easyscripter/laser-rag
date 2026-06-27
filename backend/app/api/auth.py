"""Authentication endpoints (spec §6).

``POST /auth/login`` exchanges username/password for an access + refresh token
pair (plus the role). ``POST /auth/refresh`` mints a new access token from a
valid refresh token. The active tenant is the configured default until
multi-tenant onboarding (spec §11).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_app_settings, get_auth_service
from app.auth.service import AuthService
from app.auth.tokens import (
    TokenError,
    create_access_token,
    create_refresh_token,
    decode_token,
)
from app.core.config import Settings
from app.core.constants import TOKEN_TYPE_REFRESH
from app.core.logging import get_logger
from app.schemas.auth import (
    AccessTokenResponse,
    LoginRequest,
    RefreshRequest,
    TokenResponse,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

_INVALID_CREDENTIALS = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="invalid username or password",
    headers={"WWW-Authenticate": "Bearer"},
)


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    service: AuthService = Depends(get_auth_service),
    settings: Settings = Depends(get_app_settings),
) -> TokenResponse:
    """Authenticate and return an access + refresh token pair (spec §6)."""
    user = await service.authenticate(
        tenant_id=settings.default_tenant_id,
        username=body.username,
        password=body.password,
    )
    if user is None:
        logger.info("auth.login.failed", username=body.username)
        raise _INVALID_CREDENTIALS

    logger.info("auth.login.ok", username=user.username, role=user.role.value)
    return TokenResponse(
        access_token=create_access_token(
            sub=user.id, username=user.username, role=user.role, tenant_id=user.tenant_id
        ),
        refresh_token=create_refresh_token(
            sub=user.id, username=user.username, role=user.role, tenant_id=user.tenant_id
        ),
        role=user.role,
    )


@router.post("/refresh", response_model=AccessTokenResponse)
async def refresh(body: RefreshRequest) -> AccessTokenResponse:
    """Exchange a valid refresh token for a fresh access token (spec §6)."""
    try:
        claims = decode_token(body.refresh_token, expected_type=TOKEN_TYPE_REFRESH)
    except TokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    access_token = create_access_token(
        sub=claims.sub,
        username=claims.username,
        role=claims.role,
        tenant_id=claims.tenant_id,
    )
    return AccessTokenResponse(access_token=access_token)
