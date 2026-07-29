import pytest

pytestmark = pytest.mark.asyncio


async def test_add_to_cart_anonymous(client):
    resp = await client.post(
        "/api/cart/items",
        json={"product_id": 1, "quantity": 2},
    )
    body = resp.json()
    print(f"DEBUG add_to_cart: status={resp.status_code}, body={body}")
    assert resp.status_code == 201, f"Expected 201, got {resp.status_code}: {body}"
    data = body
    assert len(data["items"]) == 1
    assert data["cart_token"] is not None


async def test_get_cart_anonymous(client):
    resp = await client.post(
        "/api/cart/items",
        json={"product_id": 1, "quantity": 1},
    )
    token = resp.json()["cart_token"]

    resp = await client.get("/api/cart", headers={"X-Cart-Token": token})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) >= 1


async def test_update_cart_item(client):
    resp = await client.post(
        "/api/cart/items",
        json={"product_id": 2, "quantity": 1},
    )
    token = resp.json()["cart_token"]
    item_id = resp.json()["items"][0]["id"]

    resp = await client.put(
        f"/api/cart/items/{item_id}",
        json={"quantity": 5},
        headers={"X-Cart-Token": token},
    )
    assert resp.status_code == 200
    assert resp.json()["items"][0]["quantity"] == 5


async def test_remove_cart_item(client):
    resp = await client.post(
        "/api/cart/items",
        json={"product_id": 3, "quantity": 1},
    )
    token = resp.json()["cart_token"]
    item_id = resp.json()["items"][0]["id"]

    resp = await client.delete(
        f"/api/cart/items/{item_id}",
        headers={"X-Cart-Token": token},
    )
    assert resp.status_code == 200
    assert len(resp.json()["items"]) == 0


async def test_empty_cart(client):
    resp = await client.get("/api/cart")
    assert resp.status_code == 200
    data = resp.json()
    assert data["item_count"] == 0
    assert data["total"] == 0


async def test_add_to_cart_authenticated(client):
    login = await client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "admin123"},
    )
    token = login.json()["access_token"]

    resp = await client.post(
        "/api/cart/items",
        json={"product_id": 1, "quantity": 3},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert len(data["items"]) > 0
    assert data["cart_token"] is None
