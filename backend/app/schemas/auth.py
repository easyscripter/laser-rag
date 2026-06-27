"""Request/response DTOs for authentication (spec §6)."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.core.enums.auth import Role


class LoginRequest(BaseModel):
    """Body for ``POST /auth/login``."""

    username: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=1, max_length=256)


class TokenResponse(BaseModel):
    """``POST /auth/login`` payload — access + refresh tokens and the role."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    role: Role


class RefreshRequest(BaseModel):
    """Body for ``POST /auth/refresh``."""

    refresh_token: str = Field(min_length=1)


class AccessTokenResponse(BaseModel):
    """``POST /auth/refresh`` payload — a freshly minted access token."""

    access_token: str
    token_type: str = "bearer"
