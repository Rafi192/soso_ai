# orchestrator/conversation_orchestrator.py
# Core brain — owns the state machine, calls workflows, never calls OpenAI directly.
#
# New in this version:
#   - Axis pivot question for TYPE_1 and TYPE_3 before diagnostics start
#   - pending_question_key = "axis" is the reserved key for pivot answers
#   - Language detection handled automatically via prompt_builder UNIVERSAL_RULES
#   - Precise tone enforced via UNIVERSAL_RULES in every prompt

import logging
from app.schemas.session_schema import (
    UserSession,
    ConversationStage,
    STAGE_TRANSITIONS,
    CONFIDENCE_THRESHOLD,
    AXIS_REQUIRED_CATEGORIES,
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
        self.sessions = session_manager
        self.profile_wf = ProfileWorkflow()
        self.problem_wf = ProblemDetectionWorkflow()
        self.diagnostic_wf = DiagnosticWorkflow()
        self.recommendation_wf = RecommendationWorkflow()
        self.scoring = ScoringEngine()
        self.formatter = ResponseFormatter()

    # ===========================================================================
    # MAIN ENTRY POINT
    # ===========================================================================
    async def handle_message(self, user_id: str, user_input: str) -> tuple[str, str | None]:
        session = await self.sessions.load_session(user_id)
        logger.info(f"[{user_id}] Stage: {session.stage} | Input: {user_input!r}")

        reply = await self._route(session, user_input)
        logger.info(f"[{session.user_id}] Reply to save in history: {reply[:100]!r}")
        action = self._get_action(session.stage)  

        # logger.info(f"[{user_id}] Reply to save in history: {reply[:100]!r}")

        session = self.sessions.append_history(session, user_input, reply)
        await self.sessions.save_session(session)

        return self.formatter.format_text(reply), action
    
    def _get_action(self, stage: str) -> str | None:
        mapping = {
            "PROBLEM_DETECTION":  "ONBOARDING_COMPLETE",
            "FOLLOWUP":           "SHOW_BOOKING_CTA",
            "RECOMMENDATIONS":    "UPDATE_STAGE_HOT_LEAD",
        }
        return mapping.get(stage)

    # ===========================================================================
    # ROUTER
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
            return await self._handle_scoring_passthrough(session)

        elif stage == ConversationStage.RECOMMENDATIONS:
            return await self._handle_recommendations(session)

        elif stage == ConversationStage.FOLLOWUP:
            return await self._handle_followup(session, user_input)

        else:
            logger.error(f"[{session.user_id}] Unknown stage: {stage}")
            return "Something went wrong. What is the name of your restaurant?"

    # ===========================================================================
    # STAGE HANDLERS
    # ===========================================================================

    async def _handle_intro(self, session: UserSession, user_input: str) -> str:
        self._advance(session)
        return await self.profile_wf.get_next_question(session)

    async def _handle_profile(self, session: UserSession, user_input: str) -> str:
        session = await self.profile_wf.extract_answer(session, user_input)

        if self.profile_wf.is_complete(session):
            logger.info(f"[{session.user_id}] Profile complete — moving to problem detection")
            self._advance(session)
            return await self.problem_wf.get_category_menu_message(session)

        return await self.profile_wf.get_next_question(session)

    async def _handle_problem_detection(self, session: UserSession, user_input: str) -> str:
        category, needs_clarification, message = await self.problem_wf.process_problem_input(
            session, user_input
        )

        if needs_clarification:
            return message

        if category:
            session.category = category
            logger.info(f"[{session.user_id}] Category detected: {category}")
            self._advance(session)   # PROBLEM_DETECTION → CATEGORY_CONFIRMATION

        return message

    async def _handle_category_confirmation(self, session: UserSession, user_input: str) -> str:
        confirmed, message = await self.problem_wf.handle_confirmation(session, user_input)

        if confirmed:
            logger.info(f"[{session.user_id}] Category confirmed: {session.category}")
            self._advance(session)   # CATEGORY_CONFIRMATION → DIAGNOSTIC_QUESTIONS

            # Check if this category needs a pivot question before diagnostics
            if session.category in AXIS_REQUIRED_CATEGORIES:
                return await self._ask_pivot_question(session)

            return await self._ask_next_diagnostic_question(session)

        return message

    async def _handle_diagnostics(self, session: UserSession, user_input: str) -> str:
        """
        Diagnostic loop with axis pivot support.

        Special case: if pending_question_key == "axis", the user is answering
        the pivot question (delivery vs on-site / costs vs revenue).
        Save that as session.axis and start the real diagnostics.

        Normal case: save answer to pending key, update scores, ask next question.
        """
        pending_key = getattr(session, "pending_question_key", None)

        # ── Pivot answer ───────────────────────────────────────────────────────
        if pending_key == "axis":
            session.axis = self._resolve_axis(session.category, user_input)
            session.pending_question_key = None
            logger.info(f"[{session.user_id}] Axis set to: {session.axis}")
            return await self._ask_next_diagnostic_question(session)

        # ── Normal diagnostic answer ───────────────────────────────────────────
        # Step 1: multi-answer extraction — check if this message also answers
        # OTHER pending questions, not just the one that was asked.
        pending_questions_map = self._build_pending_questions_map(session)
        if pending_questions_map:
            try:
                from app.llm.openai_client import extract_diagnostic_answers
                extracted = await extract_diagnostic_answers(user_input, pending_questions_map)
                for key, value in extracted.items():
                    if key not in session.answers:   # never overwrite
                        session.answers[key] = str(value).strip()
                        logger.info(f"[{session.user_id}] Multi-extracted: {key} = {value}")
            except Exception as e:
                logger.warning(f"[{session.user_id}] Diagnostic extraction failed: {e}")

        # Step 2: SAFETY NET — always save the answer to the question that was
        # actually asked, even if extraction missed it. Guarantees progress.
        if pending_key and pending_key not in session.answers:
            question_stub = {"key": pending_key}
            session = self.diagnostic_wf.extract_answer(session, question_stub, user_input)
            logger.info(f"[{session.user_id}] Saved answer: {pending_key} = {user_input[:60]!r}")
        else:
            logger.info(f"[{session.user_id}] No pending question — first diagnostic turn")

        session.pending_question_key = None

        # ── Recalculate scores ─────────────────────────────────────────────────
        total_qs = self.diagnostic_wf.total_questions(session)
        confidence = self.scoring.calculate_confidence(session, total_qs)
        session = self.sessions.update_confidence(session, confidence)
        session.score = self.scoring.calculate_severity_score(session)

        logger.info(
            f"[{session.user_id}] Confidence: {confidence:.2f} | "
            f"Score: {session.score} | Answers: {len(session.answers)}/{total_qs}"
        )

        # ── Stop condition ─────────────────────────────────────────────────────
        critical_done = self.diagnostic_wf.all_critical_answered(session)
        threshold_met = confidence >= CONFIDENCE_THRESHOLD

        if critical_done and threshold_met:
            logger.info(f"[{session.user_id}] Threshold met — advancing to SCORING")
            self._advance(session)
            return await self._handle_scoring_passthrough(session)

        return await self._ask_next_diagnostic_question(session)

    def _build_pending_questions_map(self, session: UserSession) -> dict[str, str]:
      
        questions = self.diagnostic_wf.get_questions(session)
        pending_key = getattr(session, "pending_question_key", None)

        return {
            q["key"]: q["raw"]
            for q in questions
            if q["key"] not in session.answers and q["key"] != pending_key
        }

    async def _ask_pivot_question(self, session: UserSession) -> str:
 
        from app.llm.openai_client import chat
        from app.llm.prompt_builder import PromptBuilder
        from app.config.settings import settings

        if session.category == "TYPE_1_PLATFORM_DEPENDENCY":
            raw = "Do you want to increase your revenue more on delivery or on-site?"
        else:  # TYPE_3_LOW_MARGIN
            raw = "When you say you do not earn enough, is it more because your costs are too high or because your revenue is too low?"

        session.pending_question_key = "axis"
        logger.info(f"[{session.user_id}] Asking pivot question for {session.category}")

        messages = PromptBuilder.build_messages(
            system_prompt=PromptBuilder.pivot_system_prompt(session),
            history=session.history,
            user_input=f"Ask this question naturally: {raw}",
        )
        return await chat(
            messages=messages,
            model=settings.OPENAI_MODEL,
            max_tokens=80,
            temperature=0.6,
        )

    def _resolve_axis(self, category: str, user_input: str) -> str:
        """
        Maps the pivot answer to "A" or "B".
        TYPE_1: A = delivery, B = on-site
        TYPE_3: A = costs too high, B = revenue too low
        Defaults to "A" if unclear.
        """
        text = user_input.lower()

        if category == "TYPE_1_PLATFORM_DEPENDENCY":
            if any(w in text for w in ["delivery", "deliveroo", "uber", "platform", "online", "livraison"]):
                return "A"
            if any(w in text for w in ["on-site", "onsite", "dine", "place", "restaurant", "sur place"]):
                return "B"
            return "A"   # default to delivery for TYPE_1

        if category == "TYPE_3_LOW_MARGIN":
            if any(w in text for w in ["cost", "expensive", "spending", "waste", "charges", "dépenses", "coûts"]):
                return "A"
            if any(w in text for w in ["revenue", "sales", "income", "customers", "chiffre", "ventes", "clients"]):
                return "B"
            if any(w in text for w in ["both", "les deux", "tout"]):
                return "B"   # per MUFU Brain doc: both → start with Axis B
            return "A"   # default to costs for TYPE_3

        return "A"

    async def _ask_next_diagnostic_question(self, session: UserSession) -> str:
        next_q = self.diagnostic_wf.get_next_question(session)

        if not next_q:
            logger.info(f"[{session.user_id}] All questions exhausted — advancing to SCORING")
            self._advance(session)
            return await self._handle_scoring_passthrough(session)

        session.pending_question_key = next_q["key"]
        logger.info(f"[{session.user_id}] Asking: {next_q['key']} (pending)")

        return await self.diagnostic_wf.generate_question_message(session, next_q)

    async def _handle_scoring_passthrough(self, session: UserSession) -> str:
        session.score = self.scoring.calculate_severity_score(session)
        logger.info(f"[{session.user_id}] SCORING passthrough — final score: {session.score}")
        self._advance(session)
        result = await self._handle_recommendations(session)
        logger.info(f"[{session.user_id}] Recommendation result: {result[:80]!r}")
        return result

    async def _handle_recommendations(self, session: UserSession) -> str:
        reply = await self.recommendation_wf.generate(session)
        session.stage = ConversationStage.FOLLOWUP
        return reply

    async def _handle_followup(self, session: UserSession, user_input: str) -> str:
        from app.llm.prompt_builder import PromptBuilder
        from app.llm.openai_client import chat
        from app.config.settings import settings

        messages = PromptBuilder.build_messages(
            system_prompt=PromptBuilder.followup_system_prompt(session),
            history=session.history,
            user_input=user_input,
        )
        return await chat(
            messages=messages,
            model=settings.OPENAI_MODEL,
            max_tokens=300,
            temperature=0.7,
        )

    # ===========================================================================
    # HELPERS
    # ===========================================================================
    def _advance(self, session: UserSession) -> None:
        current = session.stage
        next_stage = STAGE_TRANSITIONS.get(current, current)
        logger.info(f"[{session.user_id}] {current} → {next_stage}")
        session.stage = next_stage
        session.question_index = 0