# # conversation_orchestrator.py

# import os
# import json
# import logging
# from datetime import datetime, timezone
# from app.schemas.session_schema import(
#     UserSession,
#     ConversationStage,
#     STAGE_TRANSITIONS,
#     CONFIDENCE_THRESHOLD
# )
# import redis.asyncio as redis          # async Redis client — matches your FastAPI async world
# from motor.motor_asyncio import AsyncIOMotorClient  # async MongoDB driver for FastAPI
# import openai
# from dotenv import load_dotenv

# # Workflow classes — each lives in its own file under app/workflows/
# from app.workflows.profile_workflow import ProfileWorkflow
# from app.workflows.problem_detection_workflow import ProblemDetectionWorkflow
# from app.workflows.diagnostic_workflow import DiagnosticWorkflow

# load_dotenv()


# logger = logging.getLogger(__name__)


# class ConversationState:
#     INTRO                = "INTRO"
#     PROFILE_COLLECTION   = "PROFILE_COLLECTION"
#     PROBLEM_DETECTION    = "PROBLEM_DETECTION"
#     CATEGORY_CONFIRMATION= "CATEGORY_CONFIRMATION"
#     DIAGNOSTIC_QUESTIONS = "DIAGNOSTIC_QUESTIONS"
#     SCORING              = "SCORING"
#     RECOMMENDATIONS      = "RECOMMENDATIONS"
#     FOLLOWUP             = "FOLLOWUP"

# # The allowed forward transitions — orchestrator enforces this, not the LLM
# STATE_TRANSITIONS = {
#     ConversationState.INTRO:                 ConversationState.PROFILE_COLLECTION,
#     ConversationState.PROFILE_COLLECTION:    ConversationState.PROBLEM_DETECTION,
#     ConversationState.PROBLEM_DETECTION:     ConversationState.CATEGORY_CONFIRMATION,
#     ConversationState.CATEGORY_CONFIRMATION: ConversationState.DIAGNOSTIC_QUESTIONS,
#     ConversationState.DIAGNOSTIC_QUESTIONS:  ConversationState.SCORING,
#     ConversationState.SCORING:               ConversationState.RECOMMENDATIONS,
#     ConversationState.RECOMMENDATIONS:       ConversationState.FOLLOWUP,
#     ConversationState.FOLLOWUP:              ConversationState.FOLLOWUP,  # terminal — loops
# }



# def build_empty_session() -> dict:
#     return {
#         "conversation_history": [],      # list of {role, content} dicts → sent to OpenAI
#         "current_state": ConversationState.INTRO,  # always starts at INTRO
#         "collected_profile": {},         # filled in by ProfileWorkflow
#         "detected_problem": None,        # filled in by ProblemDetectionWorkflow
#         "diagnostic_answers": [],        # filled in by DiagnosticWorkflow
#         "score": None,                   # filled in by ScoringEngine (future)
#         "last_interaction_time": None,   # ISO-8601 timestamp string
#     }


# # ===========================================================================
# # MAIN ORCHESTRATOR CLASS
# # ===========================================================================
# class ConversationOrchestrator:

#     def __init__(
#         self,
#         redis_client=None,
#         mongo_client=None,
#         openai_client=None,
#     ):
#         # --- Redis: fast in-memory session store (active conversation state) ---
#         self.redis = redis_client or redis.Redis(
#             host=os.getenv("REDIS_HOST", "localhost"),
#             port=int(os.getenv("REDIS_PORT", 6379)),
#             db=int(os.getenv("REDIS_DB", 0)),
#             decode_responses=True,      # always get strings back, not bytes
#         )

#         # --- MongoDB: persistent long-term storage (audit trail, analytics) ---
#         mongo_uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
#         self.mongo = mongo_client or AsyncIOMotorClient(mongo_uri)
#         self.db = self.mongo[os.getenv("MONGODB_DB", "conversational_ai")]
#         self.conversations_col = self.db["conversations"]  # one doc per user

#         # --- OpenAI: LLM for text generation ONLY, not flow control ---
#         self.openai = openai_client or openai.AsyncOpenAI(
#             api_key=os.getenv("OPENAI_API_KEY")
#         )

#         # --- Workflow registry: maps state → workflow class instance ---
#         # Add new workflows here as you build them
#         self.workflows: dict = {
#             ConversationState.INTRO:                 ProfileWorkflow(),
#             ConversationState.PROFILE_COLLECTION:    ProfileWorkflow(),
#             ConversationState.PROBLEM_DETECTION:     ProblemDetectionWorkflow(),
#             ConversationState.CATEGORY_CONFIRMATION: ProblemDetectionWorkflow(),
#             ConversationState.DIAGNOSTIC_QUESTIONS:  DiagnosticWorkflow(),
#         }

