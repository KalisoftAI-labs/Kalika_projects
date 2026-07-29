from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.schemas.product import ProductRead, ProductListResponse, HomepageResponse
from app.services import product_service

router = APIRouter(prefix="/catalog", tags=["catalog"])


@router.get("/home", response_model=HomepageResponse)
async def homepage(db: AsyncSession = Depends(get_db)):
    return await product_service.get_homepage_data(db)


@router.get("/products", response_model=ProductListResponse)
async def list_products(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = Query(None),
    sort_by: str = Query("item_id"),
    sort_dir: str = Query("asc", pattern="^(asc|desc)$"),
    db: AsyncSession = Depends(get_db),
):
    return await product_service.list_products(db, page, page_size, search, sort_by, sort_dir)


@router.get("/products/{item_id}", response_model=ProductRead)
async def get_product(item_id: int, db: AsyncSession = Depends(get_db)):
    product = await product_service.get_product(db, item_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


@router.get("/categories")
async def get_categories(db: AsyncSession = Depends(get_db)):
    return await product_service.build_category_tree(db)


@router.get("/categories/{main_category}")
async def get_products_by_category(
    main_category: str,
    sub_category: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    products = await product_service.get_products_by_category(db, main_category, sub_category)
    if not products:
        raise HTTPException(status_code=404, detail="No products found")
    return products
