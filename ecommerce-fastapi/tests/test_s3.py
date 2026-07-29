from unittest.mock import patch, MagicMock
from app.services.s3_service import (
    get_presigned_url,
    upload_image,
    enrich_product_with_s3_url,
)


def test_get_presigned_url_returns_none_for_noimage():
    assert get_presigned_url("noimage.jpg") is None
    assert get_presigned_url(None) is None


@patch("app.services.s3_service._get_s3_client")
def test_get_presigned_url_success(mock_get_client):
    mock_client = MagicMock()
    mock_client.generate_presigned_url.return_value = "https://s3.url/test.jpg"
    mock_get_client.return_value = mock_client

    url = get_presigned_url("kalika-images/test.jpg")
    assert url == "https://s3.url/test.jpg"
    mock_client.generate_presigned_url.assert_called_once_with(
        "get_object",
        Params={"Bucket": "kalika-ecom", "Key": "kalika-images/test.jpg"},
        ExpiresIn=3600,
    )


@patch("app.services.s3_service._get_s3_client")
def test_upload_image_success(mock_get_client):
    mock_client = MagicMock()
    mock_get_client.return_value = mock_client

    result = upload_image(b"fake-content", "photo.png")
    assert result is not None
    assert result.startswith("/kalika-images/")
    assert result.endswith(".png")
    mock_client.put_object.assert_called_once()


@patch("app.services.s3_service.get_presigned_url")
def test_enrich_product_with_s3_url(mock_get_url):
    mock_get_url.return_value = "https://s3.url/gloves.jpg"

    class FakeProduct:
        large_image = "kalika-images/gloves.jpg"

    p = FakeProduct()
    enrich_product_with_s3_url(p)
    assert p.s3_image_url == "https://s3.url/gloves.jpg"


def test_enrich_product_with_s3_url_fallback():
    class FakeProduct:
        large_image = None

    p = FakeProduct()
    enrich_product_with_s3_url(p)
    assert p.s3_image_url == "/static/images/noimage.jpg"
