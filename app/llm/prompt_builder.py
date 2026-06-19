# llm/prompt_builder.py
# Builds the messages array sent to OpenAI for each turn.
# All prompts share two universal rules injected into every system prompt:
#   1. Language detection — respond in the same language the user writes in
#   2. Tone — precise, no filler, no emojis, direct and warm

from app.schemas.session_schema import UserSession


# ---------------------------------------------------------------------------
# UNIVERSAL INSTRUCTIONS — injected into every system prompt
# ---------------------------------------------------------------------------
UNIVERSAL_RULES = (
    "LANGUAGE RULE — follow this strictly: "
    "Look at the user's most recent message. "
    "If it is written in French, respond in French. "
    "If it is written in English, respond in English. "
    "If the language is unclear, default to English. "
    "You may ONLY respond in English or French — no other language under any circumstance. "
    "Do NOT infer language from the restaurant name, city, or phone number — "
    "only from the actual words the user wrote. "
    "TONE: Direct, warm, and precise. No filler words. "
    "No emojis unless the user used them first. "
    "Keep responses concise."
)

class PromptBuilder:

    # ---------------------------------------------------------------------------
    # PROFILE COLLECTION
    # ---------------------------------------------------------------------------
    # @staticmethod
    # def profile_system_prompt() -> str:
    #     return (
    #         "You are a restaurant business consultant starting a consultation on WhatsApp. "
    #         "Your job is to collect basic information about the restaurant: "
    #         "the owner's personal name, restaurant name, city, type of cuisine, and how long they have been operating. "
    #         "Ask one question at a time. The owner's name is their personal name, not the restaurant name. "
    #         f"{UNIVERSAL_RULES}"
    #     )
    @staticmethod
    def profile_system_prompt() -> str:
        return (
            "You are a restaurant business consultant starting a consultation on WhatsApp. "
            "Ask the question provided to you EXACTLY as written — do not rephrase or shorten it. "
            "Do not add extra questions or commentary. "
            f"{UNIVERSAL_RULES}"
        )

    # ---------------------------------------------------------------------------
    # PROBLEM DETECTION
    # ---------------------------------------------------------------------------
    @staticmethod
    def problem_detection_system_prompt(session: UserSession) -> str:
        restaurant_name = session.profile.get("restaurant_name", "the restaurant")
        return (
            f"You are a restaurant business consultant helping {restaurant_name}. "
            "Your job is to understand what business problem they are facing. "
            "Listen carefully and ask clarifying questions if needed. "
            f"{UNIVERSAL_RULES}"
        )

    # ---------------------------------------------------------------------------
    # CATEGORY CONFIRMATION
    # ---------------------------------------------------------------------------
    @staticmethod
    def category_confirmation_prompt(session: UserSession, detected_label: str) -> str:
        return (
            f"You are confirming the user's main problem with them. "
            f"You detected their issue as: '{detected_label}'. "
            "Rephrase this back to them in one empathetic sentence and ask if that is correct. "
            f"{UNIVERSAL_RULES}"
        )

    # ---------------------------------------------------------------------------
    # PIVOT QUESTION (Axis selection for TYPE_1 and TYPE_3)
    # ---------------------------------------------------------------------------
    @staticmethod
    def pivot_system_prompt(session: UserSession) -> str:
        restaurant_name = session.profile.get("restaurant_name", "the restaurant")
        return (
            f"You are a restaurant business consultant running a diagnosis for {restaurant_name}. "
            "Ask the pivot question naturally to understand which direction to focus on. "
            f"{UNIVERSAL_RULES}"
        )

    # ---------------------------------------------------------------------------
    # DIAGNOSTIC QUESTIONS
    # ---------------------------------------------------------------------------
    @staticmethod
    def diagnostic_system_prompt(session: UserSession) -> str:
        category = session.category or "general"
        axis_info = f" (axis: {session.axis})" if session.axis else ""
        answered = len(session.answers)
        return (
            f"You are a restaurant consultant running a structured diagnostic on '{category}'{axis_info}. "
            f"You have collected {answered} answers so far. "
            "Rephrase the next question naturally. Acknowledge the previous answer briefly if relevant. "
            "One question only per message. "
            f"{UNIVERSAL_RULES}"
        )

    # ---------------------------------------------------------------------------
    # RECOMMENDATIONS
    # ---------------------------------------------------------------------------
    @staticmethod
    def recommendations_system_prompt(session: UserSession) -> str:
        restaurant_name = session.profile.get("restaurant_name", "the restaurant")
        return (
            f"You are delivering final recommendations to {restaurant_name}. "
            "Present findings clearly, be specific and actionable. "
            "End by offering to go deeper on any recommendation. "
            f"{UNIVERSAL_RULES}"
        )

    # ---------------------------------------------------------------------------
    # FOLLOWUP
    # ---------------------------------------------------------------------------
    @staticmethod
    def followup_system_prompt(session: UserSession) -> str:
        restaurant_name = session.profile.get("restaurant_name", "the restaurant")
        category = session.category or "general"
        
        recs_text = "\n".join(f"- {r}" for r in session.last_recommendations) if session.last_recommendations else "No recommendations recorded."
        
        return (
            f"You are a restaurant business consultant continuing a conversation with {restaurant_name}. "
            f"The main problem area was: {category}. "
            f"You ALREADY gave these specific recommendations:\n{recs_text}\n\n"
            "If the user asks what you recommend, what to do, or for clarification, "
            "refer back to THESE SPECIFIC recommendations — do not invent new generic advice. "
            "You may elaborate on any of these, but do not contradict or replace them. "
            f"{UNIVERSAL_RULES}"
        )

    # ---------------------------------------------------------------------------
    # SHARED: build full messages array for OpenAI
    # ---------------------------------------------------------------------------
    @staticmethod
    def build_messages(
        system_prompt: str,
        history: list[dict],
        user_input: str,
        history_limit: int = 20,
    ) -> list[dict]:
        """
        Assembles the final messages list sent to OpenAI.
        [system] + [last N history] + [new user message]
        Trimming history keeps token cost predictable on long conversations.
        """
        trimmed = history[-history_limit:] if len(history) > history_limit else history
        return [
            {"role": "system", "content": system_prompt},
            *trimmed,
            {"role": "user", "content": user_input},
        ]