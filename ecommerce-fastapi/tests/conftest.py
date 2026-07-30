import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.middleware.security import _auto_blocked, _suspicious_attempts, _rate_limit_store


@pytest.fixture(autouse=True)
def reset_security_state():
    _auto_blocked.clear()
    _suspicious_attempts.clear()
    _rate_limit_store.clear()


@pytest.fixture(scope="function")
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
