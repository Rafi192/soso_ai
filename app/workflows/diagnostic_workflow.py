# workflows/diagnostic_workflow.py
# Diagnostic questions taken DIRECTLY from the MUFU Brain document.
# Each TYPE maps to the exact questions defined by the client.

import logging
from app.schemas.session_schema import UserSession
from app.llm.openai_client import generate_conversational_question

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# CATEGORY CONSTANTS — match exactly what problem_detection_workflow assigns
# ---------------------------------------------------------------------------
class Category:
    TYPE_1_PLATFORM_DEPENDENCY = "TYPE_1_PLATFORM_DEPENDENCY"
    TYPE_2_LOCAL_VISIBILITY    = "TYPE_2_LOCAL_VISIBILITY"
    TYPE_3_LOW_MARGIN          = "TYPE_3_LOW_MARGIN"
    TYPE_4_RETENTION           = "TYPE_4_RETENTION"
    TYPE_5_DIGITAL_CHAOS       = "TYPE_5_DIGITAL_CHAOS"
    TYPE_6_LAUNCH              = "TYPE_6_LAUNCH"
    OTHER                      = "OTHER"


# ---------------------------------------------------------------------------
# QUESTION BANK — sourced from MUFU Brain doc
#
# Each question:
#   key      → stored in session.answers under this key
#   raw      → exact question text from doc (LLM rephrases for WhatsApp tone)
#   critical → must be answered before recommendations are triggered
#   signal   → string the scoring engine checks (see scoring_engine.py)
# ---------------------------------------------------------------------------
DIAGNOSTIC_QUESTIONS: dict[str, list[dict]] = {

    Category.TYPE_1_PLATFORM_DEPENDENCY: [
        {"key": "platform_revenue_pct",       "raw": "Roughly what percentage of your revenue comes from delivery platforms? (e.g., 30%, 50%, 80%...)",                                                          "critical": True,  "signal": "platform_revenue_gt_60"},
        {"key": "platforms_used",              "raw": "Which platforms are you on exactly? And which one brings you the most orders?",                                                                             "critical": True,  "signal": None},
        {"key": "commission_awareness",        "raw": "Do you have a rough idea of the commission you pay per order on these platforms?",                                                                          "critical": True,  "signal": "does_not_know_commissions"},
        {"key": "direct_ordering_channel",     "raw": "Apart from the platforms, do you have a way for your customers to order directly from you? (WhatsApp, website, phone, click & collect…)",                  "critical": True,  "signal": "no_direct_channel"},
        {"key": "collects_customer_data",      "raw": "Do you collect your customers' contact information from the platforms in any way? (QR code, card in the bag, loyalty program…)",                           "critical": True,  "signal": "does_not_collect_customer_data"},
        {"key": "tried_direct_channel",        "raw": "Have you ever tried getting your customers to order directly from you instead of through the platforms? If so, how did that go?",                          "critical": False, "signal": "never_tried_direct_channel"},
        {"key": "listing_optimized",           "raw": "Is your Uber Eats/Deliveroo listing up to date? (nice recent photos, description, hours, do you respond to Google reviews?)",                             "critical": False, "signal": "platform_listing_not_optimized"},
        {"key": "avg_order_value_and_volume",  "raw": "What's your average order value on the platforms? How many orders do you get per month?",                                                                  "critical": False, "signal": None},
        {"key": "goal_margin_or_direct",       "raw": "What would you ideally like: to earn a higher margin on your current orders, or to have more direct customers?",                                          "critical": False, "signal": None},
        {"key": "has_promotions",              "raw": "Have you set up any promotions? Buy one, get one free, or 10–20% off?",                                                                                   "critical": False, "signal": None},
    ],

    Category.TYPE_2_LOCAL_VISIBILITY: [
        {"key": "foot_traffic",                "raw": "Right now, do you get a lot of foot traffic in front of your restaurant, or is it a quiet street?",                                                        "critical": True,  "signal": None},
        {"key": "busy_slow_times",             "raw": "What are your busiest and slowest days and times?",                                                                                                        "critical": False, "signal": None},
        {"key": "google_listing_status",       "raw": "Is your Google listing up to date? (photos, hours, phone number, responses to reviews…) Do you know how many people see it each month?",                  "critical": True,  "signal": "google_listing_incomplete"},
        {"key": "social_media_activity",       "raw": "Are you active on Instagram, TikTok, or Facebook? How many followers do you have? How often do you post, roughly, per week?",                             "critical": True,  "signal": "not_active_on_social_media"},
        {"key": "google_reviews",              "raw": "How many Google reviews do you have right now? And what's your rating?",                                                                                   "critical": True,  "signal": "fewer_than_50_reviews_or_low_rating"},
        {"key": "customer_sources",            "raw": "Where do most of your customers come from these days? (walk-ins, word of mouth, Google, social media, platforms, other…)",                                 "critical": True,  "signal": "doesnt_know_customer_sources"},
        {"key": "past_visibility_efforts",     "raw": "Have you ever tried any strategies to get your name out there? And what worked or didn't work?",                                                          "critical": False, "signal": "no_marketing_efforts"},
        {"key": "marketing_budget",            "raw": "Do you have a budget—even a small one—that you can allocate to your visibility each month? (Even €50 to €200 is a start.)",                              "critical": False, "signal": "no_marketing_budget"},
        {"key": "social_media_help",           "raw": "Do you have someone on your team or in your circle who can take photos, create stories, or manage social media? Or are you handling all of that on your own?", "critical": False, "signal": "handling_comms_alone"},
        {"key": "slow_period_offers",          "raw": "Are there days or times when it's really slow and you'd like to bring in more people? Have you ever offered specials to attract customers at certain times?", "critical": False, "signal": None},
        {"key": "neighborhood_context",        "raw": "What's the area like around you? (offices, high schools, apartment complexes, shops, industrial zone…)",                                                   "critical": False, "signal": None},
    ],

    Category.TYPE_3_LOW_MARGIN: [
        {"key": "money_tracking_clarity",      "raw": "If I ask you where the money goes at the end of the month, do you have a clear idea, or is it unclear to you?",                                           "critical": True,  "signal": None},
        {"key": "food_cost_known",             "raw": "Do you know your food cost? That is, the cost of your ingredients as a percentage of your revenue?",                                                       "critical": True,  "signal": "food_cost_unknown_or_high"},
        {"key": "ingredient_order_management", "raw": "How do you manage your ingredient orders? (by gut feeling, based on the previous day's sales, using a tool, or something else…)",                         "critical": True,  "signal": "order_management_by_intuition"},
        {"key": "food_wastage",                "raw": "Do you often have products you throw away at the end of the day or week? (bread, meat, vegetables, prepared items…)",                                     "critical": True,  "signal": "moderate_to_high_waste"},
        {"key": "recipe_standardization",      "raw": "Are your recipes standardized with precise measurements, or does each cook do things a little differently?",                                               "critical": False, "signal": "no_technical_data_sheets"},
        {"key": "payroll_optimization",        "raw": "Does your payroll seem appropriate for your business? Are there times when you're paying staff to do very little?",                                        "critical": False, "signal": "poorly_optimized_staff"},
        {"key": "pos_sales_tracking",          "raw": "Do you know which products are your best sellers and most profitable? Do you use a POS system that provides these stats?",                                 "critical": False, "signal": "no_sales_tracking_by_product"},
        {"key": "menu_size",                   "raw": "Is your menu extensive, or is it short and focused? Do you have dishes that sell very little?",                                                            "critical": False, "signal": "menu_too_extensive"},
        {"key": "fixed_costs_known",           "raw": "Do you know exactly what your fixed costs (rent, insurance, various subscriptions, etc.) are each month?",                                                "critical": False, "signal": None},
        {"key": "management_tools",            "raw": "Do you use software or a tool to track your accounting, inventory, or cash register? (e.g., Zelty, Lightspeed, Addition, Excel, nothing at all…)",       "critical": True,  "signal": "no_management_tools"},
    ],

    Category.TYPE_4_RETENTION: [
        {"key": "return_rate_awareness",       "raw": "If I ask you how many of your customers come back at least once a month, do you have any idea?",                                                           "critical": True,  "signal": "doesnt_know_return_rate"},
        {"key": "identifies_regulars",         "raw": "Do you have a way to identify your loyal customers? (name, phone number, loyalty card, app account…)",                                                    "critical": True,  "signal": "no_identification_of_regulars"},
        {"key": "customer_data_collection",    "raw": "Do you collect your customers' contact information in any way? (WhatsApp number, email, loyalty program…)",                                               "critical": True,  "signal": "no_customer_database"},
        {"key": "loyalty_program",             "raw": "Do you have a loyalty program in place? (stamp card, points, discounts for regulars, app…)",                                                              "critical": True,  "signal": "no_loyalty_program"},
        {"key": "customer_communication",      "raw": "Do you send messages to your customers from time to time? (promotions, new arrivals, events…) Via WhatsApp, SMS, email, social media?",                  "critical": True,  "signal": "never_communicates_with_customers"},
        {"key": "checkout_capture",            "raw": "When a customer comes to your business, is there a moment when you ask them to join your WhatsApp list, leave their number, or scan a QR code?",         "critical": False, "signal": "no_checkout_capture"},
        {"key": "responds_to_reviews",         "raw": "When you receive a Google review (positive or negative), do you always respond?",                                                                          "critical": False, "signal": "does_not_respond_to_reviews"},
        {"key": "loyal_customer_perks",        "raw": "Do you have special offers or perks reserved for your frequent customers? (free coffee, discounts, priority access, special menus…)",                    "critical": False, "signal": "no_offers_for_loyal_customers"},
        {"key": "churn_reason",                "raw": "In your opinion, why don't customers come back? (price, quality, competition, they forget, something else?)",                                             "critical": False, "signal": None},
        {"key": "satisfaction_measurement",    "raw": "Do you have a way to know if your customers are satisfied, aside from Google reviews? (survey, asking directly, or something else?)",                     "critical": False, "signal": None},
    ],

    Category.TYPE_5_DIGITAL_CHAOS: [
        {"key": "tools_inventory",             "raw": "What tools do you use on a daily basis in your restaurant? (POS, platforms, ordering site, reservations, scheduling, accounting, other…) List everything.", "critical": True,  "signal": "more_than_4_unconnected_tools"},
        {"key": "most_frustrating_tool",       "raw": "Of these tools, which one takes up the most time or frustrates you the most? Why?",                                                                        "critical": True,  "signal": None},
        {"key": "data_reentry",                "raw": "Do you have to re-enter the same information into multiple tools? (e.g., updating the menu on Uber AND on your website AND on your POS separately…)",     "critical": True,  "signal": "frequent_reentry"},
        {"key": "sync_problems",               "raw": "Have you ever had problems because of poorly synchronized tools? (e.g., out-of-stock item still showing, menu not up to date, prices varying…)",         "critical": False, "signal": "tool_related_errors"},
        {"key": "tech_subscription_cost",      "raw": "Do you know how much you spend on tech subscriptions each month in total? (POS, platforms, website, various tools…)",                                    "critical": False, "signal": "unknown_tech_budget"},
        {"key": "unused_paid_tools",           "raw": "Do you have tools you're paying for but hardly use anymore—or not at all?",                                                                               "critical": False, "signal": "unused_paid_tools"},
        {"key": "digital_team_support",        "raw": "Do you have anyone on your team who knows a bit about digital tools? Or are you the only one managing all of this?",                                      "critical": False, "signal": "alone_in_managing_tech"},
        {"key": "pos_analytics",               "raw": "Does your current POS system provide you with sales statistics? (Which products sell best, at what times, average ticket size…)",                         "critical": False, "signal": "pos_without_analytics"},
        {"key": "tool_switch_blockers",        "raw": "Have you ever thought about switching tools to simplify all this? What's kept you from doing so? (cost, fear of migration, lack of time, other…)",       "critical": False, "signal": "afraid_to_switch_tools"},
        {"key": "ideal_tech_vision",           "raw": "If the tech worked perfectly for you, what would that look like? What would you want your tools to do that they don't do today?",                         "critical": False, "signal": None},
    ],

    Category.TYPE_6_LAUNCH: [
        {"key": "launch_type",                 "raw": "Is this a new opening, a relaunch after renovations, a change in concept, or a takeover of an existing restaurant?",                                      "critical": True,  "signal": None},
        {"key": "opening_timeline",            "raw": "How soon are you opening (or relaunching)? Or has it already happened recently?",                                                                          "critical": True,  "signal": "opening_soon_without_digital_prep"},
        {"key": "concept_description",         "raw": "Describe your concept in 2–3 sentences: what type of cuisine, what price point, and who is your target audience?",                                        "critical": True,  "signal": None},
        {"key": "neighborhood_research",       "raw": "Did you research your neighborhood before launching? (competition, foot traffic, resident demographics, nearby offices, schools…)",                        "critical": False, "signal": "no_site_survey"},
        {"key": "digital_presence_ready",      "raw": "Before opening, have you already created or updated your Google listing, social media profiles, and online menu?",                                        "critical": True,  "signal": "digital_presence_not_prepared"},
        {"key": "sales_channels_focus",        "raw": "Which channels will you focus on right from the start? (dine-in, takeout, delivery platforms, click & collect, WhatsApp…)",                               "critical": False, "signal": "too_many_channels_from_start"},
        {"key": "launch_budget",               "raw": "Do you have a budget set aside for the grand opening? (marketing, opening promotions, flyers, events, online ads…)",                                     "critical": False, "signal": "no_launch_budget"},
        {"key": "opening_event_planned",       "raw": "Have you planned anything special for the opening? (soft opening, event, launch offer, inviting local influencers, partnerships…)",                      "critical": False, "signal": "no_go_to_market_strategy"},
        {"key": "day1_data_collection",        "raw": "Have you planned a way to collect contact information from your first customers on day one? (QR code, WhatsApp list, launch loyalty program…)",          "critical": False, "signal": "no_day1_customer_acquisition"},
        {"key": "biggest_launch_concern",      "raw": "What's your biggest concern about this launch? (not enough customers, not prepared enough, lack of budget, team not ready, other…)",                     "critical": False, "signal": None},
    ],

    Category.OTHER: [
        {"key": "open_problem_description",    "raw": "Can you tell me more about the main challenge you're facing? Try to be as specific as possible.",                                                          "critical": True,  "signal": None},
        {"key": "impact_on_business",          "raw": "How is this affecting your business day-to-day? (revenue, stress, operations, team…)",                                                                    "critical": True,  "signal": None},
        {"key": "already_tried",               "raw": "Have you already tried anything to solve this? What happened?",                                                                                           "critical": False, "signal": None},
    ],
}


