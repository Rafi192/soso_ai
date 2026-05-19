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

