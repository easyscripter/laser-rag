"""Password hashing with argon2 (spec §11 — argon2 password hashing).

Thin wrapper over passlib's argon2 backend so the rest of the app never imports
passlib directly. ``verify_password`` is constant-time within the argon2 verifier.
"""

from __future__ import annotations

from passlib.context import CryptContext

_pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")


def hash_password(plain: str) -> str:
    """Return an argon2 hash (includes salt + parameters) for ``plain``."""
    return str(_pwd_context.hash(plain))


def verify_password(plain: str, hashed: str) -> bool:
    """Return whether ``plain`` matches the stored argon2 ``hashed`` value."""
    return bool(_pwd_context.verify(plain, hashed))
