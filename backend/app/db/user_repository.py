"""PostgreSQL implementation of UserRepository (spec §8, §11)."""

from __future__ import annotations

from sqlalchemy import select

from app.auth.repository import UserAccount, UserRepository
from app.core.enums.auth import Role
from app.db.models import User
from app.db.session import AsyncSessionLocal


class PostgreSQLUserRepository(UserRepository):
    """Concrete UserRepository backed by async SQLAlchemy + PostgreSQL."""

    async def get_by_username(self, *, tenant_id: str, username: str) -> UserAccount | None:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(User).where(
                    User.tenant_id == tenant_id,
                    User.username == username,
                )
            )
            row = result.scalar_one_or_none()
            if row is None:
                return None
            return UserAccount(
                id=row.id,
                tenant_id=row.tenant_id,
                username=row.username,
                password_hash=row.password_hash,
                role=Role(row.role),
            )
