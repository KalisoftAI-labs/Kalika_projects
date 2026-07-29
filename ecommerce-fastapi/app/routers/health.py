from fastapi import APIRouter
from app.database import check_db_connection

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check():
    db_ok = await check_db_connection()
    return {
        "status": "ok" if db_ok else "degraded",
        "db": "connected" if db_ok else "disconnected",
    }
