import time
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.product import Product
from app.services.s3_service import (
    enrich_products_with_s3_urls, enrich_product_with_s3_url, get_presigned_url,
)


DEFINED_MAIN_CATEGORIES = [
    "Safety", "Janitorial", "Packaging", "Facility Maintenance",
    "Chemicals & Lubricants", "Abrasives", "Adhesives, Sealants & Tape",
    "Hand & Power Tools", "Pneumatics", "Cutting Tools", "Welding Tools",
    "Measuring Instruments & Tools", "Mechanical Power Transmission",
    "ACCESSORIES", "STATIONERY", "Appliances And Utilities", "WAVE PROJECT",
    "Plastic Bags", "PTFE HOSE CTCI",
]

SUB_CATEGORY_BLOCKLIST = {"home", "system", "menu1", "shop", ""}
HOMEPAGE_CACHE_TTL = 300
VIDEO_CACHE_TTL = 3000

_home_cache: dict = {}  # ponytail: in-memory TTL, swap for Redis later


async def list_products(
    db: AsyncSession, page: int = 1, page_size: int = 20,
    search: str | None = None, sort_by: str = "item_id", sort_dir: str = "asc",
) -> dict:
    query = select(Product)
    count_query = select(func.count(Product.item_id))

    if search:
        pattern = f"%{search}%"
        filter_cond = or_(
            Product.product_title.ilike(pattern),
            Product.item_code.ilike(pattern),
            Product.main_category.ilike(pattern),
        )
        query = query.where(filter_cond)
        count_query = count_query.where(filter_cond)

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    sort_col = getattr(Product, sort_by, Product.item_id)
    order = sort_col.asc() if sort_dir == "asc" else sort_col.desc()
    query = query.order_by(order).offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    products = list(result.scalars().all())
    enrich_products_with_s3_urls(products)
    return {"items": products, "total": total, "page": page, "page_size": page_size}


async def get_product(db: AsyncSession, item_id: int) -> Product | None:
    result = await db.execute(select(Product).where(Product.item_id == item_id))
    product = result.scalar_one_or_none()
    if product:
        enrich_product_with_s3_url(product)
    return product


async def get_products_by_category(
    db: AsyncSession, main_category: str, sub_category: str | None = None
) -> list[Product]:
    query = select(Product).where(Product.main_category == main_category)
    if sub_category:
        query = query.where(Product.sub_categories == sub_category)
    result = await db.execute(query)
    products = list(result.scalars().all())
    enrich_products_with_s3_urls(products)
    return products


async def get_homepage_data(db: AsyncSession) -> dict:
    now = int(time.time())
    cached = _home_cache.get("homepage")
    if cached and cached["expires"] > now:
        return cached["data"]

    current_minute = int(now // 60)
    all_products_list: list[Product] = []
    category_products_map: dict = {}

    for cat in DEFINED_MAIN_CATEGORIES:
        first_word = cat.split(" ")[0]
        query = select(Product).where(
            Product.main_category.ilike(f"%{first_word}%")
        ).where(
            or_(Product.large_image.is_(None), ~Product.large_image.ilike("%noimage.jpg%"))
        ).order_by(Product.item_id)

        result = await db.execute(query)
        all_in_cat = list(result.scalars().all())
        total = len(all_in_cat)

        if total == 0:
            category_products_map[cat] = []
            continue

        offset = ((current_minute // 9) * 9) % max(1, total)

        if total <= 10:
            products = all_in_cat
        else:
            end = offset + 10
            if end <= total:
                products = all_in_cat[offset:end]
            else:
                products = all_in_cat[offset:] + all_in_cat[:end - total]

        category_products_map[cat] = products
        all_products_list.extend(products)

    enrich_products_with_s3_urls(all_products_list)

    hero_video_url = _get_hero_video_url()
    featured = category_products_map.get("Hand & Power Tools", [])[:10]
    categories = await build_category_tree(db)

    data = {
        "products_by_category": {k: _products_to_list(v) for k, v in category_products_map.items() if v},
        "featured_products": _products_to_list(featured),
        "hero_video_url": hero_video_url,
        "categories": categories,
    }

    _home_cache["homepage"] = {"data": data, "expires": now + HOMEPAGE_CACHE_TTL}
    return data


def _get_hero_video_url() -> str | None:
    from app.config import settings
    if not settings.AWS_ACCESS_KEY_ID:
        return None
    cache_key = "hero_video"
    cached = _home_cache.get(cache_key)
    now = int(time.time())
    if cached and cached["expires"] > now:
        return cached["data"]

    url = get_presigned_url("kalika-images/kalika-ad1.mp4", expiry=3600)
    _home_cache[cache_key] = {"data": url, "expires": now + VIDEO_CACHE_TTL}
    return url


def _products_to_list(products: list[Product]) -> list[dict]:
    return [
        {
            "item_id": p.item_id,
            "product_title": p.product_title,
            "item_code": p.item_code,
            "price": float(p.price) if p.price else 0,
            "main_category": p.main_category,
            "sub_categories": p.sub_categories,
            "large_image": p.large_image,
            "s3_image_url": getattr(p, "s3_image_url", None),
        }
        for p in products
    ]


async def build_category_tree(db: AsyncSession) -> dict:
    result = await db.execute(
        select(Product.main_category, Product.sub_categories, func.count(Product.item_id).label("cnt"))
        .where(Product.main_category.in_(DEFINED_MAIN_CATEGORIES))
        .where(or_(Product.sub_categories.is_(None), Product.sub_categories == "", Product.sub_categories.notin_(SUB_CATEGORY_BLOCKLIST)))
        .group_by(Product.main_category, Product.sub_categories)
        .order_by(Product.main_category, Product.sub_categories)
    )
    rows = result.all()

    tree: dict = {}
    for row in rows:
        main = row.main_category
        sub = row.sub_categories or ""
        cnt = row.cnt
        if main not in tree:
            tree[main] = {"name": main, "product_count": 0, "subcategories": {}}
        tree[main]["product_count"] += cnt
        if sub and sub not in SUB_CATEGORY_BLOCKLIST:
            if sub not in tree[main]["subcategories"]:
                tree[main]["subcategories"][sub] = {"name": sub, "product_count": 0}
            tree[main]["subcategories"][sub]["product_count"] += cnt

    for main_cat in DEFINED_MAIN_CATEGORIES:
        if main_cat not in tree:
            continue
        subs = tree[main_cat]["subcategories"]
        for sub_name in list(subs.keys()):
            stmt = select(Product.item_id, Product.product_title).where(
                Product.main_category == main_cat,
                Product.sub_categories == sub_name,
            ).limit(5)
            r = await db.execute(stmt)
            subs[sub_name]["products"] = [{"item_id": row[0], "product_title": row[1]} for row in r.all()]

        tree[main_cat]["subcategories"] = sorted(subs.values(), key=lambda x: x["name"])

    limited = dict(list(sorted(tree.items()))[:10])
    return limited
