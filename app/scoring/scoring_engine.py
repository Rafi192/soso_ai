# scoring/scoring_engine.py
# Pure backend logic — no AI involved.
# Calculates severity score from signal tables defined in the MUFU Brain doc.
# Also calculates confidence score (0.0-1.0) for the orchestrator stop condition.

import logging
# from signal import signal
from app.schemas.session_schema import UserSession

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# SIGNAL TABLES — one dict per TYPE (base category, not axis-suffixed)
# The scoring engine resolves the correct question list using the axis,
# but signal point values are shared across A and B for the same TYPE.
# ---------------------------------------------------------------------------
SIGNAL_SCORES = {

    "TYPE_1_PLATFORM_DEPENDENCY": {
        "platform_revenue_gt_60":           3,
        "no_direct_channel":                3,
        "does_not_know_commissions":        2,
        "does_not_collect_customer_data":   2,
        "platform_listing_not_optimized":   1,
        "never_tried_direct_channel":       2,
        # Axis B signals
        "not_on_thefork":                   2,
        "no_off_peak_promos":               2,
        "no_offpeak_menu":                  1,
    },

    "TYPE_2_LOCAL_VISIBILITY": {
        "google_listing_incomplete":            3,
        "fewer_than_50_reviews_or_low_rating":  2,
        "not_active_on_social_media":           2,
        "doesnt_know_customer_sources":         2,
        "no_marketing_budget":                  1,
        "no_marketing_efforts":                 2,
        "handling_comms_alone":                 1,
        "no_quality_content":                   2,
        "never_worked_with_influencers":        1,
    },

    "TYPE_3_LOW_MARGIN": {
        "food_cost_unknown_or_high":        3,
        "order_management_by_intuition":    2,
        "moderate_to_high_waste":           2,
        "no_technical_data_sheets":         2,
        "poorly_optimized_staff":           2,
        "no_sales_tracking_by_product":     2,
        "menu_too_extensive":               1,
        "does_not_know_commissions":        2,
        "spare_kitchen_capacity": 2,
        "open_to_virtual_brand":  2,
    },

    "TYPE_4_RETENTION": {
        "doesnt_know_return_rate":          2,
        "no_customer_database":             3,
        "not_active_on_social_media":       2,
        "no_checkout_capture":              2,
        "no_loyalty_program":               2,
        "does_not_respond_to_reviews":      1,
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
        "digital_presence_not_prepared":    3,
        "no_go_to_market_strategy":         2,
        "no_launch_budget":                 2,
        "no_quality_content":               2,
    },
}


