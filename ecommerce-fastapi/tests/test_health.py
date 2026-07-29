import pytest


pytestmark = pytest.mark.asyncio


async def test_health_endpoint(client):
    response = await client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ("ok", "degraded")
    assert data["db"] in ("connected", "disconnected")