#         # TTL for Redis session keys — 24 hours of inactivity → session expires
#         self.SESSION_TTL_SECONDS = 60 * 60 * 24

#     # -----------------------------------------------------------------------
#     # 1. LOAD SESSION — Redis first, MongoDB fallback, blank if brand new
#     # -----------------------------------------------------------------------
#     async def load_user_session(self, user_id: str) -> dict:
#         """
#         Try Redis first (fast). If the session has expired or never existed,
#         fall back to MongoDB (persistent). If MongoDB also has nothing,
#         create a fresh empty session and save it immediately.
#         """
#         raw = await self.redis.get(user_id)

#         if raw:
#             logger.info(f"[{user_id}] Session loaded from Redis")
#             return json.loads(raw)  # deserialize JSON string → Python dict

#         # Redis miss → try MongoDB
#         mongo_doc = await self.conversations_col.find_one({"user_id": user_id})
#         if mongo_doc:
#             session = mongo_doc["session"]
#             logger.info(f"[{user_id}] Session restored from MongoDB")
#             # Warm Redis back up so the next message is fast
#             await self._save_to_redis(user_id, session)
#             return session

#         # Completely new user → build and persist an empty session
#         logger.info(f"[{user_id}] New user — creating empty session")
#         session = build_empty_session()
#         await self._save_to_redis(user_id, session)
#         await self._save_to_mongo(user_id, session)
#         return session

#     # -----------------------------------------------------------------------
#     # 2. DETERMINE CURRENT STATE — reads from session, never guesses
#     # -----------------------------------------------------------------------
#     def get_current_state(self, session: dict) -> str:
#         """
#         The state is always stored in the session — the orchestrator never
#         infers it from message content. That's the LLM's job to inform us
#         when a stage is COMPLETE (see advance_state_if_ready).
#         """
#         return session.get("current_state", ConversationState.INTRO)

#     # -----------------------------------------------------------------------
#     # 3. ROUTE TO WORKFLOW — returns the right workflow object for this state
#     # -----------------------------------------------------------------------
#     def route_to_workflow(self, state: str):
#         """
#         Looks up the workflow class registered for this state.
#         Returns None for states that don't need a workflow (SCORING, etc.)
#         """
#         workflow = self.workflows.get(state)
#         if not workflow:
#             logger.warning(f"No workflow registered for state: {state}")
#         return workflow

#     # -----------------------------------------------------------------------
#     # 4. BUILD PROMPT — workflow provides the system prompt, orchestrator
#     #    injects conversation history → full messages array for OpenAI
#     # -----------------------------------------------------------------------
#     def build_messages(self, session: dict, user_input: str, workflow) -> list:
#         """
#         Constructs the messages array that gets sent to the OpenAI API.

#         Structure:
#           [system prompt]          ← workflow defines this (persona + instructions)
#           [conversation history]   ← everything said so far (stored in session)
#           [new user message]       ← what the user just sent

#         This is the HYBRID part: LLM gets full context but operates inside
#         boundaries set by the workflow's system prompt.
#         """
#         system_prompt = workflow.get_system_prompt(session)

#         messages = [{"role": "system", "content": system_prompt}]
#         messages += session["conversation_history"]         # prior turns
#         messages.append({"role": "user", "content": user_input})  # new turn

#         return messages

#     # -----------------------------------------------------------------------
#     # 5. CALL LLM — async, uses the messages built above
#     # -----------------------------------------------------------------------
#     async def call_llm(self, messages: list) -> str:
#         """
#         Sends messages to OpenAI and returns the assistant's reply as a
#         plain string. Temperature 0.7 = slightly creative but not unhinged.
#         The orchestrator decides WHAT to ask; the LLM decides HOW to say it.
#         """
#         response = await self.openai.chat.completions.create(
#             model=os.getenv("OPENAI_MODEL", "gpt-4o"),
#             messages=messages,
#             temperature=0.7,
#             max_tokens=500,   # WhatsApp messages should be short — enforce it
#         )
#         return response.choices[0].message.content.strip()

