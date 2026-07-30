from fastapi import APIRouter, Depends, Query, UploadFile, File, Form, HTTPException
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import require_role
from app.schemas.product import ProductRead, ProductListResponse
from app.services import admin_product_service, export_service, product_service

router = APIRouter(prefix="/admin/products", tags=["admin"], dependencies=[Depends(require_role("Admin"))])


@router.get("", response_model=ProductListResponse)
async def list_products(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = Query(None),
    sort_by: str = Query("item_id"),
    sort_dir: str = Query("asc"),
    db: AsyncSession = Depends(get_db),
):
    return await admin_product_service.admin_list_products(db, page, page_size, search, sort_by, sort_dir)


@router.get("/datatables")
async def datatables(
    draw: int = Query(alias="draw"),
    start: int = Query(alias="start"),
    length: int = Query(alias="length"),
    search_value: str | None = Query(None, alias="search[value]"),
    order_column: int = Query(0, alias="order[0][column]"),
    order_dir: str = Query("asc", alias="order[0][dir]"),
    db: AsyncSession = Depends(get_db),
):
    return await admin_product_service.admin_datatables(db, draw, start, length, search_value, order_column, order_dir)


@router.get("/{item_id}", response_model=ProductRead)
async def get_product(item_id: int, db: AsyncSession = Depends(get_db)):
    product = await product_service.get_product(db, item_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


@router.post("", response_model=ProductRead, status_code=201)
async def create_product(body: dict, db: AsyncSession = Depends(get_db)):
    try:
        return await admin_product_service.create_product(db, body)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{item_id}", response_model=ProductRead)
async def update_product(item_id: int, body: dict, db: AsyncSession = Depends(get_db)):
    product = await admin_product_service.update_product(db, item_id, body)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


@router.delete("/{item_id}")
async def delete_product(item_id: int, db: AsyncSession = Depends(get_db)):
    if not await admin_product_service.delete_product(db, item_id=item_id):
        raise HTTPException(status_code=404, detail="Product not found")
    return {"message": "Product deleted"}


@router.post("/bulk")
async def bulk_import(
    file: UploadFile = File(...),
    modification_type: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="CSV file required")

    try:
        content = (await file.read()).decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            content = (await file.read()).decode("latin-1")
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Encoding error: {e}")

    result = await admin_product_service.bulk_import_csv(db, content, modification_type)
    msg = f"{result['success']} succeeded"
    if result["errors"]:
        msg += f", {len(result['errors'])} errors"
        return {"message": msg, "errors": result["errors"][:10]}
    return {"message": msg}


@router.get("/export/csv", response_class=PlainTextResponse)
async def export_csv(
    options: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    opt_list = options.split(",") if options else None
    csv_content = await export_service.export_products_to_csv(db, opt_list)
    return PlainTextResponse(csv_content, media_type="text/csv", headers={
        "Content-Disposition": "attachment; filename=products_export.csv",
    })
