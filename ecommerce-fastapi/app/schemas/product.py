from pydantic import BaseModel, Field
from typing import Optional
from decimal import Decimal
from datetime import datetime


class ProductRead(BaseModel):
    item_id: int
    main_category: str
    sub_categories: Optional[str] = None
    item_code: str
    product_title: str
    product_description: Optional[str] = None
    upc: Optional[str] = None
    brand: Optional[str] = None
    department: Optional[str] = None
    type: Optional[str] = None
    tag: Optional[str] = None
    list_price: Optional[Decimal] = None
    price: Decimal
    inventory: Optional[int] = None
    min_order_qty: Optional[int] = None
    available: Optional[str] = None
    large_image: Optional[str] = None
    additional_images: Optional[str] = None
    status: Optional[str] = "New"
    last_modified: Optional[datetime] = None
    lead_time: Optional[str] = None
    length: Optional[str] = None
    material_type: Optional[str] = None
    sys_num_images: Optional[str] = None
    sys_product_type: Optional[str] = None
    unit_of_measure: Optional[str] = None
    unspsc: Optional[str] = None
    s3_image_url: Optional[str] = None

    model_config = {"from_attributes": True}


class ProductListResponse(BaseModel):
    items: list[ProductRead]
    total: int
    page: int
    page_size: int


class CategoryItem(BaseModel):
    name: str
    product_count: int = 0


class SubCategory(CategoryItem):
    products: list[dict] = []


class MainCategory(BaseModel):
    name: str
    product_count: int = 0
    subcategories: list[SubCategory] = []


class HomepageProduct(BaseModel):
    item_id: int
    product_title: str
    item_code: str
    price: float = 0.0
    main_category: str = ""
    sub_categories: str | None = None
    large_image: str | None = None
    s3_image_url: str | None = None


class HomepageResponse(BaseModel):
    products_by_category: dict[str, list[HomepageProduct]]
    featured_products: list[HomepageProduct]
    hero_video_url: str | None = None
    categories: dict[str, MainCategory]
