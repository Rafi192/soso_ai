from typing import Optional
from pydantic import BaseModel, Field
from datetime import datetime

class ConversationStage:
    #valid stages of the conversation

    INTRO = "INTRO"
    PROFILE_COLLECTION = "PROFILE_COLLECTION"
    PROBLEM_DETECTION = "PROBLEM_DETECTION"
    CATEGORY_CONFIRMATION = "CATEGORY_CONFIRMATION"
    DIAGNOSTIC_QUESTIONS = "DIAGNOSTIC_QUESTIONS"
    SCORING = "SCORING"
    RECOMMENDATIONS = "RECOMMENDATIONS"
    FOLLOWUP = "FOLLOWUP"


STAGE_TRANSITIONS: dict[str, str] = {
    ConversationStage.INTRO:                 ConversationStage.PROFILE_COLLECTION,
    ConversationStage.PROFILE_COLLECTION:    ConversationStage.PROBLEM_DETECTION,
    ConversationStage.PROBLEM_DETECTION:     ConversationStage.CATEGORY_CONFIRMATION,
    ConversationStage.CATEGORY_CONFIRMATION: ConversationStage.DIAGNOSTIC_QUESTIONS,
    ConversationStage.DIAGNOSTIC_QUESTIONS:  ConversationStage.SCORING,
    ConversationStage.SCORING:               ConversationStage.RECOMMENDATIONS,
    ConversationStage.RECOMMENDATIONS:       ConversationStage.FOLLOWUP,
    ConversationStage.FOLLOWUP:              ConversationStage.FOLLOWUP,  
}
 
# Confidence threshold above which we stop diagnostics and go to recommendations
CONFIDENCE_THRESHOLD = 0.80

AXIS_REQUIRED_CATEGORIES = ["TYPE_1_PLATFORM_DEPENDENCY", "TYPE_3_LOW_MARGIN"]


class UserSession(BaseModel):
    # complete session stored per suer in redis as serialized JSON

    user_id:str
    stage:str = ConversationStage.INTRO
    question_index:int =  0
    confidence_scores:float = 0.0

    profile: dict = Field(default_factory=dict)   # owner_name, restaurant_name, city, cuisine_type, years_operating

    category:Optional[str] = None
    answers:dict = Field(default_factory=dict)

    score:Optional[float] = 0.0

    axis: Optional[str] = None

    #diagnostic turn tracking-- 
    #stores the key of the question currently waiting for an answer
    pending_question_key:Optional[str] = None

    # converstation history - sent to openAI each turn
    history:list = Field(default_factory=list)

    # metadata
    created_at:Optional[str] = None
    last_active:Optional[str] = None


def empty_session(user_id:str) -> UserSession:
    # factory for bran new users

    now = datetime.utcnow().isoformat()
    return UserSession(
        user_id=user_id,
        created_at=now,
        last_active=now
    )

