
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from motor.motor_asyncio import AsyncIOMotorClient

from app.api.chat import router as chat_router
from app.memory.redis_client import get_redis, close_redis
from app.memory.session_manager import SessionManager
from app.orchestrator.conversation_orchestrator import ConversationOrchestrator
from app.config.settings import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# LIFESPAN — runs startup and shutdown logic
# Replaces the old @app.on_event("startup") pattern
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up...")

    redis_client = await get_redis()
    session_manager = SessionManager(redis_client)      # wra Redis in SessionManager
    orchestrator = ConversationOrchestrator(session_manager)  # pass SessionManager

    app.state.orchestrator = orchestrator

    logger.info(f"Connected to Redis at {settings.REDIS_HOST}:{settings.REDIS_PORT}")
    logger.info(f"Using OpenAI model: {settings.OPENAI_MODEL}")
    logger.info("Startup complete.")

    yield

    logger.info("Shutting down...")
    await close_redis()
    logger.info("Redis connection closed.")


# ---------------------------------------------------------------------------
# APP
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Restaurant Consultation AI",
    description="Conversational diagnostic system for restaurant owners via WhatsApp",
    version="1.0.0",
    lifespan=lifespan,
)

# Register routes
app.include_router(chat_router, prefix="/api/v1")


# ---------------------------------------------------------------------------
# HEALTH CHECK
# ---------------------------------------------------------------------------
@app.get("/health")
async def health_check():
    return {"status": 200, "message": "Server is healthy"}