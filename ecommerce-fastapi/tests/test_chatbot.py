from unittest.mock import patch
import pytest

pytestmark = pytest.mark.asyncio


@patch("app.services.chatbot_service._get_model")
async def test_chat_message(mock_get_model, client):
    class FakeConvo:
        def send_message(self, msg):
            return type("R", (), {"text": f"Echo: {msg}"})()

    class FakeModel:
        def start_chat(self, history=None):
            return FakeConvo()

    mock_get_model.return_value = FakeModel()

    resp = await client.post("/api/chatbot/message", json={"message": "Hello"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["response"] == "Echo: Hello"
    assert data["conversation_id"]


@patch("app.services.chatbot_service._get_model")
async def test_chat_conversation_continuity(mock_get_model, client):
    class FakeConvo:
        def send_message(self, msg):
            return type("R", (), {"text": msg.upper()})()

    mock_get_model.return_value = type("M", (), {"start_chat": lambda self, history=None: FakeConvo()})()

    resp = await client.post("/api/chatbot/message", json={"message": "hi"})
    cid = resp.json()["conversation_id"]

    resp = await client.post("/api/chatbot/message", json={"message": "again", "conversation_id": cid})
    assert resp.status_code == 200
    assert resp.json()["response"] == "AGAIN"


async def test_chat_empty_message(client):
    resp = await client.post("/api/chatbot/message", json={"message": "   "})
    assert resp.status_code == 400


async def test_chat_no_message_field(client):
    resp = await client.post("/api/chatbot/message", json={})
    assert resp.status_code == 422


@patch("app.services.chatbot_service._get_model")
async def test_chat_clear(mock_get_model, client):
    class FakeConvo:
        def send_message(self, msg):
            return type("R", (), {"text": "ok"})()

    mock_get_model.return_value = type("M", (), {"start_chat": lambda self, history=None: FakeConvo()})()

    resp = await client.post("/api/chatbot/message", json={"message": "test"})
    cid = resp.json()["conversation_id"]

    resp = await client.post("/api/chatbot/clear", json={"conversation_id": cid})
    assert resp.status_code == 200
    assert "cleared" in resp.json()["message"]


async def test_chat_no_api_key(client):
    from app.config import settings
    old = settings.GEMINI_API_KEY
    settings.GEMINI_API_KEY = None
    from app.services import chatbot_service
    chatbot_service._model = None
    try:
        resp = await client.post("/api/chatbot/message", json={"message": "hi"})
        assert resp.status_code == 200
        assert "not configured" in resp.json()["response"]
    finally:
        settings.GEMINI_API_KEY = old
        chatbot_service._model = None
