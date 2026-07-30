from fastapi import FastAPI
from contextlib import asynccontextmanager

from app.database import engine, Base
from app.config import settings
from app.routers import health, catalog, auth, cart, punchout, admin_products, admin_dashboard, admin_orders, admin_users
# Import models so they register with Base.metadata
import app.models.product  # noqa: F401
import app.models.user  # noqa: F401
import app.models.cart  # noqa: F401
import app.models.order  # noqa: F401
import app.models.punchout_session  # noqa: F401


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

from app.middleware.security import SecurityMiddleware, RateLimitMiddleware
app.add_middleware(SecurityMiddleware)
app.add_middleware(RateLimitMiddleware)

app.include_router(health.router, prefix="/api")
app.include_router(catalog.router, prefix="/api")
app.include_router(auth.router, prefix="/api")
app.include_router(cart.router, prefix="/api")
app.include_router(punchout.router, prefix="/api")
app.include_router(admin_products.router, prefix="/api")
app.include_router(admin_dashboard.router, prefix="/api")
app.include_router(admin_orders.router, prefix="/api")
app.include_router(admin_users.router, prefix="/api")


@app.get("/")
async def root():
    return {"app": settings.APP_NAME, "status": "running"}
