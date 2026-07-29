from pydantic import BaseModel
from typing import Optional
from decimal import Decimal
from datetime import datetime


class CheckoutRequest(BaseModel):
    punchout_return_url: Optional[str] = None
    buyer_cookie: Optional[str] = None


class OrderItemRead(BaseModel):
    product_title: str
    item_code: str
    quantity: int
    unit_price: float
    subtotal: float
    unit_of_measure: str = "EA"
    unspsc: Optional[str] = None


class OrderRead(BaseModel):
    id: int
    total_cost: float
    currency: str = "INR"
    status: str = "completed"
    buyer_cookie: Optional[str] = None
    items: list[OrderItemRead] = []
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class CheckoutResponse(BaseModel):
    success: bool
    order: Optional[OrderRead] = None
    cxml_payload: Optional[str] = None
    message: str = ""
