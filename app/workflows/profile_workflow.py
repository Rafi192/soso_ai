
# Collects restaurant profile information per MUFU Brain doc.
# Asks one question at a time, BUT also runs an extraction pass on every
# message so that if the user answers multiple fields in one message,
# all of them are captured — not just the one being asked.
#
# RISK MITIGATION:
# - Extraction never overwrites an already-saved field
# - extract_answer() always saves the CURRENTLY-ASKED field as a fallback,
#   guaranteeing forward progress even if extraction finds nothing
# - Extraction runs on the cheap mini model at temperature 0.0


# workflows/profile_workflow.py
import logging
from app.schemas.session_schema import UserSession
from app.llm.prompt_builder import PromptBuilder
from app.llm.openai_client import chat, extract_profile_fields
from app.config.settings import settings

logger = logging.getLogger(__name__)

# Questions in exact MUFU Brain doc order.
# The first question includes the greeting per the doc's intro script.
PROFILE_QUESTIONS = [
    {
        "key": "restaurant_name",
        "raw": "Hi, I'm your personal advisor, I'm here to help you (re)boost your restaurant. To start, what is the name of your restaurant?",
        "raw_fr": "Bonjour, je suis votre conseiller personnel, je suis ici pour vous aider à (re)booster votre restaurant. Pour commencer, quel est le nom de votre restaurant ?",
        "question_only": "What is the name of your restaurant?",
    },
    {
        "key": "city",
        "raw": "Great! And where are you located? (city, neighborhood or full address)",
        "question_only": "Where is your restaurant located? (city, neighborhood or full address)",
    },
    {
        "key": "owner_name",
        "raw": "Are you the manager? How can I call you?",
        "question_only": "Are you the manager? What is your name?",
    },
    {
        "key": "cuisine_type",
        "raw": "What type of food do you serve? (e.g.: burgers, tacos, pizza, sushi, African food, sandwiches...)",
        "question_only": "What type of food do you serve?",
    },
    {
        "key": "locations_and_service",
        "raw": "How many locations do you have? And do you mainly work on-site, takeaway, delivery, or all three?",
        "question_only": "How many locations do you have, and do you mainly work on-site, takeaway, delivery, or all three?",
    },
    {
        "key": "platforms_or_direct",
        "raw": "Which delivery platforms are you on? (Uber Eats, Deliveroo, Just Eat, other...) or do you have a direct ordering system (your website, your app, other)?",
        "question_only": "Which delivery platforms are you on, or do you have a direct ordering system?",
    },
]

# Map of key -> question text, used for extraction prompts
PROFILE_FIELD_QUESTIONS = {q["key"]: q["question_only"] for q in PROFILE_QUESTIONS}


class ProfileWorkflow:

    def is_complete(self, session: UserSession) -> bool:
        required = [q["key"] for q in PROFILE_QUESTIONS]
        return all(k in session.profile for k in required)

    def get_next_unanswered(self, session: UserSession) -> dict | None:
        for q in PROFILE_QUESTIONS:
            if q["key"] not in session.profile:
                return q
        return None

    def _missing_fields(self, session: UserSession) -> dict[str, str]:
        """Returns {key: question} for all fields not yet collected."""
        return {
            k: v for k, v in PROFILE_FIELD_QUESTIONS.items()
            if k not in session.profile
        }

    async def extract_answer(self, session: UserSession, user_input: str) -> UserSession:
        """
        Two-step save:
          1. Run extraction on the full message — may capture multiple fields
             at once (e.g. user gives restaurant name + city + cuisine together).
          2. SAFETY NET: ensure the field for the question that was actually
             asked gets saved even if extraction missed it. This guarantees
             the conversation always moves forward.

        Never overwrites a field that's already saved.
        """
        missing = self._missing_fields(session)

        # ── Step 1: multi-field extraction ──────────────────────────────────
        if missing:
            try:
                extracted = await extract_profile_fields(user_input, missing)
                for key, value in extracted.items():
                    if key not in session.profile:   # never overwrite
                        session.profile[key] = str(value).strip()
                        logger.info(f"[{session.user_id}] Profile extracted: {key} = {value}")
            except Exception as e:
                # Extraction failure must never break the conversation —
                # fall through to the safety net below.
                logger.warning(f"[{session.user_id}] Profile extraction failed: {e}")

        # ── Step 2: safety net — save answer to the question just asked ─────
        # session.pending_question_key is set by the orchestrator before
        # asking. If that field is still missing after extraction, save the
        # raw message to it directly so we never get stuck on one question.
        pending_key = getattr(session, "pending_question_key", None)
        if pending_key and pending_key in PROFILE_FIELD_QUESTIONS:
            if pending_key not in session.profile:
                session.profile[pending_key] = user_input.strip()
                logger.info(f"[{session.user_id}] Profile saved (fallback): {pending_key} = {user_input.strip()}")

        return session
    
    async def detect_language(self, session:UserSession) -> str:
        #detects the user lanuguage in eitherfr in french or en if english
        last_user_msg = ''
        for msg in reversed(session.history):
            if msg["role"] == "user":
                last_user_msg = msg["content"]
                break
        
        if not last_user_msg:
            return 'en'  # default to English if no user message found
        
        try:
            messages = [
                {"role": "system",
                 "content": (
                     "Detect the language of the following message"
                     "Respond with ONLY one word: 'fr' if French, 'en' if English."
                     "No explanations, no extra text, just the language code. Do not hallucinate or guess — if it's not clearly one of those two languages, respond with 'en' by default."
                 )}
            ]



            result = await chat(
                messages = messages,
                model = settings.OPENAI_MINI_MODEL,
                temperature = 0.0
            )

            result = result.strip().lower()
            return 'fr' if result == 'fr' else 'en'
        
        except Exception as e:
            return 'en'  # on any error, default to English


    async def get_next_question(self, session: UserSession) -> str | None:
      
        next_q = self.get_next_unanswered(session)
        if not next_q:
            return None

        session.pending_question_key = next_q["key"]
        lang= await self.detect_language(session)
        raw = next_q.get(f"raw_{lang}", next_q.get("raw_en", next_q["raw"]))
 
        # Present the question exactly as written — LLM should not rephrase
        system = PromptBuilder.profile_system_prompt()
        messages = PromptBuilder.build_messages(
            system_prompt=system,
            history=session.history,
            user_input=(
                f"Present this exact question to the user, word for word, "
                f"with no changes: \"{raw}\""
            ),
        )
        return await chat(
            messages=messages,
            model=settings.OPENAI_MODEL,
            max_tokens=120,
            temperature=0.3,   # low temperature — minimize rephrasing drift
        )