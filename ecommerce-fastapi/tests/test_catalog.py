import pytest


pytestmark = pytest.mark.asyncio


async def test_list_products(client):
    resp = await client.get("/api/catalog/products")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data


async def test_list_products_with_search(client):
    resp = await client.get("/api/catalog/products?search=Safety")
    assert resp.status_code == 200
    data = resp.json()
    for item in data["items"]:
        assert "Safety" in item["main_category"]


async def test_get_product_found(client):
    resp = await client.get("/api/catalog/products/1")
    assert resp.status_code == 200
    data = resp.json()
    assert data["item_id"] == 1


async def test_get_product_not_found(client):
    resp = await client.get("/api/catalog/products/99999")
    assert resp.status_code == 404


async def test_categories(client):
    resp = await client.get("/api/catalog/categories")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, dict)


async def test_homepage(client):
    resp = await client.get("/api/catalog/home")
    assert resp.status_code == 200
    data = resp.json()
    assert "products_by_category" in data
    assert "featured_products" in data
    assert "hero_video_url" in data
    assert "categories" in data
    assert isinstance(data["categories"], dict)
