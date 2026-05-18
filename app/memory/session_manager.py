#memory/session_manager.py

import json
import logging 

import redis.asyncio as redis

from app.config.settings import settings
from app.schemas.session_schema import UserSession, empty_session

logger = logging.getLogger(__name__)

class SessionManager:

    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self.ttl = settings.REDIS_TTL_SECONDS

    
    #load session from redis. 
    #if the key doesnt exist( new user or expired TTL), 
    #create a fresh empty session and return it
    async def load_session(self, user_id:str) -> UserSession:

        raw_session = await self.redis.get(user_id)

        if raw_session:
            data = json.loads(raw_session)
            logger.info(f"session loaded for user_id: {user_id}")

            return UserSession(**data)
        
        logger.info(f"no existing session for user_id: {user_id}. creating new session.")

        session = empty_session(user_id)
        await self.save(session)
        return session

