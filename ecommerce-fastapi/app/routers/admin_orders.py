from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import require_role
from app.models.order import PunchOutOrder

router = APIRouter(prefix="/admin/orders", tags=["admin"], dependencies=[Depends(require_role("Admin"))])


@router.get("")
async def list_orders(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(PunchOutOrder).order_by(PunchOutOrder.created_at.desc())
    )
    orders = []
    for o in result.scalars().unique().all():
        items = []
        for i in o.items or []:
            items.append({
                "product_title": i.product_title,
                "item_code": i.item_code,
                "quantity": i.quantity,
                "unit_price": float(i.unit_price),
                "subtotal": float(i.subtotal),
            })
        orders.append({
            "id": o.id,
            "buyer_cookie": o.buyer_cookie,
            "total_cost": float(o.total_cost),
            "currency": o.currency or "INR",
            "status": o.status,
            "created_at": str(o.created_at or ""),
            "items": items,
        })
    return orders


@router.get("/pending")
async def pending_orders(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(PunchOutOrder).where(PunchOutOrder.status == "pending").order_by(PunchOutOrder.created_at.desc())
    )
    return [_order_to_dict(o) for o in result.scalars().unique().all()]


@router.get("/completed")
async def completed_orders(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(PunchOutOrder).where(PunchOutOrder.status.in_(["completed", "shipped"])).order_by(PunchOutOrder.created_at.desc())
    )
    return [_order_to_dict(o) for o in result.scalars().unique().all()]


def _order_to_dict(o: PunchOutOrder) -> dict:
    return {
        "id": o.id,
        "buyer_cookie": o.buyer_cookie,
        "total_cost": float(o.total_cost),
        "currency": o.currency or "INR",
        "status": o.status,
        "created_at": str(o.created_at or ""),
    }
