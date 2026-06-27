"""Phase 5 — Authentication: passwords, JWT, login service, and route guards.

Drives behavior through public interfaces with in-test fakes (no Postgres/Redis):
the app lifespan is not entered (TestClient without its context manager), and the
user repository / job plumbing are swapped via dependency_overrides.
"""

from __future__ import annotations

import time
from collections.abc import Iterator

import jwt
import pytest
from app.api.deps import (
    get_app_settings,
    get_auth_service,
    get_current_user,
    get_job_store,
    get_task_queue,
)
from app.auth.passwords import hash_password, verify_password
from app.auth.repository import UserAccount, UserRepository
from app.auth.service import AuthService
from app.auth.tokens import (
    TokenClaims,
    TokenError,
    create_access_token,
    create_refresh_token,
    decode_token,
)
from app.core.config import Settings, get_settings
from app.core.constants import TOKEN_TYPE_ACCESS, TOKEN_TYPE_REFRESH
from app.core.enums.auth import Role
from app.main import create_app
from app.queue.store import InMemoryJobStore
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------


class _FakeUserRepo(UserRepository):
    def __init__(self, users: list[UserAccount]) -> None:
        self._by_key = {(u.tenant_id, u.username): u for u in users}

    async def get_by_username(self, *, tenant_id: str, username: str) -> UserAccount | None:
        return self._by_key.get((tenant_id, username))


class _FakeTaskQueue:
    async def enqueue_index(self, job_id: str, *, from_stage: int = 1) -> None:
        return None


def _curator() -> TokenClaims:
    return TokenClaims(
        sub="u-cur", username="cur", role=Role.CURATOR, tenant_id="default",
        type=TOKEN_TYPE_ACCESS,
    )


def _reader() -> TokenClaims:
    return TokenClaims(
        sub="u-rdr", username="rdr", role=Role.READER, tenant_id="default",
        type=TOKEN_TYPE_ACCESS,
    )


@pytest.fixture
def client() -> Iterator[TestClient]:
    app = create_app()
    app.dependency_overrides[get_app_settings] = lambda: Settings()
    app.dependency_overrides[get_job_store] = InMemoryJobStore
    app.dependency_overrides[get_task_queue] = _FakeTaskQueue
    yield TestClient(app)
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Cycle 1 — Password hashing (argon2)
# ---------------------------------------------------------------------------


def test_password_hash_roundtrips_and_rejects_wrong_password() -> None:
    hashed = hash_password("correct horse")
    assert hashed != "correct horse"  # never store plaintext
    assert verify_password("correct horse", hashed) is True
    assert verify_password("wrong", hashed) is False


# ---------------------------------------------------------------------------
# Cycle 2 — JWT encode/decode
# ---------------------------------------------------------------------------


def test_access_token_roundtrips_claims() -> None:
    token = create_access_token(
        sub="u1", username="alice", role=Role.CURATOR, tenant_id="default"
    )
    claims = decode_token(token, expected_type=TOKEN_TYPE_ACCESS)
    assert claims.sub == "u1"
    assert claims.username == "alice"
    assert claims.role is Role.CURATOR
    assert claims.tenant_id == "default"
    assert claims.type == TOKEN_TYPE_ACCESS


def test_decode_rejects_wrong_token_type() -> None:
    refresh = create_refresh_token(
        sub="u1", username="alice", role=Role.READER, tenant_id="default"
    )
    # A refresh token must not be accepted where an access token is required.
    with pytest.raises(TokenError):
        decode_token(refresh, expected_type=TOKEN_TYPE_ACCESS)


def test_decode_rejects_expired_token() -> None:
    settings = get_settings()
    payload = {
        "sub": "u1", "username": "alice", "role": Role.READER.value,
        "tenant_id": "default", "type": TOKEN_TYPE_ACCESS,
        "iat": int(time.time()) - 120, "exp": int(time.time()) - 60,
    }
    expired = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    with pytest.raises(TokenError):
        decode_token(expired, expected_type=TOKEN_TYPE_ACCESS)


