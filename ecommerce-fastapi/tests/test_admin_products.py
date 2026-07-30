import time
import pytest

pytestmark = pytest.mark.asyncio
ADMIN_TOKEN = None


async def _admin_token(client):
    global ADMIN_TOKEN
    if not ADMIN_TOKEN:
        resp = await client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
        ADMIN_TOKEN = resp.json()["access_token"]
    return ADMIN_TOKEN


async def _create_test_product(client, token, suffix: str = "") -> dict:
    tag = f"{int(time.time())}{suffix}"
    resp = await client.post(
        "/api/admin/products",
        json={"main_category": "TestCat", "item_code": f"TST-{tag}", "product_title": f"Test {tag}", "price": 25.00},
        headers={"Authorization": f"Bearer {token}"},
    )
    return resp.json()


async def test_admin_list_products(client):
    token = await _admin_token(client)
    resp = await client.get("/api/admin/products", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["total"] > 0


async def test_admin_list_requires_auth(client):
    resp = await client.get("/api/admin/products")
    assert resp.status_code == 401


async def test_admin_create_product(client):
    token = await _admin_token(client)
    p = await _create_test_product(client, token, "create")
    assert p["item_code"].endswith("create")


async def test_admin_update_product(client):
    token = await _admin_token(client)
    p = await _create_test_product(client, token, "upd")
    resp = await client.put(
        f"/api/admin/products/{p['item_id']}",
        json={"product_title": "Updated Via Test", "price": 49.99},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["product_title"] == "Updated Via Test"
    assert float(resp.json()["price"]) == 49.99


async def test_admin_delete_not_found(client):
    token = await _admin_token(client)
    resp = await client.delete("/api/admin/products/99999", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 404


async def test_admin_create_then_delete(client):
    token = await _admin_token(client)
    p = await _create_test_product(client, token, "del")
    resp = await client.delete(f"/api/admin/products/{p['item_id']}", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    resp = await client.get(f"/api/admin/products/{p['item_id']}", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 404


async def test_admin_bulk_csv_add(client):
    token = await _admin_token(client)
    tag = int(time.time())
    csv_data = f"main_category,item_code,product_title,price\nBulkCat,BULK-{tag}-A,Bulk Item A,10.00\nBulkCat,BULK-{tag}-B,Bulk Item B,20.00"
    resp = await client.post(
        "/api/admin/products/bulk",
        files={"file": ("test.csv", csv_data, "text/csv")},
        data={"modification_type": "add"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert "succeeded" in resp.json()["message"]


async def test_admin_bulk_csv_update_price(client):
    token = await _admin_token(client)
    p = await _create_test_product(client, token, "bup")
    csv_data = f"item_id,price\n{p['item_id']},199.99"
    resp = await client.post(
        "/api/admin/products/bulk",
        files={"file": ("update.csv", csv_data, "text/csv")},
        data={"modification_type": "update_price"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200


async def test_admin_bulk_csv_delete(client):
    token = await _admin_token(client)
    p = await _create_test_product(client, token, "bdel")
    csv_data = f"item_id\n{p['item_id']}"
    resp = await client.post(
        "/api/admin/products/bulk",
        files={"file": ("delete.csv", csv_data, "text/csv")},
        data={"modification_type": "delete"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200


async def test_admin_datatables(client):
    token = await _admin_token(client)
    resp = await client.get(
        "/api/admin/products/datatables?draw=1&start=0&length=10",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "draw" in data
    assert data["recordsTotal"] > 0


async def test_admin_export_csv(client):
    token = await _admin_token(client)
    resp = await client.get(
        "/api/admin/products/export/csv",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert "text/csv" in resp.headers.get("content-type", "")
    assert resp.text.startswith("item id")
