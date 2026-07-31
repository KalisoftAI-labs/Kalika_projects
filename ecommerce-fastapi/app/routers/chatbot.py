from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional

from app.services import chatbot_service

router = APIRouter(prefix="/chatbot", tags=["chatbot"])


class ChatMessage(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    conversation_id: Optional[str] = None


class ClearRequest(BaseModel):
    conversation_id: str


@router.post("/message")
async def chat(body: ChatMessage):
    if not body.message.strip():
        raise HTTPException(status_code=400, detail="No message provided")
    return chatbot_service.send_message(body.message.strip(), body.conversation_id)


@router.post("/clear")
async def clear(body: ClearRequest):
    cleared = chatbot_service.clear_conversation(body.conversation_id)
    return {"message": "Chat history cleared" if cleared else "Conversation not found"}
