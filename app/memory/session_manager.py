#memory/session_manager.py

from datetime import datetime, UTC
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
        session_data = await self.redis.get(user_id)

        if session_data:
            data = json.loads(session_data)
            return UserSession(**data)
        
        # no session found , create a new one
        logger.info(f"no session found for user {user_id}, creating new session")

        session = empty_session(user_id)
        await self.save_session(session)
        return session
    
    #save session method 

    async def save_session(self, session:UserSession) -> None:

        # session data will be saved based on user activity, so we update the last_active timestamp on every save

        session.last_active = datetime.now(UTC).isoformat()

        await self.redis.set(
            session.user_id,
            session.model_dump_json(),
            ex=self.ttl
        )
        logger.info(f"session for user {session.user_id} saved to redis with session stage {session.stage} and question index {session.question_index}")

    
    # now need to create helper methods for orchestrator and workflows

    # updating stage 
    def update_stage(self, session:UserSession, new_stage:str) -> UserSession:
        session.stage = new_stage
        session.question_index = 0 # reset question index whenever stage changes
        return session
    

    def append_history(self, session:UserSession, user_message:str, assistant_reply:str) -> UserSession:
        session.history.append({""
        "role": "user",
        "content": user_message})

        session.history.append({
            "role": "assistant",
            "content": assistant_reply
        })
        return session
    
    