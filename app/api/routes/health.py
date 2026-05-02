"""Health check endpoints"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import datetime

from app.storage.database import get_db
from app.models.schemas import HealthStatus

router = APIRouter()

@router.get("/health", response_model=HealthStatus)
async def health_check(db: Session = Depends(get_db)):
    """
    Check system health status
    """
    # Check database connection
    try:
        db.execute("SELECT 1")
        db_status = "healthy"
    except Exception as e:
        db_status = "unhealthy"
    
    return HealthStatus(
        status="operational",
        timestamp=datetime.utcnow(),
        component_status={
            "database": db_status,
            "api": "healthy",
        },
        system_health={
            "response_time_ms": 10.5,
            "uptime_seconds": 3600,
        }
    )
