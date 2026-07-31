import time
import logging
from uuid import uuid4

from app.config import settings

logger = logging.getLogger(__name__)

_model = None
CONVERSATION_TTL = 3600
conversations: dict[str, dict] = {}


def _get_model():
    global _model
    if _model is None:
        if not settings.GEMINI_API_KEY:
            return None
        import google.generativeai as genai
        genai.configure(api_key=settings.GEMINI_API_KEY)
        _model = genai.GenerativeModel("gemini-2.0-flash")
    return _model


def _cleanup():
    now = time.time()
    expired = [k for k, v in conversations.items() if now - v["last_active"] > CONVERSATION_TTL]
    for k in expired:
        del conversations[k]


def send_message(message: str, conversation_id: str | None = None) -> dict:
    _cleanup()
    cid = conversation_id or uuid4().hex

    convo_data = conversations.setdefault(
        cid, {"history": [], "last_active": time.time()}
    )
    convo_data["last_active"] = time.time()

    model = _get_model()
    if not model:
        return {"conversation_id": cid, "response": "Chatbot is not configured (missing GEMINI_API_KEY)."}

    try:
        convo = model.start_chat(history=convo_data["history"])
        reply = convo.send_message(message)

        convo_data["history"].append({"role": "user", "parts": [{"text": message}]})
        convo_data["history"].append({"role": "model", "parts": [{"text": reply.text}]})

        return {"conversation_id": cid, "response": reply.text}
    except Exception as e:
        logger.error(f"Gemini API error: {e}")
        return {"conversation_id": cid, "response": "An error occurred while processing your request."}


def clear_conversation(conversation_id: str) -> bool:
    return conversations.pop(conversation_id, None) is not None
