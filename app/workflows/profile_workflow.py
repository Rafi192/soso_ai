# workflows/profile_workflow.py
# Collects basic restaurant profile information.
# Runs during INTRO and PROFILE_COLLECTION stages.
# Asks one question at a time, saves answers into session.profile.

import logging
from app.schemas.session_schema import UserSession
from app.llm.prompt_builder import PromptBuilder
from app.llm.openai_client import chat
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
        required = [q["key"] for q in PROFILE_QUESTIONS]
        return all(k in session.profile for k in required)

    def get_next_unanswered(self, session: UserSession) -> dict | None:
        """
        Returns the next unanswered question dict, or None if all done.
        Uses session.profile keys — not question_index — to find what's missing.
        This way it's immune to index offset bugs.
        """
        for q in PROFILE_QUESTIONS:
            if q["key"] not in session.profile:
                return q
        return None

    def extract_answer(self, session: UserSession, user_input: str) -> UserSession:
        """
        Saves user_input to the FIRST unanswered profile key.
        Called by orchestrator BEFORE get_next_question().
        Only saves if there's an unanswered question pending.
        """
        next_q = self.get_next_unanswered(session)
        if next_q:
            session.profile[next_q["key"]] = user_input.strip()
            logger.info(f"[{session.user_id}] Profile saved: {next_q['key']} = {user_input.strip()}")
        return session

    async def get_next_question(self, session: UserSession, user_input: str = "") -> str:
        """
        Returns the next unanswered question rephrased by LLM.
        Does NOT save answers — extract_answer() handles that.
        """
        next_q = self.get_next_unanswered(session)
        if not next_q:
            return None     # all done — orchestrator handles transition

        system = PromptBuilder.profile_system_prompt()
        messages = PromptBuilder.build_messages(
            system_prompt=system,
            history=session.history,
            user_input=f"Ask this question naturally: {next_q['raw']}",
        )
        return await chat(
            messages=messages,
            model=settings.OPENAI_MODEL,
            max_tokens=100,
            temperature=0.7,
        )