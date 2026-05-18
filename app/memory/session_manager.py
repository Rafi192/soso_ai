#memory/session_manager.py

import json
import logging 

import redis.asyncio as redis

from app.config.settings import settings
from app.schemas.session_schema import UserSession, empty_session

logger = logging.getLogger(__name__)

