# workflows/recommendation_workflow.py
# Generates the final output: summary + root cause + recommendations + next steps.
# Deterministic engine selects recommendations; LLM formats them humanly.

import logging
from app.schemas.session_schema import UserSession
from app.llm.openai_client import summarize_findings, generate_final_response
from app.scoring.scoring_engine import ScoringEngine
from app.recommendations.recommendation_engine import RecommendationEngine

logger = logging.getLogger(__name__)


class RecommendationWorkflow:

    def __init__(self):
        self.scoring = ScoringEngine()
        self.rec_engine = RecommendationEngine()

    async def generate(self, session: UserSession) -> str:
        """
        Full recommendation pipeline:
        1. Calculate final severity score
        2. Select recommendations (deterministic)
        3. Summarize findings (LLM)
        4. Format final message (LLM)
        """
        # Step 1: Final score
        session.score = self.scoring.calculate_severity_score(session)
        logger.info(f"[{session.user_id}] Final score: {session.score}")

        # Step 2: Pick recommendations — no AI, pure logic
        recommendations = self.rec_engine.get_recommendations(session)
        logger.info(f"[{session.user_id}] {len(recommendations)} recommendations selected")

        # Step 3: LLM summarizes the findings in natural language
        summary = await summarize_findings(
            answers=session.answers,
            category=session.category or "GENERAL",
            score=session.score,
        )

        # Step 4: LLM formats everything into one final WhatsApp message
        final_message = await generate_final_response(
            summary=summary,
            recommendations=recommendations,
            profile=session.profile,
        )

        return final_message