import httpx
import pytest
from app.core.constants import API_V1_PREFIX
from app.main import app
from httpx import ASGITransport


@pytest.mark.asyncio
async def test_health_ok() -> None:
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(f"{API_V1_PREFIX}/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
