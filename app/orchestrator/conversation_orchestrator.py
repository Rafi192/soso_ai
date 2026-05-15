# conversation_orchestrator.py
import redis
import os
import openai
import json
from app.workflows import profile_workflow.profile_info
from app.workflows import problem_detection_workflow.problem_info
from app.workflows import diagnostic_workflow.diagnosis_info

from dotenv import load_dotenv
load_dotenv()

class ConversationOrchestrator:
    def __init__(self, redis_client=None, openai_client=None):
        self.redis_client = redis_client if redis_client is not None else redis.Redis(host=os.getenv("REDIS_HOST"), port=os.getenv("REDIS_PORT"), db=os.getenv("REDIS_DB"), decode_responses=True)
        self.openai_client = openai_client if openai_client is not None else openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))




    def load_user_session(self, user_id):
        # Load user session from Redis
        #if no session exists, return an empty session and create a new one in Redis
        if not self.redis_client.exists(user_id):
            new_session = {
                "conversation_history": [],
                "current_workflow": None,
                "conversation_state": None,
                "last_interaction_time": None
            }
            self.redis_client.set(user_id, json.dumps(new_session))
        
        session_data = self.redis_client.get(user_id)
        return json.loads(session_data)

    def determine_conversation_state(self, user_session):
        # Determine the current state of the conversation based on user session
        user_session["conversation_state"] = "initial" if not user_session["conversation_history"] else "ongoing"
        return user_session["conversation_state"]
    

    def route_to_workflow(self, conversation_state):
        # Route the conversation to the appropriate workflow based on the conversation state
        if conversation_state == "initial":
            return profile_info()
        
        if conversation_state == "ongoing":
            return problem_info()
        
        if conversation_state == "diagnosis":
            return diagnosis_info()
        
        

    def get_next_action(self, conversation_state):
        # Get the next action to take based on the conversation state
        pass

    def generate_response(self, user_input, conversation_state):
        # Generate a response based on user input and conversation state
        

    def save_updated_session(self, user_id, updated_session):
        # Save the updated user session back to Redis
        pass


    def final_response(self, user_input, user_id):
        # Main method to handle the conversation flow
        user_session = self.load_user_session(user_id)
        conversation_state = self.determine_conversation_state(user_session)
        self.route_to_workflow(conversation_state)
        next_action = self.get_next_action(conversation_state)
        response = self.generate_response(user_input, conversation_state)
        updated_session = self.update_user_session(user_session, conversation_state)
        self.save_updated_session(user_id, updated_session)
        return response

