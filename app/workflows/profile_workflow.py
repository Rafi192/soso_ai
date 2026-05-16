# workflows/profile_workflow.py
# Collects basic restaurant profile information.
# Runs during INTRO and PROFILE_COLLECTION stages.
# Asks one question at a time, saves answers into session.profile.

import logging
from app.schemas.session_schema import UserSession
from app.llm.prompt_builder import PromptBuilder
from app.llm.openai_client import _chat
from app.config.settings import settings

logger = logging.getLogger(__name__)

# The questions asked in order, with the session key they map to.
# question_index in the session tracks where we are.
PROFILE_QUESTIONS = [
    {
        "key": "owner_name",
        "raw": "What's your name?",
    },
    {
        "key": "restaurant_name",
        "raw": "What's the name of your restaurant?",
    },
    {
        "key": "city",
        "raw": "Which city is your restaurant located in?",
    },
    {
        "key": "cuisine_type",
        "raw": "What type of cuisine do you serve?",
    },
    {
        "key": "years_operating",
        "raw": "How long have you been operating?",
    },
]


class ProfileWorkflow:

    def is_complete(self, session: UserSession) -> bool:
        """
        Profile is complete when all required fields have been collected.
        """
        required = [q["key"] for q in PROFILE_QUESTIONS]
        return all(k in session.profile for k in required)

    def get_next_question_index(self, session: UserSession) -> int:
        """
        Find the first question whose key hasn't been answered yet.
        """
        for i, q in enumerate(PROFILE_QUESTIONS):
            if q["key"] not in session.profile:
                return i
        return len(PROFILE_QUESTIONS)   # all done

    async def get_next_question(self, session: UserSession, user_input: str) -> str:
        """
        Returns the next question to ask, rephrased naturally by the LLM.
        If user_input contains an answer to the previous question, save it first.
        """
        # Save the answer to the previous question if there was one
        prev_index = session.question_index - 1
        if 0 <= prev_index < len(PROFILE_QUESTIONS) and user_input.strip():
            key = PROFILE_QUESTIONS[prev_index]["key"]
            session.profile[key] = user_input.strip()
            logger.info(f"[{session.user_id}] Profile saved: {key} = {user_input.strip()}")

        # Find the next unanswered question
        next_index = self.get_next_question_index(session)
        if next_index >= len(PROFILE_QUESTIONS):
            return None     # signal to orchestrator: profile is complete

        raw_question = PROFILE_QUESTIONS[next_index]["raw"]

        # Rephrase using LLM for natural WhatsApp tone
        system = PromptBuilder.profile_system_prompt()
        messages = PromptBuilder.build_messages(
            system_prompt=system,
            history=session.history,
            user_input=f"Ask this question naturally: {raw_question}",
        )
        reply = await _chat(
            messages=messages,
            model=settings.OPENAI_MODEL,
            max_tokens=100,
            temperature=0.7,
        )
        return reply

    def extract_answer(self, session: UserSession, user_input: str) -> UserSession:
        """
        Called by orchestrator to save the current answer before advancing.
        """
        idx = session.question_index
        if idx < len(PROFILE_QUESTIONS):
            key = PROFILE_QUESTIONS[idx]["key"]
            session.profile[key] = user_input.strip()
        return session