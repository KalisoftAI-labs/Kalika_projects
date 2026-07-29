import pytest

pytestmark = pytest.mark.asyncio


async def test_checkout_empty_cart(client):
    resp = await client.post("/api/cart/checkout", json={})
    assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.text[:200]}"
    assert "empty" in resp.text.lower()


async def test_checkout_anonymous_standard(client):
    resp = await client.post("/api/cart/items", json={"product_id": 1, "quantity": 2})
    token = resp.json()["cart_token"]

    resp = await client.post(
        "/api/cart/checkout",
        json={},
        headers={"X-Cart-Token": token},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert len(data["order"]["items"]) == 1
    assert data["order"]["items"][0]["product_title"] == "Nitrile Safety Gloves"

    resp = await client.get("/api/cart", headers={"X-Cart-Token": token})
    assert resp.json()["item_count"] == 0


async def test_checkout_anonymous_punchout(client):
    resp = await client.post("/api/cart/items", json={"product_id": 2, "quantity": 3})
    token = resp.json()["cart_token"]

    resp = await client.post(
        "/api/cart/checkout",
        json={"punchout_return_url": "https://buyer.ariba.com/punchback", "buyer_cookie": "test-cookie-123"},
        headers={"X-Cart-Token": token},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["cxml_payload"] is not None
    assert "PunchOutOrderMessage" in data["cxml_payload"]
    assert "test-cookie-123" in data["cxml_payload"]
    assert "Cut Resistant Gloves" in data["cxml_payload"]


async def test_cxml_structure(client):
    resp = await client.post("/api/cart/items", json={"product_id": 1, "quantity": 1})
    token = resp.json()["cart_token"]

    resp = await client.post(
        "/api/cart/checkout",
        json={"punchout_return_url": "https://test.ariba.com/return", "buyer_cookie": "cookie-xyz"},
        headers={"X-Cart-Token": token},
    )
    xml = resp.json()["cxml_payload"]
    assert "<!DOCTYPE cXML SYSTEM" in xml, f"Missing DOCTYPE: {xml[:200]}"
    assert "<BuyerCookie>cookie-xyz</BuyerCookie>" in xml
    assert "<SupplierPartID>SAF-GLOVE-001</SupplierPartID>" in xml
    assert "<UnitOfMeasure>" in xml
    assert "currency=\"INR\"" in xml or "currency='INR'" in xml
