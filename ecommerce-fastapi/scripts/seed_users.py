"""
Seed admin + test users into the new DB.
Run: python -m scripts.seed_users
"""

import asyncio
from app.database import engine, Base, async_session
import app.models.user  # noqa: F401


async def seed():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as db:
        from app.services.auth_service import create_user

        admin = await create_user(db, "admin", "admin@kalikaindia.com", "admin123", role="Admin")
        print(f"Admin: {admin.username} (id={admin.id})")

        user = await create_user(db, "testuser", "test@kalikaindia.com", "test123")
        print(f"User: {user.username} (id={user.id})")


if __name__ == "__main__":
    asyncio.run(seed())
