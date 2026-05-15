from fastapi import FastAPI
import openai
import json
from dotenv import load_dotenv
import os
load_dotenv()

#initializin g the fastapi APP
app = FastAPI()

#initialize redis client
import redis.asyncio as redis
redis_client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)

#initializing openai client
openai_client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# checking the server
@app.get("/health")
async def health_check():
    return {
        "status":200,
        "message": "Server is healthy"
    }

