# recommendations/recommendation_engine.py
# Deterministic recommendation selection — no AI.
# Priority matrix sourced directly from updated MUFU Brain doc:
#
# TYPE 1 Delivery → GFV/MrBeast Burger (primary), TheFork (secondary)
# TYPE 1 On-site  → TheFork (primary), WhatsApp list (secondary)
# TYPE 2          → Hemblem (primary), TheFork (secondary)
# TYPE 3 Costs    → Calculate food cost, simplify menu, recipe sheets
# TYPE 3 Revenue  → GFV/MrBeast Burger (primary), Hemblem (secondary)
# TYPE 4          → Hemblem (primary), TheFork (secondary)
# TYPE 5          → Zelty/Innovorder/Tiller (primary)
# TYPE 6          → Hemblem (primary), TheFork (secondary)

import logging
from app.schemas.session_schema import UserSession

logger = logging.getLogger(__name__)


RECOMMENDATIONS: dict[str, list[dict]] = {

    # ── TYPE 1 Axis A — Delivery ─────────────────────────────────────────────
    "TYPE_1_PLATFORM_DEPENDENCY_A": [
        {
            "id": "T1A_001",
            "text": (
                "We have an exclusive partnership with Global Food Ventures, which operates the MrBeast Burger license. "
                "You cook MrBeast Burger from your existing kitchen, without investment, without changing your concept. "
                "You sell on Uber Eats and Deliveroo under their brand and earn a commission on each sale. "
                "Restaurants that already have it see a significant increase in delivery orders from the first month. "
                "It is free, no risk, and directly increases your delivery revenue. Would you like me to connect you with their team?"
            ),
            # "min_score": 3.0,
            # "signals": ["platform_revenue_gt_60", "no_direct_channel"],
            "min_score": 0.0,
            "signals": [],
        },
        {
            "id": "T1A_002",
            "text": (
                "Put a click-and-collect QR code in each delivery bag to capture customers' phone numbers "
                "by offering them a 10-20% discount or a free dessert/drink on their next direct order."
            ),
            "min_score": 2.0,
            "signals": ["no_direct_channel", "does_not_collect_customer_data"],
        },
        {
            "id": "T1A_003",
            "text": (
                "Launch a WhatsApp list campaign — collect customer phone numbers and send one promotion per week "
                "to your direct customers to reduce platform dependency progressively."
            ),
            "min_score": 2.0,
            "signals": ["does_not_collect_customer_data"],
        },
        {
            "id": "T1A_004",
            "text": (
                "Consider a direct ordering system such as Zelty, Innovorder, Sunday, or Tiller — "
                "these charge only 0-2% commission compared to the 25-35% you currently pay on platforms."
            ),
            "min_score": 4.0,
            "signals": ["platform_revenue_gt_60", "no_direct_channel"],
        },
    ],

    # ── TYPE 1 Axis B — On-site ──────────────────────────────────────────────
    "TYPE_1_PLATFORM_DEPENDENCY_B": [
        {
            "id": "T1B_001",
            "text": (
                "Activate TheFork with targeted promotions on your off-peak time slots. "
                "TheFork lets you offer 20% to 50% discounts on specific time slots you choose. "
                "TheFork users actively look for good deals, so you attract the right people at the right time."
            ),
            "min_score": 1.0,
            "signals": ["not_on_thefork", "no_off_peak_promos"],
        },
        {
            "id": "T1B_002",
            "text": (
                "Create one simple flagship offer only for your slow time slots: "
                "a fixed-price daily menu, a happy hour with a free drink, or a fast lunch formula for local workers. "
                "Push this offer on social media and on your Google Business Profile."
            ),
            "min_score": 1.0,
            "signals": ["no_offpeak_menu"],
        },
        {
            "id": "T1B_003",
            "text": (
                "Put a QR code on every table so on-site customers join your WhatsApp list. "
                "Build your customer base and bring them back during future off-peak slots with a direct offer."
            ),
            "min_score": 1.0,
            "signals": [],
        },
    ],

    # ── TYPE 2 — Local Visibility ────────────────────────────────────────────
    "TYPE_2_LOCAL_VISIBILITY": [
        {
            "id": "T2_001",
            "text": (
                "We have an exclusive partnership with Hemblem — the platform that connects restaurants "
                "with influencers and food content creators. You sign up, receive up to 10 requests per week "
                "from influencers who want to come eat at your place, they post on their social media, "
                "and their followers discover your restaurant — all without ad budget. "
                "Through our partnership you get privileged access and an exclusive rate. "
                "Would you like me to connect you directly with their team?"
            ),
            "min_score": 1.0,
            "signals": ["not_active_on_social_media", "never_worked_with_influencers"],
        },
        {
            "id": "T2_002",
            "text": (
                "TheFork lets you offer 20% to 50% discounts on specific time slots you choose. "
                "TheFork users actively look for good deals and help fill the hours when your restaurant is empty."
            ),
            "min_score": 1.0,
            "signals": [],
        },
        {
            "id": "T2_003",
            "text": (
                "Complete your Google Business profile immediately — add recent photos, accurate hours, "
                "and start responding to every review. This is the highest-impact zero-cost action for local visibility."
            ),
            "min_score": 1.0,
            "signals": ["google_listing_incomplete", "fewer_than_50_reviews_or_low_rating"],
        },
    ],

    # ── TYPE 3 Axis A — Reduce costs ─────────────────────────────────────────
    "TYPE_3_LOW_MARGIN_A": [
        {
            "id": "T3A_001",
            "text": (
                "Calculate your real food cost over the last 30 days: "
                "total ingredient purchases divided by revenue multiplied by 100. "
                "This is your baseline — you cannot improve what you do not measure."
            ),
            "min_score": 0.0,
            "signals": [],
        },
        {
            "id": "T3A_002",
            "text": (
                "Identify your 3 least-sold products and remove them from the menu. "
                "Fewer items means less waste, simpler production, and better quality on what remains."
            ),
            "min_score": 0.0,
            # "signals": ["menu_too_extensive", "moderate_to_high_waste"],
            "signals": [],
        },
        {
            "id": "T3A_003",
            "text": (
                "Create simple recipe sheets for your 5 best-selling products with precise quantities. "
                "This standardizes production, reduces cost variance between cooks, and cuts waste."
            ),
            "min_score": 0.0,
            # "signals": ["no_technical_data_sheets"],
            "signals": [],
        },
        {
            "id": "T3A_004",
            "text": (
                "Adjust staff schedules based on actual sales data — payroll should stay below 35% of revenue. "
                "Cross-reference your schedule with revenue history by time slot to identify overstaffed periods."
            ),
            "min_score": 0.0,
            # "signals": ["poorly_optimized_staff"],
            "signals": [],
        },
    ],

    # ── TYPE 3 Axis B — Increase revenue ─────────────────────────────────────
    "TYPE_3_LOW_MARGIN_B": [
        {
            "id": "T3B_001",
            "text": (
                "We have an exclusive partnership with Global Food Ventures (MrBeast Burger). "
                "Add a delivery-only concept from your existing kitchen during off-peak hours "
                "to generate additional revenue with low incremental cost — no investment, no risk. "
                "Would you like me to connect you with their team?"
            ),
            "min_score": 0.0,
            # "signals": ["spare_kitchen_capacity", "open_to_virtual_brand"],
            "signals": [],

        },
        {
            "id": "T3B_002",
            "text": (
                "We also have a partnership with Hemblem to help drive more customers to your restaurant. "
                "More covers directly increases your revenue without touching your cost structure."
            ),
            "min_score": 0.0,
            "signals": [],
        },
    ],

    # ── TYPE 4 — Retention ───────────────────────────────────────────────────
    "TYPE_4_RETENTION": [
        {
            "id": "T4_001",
            "text": (
                "We have an exclusive partnership with Hemblem — they connect your restaurant with local influencers "
                "and food content creators who post about you in exchange for a meal. "
                "A stronger social media presence keeps your restaurant top of mind between visits "
                "and supports customer return. Would you like me to connect you with their team?"
            ),
            "min_score": 1.0,
            "signals": ["not_active_on_social_media", "no_customer_database"],
        },
        {
            "id": "T4_002",
            "text": (
                "TheFork can bring former customers back during targeted off-peak time slots with special offers. "
                "Use it to reactivate your existing customer base at times when your restaurant is quiet."
            ),
            "min_score": 1.0,
            "signals": [],
        },
        {
            "id": "T4_003",
            "text": (
                "Create a WhatsApp Business list — offer every customer at the register the chance to sign up "
                "for your weekly offers. Target: 50 numbers in 30 days. "
                "Send one promotion per week to bring them back."
            ),
            "min_score": 2.0,
            "signals": ["no_customer_database", "no_loyalty_program"],
        },
    ],

    # ── TYPE 5 — Digital Chaos ───────────────────────────────────────────────
    "TYPE_5_DIGITAL_CHAOS": [
        {
            "id": "T5_001",
            "text": (
                "List all your subscriptions and their exact monthly cost. "
                "Immediately identify unused tools and cancel them — this creates instant savings."
            ),
            "min_score": 1.0,
            "signals": ["unused_paid_tools", "unknown_tech_budget"],
        },
        {
            "id": "T5_002",
            "text": (
                "Choose one central tool that handles point-of-sale, orders, and analytics. "
                "One good tool mastered beats five tools used poorly. "
                "Zelty, Innovorder, and Tiller are the best options for independent restaurants — "
                "I can help you negotiate a partnership with them."
            ),
            "min_score": 3.0,
            "signals": ["more_than_4_unconnected_tools", "frequent_reentry"],
        },
    ],

    # ── TYPE 6 — Launch ──────────────────────────────────────────────────────
    "TYPE_6_LAUNCH": [
        {
            "id": "T6_001",
            "text": (
                "Hemblem can help create organic buzz before opening by connecting your restaurant "
                "with local food influencers. Open your Instagram and TikTok accounts now — "
                "document the preparation, the team, the menu. Customers who follow the journey "
                "are far more loyal than those who discover you by chance. "
                "Would you like me to connect you with the Hemblem team?"
            ),
            "min_score": 1.0,
            "signals": ["digital_presence_not_prepared", "no_go_to_market_strategy"],
        },
        {
            "id": "T6_002",
            "text": (
                "TheFork can help fill the room in the first weeks with targeted launch offers "
                "on chosen time slots — giving you a strong start with real customers from day one."
            ),
            "min_score": 1.0,
            "signals": [],
        },
        {
            "id": "T6_003",
            "text": (
                "Organize a private soft opening with family, friends, neighbors, and local partners "
                "3-5 days before the official opening to test your processes and generate word of mouth."
            ),
            "min_score": 2.0,
            "signals": ["no_go_to_market_strategy"],
        },
    ],

    # ── OTHER ────────────────────────────────────────────────────────────────
    "OTHER": [
        {
            "id": "OTH_001",
            "text": (
                "Conduct a full business audit: food cost, labor cost, and overhead as a percentage of revenue. "
                "This gives you a clear baseline to work from."
            ),
            "min_score": 0.0,
            "signals": [],
        },
    ],
}


