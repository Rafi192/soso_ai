# recommendations/recommendation_engine.py
# Deterministic recommendation selection — no AI.
# Picks recommendations based on category, score, and triggered signals.
# The LLM in recommendation_workflow.py then formats them into a human message.
# All recommendation text is sourced directly from the MUFU Brain document.
 
import logging
from app.schemas.session_schema import UserSession
 
logger = logging.getLogger(__name__)
 
 
# ---------------------------------------------------------------------------
# RECOMMENDATION BANK — sourced from MUFU Brain doc per TYPE
#
# Each recommendation:
#   id          → unique identifier for logging/analytics
#   text        → exact recommendation from the doc
#   min_score   → minimum severity score required to trigger this
#   signals     → list of signals that make this recommendation relevant
#                 empty list = always show for this category
# ---------------------------------------------------------------------------
 
RECOMMENDATIONS: dict[str, list[dict]] = {
 
    "TYPE_1_PLATFORM_DEPENDENCY": [
        {
            "id": "T1_001",
            "text": "Put a click-and-collect QR code in every delivery bag offering customers a 10-20% discount or free dessert/drink to order directly next time.",
            "min_score": 3.0,
            "signals": ["no_direct_channel", "platform_revenue_gt_60"],
        },
        {
            "id": "T1_002",
            "text": "Promote your direct ordering QR code on social media and at the register to start shifting customers off the platforms.",
            "min_score": 2.0,
            "signals": ["no_direct_channel"],
        },
        {
            "id": "T1_003",
            "text": "Launch a campaign to collect customer contact information, set up a WhatsApp group, and send one promotion per week to your direct customers.",
            "min_score": 2.0,
            "signals": ["does_not_collect_customer_data"],
        },
        {
            "id": "T1_004",
            "text": "Consider a proprietary online ordering system (Zelty, Innovorder, Sunday, or Tiller) — these charge only 0-2% commission versus the 25-35% you currently pay.",
            "min_score": 4.0,
            "signals": ["platform_revenue_gt_60", "no_direct_channel"],
        },
        {
            "id": "T1_005",
            "text": "Update your platform listing with recent photos, accurate hours, and start responding to all Google reviews to maximize the visibility platforms already give you.",
            "min_score": 1.0,
            "signals": ["platform_listing_not_optimized"],
        },
    ],
 
    "TYPE_2_LOCAL_VISIBILITY": [
        {
            "id": "T2_001",
            "text": "Create or complete your Google Business listing immediately — add recent photos, accurate hours, phone number, and start responding to every review.",
            "min_score": 1.0,
            "signals": ["google_listing_incomplete"],
        },
        {
            "id": "T2_002",
            "text": "Launch a Google review campaign — ask every satisfied customer at checkout via a QR code. Target: 50 reviews in 30 days.",
            "min_score": 2.0,
            "signals": ["fewer_than_50_reviews_or_low_rating"],
        },
        {
            "id": "T2_003",
            "text": "Post 2-3 TikTok videos per week and at least 1 Instagram Story per day — behind-the-scenes prep, dish of the day, and before/after content perform best in the restaurant industry.",
            "min_score": 2.0,
            "signals": ["not_active_on_social_media"],
        },
        {
            "id": "T2_004",
            "text": "Partner with a local micro-influencer (5k-50k followers) — offer a complimentary dinner in exchange for an authentic post. This costs ~€30 in food and can reach 20,000 geographically targeted people.",
            "min_score": 3.0,
            "signals": ["not_active_on_social_media", "no_marketing_budget"],
        },
        {
            "id": "T2_005",
            "text": "Distribute targeted flyers in nearby offices, schools, and local businesses with an enticing introductory offer to drive first-time visits.",
            "min_score": 2.0,
            "signals": ["no_marketing_efforts"],
        },
        {
            "id": "T2_006",
            "text": "Add a direct ordering link (not a platform link) to your social media bio using Linktree or a simple landing page, with a clear call to action on every post.",
            "min_score": 2.0,
            "signals": [],     # always show for TYPE 2
        },
    ],
 
    "TYPE_3_LOW_MARGIN": [
        {
            "id": "T3_001",
            "text": "Calculate your actual food cost for the last 30 days using this formula: total ingredient purchases ÷ revenue × 100. This is your baseline.",
            "min_score": 1.0,
            "signals": ["food_cost_unknown_or_high"],
        },
        {
            "id": "T3_002",
            "text": "Simplify your menu — identify the 3 products that sell the least and remove them to reduce waste and simplify production.",
            "min_score": 2.0,
            "signals": ["menu_too_extensive", "moderate_to_high_waste"],
        },
        {
            "id": "T3_003",
            "text": "Create simple technical data sheets for your 5 best-selling items with precise portion sizes to standardize production and reduce cost variance.",
            "min_score": 2.0,
            "signals": ["no_technical_data_sheets"],
        },
        {
            "id": "T3_004",
            "text": "Adjust staff schedules based on actual sales data — payroll should stay below 35% of revenue. Cross-reference your schedule with revenue history by time slot.",
            "min_score": 2.0,
            "signals": ["poorly_optimized_staff"],
        },
        {
            "id": "T3_005",
            "text": "Implement Melba as your inventory and POS management tool — it imports sales from your POS, purchases from suppliers, and automatically calculates weekly food cost without manual re-entry.",
            "min_score": 3.0,
            "signals": ["no_management_tools"],
        },
    ],
 
    "TYPE_4_RETENTION": [
        {
            "id": "T4_001",
            "text": "Create a WhatsApp Business list and offer every customer at the register the chance to sign up for your offers. Target: 50 numbers in 30 days.",
            "min_score": 2.0,
            "signals": ["no_customer_database", "never_communicates_with_customers"],
        },
        {
            "id": "T4_002",
            "text": "Launch a simple loyalty program — even a paper stamp card is enough to start. The key is to create a mechanism that rewards repeat visits.",
            "min_score": 2.0,
            "signals": ["no_loyalty_program"],
        },
        {
            "id": "T4_003",
            "text": "Send 1 WhatsApp message per week to your customer list with a simple time-limited offer (e.g., 'Tonight only: free dessert with any meal order').",
            "min_score": 2.0,
            "signals": ["never_communicates_with_customers"],
        },
        {
            "id": "T4_004",
            "text": "Install a QR code at the register and on every table inviting customers to join your WhatsApp list with a welcome offer.",
            "min_score": 2.0,
            "signals": ["no_checkout_capture"],
        },
        {
            "id": "T4_005",
            "text": "Consider Zenchef — it combines reservation management, customer CRM, and automated follow-ups in one interface, automatically populating your contact database with every reservation.",
            "min_score": 4.0,
            "signals": ["no_customer_database", "no_loyalty_program"],
        },
    ],
 
    "TYPE_5_DIGITAL_CHAOS": [
        {
            "id": "T5_001",
            "text": "List all your tech subscriptions and their exact monthly cost. Immediately cancel any you no longer use — this creates instant savings.",
            "min_score": 1.0,
            "signals": ["unused_paid_tools"],
        },
        {
            "id": "T5_002",
            "text": "Choose one central tool that handles point-of-sale, orders, and analytics. One good tool mastered beats five tools used poorly. Lightspeed is the recommended solution.",
            "min_score": 3.0,
            "signals": ["more_than_4_unconnected_tools", "frequent_reentry"],
        },
        {
            "id": "T5_003",
            "text": "Prioritize eliminating manual data re-entry first — find one integration or tool that syncs your menu across platforms automatically.",
            "min_score": 2.0,
            "signals": ["frequent_reentry"],
        },
        {
            "id": "T5_004",
            "text": "Ensure your POS system has real-time sales analytics by product and time slot — this data is essential for staffing, menu, and inventory decisions.",
            "min_score": 2.0,
            "signals": ["pos_without_analytics"],
        },
    ],
 
    "TYPE_6_LAUNCH": [
        {
            "id": "T6_001",
            "text": "Open your TikTok and Instagram accounts now — document the construction, hiring, suppliers, and menu development. Customers who follow the journey are infinitely more loyal than those who discover you by chance.",
            "min_score": 1.0,
            "signals": ["digital_presence_not_prepared"],
        },
        {
            "id": "T6_002",
            "text": "Organize a private soft opening with family, friends, neighbors, and local partners 3-5 days before the official opening to test your processes and generate word-of-mouth.",
            "min_score": 2.0,
            "signals": ["no_go_to_market_strategy"],
        },
        {
            "id": "T6_003",
            "text": "Prepare a limited-time launch offer (e.g., special-price discovery menu for the first 15 days) to create urgency and attract your first wave of customers.",
            "min_score": 2.0,
            "signals": [],     # always show for TYPE 6
        },
        {
            "id": "T6_004",
            "text": "Set up customer data collection from Day 1 — QR code at the register, WhatsApp list, and a launch loyalty card so you own your customer relationships from the start.",
            "min_score": 2.0,
            "signals": ["no_day1_customer_acquisition"],
        },
        {
            "id": "T6_005",
            "text": "Distribute flyers in local offices, schools, and businesses with a special opening offer. Goal: reach 200-500 people before opening day.",
            "min_score": 2.0,
            "signals": ["no_site_survey"],
        },
        {
            "id": "T6_006",
            "text": "Create or complete your Google Business listing, reactivate your social media accounts, and post an opening announcement with photos now — before the doors open.",
            "min_score": 1.0,
            "signals": ["digital_presence_not_prepared"],
        },
    ],
 
    "OTHER": [
        {
            "id": "OTH_001",
            "text": "Conduct a full business audit: food cost, labor cost, and overhead as a percentage of revenue. This gives you a clear baseline to work from.",
            "min_score": 0.0,
            "signals": [],
        },
    ],
}
 
 
class RecommendationEngine:
 
    def get_recommendations(
        self,
        session: UserSession,
        max_recommendations: int = 3,
    ) -> list[str]:
        """
        Selects the top N recommendations for this user based on:
        - Their problem category
        - Their severity score (min_score filter)
        - Their triggered signals (signal relevance filter)
 
        Returns a plain list of recommendation text strings.
        The LLM in recommendation_workflow.py formats these into a
        friendly WhatsApp message — it never selects them.
        """
        category = session.category or "OTHER"
        score = session.score
        triggered_signals = self._get_triggered_signals(session)
 
        candidates = RECOMMENDATIONS.get(category, RECOMMENDATIONS["OTHER"])
 
        # Filter 1: severity score must meet minimum threshold
        score_filtered = [r for r in candidates if score >= r["min_score"]]
 
        # Filter 2: separate into signal-matched and always-show
        signal_matched = [
            r for r in score_filtered
            if r["signals"] and any(s in triggered_signals for s in r["signals"])
        ]
        always_show = [
            r for r in score_filtered
            if not r["signals"]
        ]
 
        # Merge: signal-matched first (most relevant), then always-show as padding
        merged = signal_matched + always_show
 
        # Deduplicate by id preserving order
        seen = set()
        unique = []
        for r in merged:
            if r["id"] not in seen:
                seen.add(r["id"])
                unique.append(r)
 
        selected = unique[:max_recommendations]
 
        # Fallback: if nothing matched at all
        if not selected:
            selected = RECOMMENDATIONS["OTHER"][:1]
 
        logger.info(
            f"[{session.user_id}] {len(selected)} recommendations selected "
            f"(category: {category}, score: {score}, signals: {triggered_signals})"
        )
 
        return [r["text"] for r in selected]
 
    def _get_triggered_signals(self, session: UserSession) -> list[str]:
        """
        Rebuilds the list of triggered signal names from session answers.
        Imports diagnostic_workflow here to avoid circular imports at module level.
        """
        from app.workflows.diagnostic_workflow import DIAGNOSTIC_QUESTIONS, Category
        from app.scoring.scoring_engine import _eval_signal
 
        category = session.category or "OTHER"
        questions = DIAGNOSTIC_QUESTIONS.get(category, [])
 
        triggered = []
        for q in questions:
            signal = q.get("signal")
            key = q.get("key")
            if signal and key in session.answers:
                if _eval_signal(signal, session.answers[key]):
                    triggered.append(signal)
 
        return triggered