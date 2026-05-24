# api/chat.py

import logging
from fastapi import APIRouter, HTTPException, Request

from app.schemas.chat_schema import ChatRequest, ChatResponse

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/generate", response_model=ChatResponse)
async def generate(request: Request, body: ChatRequest):
    """
    Receives a message from the NestJS backend.
    Returns the AI reply in the shape NestJS expects.
    """
    orchestrator = request.app.state.orchestrator

    if not body.userMessage.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    try:
        reply = await orchestrator.handle_message(
            user_id=body.whatsappNumber,    # use whatsappNumber as the user_id key
            user_input=body.userMessage,
        )
    except Exception as e:
        logger.exception(f"Orchestrator error for {body.whatsappNumber}: {e}")
        raise HTTPException(status_code=500, detail="Internal error — please try again")

    # Load session to check stage for action mapping
    session = await orchestrator.sessions.load_session(body.whatsappNumber)

    # Map Python stage → NestJS actionTriggered
    action = _stage_to_action(session.stage)

    return ChatResponse(
        responseText=reply,
        extractedData={},          # Python side doesn't extract structured data yet
        actionTriggered=action,
    )


def _stage_to_action(stage: str) -> str | None:
    """Map Python conversation stage to an action string NestJS understands."""
    mapping = {
        "PROFILE_COLLECTION": None,
        "PROBLEM_DETECTION": "ONBOARDING_COMPLETE",
        "DIAGNOSTIC_QUESTIONS": None,
        "RECOMMENDATIONS": "UPDATE_STAGE_HOT_LEAD",
        "FOLLOWUP": "SHOW_BOOKING_CTA",
    }
    return mapping.get(stage)