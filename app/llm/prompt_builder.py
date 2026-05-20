# llm/prompt_builder.py
# Builds the messages array sent to OpenAI for each turn.

from app.schemas.session_schema import UserSession


class PromptBuilder:

    # ---------------------------------------------------------------------------
    # PROFILE COLLECTION
    # ---------------------------------------------------------------------------
    @staticmethod
    def profile_system_prompt() -> str:
        return (
            "You are a friendly restaurant business consultant starting a new consultation "
            "on WhatsApp. Your job right now is to warmly greet the user and collect basic "
            "information about their restaurant: name, city, type of cuisine, and how long "
            "they've been operating. Ask one question at a time. Be conversational and brief."
        )

    # ---------------------------------------------------------------------------
    # PROBLEM DETECTION
    # ---------------------------------------------------------------------------
    @staticmethod
    def problem_detection_system_prompt(session: UserSession) -> str:
        restaurant_name = session.profile.get("restaurant_name", "their restaurant")
        return (
            f"You are a restaurant business consultant helping {restaurant_name}. "
            "Your job is to understand what business problem they're facing. "
            "Listen carefully to their response. Be empathetic and ask clarifying questions "
            "to understand their main pain point. Keep messages short (2-3 sentences max)."
        )

    # ---------------------------------------------------------------------------
    # CATEGORY CONFIRMATION
    # ---------------------------------------------------------------------------
    @staticmethod
    def category_confirmation_prompt(session: UserSession, detected_category: str) -> str:
        return (
            f"You are confirming the user's main problem category with them. "
            f"You've detected their issue is: '{detected_category}'. "
            "Explain this back to them in simple, empathetic terms and ask them to confirm "
            "if this sounds right. If they say no, ask them to describe their problem differently."
        )

    # ---------------------------------------------------------------------------
    # DIAGNOSTIC QUESTIONS
    # ---------------------------------------------------------------------------
    @staticmethod
    def diagnostic_system_prompt(session: UserSession) -> str:
        category = session.category or "general"
        answered = len(session.answers)
        return (
            f"You are a restaurant consultant running a structured diagnostic on "
            f"the topic: '{category}'. "
            f"You have collected {answered} answers so far. "
            "Ask the next question naturally. One question only. "
            "Acknowledge their previous answer briefly before asking. "
            "Keep each message under 3 sentences."
        )

    # ---------------------------------------------------------------------------
    # RECOMMENDATIONS
    # ---------------------------------------------------------------------------
    @staticmethod
    def recommendations_system_prompt(session: UserSession) -> str:
        restaurant_name = session.profile.get("restaurant_name", "your restaurant")
        return (
            f"You are delivering final recommendations to {restaurant_name}. "
            "Be warm, specific, and actionable. Present findings clearly. "
            "End by offering to go deeper on any recommendation."
        )

    # ---------------------------------------------------------------------------
    # SHARED: build full messages array for OpenAI
    # system prompt + trimmed history + new user message
    # ---------------------------------------------------------------------------
    @staticmethod
    def build_messages(
        system_prompt: str,
        history: list[dict],
        user_input: str,
        history_limit: int = 10,    # last 5 turns (10 messages) — keeps token cost low
    ) -> list[dict]:
        """
        Assembles the final messages list sent to OpenAI.
        Always: [system] + [last N history messages] + [new user message]
        Trimming history prevents runaway token costs on long conversations.
        """
        trimmed_history = history[-history_limit:] if len(history) > history_limit else history
        return [
            {"role": "system", "content": system_prompt},
            *trimmed_history,
            {"role": "user", "content": user_input},
        ]