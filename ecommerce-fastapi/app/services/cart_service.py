from decimal import Decimal
from uuid import uuid4
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cart import CartItem
from app.models.product import Product
from app.services.s3_service import enrich_product_with_s3_url


def _make_cart_token() -> str:
    return uuid4().hex


async def _resolve_cart(
    db: AsyncSession, user_id: int | None, session_token: str | None
) -> tuple[str | None, list[CartItem]]:
    if user_id:
        result = await db.execute(
            select(CartItem).where(CartItem.user_id == user_id).order_by(CartItem.created_at)
        )
        return None, list(result.scalars().all())

    token = session_token or _make_cart_token()
    result = await db.execute(
        select(CartItem).where(CartItem.session_token == token).order_by(CartItem.created_at)
    )
    return token, list(result.scalars().all())


async def get_cart(
    db: AsyncSession, user_id: int | None = None, session_token: str | None = None
) -> dict:
    token, items = await _resolve_cart(db, user_id, session_token)

    cart_items = []
    total = Decimal("0")
    for ci in items:
        subtotal = ci.quantity * ci.product.price
        total += subtotal
        enrich_product_with_s3_url(ci.product)
        cart_items.append({
            "id": ci.id,
            "product_id": ci.product_id,
            "product_title": ci.product.product_title,
            "item_code": ci.product.item_code,
            "price": ci.product.price,
            "quantity": ci.quantity,
            "subtotal": subtotal,
            "s3_image_url": getattr(ci.product, "s3_image_url", None),
            "created_at": ci.created_at,
        })

    return {
        "items": cart_items,
        "total": float(total),
        "item_count": len(cart_items),
        "cart_token": token if not user_id else None,
    }


async def add_to_cart(
    db: AsyncSession,
    product_id: int,
    quantity: int = 1,
    user_id: int | None = None,
    session_token: str | None = None,
) -> dict:
    token = session_token or _make_cart_token()

    if user_id:
        existing = await db.execute(
            select(CartItem).where(CartItem.product_id == product_id, CartItem.user_id == user_id)
        )
    else:
        existing = await db.execute(
            select(CartItem).where(CartItem.product_id == product_id, CartItem.session_token == token)
        )
    item = existing.scalar_one_or_none()

    if item:
        item.quantity += quantity
    else:
        item = CartItem(
            user_id=user_id,
            session_token=token if not user_id else None,
            product_id=product_id,
            quantity=quantity,
        )
        db.add(item)

    await db.commit()
    return await get_cart(db, user_id, token)


async def update_cart_item(
    db: AsyncSession,
    item_id: int,
    quantity: int,
    user_id: int | None = None,
    session_token: str | None = None,
) -> dict:
    item = await db.get(CartItem, item_id)
    if not item:
        raise ValueError("Cart item not found")

    if quantity <= 0:
        await db.delete(item)
    else:
        item.quantity = quantity

    await db.commit()
    return await get_cart(db, user_id, session_token)


async def remove_from_cart(
    db: AsyncSession,
    item_id: int,
    user_id: int | None = None,
    session_token: str | None = None,
) -> dict:
    item = await db.get(CartItem, item_id)
    if item:
        await db.delete(item)
        await db.commit()
    return await get_cart(db, user_id, session_token)


async def clear_cart(
    db: AsyncSession, user_id: int | None = None, session_token: str | None = None
):
    if user_id:
        await db.execute(delete(CartItem).where(CartItem.user_id == user_id))
    elif session_token:
        await db.execute(delete(CartItem).where(CartItem.session_token == session_token))
    await db.commit()
