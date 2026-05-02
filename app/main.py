"""FastAPI Application Entry Point"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import logging
from pathlib import Path

from app.core.config import get_settings
from app.api.routes import health, logs, metrics, rca, dashboard, errors
# from app.api.routes import charts  # Temporarily disabled - requires matplotlib
from app.storage.database import init_db

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI application
app = FastAPI(
    title="RCA Dashboard API",
    description="Root Cause Analysis Dashboard for production observability",
    version="1.0.0",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(health.router, prefix="/api", tags=["health"])
app.include_router(logs.router, prefix="/api/logs", tags=["logs"])
app.include_router(metrics.router, prefix="/api/metrics", tags=["metrics"])
app.include_router(rca.router, prefix="/api/rca", tags=["rca"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["dashboard"])
app.include_router(errors.router, prefix="/api", tags=["errors"])
# app.include_router(charts.router, prefix="/api/charts", tags=["charts"])  # Temporarily disabled

# Mount frontend static files
frontend_path = Path(__file__).parent.parent / "frontend"
if frontend_path.exists():
    app.mount("/", StaticFiles(directory=str(frontend_path), html=True), name="static")

@app.on_event("startup")
async def startup_event():
    """Initialize database on startup"""
    logger.info("Initializing RCA Dashboard...")
    try:
        init_db()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.warning(f"Database initialization failed: {e}")
        logger.info("Running in demo mode without persistent database")
    logger.info("RCA Dashboard ready")

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("Shutting down RCA Dashboard...")

if __name__ == "__main__":
    import uvicorn
    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        workers=settings.api_workers,
        reload=True,
    )
