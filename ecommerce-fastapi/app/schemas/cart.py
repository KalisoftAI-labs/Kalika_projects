from pydantic import BaseModel
from typing import Optional
from decimal import Decimal
from datetime import datetime


class CartItemAdd(BaseModel):
    product_id: int
    quantity: int = 1


class CartItemUpdate(BaseModel):
    quantity: int


class CartItemRead(BaseModel):
    id: int
    product_id: int
    product_title: str = ""
    item_code: str = ""
    price: float = 0.0
    quantity: int
    subtotal: float = 0.0
    s3_image_url: Optional[str] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class CartResponse(BaseModel):
    items: list[CartItemRead] = []
    total: float = 0.0
    item_count: int = 0
    cart_token: Optional[str] = None