class RecommendationEngine:

    def get_recommendations(
        self,
        session: UserSession,
        max_recommendations: int = 4,
    ) -> list[str]:
        """
        Selects recommendations based on category, axis, score, and signals.
        Returns plain text strings — LLM formats them into a friendly message.
        """
        category = session.category or "OTHER"
        score = session.score or 0.0

        # Resolve the correct recommendation key (with axis if applicable)
        if session.axis and category in ["TYPE_1_PLATFORM_DEPENDENCY", "TYPE_3_LOW_MARGIN"]:
            rec_key = f"{category}_{session.axis}"
        else:
            rec_key = category

        triggered_signals = self._get_triggered_signals(session)
        candidates = RECOMMENDATIONS.get(rec_key, RECOMMENDATIONS["OTHER"])

        # Filter by minimum score
        score_filtered = [r for r in candidates if score >= r["min_score"]]

        # Split into signal-matched and always-show
        signal_matched = [
            r for r in score_filtered
            if r["signals"] and any(s in triggered_signals for s in r["signals"])
        ]
        always_show = [
            r for r in score_filtered
            if not r["signals"]
        ]

        # Merge: signal-matched first, always-show as padding
        merged = signal_matched + always_show

        # Deduplicate preserving order
        seen = set()
        unique = []
        for r in merged:
            if r["id"] not in seen:
                seen.add(r["id"])
                unique.append(r)

        selected = unique[:max_recommendations]

        if not selected:
            selected = RECOMMENDATIONS["OTHER"][:1]

        logger.info(
            f"[{session.user_id}] {len(selected)} recommendations selected "
            f"(key: {rec_key}, score: {score}, signals: {triggered_signals})"
        )
        return [r["text"] for r in selected]

    def _get_triggered_signals(self, session: UserSession) -> list[str]:
        from app.workflows.diagnostic_workflow import DIAGNOSTIC_QUESTIONS
        from app.scoring.scoring_engine import _eval_signal

        category = session.category or "OTHER"
        if session.axis and category in ["TYPE_1_PLATFORM_DEPENDENCY", "TYPE_3_LOW_MARGIN"]:
            key = f"{category}_{session.axis}"
        else:
            key = category

        questions = DIAGNOSTIC_QUESTIONS.get(key, [])
        triggered = []
        for q in questions:
            signal = q.get("signal")
            qkey = q.get("key")
            if signal and qkey in session.answers:
                if _eval_signal(signal, session.answers[qkey]):
                    triggered.append(signal)
        return triggered