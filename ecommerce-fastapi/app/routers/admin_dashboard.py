from fastapi import APIRouter, Depends
from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import require_role
from app.models.product import Product
from app.models.user import User
from app.models.order import PunchOutOrder

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_role("Admin"))])


@router.get("/dashboard")
async def dashboard(db: AsyncSession = Depends(get_db)):
    total_products = (await db.execute(select(func.count(Product.item_id)))).scalar() or 0
    total_users = (await db.execute(select(func.count(User.id)))).scalar() or 0
    total_orders = (await db.execute(select(func.count(PunchOutOrder.id)))).scalar() or 0

    result = await db.execute(
        select(PunchOutOrder.total_cost).where(PunchOutOrder.status == "completed")
    )
    total_sales = sum(float(r[0]) for r in result.all())

    result = await db.execute(
        select(Product.main_category, func.count(Product.item_id))
        .group_by(Product.main_category)
        .order_by(func.count(Product.item_id).desc())
    )
    category_data = [{"category": r[0], "count": r[1]} for r in result.all()]

    recent = await db.execute(
        select(PunchOutOrder).order_by(PunchOutOrder.created_at.desc()).limit(5)
    )
    recent_orders = [
        {"id": o.id, "total": float(o.total_cost), "status": o.status, "date": str(o.created_at or "")}
        for o in recent.scalars().unique().all()
    ]

    return {
        "total_sales": total_sales,
        "total_products": total_products,
        "total_users": total_users,
        "total_orders": total_orders,
        "recent_orders": recent_orders,
        "category_data": category_data,
    }
