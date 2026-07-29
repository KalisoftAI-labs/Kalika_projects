import os
import uuid
import time
import logging
from functools import lru_cache

import boto3
from botocore.exceptions import ClientError

from app.config import settings

logger = logging.getLogger(__name__)

DEFAULT_IMAGE = "/static/images/noimage.jpg"
PRESIGNED_EXPIRY = 3600
CACHE_TTL = 3600
DEFAULT_CACHE_TTL = 300


@lru_cache
def _get_s3_client():
    if not settings.AWS_ACCESS_KEY_ID:
        return None
    return boto3.client(
        "s3",
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=settings.AWS_REGION,
    )


# ponytail: simple in-memory TTL cache, swap for Redis if throughput matters
_cache: dict[str, tuple[str, float]] = {}


def _cache_get(key: str) -> str | None:
    entry = _cache.get(key)
    if entry is None:
        return None
    value, expires = entry
    if time.time() > expires:
        del _cache[key]
        return None
    return value


def _cache_set(key: str, value: str, ttl: int):
    _cache[key] = (value, time.time() + ttl)


def get_presigned_url(object_key: str, expiry: int = PRESIGNED_EXPIRY) -> str | None:
    if not object_key or "noimage.jpg" in object_key:
        return None

    client = _get_s3_client()
    if not client:
        return None

    cache_key = f"s3_url_{hash(object_key)}"
    cached = _cache_get(cache_key)
    if cached:
        return cached

    try:
        clean_key = object_key.lstrip("/")
        url = client.generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.AWS_S3_BUCKET_NAME, "Key": clean_key},
            ExpiresIn=expiry,
        )
        _cache_set(cache_key, url, CACHE_TTL)
        return url
    except ClientError as e:
        logger.error(f"S3 presigned URL failed for {object_key}: {e}")
        return None


def upload_image(file_content: bytes, filename: str, content_type: str | None = None) -> str | None:
    ext = os.path.splitext(filename)[1].lower()
    type_map = {
        ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
        ".gif": "image/gif", ".webp": "image/webp", ".bmp": "image/bmp",
        ".svg": "image/svg+xml", ".ico": "image/x-icon",
    }
    ct = content_type or type_map.get(ext, "image/jpeg")
    unique_name = f"{uuid.uuid4().hex}{ext}"
    s3_key = f"kalika-images/{unique_name}"

    client = _get_s3_client()
    if not client:
        return None
    try:
        client.put_object(
            Bucket=settings.AWS_S3_BUCKET_NAME,
            Key=s3_key,
            Body=file_content,
            ContentType=ct,
        )
        logger.info(f"Uploaded to S3: {s3_key}")
        return f"/{s3_key}"
    except ClientError as e:
        logger.error(f"S3 upload failed: {e}")
        return None


def enrich_product_with_s3_url(product: dict | object) -> dict | object:
    raw_image = getattr(product, "large_image", None) if not isinstance(product, dict) else product.get("large_image")
    if not raw_image:
        s3_url = DEFAULT_IMAGE
    else:
        s3_url = get_presigned_url(raw_image) or DEFAULT_IMAGE

    if isinstance(product, dict):
        product["s3_image_url"] = s3_url
    else:
        product.s3_image_url = s3_url  # type: ignore
    return product


def enrich_products_with_s3_urls(products: list) -> list:
    for p in products:
        enrich_product_with_s3_url(p)
    return products