# ---------------------------------------------------------------------------
# SIGNAL EVALUATORS
# Each function checks the raw answer text and returns True if signal fires.
# ---------------------------------------------------------------------------
def _eval_signal(signal: str, answer: str) -> bool:
    a = answer.lower().strip()
    import re

    # ── TYPE 1 Axis A signals ────────────────────────────────────────────────
    if signal == "platform_revenue_gt_60":
        nums = re.findall(r'\d+', a)
        return int(nums[0]) > 60 if nums else False

    if signal == "no_direct_channel":
        return any(w in a for w in ["no", "nope", "don't", "dont", "nothing", "none", "never"])

    if signal == "does_not_know_commissions":
        return any(w in a for w in ["no", "don't know", "dont know", "not sure", "no idea", "unclear"])

    if signal == "does_not_collect_customer_data":
        return any(w in a for w in ["no", "nope", "don't", "dont", "nothing", "never"])

    if signal == "platform_listing_not_optimized":
        return any(w in a for w in ["no", "not", "outdated", "old", "never", "don't", "dont"])

    if signal == "never_tried_direct_channel":
        return any(w in a for w in ["no", "never", "nope", "not yet", "haven't", "havent"])

    # ── TYPE 1 Axis B signals ────────────────────────────────────────────────
    if signal == "not_on_thefork":
        return any(w in a for w in ["no", "not", "never", "don't", "dont"])

    if signal == "no_off_peak_promos":
        return any(w in a for w in ["no", "never", "not", "haven't", "havent", "nothing"])

    if signal == "no_offpeak_menu":
        return any(w in a for w in ["no", "not", "never", "don't", "dont", "nothing"])

    # ── TYPE 2 signals ───────────────────────────────────────────────────────
    if signal == "google_listing_incomplete":
        return any(w in a for w in ["no", "not", "incomplete", "missing", "never", "don't", "dont"])

    if signal == "fewer_than_50_reviews_or_low_rating":
        nums = re.findall(r'\d+', a)
        if nums:
            for n in nums:
                val = float(n)
                if val < 50 or (val < 4 and "." in a):
                    return True
        return False

    if signal == "not_active_on_social_media":
        return any(w in a for w in ["no", "not", "never", "inactive", "don't", "dont", "nothing"])

    if signal == "doesnt_know_customer_sources":
        return any(w in a for w in ["no idea", "not sure", "don't know", "dont know", "unclear", "no"])

    if signal == "no_marketing_budget":
        return any(w in a for w in ["no", "none", "nothing", "zero", "0", "no budget"])

    if signal == "no_marketing_efforts":
        return any(w in a for w in ["no", "never", "nothing", "nope", "haven't", "havent"])

    if signal == "handling_comms_alone":
        return any(w in a for w in ["alone", "myself", "just me", "only me", "by myself", "on my own"])

    if signal == "no_quality_content":
        return any(w in a for w in ["no", "not", "never", "don't", "dont", "nothing"])

    if signal == "never_worked_with_influencers":
        return any(w in a for w in ["no", "never", "not", "haven't", "havent"])

    # ── TYPE 3 signals ───────────────────────────────────────────────────────
    if signal == "food_cost_unknown_or_high":
        no_words = ["no", "don't know", "dont know", "not sure", "unclear", "no idea"]
        if any(w in a for w in no_words):
            return True
        nums = re.findall(r'\d+', a)
        return bool(nums and int(nums[0]) > 40)

    if signal == "order_management_by_intuition":
        return any(w in a for w in ["gut", "feeling", "intuition", "experience", "eye", "guess", "roughly"])

    if signal == "moderate_to_high_waste":
        return any(w in a for w in ["yes", "a lot", "moderate", "high", "quite", "often", "frequently"])
    
    if signal == "spare_kitchen_capacity":
        return any(w in a for w in ["yes", "yeah", "yep", "sure", "of course"])

    if signal == "open_to_virtual_brand":
        return any(w in a for w in ["yes", "yeah", "yep", "i'm in", "sure", "okay"])

    if signal == "no_technical_data_sheets":
        return any(w in a for w in ["no", "not", "never", "don't", "dont", "differently", "varies"])

    if signal == "poorly_optimized_staff":
        return any(w in a for w in ["yes", "sometimes", "often", "paying", "idle", "slow", "overstaffed"])

    if signal == "no_sales_tracking_by_product":
        return any(w in a for w in ["no", "not", "never", "don't", "dont", "no idea", "nothing"])

    if signal == "menu_too_extensive":
        return any(w in a for w in ["extensive", "large", "big", "long", "many", "lots", "too much"])

    # ── TYPE 4 signals ───────────────────────────────────────────────────────
    if signal == "doesnt_know_return_rate":
        return any(w in a for w in ["no idea", "not sure", "don't know", "dont know", "no", "unclear"])

    if signal == "no_customer_database":
        return any(w in a for w in ["no", "not", "never", "don't", "dont", "nothing", "none"])

    if signal == "no_loyalty_program":
        return any(w in a for w in ["no", "not", "never", "don't", "dont", "nothing", "none"])

    if signal == "no_checkout_capture":
        return any(w in a for w in ["no", "not", "never", "don't", "dont", "nothing"])

    if signal == "does_not_respond_to_reviews":
        return any(w in a for w in ["no", "not", "never", "rarely", "sometimes", "don't", "dont"])

    # ── TYPE 5 signals ───────────────────────────────────────────────────────
    if signal == "more_than_4_unconnected_tools":
        items = re.split(r'[,;]', a)
        return len(items) >= 4

    if signal == "frequent_reentry":
        return any(w in a for w in ["yes", "always", "every time", "constantly", "manually", "all the time"])

    if signal == "tool_related_errors":
        return any(w in a for w in ["yes", "often", "always", "frequently", "happened", "problem", "issue"])

    if signal == "unknown_tech_budget":
        return any(w in a for w in ["no", "not sure", "don't know", "dont know", "no idea", "unclear"])

    if signal == "unused_paid_tools":
        return any(w in a for w in ["yes", "some", "a few", "paying for", "not using", "barely"])

    if signal == "pos_without_analytics":
        return any(w in a for w in ["no", "not", "never", "don't", "dont", "basic", "old", "nothing"])

    if signal == "alone_in_managing_tech":
        return any(w in a for w in ["alone", "myself", "just me", "only me", "by myself", "on my own"])

    if signal == "afraid_to_switch_tools":
        return any(w in a for w in ["afraid", "scared", "worried", "fear", "migration", "complicated", "difficult"])

    # ── TYPE 6 signals ───────────────────────────────────────────────────────
    if signal == "opening_soon_without_digital_prep":
        return any(w in a for w in ["week", "days", "soon", "month", "next month", "shortly"])

    if signal == "digital_presence_not_prepared":
        return any(w in a for w in ["no", "not yet", "not", "never", "don't", "dont", "nothing"])

    if signal == "no_go_to_market_strategy":
        return any(w in a for w in ["no", "not", "nothing", "never", "don't", "dont", "no plan"])

    if signal == "no_launch_budget":
        return any(w in a for w in ["no", "none", "nothing", "zero", "0", "no budget", "very little"])

    return False


class ScoringEngine:

    MIN_ANSWERS_FOR_CONFIDENCE = 3

    def _resolve_question_key(self, session: UserSession) -> str:
        """
        Returns the correct DIAGNOSTIC_QUESTIONS key for this session.
        For TYPE_1 and TYPE_3, appends axis suffix if set.
        This mirrors the same logic in DiagnosticWorkflow.
        """
        category = session.category or "OTHER"
        if session.axis and category in ["TYPE_1_PLATFORM_DEPENDENCY", "TYPE_3_LOW_MARGIN"]:
            keyed = f"{category}_{session.axis}"
            return keyed
        return category

    def calculate_severity_score(self, session: UserSession) -> float:
        """
        Loops through answered questions, checks their signal,
        accumulates points from the signal table.
        Uses base category for signal table lookup (shared across A/B),
        but axis-resolved key for question list lookup.
        """
        category = session.category or "OTHER"

        # Signal points always looked up by base category
        signal_table = SIGNAL_SCORES.get(category, {})
        if not signal_table:
            return 0.0

        # Questions looked up by axis-resolved key
        question_key = self._resolve_question_key(session)

        from app.workflows.diagnostic_workflow import DIAGNOSTIC_QUESTIONS
        questions = DIAGNOSTIC_QUESTIONS.get(question_key, [])

        total_score = 0.0
        for q in questions:
            signal = q.get("signal")
            key = q.get("key")

            if not signal or key not in session.answers:
                continue

            answer = session.answers[key]
            points = signal_table.get(signal, 0)

            if _eval_signal(signal, answer):
                total_score += points
                logger.info(f"[{session.user_id}] Signal fired: {signal} (+{points})")

        logger.info(f"[{session.user_id}] Total severity score: {total_score}")
        return round(total_score, 2)

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