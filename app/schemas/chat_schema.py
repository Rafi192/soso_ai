#schemas/ chat_schema.py

from pydantic_settings import BaseSettings

class ChatRequest(BaseSettings):
    user_id:str #whatsapp number
    message:str # user message


class ChatResponse(BaseSettings):
    user_id:str
    reply:str # message 
    stage:str #current stage4 of the conversation
    
    