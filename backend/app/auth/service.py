"""Login service (spec §6 — POST /auth/login).

Verifies credentials against the user repository using argon2. Returns the
account on success or ``None`` on any failure (unknown user or wrong password),
so the API layer can answer with a single, non-enumerating 401.
"""

from __future__ import annotations

from app.auth.passwords import verify_password
from app.auth.repository import UserAccount, UserRepository


class AuthService:
    """Authenticate a username/password against a :class:`UserRepository`."""

    def __init__(self, repository: UserRepository) -> None:
        self._repository = repository

    async def authenticate(
        self, *, tenant_id: str, username: str, password: str
    ) -> UserAccount | None:
        """Return the matching account, or ``None`` if credentials are invalid."""
        user = await self._repository.get_by_username(tenant_id=tenant_id, username=username)
        if user is None:
            return None
        if not verify_password(password, user.password_hash):
            return None
        return user
