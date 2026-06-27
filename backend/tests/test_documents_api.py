"""POST /documents, GET /jobs/{id}, POST /jobs/{id}/retry (Phase 4, spec §6).

Drives the HTTP contract with in-memory fakes for the job store and task queue,
so no Redis/arq is needed. The app lifespan (which builds the real arq pool) is
deliberately not entered — TestClient is used without its context manager.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from pathlib import Path

import pytest
from app.api.deps import (
    get_app_settings,
    get_current_user,
    get_job_store,
    get_task_queue,
)
from app.auth.tokens import TokenClaims
from app.core.config import Settings
from app.core.constants import TOKEN_TYPE_ACCESS
from app.core.enums.auth import Role
from app.core.enums.jobs import JobStatus
from app.main import create_app
from app.queue.store import InMemoryJobStore
from fastapi.testclient import TestClient


def _curator() -> TokenClaims:
    return TokenClaims(
        sub="u-curator",
        username="curator",
        role=Role.CURATOR,
        tenant_id="default",
        type=TOKEN_TYPE_ACCESS,
    )


class FakeTaskQueue:
    def __init__(self) -> None:
        self.calls: list[tuple[str, int]] = []

    async def enqueue_index(self, job_id: str, *, from_stage: int = 1) -> None:
        self.calls.append((job_id, from_stage))


@pytest.fixture
def store() -> InMemoryJobStore:
    return InMemoryJobStore()


@pytest.fixture
def queue() -> FakeTaskQueue:
    return FakeTaskQueue()


@pytest.fixture
def client(
    store: InMemoryJobStore, queue: FakeTaskQueue, tmp_path: Path
) -> Iterator[TestClient]:
    app = create_app()
    settings = Settings(upload_dir=str(tmp_path / "uploads"))
    app.dependency_overrides[get_app_settings] = lambda: settings
    app.dependency_overrides[get_job_store] = lambda: store
    app.dependency_overrides[get_task_queue] = lambda: queue
    app.dependency_overrides[get_current_user] = _curator
    yield TestClient(app)
    app.dependency_overrides.clear()


def _upload(client: TestClient, name: str = "paper.txt", data: bytes = b"hello") -> object:
    return client.post(
        "/api/v1/documents",
        files={"file": (name, data, "text/plain")},
    )


def test_upload_returns_202_with_ids_and_queues_job(
    client: TestClient, store: InMemoryJobStore, queue: FakeTaskQueue, tmp_path: Path
) -> None:
    resp = _upload(client)

    assert resp.status_code == 202
    body = resp.json()
    assert body["job_id"] and body["doc_id"]
    assert queue.calls == [(body["job_id"], 1)]

    # The job is recorded queued at stage 1 and the source file landed on disk.
    job = asyncio.run(store.get(body["job_id"]))
    assert job is not None
    assert job.status is JobStatus.QUEUED
    assert Path(job.file_path).exists()


def test_upload_rejects_unsupported_extension(client: TestClient) -> None:
    resp = _upload(client, name="malware.exe", data=b"MZ")
    assert resp.status_code == 415


def test_upload_rejects_empty_file(client: TestClient) -> None:
    resp = _upload(client, data=b"")
    assert resp.status_code == 400


def test_get_job_returns_status(client: TestClient) -> None:
    job_id = _upload(client).json()["job_id"]

    resp = client.get(f"/api/v1/jobs/{job_id}")

    assert resp.status_code == 200
    body = resp.json()
    assert body["stage"] == 1
    assert body["stage_name"] == "extract"
    assert body["status"] == JobStatus.QUEUED.value


def test_get_unknown_job_returns_404(client: TestClient) -> None:
    assert client.get("/api/v1/jobs/nope").status_code == 404


def test_retry_reenqueues_from_stage(
    client: TestClient, queue: FakeTaskQueue
) -> None:
    job_id = _upload(client).json()["job_id"]
    queue.calls.clear()

    resp = client.post(f"/api/v1/jobs/{job_id}/retry", json={"from_stage": 5})

    assert resp.status_code == 202
    assert queue.calls == [(job_id, 5)]


def test_retry_unknown_job_returns_404(client: TestClient) -> None:
    resp = client.post("/api/v1/jobs/nope/retry", json={"from_stage": 3})
    assert resp.status_code == 404
