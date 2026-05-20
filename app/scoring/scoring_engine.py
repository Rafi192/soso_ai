# scoring/scoring_engine.py
# Pure backend logic — no AI involved.
# Calculates severity score (0-13 range, not capped at 10) from the exact
# signal tables defined in the MUFU Brain document.
# Also calculates confidence score (0.0-1.0) for the orchestrator stop condition.

import logging
from app.schemas.session_schema import UserSession

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# SIGNAL TABLES — taken directly from MUFU Brain doc, one dict per TYPE.
# Key   = signal name (matches question's "signal" field in diagnostic_workflow)
# Value = points added to severity score when that signal is triggered
# ---------------------------------------------------------------------------

SIGNAL_SCORES = {

    "TYPE_1_PLATFORM_DEPENDENCY": {
        "platform_revenue_gt_60":           3,
        "no_direct_channel":                3,
        "does_not_know_commissions":        2,
        "does_not_collect_customer_data":   2,
        "platform_listing_not_optimized":   1,
        "never_tried_direct_channel":       2,
    },

    "TYPE_2_LOCAL_VISIBILITY": {
        "google_listing_incomplete":            3,
        "fewer_than_50_reviews_or_low_rating":  2,
        "not_active_on_social_media":           2,
        "doesnt_know_customer_sources":         2,
        "no_marketing_budget":                  1,
        "no_marketing_efforts":                 2,
        "handling_comms_alone":                 1,
    },

    "TYPE_3_LOW_MARGIN": {
        "food_cost_unknown_or_high":        3,
        "order_management_by_intuition":    2,
        "moderate_to_high_waste":           2,
        "no_technical_data_sheets":         2,
        "poorly_optimized_staff":           2,
        "no_sales_tracking_by_product":     2,
        "menu_too_extensive":               1,
        "no_management_tools":              3,
    },

    "TYPE_4_RETENTION": {
        "doesnt_know_return_rate":          2,
        "no_identification_of_regulars":    2,
        "no_customer_database":             3,
        "no_loyalty_program":               2,
        "never_communicates_with_customers":3,
        "no_checkout_capture":              2,
        "does_not_respond_to_reviews":      1,
        "no_offers_for_loyal_customers":    1,
    },

    "TYPE_5_DIGITAL_CHAOS": {
        "more_than_4_unconnected_tools":    3,
        "frequent_reentry":                 2,
        "tool_related_errors":              2,
        "unknown_tech_budget":              2,
        "unused_paid_tools":                3,
        "pos_without_analytics":            2,
        "alone_in_managing_tech":           1,
        "afraid_to_switch_tools":           1,
    },

    "TYPE_6_LAUNCH": {
        "opening_soon_without_digital_prep":3,
        "no_site_survey":                   2,
        "digital_presence_not_prepared":    3,
        "too_many_channels_from_start":     2,
        "no_launch_budget":                 2,
        "no_go_to_market_strategy":         2,
        "no_day1_customer_acquisition":     2,
    },
}

# ---------------------------------------------------------------------------
# SIGNAL EVALUATORS
# These functions look at the raw answer text and decide if a signal fires.
# The orchestrator calls calculate_severity_score() which runs these.
# Add more sophisticated NLP here later if needed — for now simple keywords.
# ---------------------------------------------------------------------------

