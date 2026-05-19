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

    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens
    )
    return response.choices[0].message.content.strip()


async def classify_problem(user_text:str, categories:list[str]) -> str:
    category_list = "\n".join(f"- {c}" for c in categories)

    messages = [
        {
            "role": "system",
            "content": (
                "You are a classification engine"
                "Given user text, return ONLY the single most matching category"
                "from the list below. Return exactly one category name"
                 "If nothing matches, return UNKNOWN.\n\n"
                f"Categories:\n{category_list}"
            ),
        },
        {"role": "user", "content": user_text},
            
    ]
    result = await chat(
        messages= messages,
        model= settings.gpt_mini_model,
        temperature=0.0,
        max_tokens=10

    )
    logger.info(f"Classfifiction result for user text '{user_text}' is '{result}'")
    return result.strip()