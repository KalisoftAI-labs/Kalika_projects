"""
Ensure all tables exist. Run: python scripts/create_tables.py
"""

import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import engine, Base
import app.models.product  # noqa: F401
import app.models.user  # noqa: F401
import app.models.cart  # noqa: F401
import app.models.order  # noqa: F401
import app.models.punchout_session  # noqa: F401


async def run():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("All tables ensured.")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(run())