def _eval_signal(signal: str, answer: str) -> bool:
    """
    Returns True if the signal is triggered based on the raw answer string.
    answer is always lowercased before comparison.
    """
    a = answer.lower().strip()

    # ── TYPE 1 signals ──────────────────────────────────────────────────────
    if signal == "platform_revenue_gt_60":
        # Extract any number from the answer and check if > 60
        import re
        nums = re.findall(r'\d+', a)
        if nums:
            return int(nums[0]) > 60
        return False

    if signal == "no_direct_channel":
        no_words = ["no", "nope", "don't", "dont", "nothing", "none", "never"]
        return any(w in a for w in no_words)

    if signal == "does_not_know_commissions":
        no_words = ["no", "don't know", "dont know", "not sure", "no idea", "unclear"]
        return any(w in a for w in no_words)

    if signal == "does_not_collect_customer_data":
        no_words = ["no", "nope", "don't", "dont", "nothing", "never"]
        return any(w in a for w in no_words)

    if signal == "platform_listing_not_optimized":
        no_words = ["no", "not", "outdated", "old", "never", "don't", "dont"]
        return any(w in a for w in no_words)

    if signal == "never_tried_direct_channel":
        no_words = ["no", "never", "nope", "not yet", "haven't", "havent"]
        return any(w in a for w in no_words)

    # ── TYPE 2 signals ──────────────────────────────────────────────────────
    if signal == "google_listing_incomplete":
        no_words = ["no", "not", "incomplete", "missing", "never", "don't", "dont"]
        return any(w in a for w in no_words)

    if signal == "fewer_than_50_reviews_or_low_rating":
        import re
        nums = re.findall(r'\d+', a)
        if nums:
            # If they mention a review count under 50 OR rating under 4.0
            for n in nums:
                val = float(n)
                if val < 50 or (val < 4 and "." in a):
                    return True
        return False

    if signal == "not_active_on_social_media":
        no_words = ["no", "not", "never", "inactive", "don't", "dont", "nothing"]
        return any(w in a for w in no_words)

    if signal == "doesnt_know_customer_sources":
        no_words = ["no idea", "not sure", "don't know", "dont know", "unclear", "no"]
        return any(w in a for w in no_words)

    if signal == "no_marketing_budget":
        no_words = ["no", "none", "nothing", "zero", "0", "no budget"]
        return any(w in a for w in no_words)

    if signal == "no_marketing_efforts":
        no_words = ["no", "never", "nothing", "nope", "haven't", "havent"]
        return any(w in a for w in no_words)

    if signal == "handling_comms_alone":
        yes_words = ["alone", "myself", "just me", "only me", "by myself", "on my own"]
        return any(w in a for w in yes_words)

    # ── TYPE 3 signals ──────────────────────────────────────────────────────
    if signal == "food_cost_unknown_or_high":
        import re
        no_words = ["no", "don't know", "dont know", "not sure", "unclear", "no idea"]
        if any(w in a for w in no_words):
            return True
        nums = re.findall(r'\d+', a)
        if nums and int(nums[0]) > 40:
            return True
        return False

    if signal == "order_management_by_intuition":
        gut_words = ["gut", "feeling", "intuition", "experience", "eye", "guess", "roughly"]
        return any(w in a for w in gut_words)

    if signal == "moderate_to_high_waste":
        waste_words = ["yes", "a lot", "moderate", "high", "quite", "often", "frequently"]
        return any(w in a for w in waste_words)

    if signal == "no_technical_data_sheets":
        no_words = ["no", "not", "never", "don't", "dont", "differently", "varies"]
        return any(w in a for w in no_words)

    if signal == "poorly_optimized_staff":
        yes_words = ["yes", "sometimes", "often", "paying", "idle", "slow", "overstaffed"]
        return any(w in a for w in yes_words)

    if signal == "no_sales_tracking_by_product":
        no_words = ["no", "not", "never", "don't", "dont", "no idea", "nothing"]
        return any(w in a for w in no_words)

    if signal == "menu_too_extensive":
        yes_words = ["extensive", "large", "big", "long", "many", "lots", "too much"]
        return any(w in a for w in yes_words)

    if signal == "no_management_tools":
        no_words = ["no", "nothing", "none", "excel", "paper", "manual", "nothing at all"]
        return any(w in a for w in no_words)

    # ── TYPE 4 signals ──────────────────────────────────────────────────────
    if signal == "doesnt_know_return_rate":
        no_words = ["no idea", "not sure", "don't know", "dont know", "no", "unclear"]
        return any(w in a for w in no_words)

    if signal == "no_identification_of_regulars":
        no_words = ["no", "not", "never", "don't", "dont", "nothing"]
        return any(w in a for w in no_words)

    if signal == "no_customer_database":
        no_words = ["no", "not", "never", "don't", "dont", "nothing", "none"]
        return any(w in a for w in no_words)

    if signal == "no_loyalty_program":
        no_words = ["no", "not", "never", "don't", "dont", "nothing", "none"]
        return any(w in a for w in no_words)

    if signal == "never_communicates_with_customers":
        no_words = ["no", "never", "not", "don't", "dont", "nothing", "rarely"]
        return any(w in a for w in no_words)

    if signal == "no_checkout_capture":
        no_words = ["no", "not", "never", "don't", "dont", "nothing"]
        return any(w in a for w in no_words)

    if signal == "does_not_respond_to_reviews":
        no_words = ["no", "not", "never", "rarely", "sometimes", "don't", "dont"]
        return any(w in a for w in no_words)

    if signal == "no_offers_for_loyal_customers":
        no_words = ["no", "not", "never", "don't", "dont", "nothing"]
        return any(w in a for w in no_words)

    # ── TYPE 5 signals ──────────────────────────────────────────────────────
    if signal == "more_than_4_unconnected_tools":
        # Count comma-separated items or just check for many tool mentions
        import re
        items = re.split(r'[,;]', a)
        return len(items) >= 4

    if signal == "frequent_reentry":
        yes_words = ["yes", "always", "every time", "constantly", "manually", "all the time"]
        return any(w in a for w in yes_words)

    if signal == "tool_related_errors":
        yes_words = ["yes", "often", "always", "frequently", "happened", "problem", "issue"]
        return any(w in a for w in yes_words)

    if signal == "unknown_tech_budget":
        no_words = ["no", "not sure", "don't know", "dont know", "no idea", "unclear"]
        return any(w in a for w in no_words)

    if signal == "unused_paid_tools":
        yes_words = ["yes", "some", "a few", "paying for", "not using", "barely"]
        return any(w in a for w in yes_words)

    if signal == "pos_without_analytics":
        no_words = ["no", "not", "never", "don't", "dont", "basic", "old", "nothing"]
        return any(w in a for w in no_words)

    if signal == "alone_in_managing_tech":
        yes_words = ["alone", "myself", "just me", "only me", "by myself", "on my own"]
        return any(w in a for w in yes_words)

    if signal == "afraid_to_switch_tools":
        yes_words = ["afraid", "scared", "worried", "fear", "migration", "complicated", "difficult"]
        return any(w in a for w in yes_words)

    # ── TYPE 6 signals ──────────────────────────────────────────────────────
    if signal == "opening_soon_without_digital_prep":
        soon_words = ["week", "days", "soon", "month", "next month", "shortly"]
        return any(w in a for w in soon_words)

    if signal == "no_site_survey":
        no_words = ["no", "not", "never", "don't", "dont", "nothing"]
        return any(w in a for w in no_words)

    if signal == "digital_presence_not_prepared":
        no_words = ["no", "not yet", "not", "never", "don't", "dont", "nothing"]
        return any(w in a for w in no_words)

    if signal == "too_many_channels_from_start":
        many_words = ["all", "everything", "all three", "multiple", "dine-in and delivery", "all channels"]
        return any(w in a for w in many_words)

    if signal == "no_launch_budget":
        no_words = ["no", "none", "nothing", "zero", "0", "no budget", "very little"]
        return any(w in a for w in no_words)

    if signal == "no_go_to_market_strategy":
        no_words = ["no", "not", "nothing", "never", "don't", "dont", "no plan"]
        return any(w in a for w in no_words)

    if signal == "no_day1_customer_acquisition":
        no_words = ["no", "not", "nothing", "never", "don't", "dont", "no plan"]
        return any(w in a for w in no_words)

    # Unknown signal — don't score it
    return False


