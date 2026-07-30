import pytest
from app.middleware.security import BLOCKED_IPS, SUSPICIOUS_PATHS, _auto_blocked

pytestmark = pytest.mark.asyncio


async def test_blocked_ip(client):
    resp = await client.get("/api/health", headers={"x-forwarded-for": "141.98.11.98"})
    assert resp.status_code == 403


async def test_suspicious_env_path(client):
    resp = await client.get("/.env")
    assert resp.status_code == 403


async def test_suspicious_git_path(client):
    resp = await client.get("/.git/config")
    assert resp.status_code == 403


async def test_suspicious_php_path(client):
    resp = await client.get("/phpinfo.php")
    assert resp.status_code == 403


async def test_known_ips_are_blocked():
    assert "216.180.246.246" in BLOCKED_IPS
    assert "185.177.72.38" in BLOCKED_IPS
    assert "141.98.11.98" in BLOCKED_IPS
    assert len(BLOCKED_IPS) == 12


async def test_suspicious_paths_are_defined():
    assert ".env" in SUSPICIOUS_PATHS
    assert ".git" in SUSPICIOUS_PATHS
    assert len(SUSPICIOUS_PATHS) == 14


async def test_rate_limit_not_blocking_normal(client):
    _auto_blocked.clear()
    for _ in range(5):
        resp = await client.get("/api/health")
        assert resp.status_code == 200
