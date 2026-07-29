import time
import pytest

pytestmark = pytest.mark.asyncio

TAG = str(int(time.time()))


async def test_register(client):
    resp = await client.post(
        "/api/auth/register",
        json={"username": f"newuser_{TAG}", "email": f"{TAG}@test.com", "password": "newpass"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert f"newuser_{TAG}" in data["username"]


async def test_register_duplicate(client):
    resp = await client.post(
        "/api/auth/register",
        json={"username": f"newuser_{TAG}", "email": "dup@test.com", "password": "x"},
    )
    assert resp.status_code == 409


async def test_login(client):
    resp = await client.post(
        "/api/auth/login",
        json={"username": f"newuser_{TAG}", "password": "newpass"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data


async def test_login_wrong_password(client):
    resp = await client.post(
        "/api/auth/login",
        json={"username": f"newuser_{TAG}", "password": "wrong"},
    )
    assert resp.status_code == 401


async def test_login_admin(client):
    resp = await client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "admin123"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


async def test_me_authenticated(client):
    login_resp = await client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "admin123"},
    )
    token = login_resp.json()["access_token"]

    resp = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["username"] == "admin"


async def test_me_unauthenticated(client):
    resp = await client.get("/api/auth/me")
    assert resp.status_code == 401


async def test_refresh(client):
    login_resp = await client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "admin123"},
    )
    refresh = login_resp.json()["refresh_token"]

    resp = await client.post("/api/auth/refresh", json={"refresh_token": refresh})
    assert resp.status_code == 200
    assert "access_token" in resp.json()

