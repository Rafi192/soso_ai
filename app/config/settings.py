# config/settings.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):

    # Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_TTL_SECONDS: int = 86400      # 24 hours

    # OpenAI
    OPENAI_API_KEY: str
    OPENAI_MODEL: str = "gpt-4o"
    OPENAI_MINI_MODEL: str = "gpt-4o-mini"

    # MongoDB
    MONGODB_URI: str
    MONGODB_DB: str
    MONGODB_COLLECTION: str

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()