#     # -----------------------------------------------------------------------
#     # 6. ADVANCE STATE — workflow tells orchestrator if the stage is done
#     # -----------------------------------------------------------------------
#     def advance_state_if_ready(self, session: dict, user_input: str, workflow) -> dict:
#         """
#         Asks the workflow: 'Is this stage complete given what the user said?'
#         If yes, move to the next state using STATE_TRANSITIONS.
#         The LLM does NOT call this — the workflow's is_complete() method
#         contains deterministic logic (e.g., required fields collected).
#         """
#         if workflow and workflow.is_complete(session, user_input):
#             current = session["current_state"]
#             next_state = STATE_TRANSITIONS.get(current, current)
#             logger.info(f"State transition: {current} → {next_state}")
#             session["current_state"] = next_state

#             # Let the workflow extract any structured data before leaving
#             # e.g., ProfileWorkflow saves name/age into collected_profile
#             session = workflow.extract_data(session, user_input)

#         return session

#     # -----------------------------------------------------------------------
#     # 7. UPDATE SESSION — append the new turn to conversation history
#     # -----------------------------------------------------------------------
#     def update_history(self, session: dict, user_input: str, assistant_reply: str) -> dict:
#         """
#         Appends the latest user + assistant turn to conversation_history.
#         This is what gets re-sent to OpenAI on the next message as context.
#         Also stamps the last interaction time for TTL/audit purposes.
#         """
#         session["conversation_history"].append({"role": "user",    "content": user_input})
#         session["conversation_history"].append({"role": "assistant","content": assistant_reply})
#         session["last_interaction_time"] = datetime.now(timezone.utc).isoformat()
#         return session

#     # -----------------------------------------------------------------------
#     # 8. SAVE SESSION — write back to both Redis (fast) and MongoDB (durable)
#     # -----------------------------------------------------------------------
#     async def save_session(self, user_id: str, session: dict):
#         """
#         Dual-write pattern:
#           Redis  → fast reads for the next message
#           MongoDB → durable storage if Redis evicts the key
#         Always save both so they stay in sync.
#         """
#         await self._save_to_redis(user_id, session)
#         await self._save_to_mongo(user_id, session)

#     async def _save_to_redis(self, user_id: str, session: dict):
#         await self.redis.set(
#             user_id,
#             json.dumps(session),          # serialize dict → JSON string
#             ex=self.SESSION_TTL_SECONDS,  # auto-expire after 24h inactivity
#         )

#     async def _save_to_mongo(self, user_id: str, session: dict):
#         await self.conversations_col.update_one(
#             {"user_id": user_id},         # filter: find this user's doc
#             {"$set": {"session": session, "updated_at": datetime.now(timezone.utc)}},
#             upsert=True,                  # create if doesn't exist, update if it does
#         )

#     # -----------------------------------------------------------------------
#     # 9. FINAL RESPONSE — the single public method your FastAPI route calls
#     # -----------------------------------------------------------------------
#     async def get_response(self, user_input: str, user_id: str) -> str:
#         """
#         The main entry point. Your FastAPI webhook calls this and gets back
#         a string to send to WhatsApp.

#         Full flow:
#           load session → get state → route to workflow → check if stage done
#           → advance state if needed → build messages → call LLM
#           → update history → save session → return reply
#         """
#         # Step 1: Load what we know about this user
#         session = await self.load_user_session(user_id)

#         # Step 2: Where are we in the conversation?
#         state = self.get_current_state(session)
#         logger.info(f"[{user_id}] Current state: {state}")

#         # Step 3: Which workflow owns this state?
#         workflow = self.route_to_workflow(state)

#         # Step 4: Did the user's message complete this stage? If so, advance.
#         session = self.advance_state_if_ready(session, user_input, workflow)

#         # Step 5: Re-fetch workflow in case state just changed
#         # (e.g., we moved from PROFILE_COLLECTION → PROBLEM_DETECTION)
#         new_state = self.get_current_state(session)
#         workflow = self.route_to_workflow(new_state)

#         # Step 6: Build the full messages array for OpenAI
#         if workflow:
#             messages = self.build_messages(session, user_input, workflow)
#         else:
#             # Fallback for states with no workflow yet (SCORING, RECOMMENDATIONS)
#             messages = self.build_messages(session, user_input, FallbackWorkflow())

#         # Step 7: LLM generates the reply text — it doesn't control flow
#         assistant_reply = await self.call_llm(messages)

#         # Step 8: Record this turn in conversation history
#         session = self.update_history(session, user_input, assistant_reply)

#         # Step 9: Persist everything
#         await self.save_session(user_id, session)

#         return assistant_reply