class ScoringEngine:

    MIN_ANSWERS_FOR_CONFIDENCE = 3

    # ---------------------------------------------------------------------------
    # SEVERITY SCORE
    # Loops through all answered questions, checks their signal against
    # the answer text, accumulates points from the signal table.
    # ---------------------------------------------------------------------------
    def calculate_severity_score(self, session: UserSession) -> float:
        category = session.category or "OTHER"
        signal_table = SIGNAL_SCORES.get(category, {})

        if not signal_table:
            return 0.0

        # Import here to avoid circular imports
        from app.workflows.diagnostic_workflow import DIAGNOSTIC_QUESTIONS, Category
        questions = DIAGNOSTIC_QUESTIONS.get(category, [])

        total_score = 0.0

        for q in questions:
            signal = q.get("signal")
            key = q.get("key")

            # Skip if no signal defined or question not answered yet
            if not signal or key not in session.answers:
                continue

            answer = session.answers[key]
            points = signal_table.get(signal, 0)

            if _eval_signal(signal, answer):
                total_score += points
                logger.info(f"[{session.user_id}] Signal fired: {signal} (+{points})")

        logger.info(f"[{session.user_id}] Total severity score: {total_score}")
        return round(total_score, 2)

    # ---------------------------------------------------------------------------
    # CONFIDENCE SCORE — how much do we know? (0.0 → 1.0)
    # Simple ratio: answered / total available questions.
    # ---------------------------------------------------------------------------
    def calculate_confidence(self, session: UserSession, total_questions: int) -> float:
        answered = len(session.answers)

        if answered < self.MIN_ANSWERS_FOR_CONFIDENCE:
            return 0.0

        if total_questions == 0:
            return 1.0

        confidence = answered / total_questions
        logger.info(
            f"[{session.user_id}] Confidence: {confidence:.2f} "
            f"({answered}/{total_questions} answered)"
        )
        return round(min(confidence, 1.0), 2)
