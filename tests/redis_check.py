from dotenv import load_dotenv
import os
import redis
load_dotenv()


redis_host = os.getenv("REDIS_HOST")
redis_port = os.getenv("REDIS_PORT")
redis_db =  os.getenv("REDIS_DB")

try:

    r = redis.Redis(
        host=redis_host,
        port=redis_port,
        db=redis_db,
        decode_responses=True
    )
    response = r.ping()
    if response:
        print("Successfully connected to Redis!")
    
    r.set("test_key", "Hello, Redis!")
    
    value= r.get("test_key")
    print(f"value for 'test_key': {value}")

    print("Stored value", value)

except Exception as e:
    print(f"Error connecting to Redis: {e}")