"""JWT access/refresh tokens (spec §6, §11).

Access tokens authorize API calls; refresh tokens mint new access tokens. Both
carry ``role`` and ``tenant_id`` (the multi-tenancy seam). ``decode_token`` is the
single validation entrypoint — it raises :class:`TokenError` on anything invalid.
"""

from __future__ import annotations

from datetime import timedelta

import jwt
from pydantic import BaseModel, ConfigDict

from app.core.config import get_settings
from app.core.constants import TOKEN_TYPE_ACCESS, TOKEN_TYPE_REFRESH
from app.core.enums.auth import Role
from app.core.time import utcnow


class TokenError(Exception):
    """Raised when a JWT is missing, malformed, expired, or of the wrong type."""


class TokenClaims(BaseModel):
    """The claims LaserRAG puts in (and reads back from) a JWT."""

    model_config = ConfigDict(extra="ignore")

    sub: str  # user id
    username: str
    role: Role
    tenant_id: str
    type: str  # TOKEN_TYPE_ACCESS | TOKEN_TYPE_REFRESH


def _encode(claims: TokenClaims, *, ttl: timedelta) -> str:
    settings = get_settings()
    now = utcnow()
    payload = {
        **claims.model_dump(mode="json"),
        "iat": int(now.timestamp()),
        "exp": int((now + ttl).timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_access_token(*, sub: str, username: str, role: Role, tenant_id: str) -> str:
    """Mint a short-lived access token for API authorization."""
    settings = get_settings()
    claims = TokenClaims(
        sub=sub, username=username, role=role, tenant_id=tenant_id, type=TOKEN_TYPE_ACCESS
    )
    return _encode(claims, ttl=timedelta(minutes=settings.access_token_ttl_minutes))


def create_refresh_token(*, sub: str, username: str, role: Role, tenant_id: str) -> str:
    """Mint a long-lived refresh token used only to obtain new access tokens."""
    settings = get_settings()
    claims = TokenClaims(
        sub=sub, username=username, role=role, tenant_id=tenant_id, type=TOKEN_TYPE_REFRESH
    )
    return _encode(claims, ttl=timedelta(days=settings.refresh_token_ttl_days))


def decode_token(token: str, *, expected_type: str | None = None) -> TokenClaims:
    """Verify signature + expiry, returning claims. Raise ``TokenError`` otherwise.

    When ``expected_type`` is given, the token's ``type`` must match (so a refresh
    token cannot be used as an access token, and vice versa).
    """
    settings = get_settings()
    try:
        payload = jwt.decode(
            token, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
        )
    except jwt.PyJWTError as exc:
        raise TokenError(str(exc)) from exc

    try:
        claims = TokenClaims.model_validate(payload)
    except ValueError as exc:
        raise TokenError("malformed token claims") from exc

    if expected_type is not None and claims.type != expected_type:
        raise TokenError(f"expected {expected_type} token, got {claims.type}")
    return claims
