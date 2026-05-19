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
    return response.choices[0].message.content