# # ---------------------------------------------------------------------------
# # FALLBACK WORKFLOW — used when a state has no registered workflow yet
# # Prevents crashes during development when you haven't built all workflows
# # ---------------------------------------------------------------------------
# class FallbackWorkflow:
#     def get_system_prompt(self, session: dict) -> str:
#         return (
#             "You are a helpful assistant. "
#             f"The current conversation stage is: {session.get('current_state')}. "
#             "Guide the user appropriately."
#         )

#     def is_complete(self, session: dict, user_input: str) -> bool:
#         return False  # never auto-advance from an unbuilt workflow

#     def extract_data(self, session: dict, user_input: str) -> dict:
#         return session  # no-op


#--------------------------------------------------------------------

# orchestrator/conversation_orchestrator.py
# The core brain. Every incoming message passes through here.
# Owns the state machine. Calls workflows. Never talks to OpenAI directly.
#
# Flow per message:
#   Load session → detect stage → evaluate info → determine missing info
#   → choose next question → generate response → update confidence
#   → if enough info: recommend, else: continue diagnostics
#   → save session → return reply
#
# KEY DESIGN:
#   session.pending_question_key tracks WHICH question we are waiting to
#   receive an answer for. This is set when we ASK a question, and read+cleared
#   when the user REPLIES. This is the fix for the answer-saving bug where
#   get_next_question() would return the wrong key on subsequent turns.

import logging

from requests import session
from app.schemas.session_schema import (
    UserSession,
    ConversationStage,
    STAGE_TRANSITIONS,
    CONFIDENCE_THRESHOLD,
)
from app.memory.session_manager import SessionManager
from app.workflows.profile_workflow import ProfileWorkflow
from app.workflows.problem_detection_workflow import ProblemDetectionWorkflow
from app.workflows.diagnostic_workflow import DiagnosticWorkflow
from app.workflows.recommendation_workflow import RecommendationWorkflow
from app.scoring.scoring_engine import ScoringEngine
from app.llm.response_formatter import ResponseFormatter

logger = logging.getLogger(__name__)


