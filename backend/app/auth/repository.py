"""User account model + lookup interface (spec §8, §11).

``UserRepository`` is the seam the login service depends on; the PostgreSQL
implementation lives in ``app/db/user_repository.py``.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.core.enums.auth import Role


@dataclass(frozen=True, slots=True)
class UserAccount:
    """An authenticatable user (spec §8 users)."""

    id: str
    tenant_id: str
    username: str
    password_hash: str
    role: Role


class UserRepository(ABC):
    """Read-side lookup of user accounts for authentication."""

    @abstractmethod
    async def get_by_username(self, *, tenant_id: str, username: str) -> UserAccount | None:
        """Return the account for ``(tenant_id, username)`` or ``None``."""
