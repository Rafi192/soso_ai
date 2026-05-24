# schemas/chat_schema.py

from typing import Optional, Any
from pydantic import BaseModel


class ChatRequest(BaseModel):
    whatsappNumber: str          # NestJS sends this field name
    userMessage: str             # NestJS sends this field name
    conversationHistory: list = []
    restaurantProfile: Optional[dict] = None


class ChatResponse(BaseModel):
    responseText: str            # NestJS reads this field name
    extractedData: dict = {}     # NestJS reads this
    actionTriggered: Optional[str] = None   # NestJS reads this