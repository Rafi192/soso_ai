#this creates a single shared async redis connection used accross the application

import redis.asyncio as redis

from app.config.settings import settings

redis_client : redis.Redis | None = None

async def get_redis() -> redis.Redis:

    global redis_client

    if redis_client is None:
        redis_client = redis.Redis(
            host=settings.REDIS_HOST,
            port = settings.REDIS_PORT,
            db= settings.REDIS_DB,
            decode_responses=True
        )
    
    return redis_client

async def close_redis():

    global redis_client
    if redis_client:
        await redis_client.aclose()
        redis_client = None