class ConversationOrchestrator:

    def __init__(self, session_manager: SessionManager):
        # Dependencies injected — easier to test and swap
        self.sessions = session_manager
        self.profile_wf = ProfileWorkflow()
        self.problem_wf = ProblemDetectionWorkflow()
        self.diagnostic_wf = DiagnosticWorkflow()
        self.recommendation_wf = RecommendationWorkflow()
        self.scoring = ScoringEngine()
        self.formatter = ResponseFormatter()

    # ===========================================================================
    # MAIN ENTRY POINT — called by api/chat.py
    # ===========================================================================
    async def handle_message(self, user_id: str, user_input: str) -> str:
        """
        Receives a raw WhatsApp message, runs the full orchestration pipeline,
        returns the reply string to send back to WhatsApp.
        """
        # ── 1. LOAD SESSION ────────────────────────────────────────────────────
        session = await self.sessions.load_session(user_id)
        logger.info(f"[{user_id}] Stage: {session.stage} | Input: {user_input!r}")

        # ── 2. DETECT STAGE AND ROUTE ──────────────────────────────────────────
        reply = await self._route(session, user_input)

        # ── 3. UPDATE HISTORY ──────────────────────────────────────────────────
        session = self.sessions.append_history(session, user_input, reply)

        # ── 4. SAVE SESSION ────────────────────────────────────────────────────
        await self.sessions.save_session(session)

        # ── 5. FORMAT AND RETURN ───────────────────────────────────────────────
        return self.formatter.format_text(reply)

    # ===========================================================================
    # ROUTER — dispatches to the right handler based on current stage
    # The only place where stage → handler mapping lives.
    # ===========================================================================
    async def _route(self, session: UserSession, user_input: str) -> str:
        stage = session.stage

        if stage == ConversationStage.INTRO:
            return await self._handle_intro(session, user_input)

        elif stage == ConversationStage.PROFILE_COLLECTION:
            return await self._handle_profile(session, user_input)

        elif stage == ConversationStage.PROBLEM_DETECTION:
            return await self._handle_problem_detection(session, user_input)

        elif stage == ConversationStage.CATEGORY_CONFIRMATION:
            return await self._handle_category_confirmation(session, user_input)

        elif stage == ConversationStage.DIAGNOSTIC_QUESTIONS:
            return await self._handle_diagnostics(session, user_input)

        elif stage == ConversationStage.SCORING:
            # BUG FIX 2: SCORING is a silent internal stage — no message sent.
            # Calculate final score, advance to RECOMMENDATIONS, generate reply.
            return await self._handle_scoring_passthrough(session)

        elif stage == ConversationStage.RECOMMENDATIONS:
            return await self._handle_recommendations(session)

        elif stage == ConversationStage.FOLLOWUP:
            return await self._handle_followup(session, user_input)

        else:
            logger.error(f"[{session.user_id}] Unknown stage: {stage}")
            return "Sorry, something went wrong. Let's start fresh — what's your restaurant called?"

    # ===========================================================================
    # STAGE HANDLERS
    # ===========================================================================

    async def _handle_intro(self, session: UserSession, user_input: str) -> str:
        """
        First ever message from this user.
        Send a warm greeting and ask the first profile question.
        """
        self._advance(session)       # INTRO → PROFILE_COLLECTION
        # question = await self.profile_wf.get_next_question(session, user_input)
        # session.question_index = 1   # we're now waiting for answer to question 0
        # return question
        return await self.profile_wf.get_next_question(session)

    async def _handle_profile(self, session: UserSession, user_input: str) -> str:
        """
        Collect profile fields one at a time.
        Save each answer, ask the next question.
        When all collected, move to problem detection.
        """
        # Save the answer to the question we just asked
        session = self.profile_wf.extract_answer(session, user_input)
        # Step 2: check if all done
        if self.profile_wf.is_complete(session):
            logger.info(f"[{session.user_id}] Profile complete — moving to problem detection")
            self._advance(session)      # PROFILE_COLLECTION → PROBLEM_DETECTION
            return await self.problem_wf.get_category_menu_message(session)

        # Step 3: ask next question
        return await self.profile_wf.get_next_question(session)
        # session.question_index += 1

        # if self.profile_wf.is_complete(session):
        #     logger.info(f"[{session.user_id}] Profile complete — moving to problem detection")
        #     self._advance(session)   # PROFILE_COLLECTION → PROBLEM_DETECTION
        #     return await self.problem_wf.get_category_menu_message(session)

        # # More profile questions remain
        # question = await self.profile_wf.get_next_question(session, user_input)
        # return question

    async def _handle_problem_detection(self, session: UserSession, user_input: str) -> str:
        
        """
        Detect the user's problem category from their response.
        Handles numeric selection, free text, and multiple problems.
        process_problem_input() handles all three cases internally.
        """
        category, needs_clarification, message = await self.problem_wf.process_problem_input(
            session, user_input
        )

        if needs_clarification:
            # User mentioned several problems — stay in PROBLEM_DETECTION
            # message already contains the re-ask with menu
            return message

        if category:
            session.category = category      # only the string
            logger.info(f"[{session.user_id}] Category detected: {category}")
            self._advance(session)           # PROBLEM_DETECTION → CATEGORY_CONFIRMATION

        # message already contains "If I understand correctly... is that right?"
        return message

    async def _handle_category_confirmation(self, session: UserSession, user_input: str) -> str:
        confirmed, message = await self.problem_wf.handle_confirmation(session, user_input)

        if confirmed:
            logger.info(f"[{session.user_id}] Category confirmed: {session.category}")
            self._advance(session)
            return await self._ask_next_diagnostic_question(session)

        return message
    
    async def _handle_diagnostics(self, session: UserSession, user_input: str) -> str:
        """
        The core diagnostic loop — one question per message.

        BUG FIX 1: The original code called get_next_question() to find which
        question to save the answer to. But get_next_question() returns the first
        UNANSWERED question — which after the first answer is already the NEXT
        question, not the one the user just answered. Answers were being saved
        to the wrong key.

        FIX: We store the key of the question we asked in session.pending_question_key
        when we ASK it (in _ask_next_diagnostic_question). When the user replies,
        we read that key here to save the answer to exactly the right place.

        Flow per message:
          1. Read pending_question_key → save user_input under that key
          2. Clear pending_question_key
          3. Recalculate confidence and severity score
          4. If critical questions done AND confidence ≥ threshold → recommend
          5. Else → ask the next question (which sets a new pending_question_key)
        """
        # ── Step 1: Save answer to the question we asked last turn ─────────────
        pending_key = getattr(session, "pending_question_key", None)

        if pending_key and pending_key not in session.answers:
            # Build a minimal question dict so extract_answer can use it
            question_stub = {"key": pending_key}
            session = self.diagnostic_wf.extract_answer(session, question_stub, user_input)
            logger.info(f"[{session.user_id}] Saved answer: {pending_key} = {user_input[:60]!r}")
        else:
            # No pending key means this is the very first diagnostic message
            # (user just confirmed category). Nothing to save yet.
            logger.info(f"[{session.user_id}] No pending question — first diagnostic turn")

        # ── Step 2: Clear pending key ──────────────────────────────────────────
        session.pending_question_key = None

        # ── Step 3: Recalculate scores ─────────────────────────────────────────
        total_qs = self.diagnostic_wf.total_questions(session)
        confidence = self.scoring.calculate_confidence(session, total_qs)
        session = self.sessions.update_confidence(session, confidence)
        session.score = self.scoring.calculate_severity_score(session)

        logger.info(
            f"[{session.user_id}] Confidence: {confidence:.2f} | "
            f"Score: {session.score} | Answers: {len(session.answers)}/{total_qs}"
        )

        # ── Step 4: Should we stop and recommend? ─────────────────────────────
        critical_done = self.diagnostic_wf.all_critical_answered(session)
        threshold_met = confidence >= CONFIDENCE_THRESHOLD

        if critical_done and threshold_met:
            logger.info(f"[{session.user_id}] Threshold met — advancing to SCORING")
            self._advance(session)   # DIAGNOSTIC_QUESTIONS → SCORING
            return await self._handle_scoring_passthrough(session)

        # ── Step 5: Ask the next question ─────────────────────────────────────
        return await self._ask_next_diagnostic_question(session)

    async def _ask_next_diagnostic_question(self, session: UserSession) -> str:
        """
        Finds the next unanswered question, stores its key as pending_question_key
        so the NEXT incoming message knows exactly which answer to save, then
        returns the conversational question text.

        If no questions remain → force-advance to SCORING.
        """
        next_q = self.diagnostic_wf.get_next_question(session)

        if not next_q:
            logger.info(f"[{session.user_id}] All questions exhausted — advancing to SCORING")
            self._advance(session)   # DIAGNOSTIC_QUESTIONS → SCORING
            return await self._handle_scoring_passthrough(session)

        # Store which question we are asking so the next reply saves correctly
        session.pending_question_key = next_q["key"]
        logger.info(f"[{session.user_id}] Asking: {next_q['key']} (pending)")

        return await self.diagnostic_wf.generate_question_message(session, next_q)

    async def _handle_scoring_passthrough(self, session: UserSession) -> str:
        """
        BUG FIX 2: SCORING is a silent internal stage — no WhatsApp message is
        sent to the user for this stage. It exists only to run the final score
        calculation cleanly before recommendations.

        Sequence:
          1. Calculate final severity score (already updated turn-by-turn, but
             this is the authoritative final calculation)
          2. Advance SCORING → RECOMMENDATIONS
          3. Immediately generate and return the recommendation message
        """
        # Final authoritative score calculation
        session.score = self.scoring.calculate_severity_score(session)
        logger.info(f"[{session.user_id}] SCORING passthrough — final score: {session.score}")

        # Advance silently: SCORING → RECOMMENDATIONS
        self._advance(session)

        # Generate and return recommendations (this is the message the user sees)
        return await self._handle_recommendations(session)

    async def _handle_recommendations(self, session: UserSession) -> str:
        """
        Generate and return the final recommendation message.
        Then move to FOLLOWUP stage.
        """
        reply = await self.recommendation_wf.generate(session)
        session.stage = ConversationStage.FOLLOWUP
        return reply

    async def _handle_followup(self, session: UserSession, user_input: str) -> str:
        """
        Terminal stage — user can ask follow-up questions.
        Simple open-ended LLM response using full session context.
        """
        from app.llm.prompt_builder import PromptBuilder
        from app.llm.openai_client import _chat
        from app.config.settings import settings

        system = PromptBuilder.recommendations_system_prompt(session)
        messages = PromptBuilder.build_messages(
            system_prompt=system,
            history=session.history,
            user_input=user_input,
        )
        return await _chat(
            messages=messages,
            model=settings.OPENAI_MODEL,
            max_tokens=300,
            temperature=0.7,
        )

    # ===========================================================================
    # HELPERS
    # ===========================================================================
    def _advance(self, session: UserSession) -> None:
        """
        Move session to the next stage using the STATE_TRANSITIONS map.
        This is the ONLY place stage transitions happen.
        """
        current = session.stage
        next_stage = STAGE_TRANSITIONS.get(current, current)
        logger.info(f"[{session.user_id}] {current} → {next_stage}")
        session.stage = next_stage
        session.question_index = 0