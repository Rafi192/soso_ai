# api/chat.py
# The only HTTP endpoint the WhatsApp backend talks to.
# Thin layer — validates input, calls orchestrator, returns reply.

import logging
from fastapi import APIRouter, HTTPException, Request

from app.schemas.chat_schema import ChatRequest, ChatResponse
from app.orchestrator.conversation_orchestrator import ConversationOrchestrator

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
async def chat(request: Request, body: ChatRequest):
    """
    Receives a WhatsApp message from the Node.js backend.
    Returns the AI reply.

    Body:
        user_id: "whatsapp:+8801XXXXXXXXX"
        message: "I want to grow my restaurant revenue"
    """
    # Orchestrator is attached to app state in main.py (see below)
    orchestrator: ConversationOrchestrator = request.app.state.orchestrator

    if not body.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    try:
        reply = await orchestrator.handle_message(
            user_id=body.user_id,
            user_input=body.message,
        )
    except Exception as e:
        logger.exception(f"Orchestrator error for {body.user_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal error — please try again")

    # Load session just for stage reporting (no extra Redis call — it's cached)
    session = await orchestrator.sessions.load(body.user_id)

    return ChatResponse(
        user_id=body.user_id,
        reply=reply,
        stage=session.stage,
    )
