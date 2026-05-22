import logging
from openai import AsyncOpenAI
from app.config.settings import settings

logger = logging.getLogger(__name__)

client: AsyncOpenAI | None = None

def get_openai_client() -> AsyncOpenAI:

    global client
    if client is None:
        client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    
    return client


# openai chat method
async def chat(
        messages:list[dict],
        model:str,
        temperature:float,
        max_tokens:int

):
    client = get_openai_client()

    response = await client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens
    )
    return response.choices[0].message.content.strip()

async def classify_problem(user_text: str, categories: list[str]) -> str:

    # Descriptions tell the LLM what each category actually means
    category_descriptions = {
        "TYPE_1_PLATFORM_DEPENDENCY": "too dependent on Uber Eats, Deliveroo, delivery platforms, paying high commissions",
        "TYPE_2_LOCAL_VISIBILITY":    "not enough customers, lack of visibility, no one knows about us, need more foot traffic, weak marketing",
        "TYPE_3_LOW_MARGIN":          "making sales but low profit, food cost too high, money disappearing, margins too thin",
        "TYPE_4_RETENTION":           "customers come once but don't return, repeat business problem, loyalty issues",
        "TYPE_5_DIGITAL_CHAOS":       "too many tools, nothing connects, digital mess, tech frustration",
        "TYPE_6_LAUNCH":              "new opening, relaunching, new location, just starting out",
        "OTHER":                      "anything that doesn't fit the above",
    }

    # Build a clean description list for the prompt
    described = "\n".join(
        f"- {cat}: {desc}"
        for cat, desc in category_descriptions.items()
        if cat in categories
    )

    messages = [
        {
            "role": "system",
            "content": (
                "You are a classification engine for restaurant business problems. "
                "Given the user's text, return ONLY the single most matching category key exactly as written. "
                "No explanation, no punctuation, just the key.\n\n"
                f"Categories:\n{described}"
            ),
        },
        {"role": "user", "content": user_text},
    ]

    result = await chat(
        messages=messages,
        model=settings.OPENAI_MINI_MODEL,   # cheap — classification only
        max_tokens=20,
        temperature=0.0,                     # fully deterministic
    )

    result = result.strip()
    logger.info(f"Classification result for user text '{user_text}' is '{result}'")
    return result

async def generate_conversational_question(
        raw_question:str,
        context:str,
        history:list[dict]

)->str:
    # takes raw diagnostic question and rewrites it to sound like a real consultant. 
    
    messages = [
        {
            "role": "system",
            "content": (
                "You are a friendly restaurant business consultant speaking on WhatsApp. "
                "Rewrite the given question to sound warm, conversational, and natural. "
                "Keep it short (1-2 sentences max). Do not add new questions. "
                f"Context about this user: {context}"
            ),
        },
        *history[-6:],          # last 3 turns for context — not the full history
        {"role": "user", "content": f"Rephrase this question naturally: {raw_question}"},
    ]
    return await chat(
        messages=messages,
        model=settings.OPENAI_MODEL,
        max_tokens=120,
        temperature=0.7,
    )
    

#summarize findings - used at the end of diagnostics

async def summarize_findings(answers: dict, category: str, score: float) -> str:
    """
    Generate a natural-language summary of what was discovered.
    Used as context before generating final recommendations.
    """
    answers_text = "\n".join(f"- {k}: {v}" for k, v in answers.items())
    messages = [
        {
            "role": "system",
            "content": (
                "You are a restaurant business analyst. "
                "Write a concise 2-3 sentence summary of findings for a consultant. "
                "Be factual and specific. No fluff."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Category: {category}\n"
                f"Severity score: {score}/10\n"
                f"Answers collected:\n{answers_text}\n\n"
                "Summarize the key findings."
            ),
        },
    ]
    return await chat(
        messages=messages,
        model=settings.OPENAI_MODEL,
        max_tokens=200,
        temperature=0.3,    #
    )

# GENERATE FINAL RESPONSE — recommendations screen
# ---------------------------------------------------------------------------
async def generate_final_response(
    summary: str,
    recommendations: list[str],
    profile: dict,
) -> str:
    """
    Generates the final WhatsApp message combining summary + recommendations.
    The recommendations list comes from your RecommendationEngine (deterministic),
    the LLM just makes it sound human.
    """
    rec_text = "\n".join(f"{i+1}. {r}" for i, r in enumerate(recommendations))
    restaurant_name = profile.get("restaurant_name", "your restaurant")
 
    messages = [
        {
            "role": "system",
            "content": (
                "You are a warm, expert restaurant business consultant on WhatsApp. "
                "Format the following analysis into a clear, encouraging final message. "
                "Use simple language. Structure: brief summary, then numbered recommendations. "
                "Keep the total under 300 words. End with an offer to elaborate."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Restaurant: {restaurant_name}\n\n"
                f"Findings summary:\n{summary}\n\n"
                f"Recommendations:\n{rec_text}"
            ),
        },
    ]
    return await chat(
        messages=messages,
        model=settings.OPENAI_MODEL,
        max_tokens=400,
        temperature=0.6,
    )
 