from pymongo import MongoClient
from dotenv import load_dotenv
import os

load_dotenv()


MONGODB_URI = os.getenv("MONGODB_URI")
MONGO_DB = os.getenv("MONGO_DB")

try:
    client = MongoClient(MONGODB_URI)

    client.admin.command('ping')
    print("Successfully connected to MongoDB!")

    databases = client.list_database_names()
    print("Databases:")
    for db in databases:
        print(f"- {db}")
    
    db = client[MONGO_DB]
    collections = db.list_collection_names()
    print(f"Collections in '{MONGO_DB}':")
    for collection in collections:
        print(f"- {collection}")
    
    print("MongoDB connection and query successful!")

except Exception as e:
    print(f"Error connecting to MongoDB: {e}")


