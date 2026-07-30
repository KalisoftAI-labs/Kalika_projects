import csv
import io
import json
import logging
from decimal import Decimal
from typing import Any

from sqlalchemy import select, func, or_, delete as sa_delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product import Product
from app.services.s3_service import enrich_products_with_s3_urls

logger = logging.getLogger(__name__)

ALL_DB_COLUMNS = [
    "action", "main_category", "sub_categories", "item_code",
    "product_title", "product_description", "upc", "brand", "department",
    "type", "tag", "list_price", "price", "inventory", "min_order_qty",
    "available", "large_image", "additional_images", "status",
    "lead_time", "length", "material_type", "sys_discount_group",
    "sys_num_images", "sys_product_type", "unit_of_measure", "unspsc",
]


async def admin_list_products(
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
            Product.status.ilike(pattern),
        )
        query = query.where(filter_cond)
        count_query = count_query.where(filter_cond)

    total = (await db.execute(count_query)).scalar() or 0
    sort_col = getattr(Product, sort_by, Product.item_id)
    order = sort_col.asc() if sort_dir == "asc" else sort_col.desc()
    result = await db.execute(query.order_by(order).offset((page - 1) * page_size).limit(page_size))
    products = list(result.scalars().all())
    enrich_products_with_s3_urls(products)
    return {"items": products, "total": total, "page": page, "page_size": page_size}


async def admin_datatables(
    db: AsyncSession, draw: int, start: int, length: int,
    search_value: str | None, order_column: int, order_dir: str,
) -> dict:
    query = select(Product)
    count_query = select(func.count(Product.item_id))

    if search_value:
        pattern = f"%{search_value}%"
        filter_cond = or_(
            Product.product_title.ilike(pattern),
            Product.item_code.ilike(pattern),
            Product.status.ilike(pattern),
            Product.main_category.ilike(pattern),
        )
        query = query.where(filter_cond)
        count_query = count_query.where(filter_cond)

    records_total = (await db.execute(select(func.count(Product.item_id)))).scalar() or 0
    records_filtered = (await db.execute(count_query)).scalar() or 0

    orderable = ["item_id", "product_title", "item_code", "status", None, "last_modified"]
    if order_column < len(orderable) and orderable[order_column]:
        col = getattr(Product, orderable[order_column])
        query = query.order_by(col.asc() if order_dir == "asc" else col.desc())
    else:
        query = query.order_by(Product.item_id.asc())

    result = await db.execute(query.offset(start).limit(length))
    products = list(result.scalars().all())
    enrich_products_with_s3_urls(products)

    data = []
    for p in products:
        data.append({
            "item_id": p.item_id,
            "main_category": p.main_category,
            "sub_categories": p.sub_categories or "",
            "item_code": p.item_code,
            "product_title": p.product_title,
            "product_description": p.product_description or "",
            "price": float(p.price) if p.price else 0,
            "large_image": p.large_image,
            "s3_image_url": getattr(p, "s3_image_url", None),
            "upc": p.upc or "",
            "status": p.status or "New",
            "inventory": int(p.inventory) if p.inventory else 0,
            "last_modified": p.last_modified.isoformat() if p.last_modified else "",
        })

    return {"draw": draw, "recordsTotal": records_total, "recordsFiltered": records_filtered, "data": data}


async def create_product(db: AsyncSession, data: dict) -> Product:
    product = Product(**{k: v for k, v in data.items() if hasattr(Product, k)})
    db.add(product)
    await db.commit()
    await db.refresh(product)
    return product


async def update_product(db: AsyncSession, item_id: int, data: dict) -> Product | None:
    product = await db.get(Product, item_id)
    if not product:
        return None
    for key, value in data.items():
        if hasattr(product, key) and key != "item_id":
            setattr(product, key, value)
    await db.commit()
    await db.refresh(product)
    return product


async def delete_product(db: AsyncSession, item_id: int | None = None, item_code: str | None = None) -> bool:
    if item_id:
        product = await db.get(Product, item_id)
    else:
        result = await db.execute(select(Product).where(Product.item_code == item_code))
        product = result.scalar_one_or_none()
    if not product:
        return False
    await db.delete(product)
    await db.commit()
    return True


async def bulk_import_csv(db: AsyncSession, csv_content: str, mode: str) -> dict:
    reader = csv.DictReader(io.StringIO(csv_content))
    success = 0
    errors = []

    for row_num, row in enumerate(reader, start=1):
        cleaned = {}
        for k, v in row.items():
            if k is None:
                continue
            ck = k.strip().replace(" ", "_").replace("\ufeff", "").lower()
            cleaned[ck] = v

        try:
            if mode == "add":
                missing = [f for f in ["main_category", "item_code", "product_title", "price"] if not cleaned.get(f)]
                if missing:
                    raise ValueError(f"Missing required fields: {missing}")
                data = {col: cleaned.get(col) for col in ALL_DB_COLUMNS if col != "item_id"}
                if cleaned.get("additional_images"):
                    try:
                        data["additional_images"] = json.dumps(json.loads(cleaned["additional_images"]))
                    except json.JSONDecodeError:
                        data["additional_images"] = "[]"
                await create_product(db, data)
                success += 1

            elif mode == "update_price":
                item_id = int(cleaned.get("item_id", 0))
                price = float(cleaned.get("price", 0))
                if await update_product(db, item_id, {"price": price}):
                    success += 1
                else:
                    errors.append(f"Row {row_num}: Product {item_id} not found")

            elif mode == "update_description":
                item_id = int(cleaned.get("item_id", 0))
                desc = cleaned.get("product_description", "")
                if await update_product(db, item_id, {"product_description": desc}):
                    success += 1
                else:
                    errors.append(f"Row {row_num}: Product {item_id} not found")

            elif mode == "delete":
                item_id = cleaned.get("item_id")
                if item_id and await delete_product(db, item_id=int(item_id)):
                    success += 1
                else:
                    errors.append(f"Row {row_num}: Product {item_id} not found")

        except Exception as e:
            errors.append(f"Row {row_num}: {e}")

    return {"success": success, "errors": errors}
