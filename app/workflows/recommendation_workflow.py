# workflows/recommendation_workflow.py
# Generates the final recommendation message.
# Deterministic engine selects WHAT to recommend.
# LLM only formats HOW to present it — never changes the content.

import logging
from app.schemas.session_schema import UserSession
from app.llm.openai_client import chat
from app.llm.prompt_builder import PromptBuilder
from app.config.settings import settings
from app.scoring.scoring_engine import ScoringEngine
from app.recommendations.recommendation_engine import RecommendationEngine

logger = logging.getLogger(__name__)


class RecommendationWorkflow:

    def __init__(self):
        self.scoring = ScoringEngine()
        self.rec_engine = RecommendationEngine()

    async def generate(self, session: UserSession) -> str:
    # Always recalculate — don't trust the session score
        session.score = self.scoring.calculate_severity_score(session)
        logger.info(f"[{session.user_id}] Final score: {session.score}")

        recommendations = self.rec_engine.get_recommendations(session, max_recommendations=4)
        session.last_recommendations = recommendations
        logger.info(f"[{session.user_id}] {len(recommendations)} recommendations selected")

        final_message = await self._format_recommendations(session, recommendations)
        logger.info(f"[{session.user_id}] Formatted message: {final_message[:80]!r}")
        return final_message

#     async def generate(self, session: UserSession) -> str:
       
#         # # Step 1: Final score
#         # session.score = self.scoring.calculate_severity_score(session)
#         # logger.info(f"[{session.user_id}] Final score: {session.score}")
#         if session.score is None:
#             raise ValueError(
#                 f"[{session.user_id}] Recommendation workflow called before score calculation."
#             )
        
#         logger.info(
#     f"[{session.user_id}]---- Using severity score ----{session.score}"
# )

#         # Step 2: Select recommendations — pure logic, no AI
#         recommendations = self.rec_engine.get_recommendations(session, max_recommendations=4)  # get top 4 recommendations for the LLM to format
#         session.last_recommendations = recommendations
#         logger.info(f"[{session.user_id}] {len(recommendations)} recommendations selected")

#         # Step 3: Format the message
#         return await self._format_recommendations(session, recommendations)
    
    async def _format_recommendations(
    self, session: UserSession, recommendations: list[str]
) -> str:
        
        owner_name = session.profile.get("owner_name", "")
        restaurant_name = session.profile.get("restaurant_name", "your restaurant")
        category = session.category or "GENERAL"

        # Detect language from last user message — not from profile data
        last_user_msg = ""
        for msg in reversed(session.history):
            if msg["role"] == "user":
                last_user_msg = msg["content"]
                break

        numbered = "\n".join(
            f"{i+1}. {rec}" for i, rec in enumerate(recommendations)
        )

        # system_prompt = (
        #     f"You are a restaurant business consultant delivering final recommendations "
        #     f"to {owner_name} at {restaurant_name}. "
        #     "Present the recommendations below exactly as written — do not replace, "
        #     "summarize, or omit any of them. Do not invent new recommendations. "
        #     "If a recommendation mentions a partnership (GFV, MrBeast Burger, Hemblem, TheFork, "
        #     "Zelty, Innovorder, Tiller), keep that reference intact. "
        #     "Structure: one short intro sentence, numbered recommendations, one closing sentence. "
        #     f"Problem area: {category}. Score: {session.score}. "
        #     # Explicit language instruction — use last message, not profile data
        #     f"IMPORTANT: The user's last message was '{last_user_msg}'. "
        #     f"You MUST respond in the exact same language as that message. "
        #     f"If the last message is in English, respond in English only. "
        #     f"If in French, respond in French only. Never mix languages. "
        #     f"If unclear, default to English. "        
        #     f"Never respond in any other language. "
        #     "No emojis. No filler. Under 300 words."
        # )
        system_prompt = (
    f"You are a restaurant business consultant delivering final recommendations "
    f"to {owner_name} at {restaurant_name}. "
    "Present the recommendations below exactly as written — do not replace, "
    "summarize, or omit any of them. Do not invent new recommendations. "
    "If a recommendation mentions a partnership (GFV, MrBeast Burger, Hemblem, TheFork, "
    "Zelty, Innovorder, Tiller), keep that reference intact. "
    "Structure: one short intro sentence addressed to the owner by name, "
    "then the numbered recommendations, "
    "then one closing sentence offering to elaborate. "
    f"Problem area: {category}. Severity score: {session.score}. "
    "LANGUAGE: Respond in English or French only, matching the language of the conversation. "
    "Default to English if unclear. Never respond in any other language. "
    "TONE: Direct, warm, precise. No filler words. No emojis. Under 300 words."
)

        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": (
                    f"Present these recommendations to {owner_name} at {restaurant_name}:\n\n"
                    f"{numbered}"
                ),
            },
        ]

        return await chat(
            messages=messages,
            model=settings.OPENAI_MODEL,
            max_tokens=500,
            temperature=0.5,
        )

    # async def _format_recommendations(
    #     self, session: UserSession, recommendations: list[str]
    # ) -> str:
    #     """
    #     Asks the LLM to present the recommendations in a warm, structured
    #     WhatsApp message. The LLM must present the recommendations exactly
    #     as given — it must not replace, summarize, or ignore any of them.
    #     Partnerships (GFV, Hemblem, TheFork) must be mentioned by name.
    #     """
    #     owner_name = session.profile.get("owner_name", "")
    #     restaurant_name = session.profile.get("restaurant_name", "your restaurant")
    #     category = session.category or "GENERAL"

    #     # Number each recommendation for the LLM
    #     numbered = "\n".join(
    #         f"{i+1}. {rec}" for i, rec in enumerate(recommendations)
    #     )

    #     system_prompt = (
    #         f"You are a restaurant business consultant delivering final recommendations "
    #         f"to {owner_name} at {restaurant_name}. "
    #         "Present the recommendations below exactly as written — do not replace, "
    #         "summarize, or omit any of them. Do not invent new recommendations. "
    #         "If a recommendation mentions a partnership (GFV, MrBeast Burger, Hemblem, TheFork, "
    #         "Zelty, Innovorder, Tiller), keep that reference intact — these are real exclusive partnerships. "
    #         "Structure your message as: one short intro sentence, then the numbered recommendations, "
    #         "then one closing sentence offering to elaborate. "
    #         f"Severity score: {session.score}. Problem area: {category}. "
    #         f"{PromptBuilder.UNIVERSAL_RULES if hasattr(PromptBuilder, 'UNIVERSAL_RULES') else ''}"
    #     )

    #     # Build the universal rules inline since we need them here
    #     universal_rules = (
    #         "LANGUAGE: Detect the language the user is writing in and respond in that same language. "
    #         "TONE: Direct, warm, precise. No filler, no emojis unless user used them first. "
    #         "Under 300 words total."
    #     )

    #     messages = [
    #         {
    #             "role": "system",
    #             "content": f"{system_prompt}\n\n{universal_rules}",
    #         },
    #         {
    #             "role": "user",
    #             "content": (
    #                 f"Present these recommendations to {owner_name} at {restaurant_name}:\n\n"
    #                 f"{numbered}"
    #             ),
    #         },
    #     ]

    #     return await chat(
    #         messages=messages,
    #         model=settings.OPENAI_MODEL,
    #         max_tokens=500,
    #         temperature=0.5,   # low temperature — we want faithful presentation
    #     )