from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import optional_current_user
from app.models.user import User
from app.schemas.cart import CartItemAdd, CartItemUpdate, CartResponse
from app.schemas.order import CheckoutRequest, CheckoutResponse
from app.services import cart_service, checkout_service

router = APIRouter(prefix="/cart", tags=["cart"])


@router.get("", response_model=CartResponse)
async def get_cart(
    x_cart_token: str | None = Header(None),
    current_user: User | None = Depends(optional_current_user),
    db: AsyncSession = Depends(get_db),
):
    uid = current_user.id if current_user else None
    return await cart_service.get_cart(db, user_id=uid, session_token=x_cart_token)


@router.post("/items", response_model=CartResponse, status_code=201)
async def add_to_cart(
    body: CartItemAdd,
    x_cart_token: str | None = Header(None),
    current_user: User | None = Depends(optional_current_user),
    db: AsyncSession = Depends(get_db),
):
    uid = current_user.id if current_user else None
    try:
        return await cart_service.add_to_cart(db, body.product_id, body.quantity, uid, x_cart_token)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/items/{item_id}", response_model=CartResponse)
async def update_cart_item(
    item_id: int,
    body: CartItemUpdate,
    x_cart_token: str | None = Header(None),
    current_user: User | None = Depends(optional_current_user),
    db: AsyncSession = Depends(get_db),
):
    uid = current_user.id if current_user else None
    try:
        return await cart_service.update_cart_item(db, item_id, body.quantity, uid, x_cart_token)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/items/{item_id}", response_model=CartResponse)
async def remove_from_cart(
    item_id: int,
    x_cart_token: str | None = Header(None),
    current_user: User | None = Depends(optional_current_user),
    db: AsyncSession = Depends(get_db),
):
    uid = current_user.id if current_user else None
    return await cart_service.remove_from_cart(db, item_id, uid, x_cart_token)


@router.post("/checkout", response_model=CheckoutResponse)
async def checkout(
    body: CheckoutRequest,
    x_cart_token: str | None = Header(None),
    current_user: User | None = Depends(optional_current_user),
    db: AsyncSession = Depends(get_db),
):
    uid = current_user.id if current_user else None
    result = await checkout_service.checkout(
        db, user_id=uid, session_token=x_cart_token,
        punchout_return_url=body.punchout_return_url,
        buyer_cookie=body.buyer_cookie,
    )
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return result
