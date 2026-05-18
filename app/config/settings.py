#config/settings.py

from pydantic_settings import BaseSettings

class Settings(BaseSettings):

    #redis configs
    REDIS_HOST = "localhost"
    REDIS_PORT = 6379
    REDIS_DB = 0  # 0 represents the caching database, 1 represents the session database

    REDIS_TTL_SECONDS = 86400  # 24 hours

    #openAI configs
    OPENAI_API_KEY :str
    gpt_base_model:str = "gpt-4o"
    gpt_mini_model:str = "gpt-4o-mini"

    #mongoDB variables
    MONGO_URI:str = ""
    MONGO_DB:str = "soso_DB"

    class config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()