class DiagnosticWorkflow:

    def get_questions(self, category: str) -> list[dict]:
        return DIAGNOSTIC_QUESTIONS.get(category, DIAGNOSTIC_QUESTIONS[Category.OTHER])

    def get_next_question(self, session: UserSession) -> dict | None:
        """Returns the first unanswered question, or None if all answered."""
        for q in self.get_questions(session.category or Category.OTHER):
            if q["key"] not in session.answers:
                return q
        return None

    def total_questions(self, session: UserSession) -> int:
        return len(self.get_questions(session.category or Category.OTHER))

    def extract_answer(self, session: UserSession, question: dict, user_input: str) -> UserSession:
        session.answers[question["key"]] = user_input.strip()
        logger.info(f"[{session.user_id}] {question['key']} = {user_input.strip()[:60]}")
        return session

    async def generate_question_message(self, session: UserSession, question: dict) -> str:
        context = (
            f"Restaurant: {session.profile.get('restaurant_name', 'unknown')}. "
            f"Problem type: {session.category}. "
            f"Questions answered so far: {len(session.answers)}."
        )
        return await generate_conversational_question(
            raw_question=question["raw"],
            context=context,
            history=session.history,
        )

    def all_critical_answered(self, session: UserSession) -> bool:
        questions = self.get_questions(session.category or Category.OTHER)
        critical_keys = [q["key"] for q in questions if q["critical"]]
        return all(k in session.answers for k in critical_keys)

    def get_triggered_signals(self, session: UserSession) -> list[str]:
        """
        Returns signal names for all answered questions.
        The scoring engine uses these to look up point values.
        """
        questions = self.get_questions(session.category or Category.OTHER)
        return [
            q["signal"]
            for q in questions
            if q["signal"] and q["key"] in session.answers
        ]