def test_decode_rejects_bad_signature() -> None:
    token = create_access_token(
        sub="u1", username="alice", role=Role.READER, tenant_id="default"
    )
    with pytest.raises(TokenError):
        decode_token(token + "tampered")


# ---------------------------------------------------------------------------
# Cycle 3 — AuthService
# ---------------------------------------------------------------------------


def _account(username: str = "alice", password: str = "s3cret", role: Role = Role.CURATOR) -> UserAccount:
    return UserAccount(
        id=f"id-{username}", tenant_id="default", username=username,
        password_hash=hash_password(password), role=role,
    )


async def test_authenticate_returns_user_on_valid_credentials() -> None:
    service = AuthService(_FakeUserRepo([_account()]))
    user = await service.authenticate(
        tenant_id="default", username="alice", password="s3cret"
    )
    assert user is not None
    assert user.username == "alice"


async def test_authenticate_rejects_wrong_password_and_unknown_user() -> None:
    service = AuthService(_FakeUserRepo([_account()]))
    assert await service.authenticate(
        tenant_id="default", username="alice", password="nope"
    ) is None
    assert await service.authenticate(
        tenant_id="default", username="ghost", password="s3cret"
    ) is None


# ---------------------------------------------------------------------------
# Cycle 4 — POST /auth/login
# ---------------------------------------------------------------------------


def test_login_returns_token_pair_and_role(client: TestClient) -> None:
    repo = _FakeUserRepo([_account(role=Role.CURATOR)])
    client.app.dependency_overrides[get_auth_service] = lambda: AuthService(repo)

    resp = client.post(
        "/api/v1/auth/login", json={"username": "alice", "password": "s3cret"}
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["role"] == Role.CURATOR.value
    assert body["token_type"] == "bearer"
    claims = decode_token(body["access_token"], expected_type=TOKEN_TYPE_ACCESS)
    assert claims.username == "alice"
    assert decode_token(body["refresh_token"], expected_type=TOKEN_TYPE_REFRESH).sub == "id-alice"


def test_login_rejects_bad_credentials(client: TestClient) -> None:
    repo = _FakeUserRepo([_account()])
    client.app.dependency_overrides[get_auth_service] = lambda: AuthService(repo)

    resp = client.post(
        "/api/v1/auth/login", json={"username": "alice", "password": "wrong"}
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Cycle 5 — POST /auth/refresh
# ---------------------------------------------------------------------------


def test_refresh_mints_new_access_token(client: TestClient) -> None:
    refresh = create_refresh_token(
        sub="u1", username="alice", role=Role.READER, tenant_id="default"
    )
    resp = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})

    assert resp.status_code == 200
    access = resp.json()["access_token"]
    assert decode_token(access, expected_type=TOKEN_TYPE_ACCESS).username == "alice"


def test_refresh_rejects_access_token(client: TestClient) -> None:
    access = create_access_token(
        sub="u1", username="alice", role=Role.READER, tenant_id="default"
    )
    resp = client.post("/api/v1/auth/refresh", json={"refresh_token": access})
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Cycle 6 — Route guards
# ---------------------------------------------------------------------------


def test_protected_route_requires_token(client: TestClient) -> None:
    # No get_current_user override → real bearer extraction runs, finds nothing.
    assert client.get("/api/v1/jobs/whatever").status_code == 401


def test_reader_may_read_jobs_but_not_retry(client: TestClient) -> None:
    client.app.dependency_overrides[get_current_user] = _reader

    # any authenticated user may read job status (missing job → 404, not 401/403)
    assert client.get("/api/v1/jobs/missing").status_code == 404
    # retry is curator-only → reader forbidden
    assert client.post(
        "/api/v1/jobs/missing/retry", json={"from_stage": 1}
    ).status_code == 403


def test_curator_may_retry(client: TestClient) -> None:
    client.app.dependency_overrides[get_current_user] = _curator
    # guard passes → reaches handler → job not found → 404 (proves authorization ok)
    assert client.post(
        "/api/v1/jobs/missing/retry", json={"from_stage": 1}
    ).status_code == 404
