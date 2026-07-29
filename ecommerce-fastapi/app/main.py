from fastapi import FastAPI
from contextlib import asynccontextmanager

from app.database import engine, Base
from app.config import settings
from app.routers import health, catalog, auth, cart
# Import models so they register with Base.metadata
import app.models.product  # noqa: F401
import app.models.user  # noqa: F401
import app.models.cart  # noqa: F401
import app.models.order  # noqa: F401


@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"Starting {settings.APP_NAME}...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()
    print("Shutdown complete.")


app = FastAPI(
    title=settings.APP_NAME,
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(health.router, prefix="/api")
app.include_router(catalog.router, prefix="/api")
app.include_router(auth.router, prefix="/api")
app.include_router(cart.router, prefix="/api")


@app.get("/")
async def root():
    return {"app": settings.APP_NAME, "status": "running"}
