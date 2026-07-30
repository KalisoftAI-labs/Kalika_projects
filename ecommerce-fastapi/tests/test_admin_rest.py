import pytest

pytestmark = pytest.mark.asyncio
TOKEN = None


async def _admin_token(client):
    global TOKEN
    if not TOKEN:
        resp = await client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
        TOKEN = resp.json()["access_token"]
    return TOKEN


async def test_dashboard(client):
    token = await _admin_token(client)
    resp = await client.get("/api/admin/dashboard", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert "total_sales" in data
    assert "total_products" in data
    assert data["total_products"] > 0
    assert "category_data" in data


async def test_dashboard_requires_auth(client):
    resp = await client.get("/api/admin/dashboard")
    assert resp.status_code == 401


async def test_list_orders(client):
    token = await _admin_token(client)
    resp = await client.get("/api/admin/orders", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


async def test_list_pending_orders(client):
    token = await _admin_token(client)
    resp = await client.get("/api/admin/orders/pending", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200


async def test_list_completed_orders(client):
    token = await _admin_token(client)
    resp = await client.get("/api/admin/orders/completed", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200


async def test_list_users(client):
    token = await _admin_token(client)
    resp = await client.get("/api/admin/users", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    users = resp.json()
    assert len(users) >= 2
    usernames = [u["username"] for u in users]
    assert "admin" in usernames


async def test_create_user(client):
    token = await _admin_token(client)
    tag = f"cr-{int(__import__('time').time())}"
    resp = await client.post(
        "/api/admin/users",
        json={"username": f"newadmin{tag}", "email": f"{tag}@cr-test.com", "password": "test123", "role": "User"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    assert resp.json()["username"] == f"newadmin{tag}"


async def test_update_user(client):
    token = await _admin_token(client)
    tag = f"upd-{int(__import__('time').time())}"
    resp = await client.post(
        "/api/admin/users",
        json={"username": f"upduser{tag}", "email": f"{tag}@upd-test.com", "password": "pass", "role": "User"},
        headers={"Authorization": f"Bearer {token}"},
    )
    uid = resp.json()["id"]

    resp = await client.put(
        f"/api/admin/users/{uid}",
        json={"role": "Admin", "is_active": False},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["role"] == "Admin"
    assert resp.json()["is_active"] is False
