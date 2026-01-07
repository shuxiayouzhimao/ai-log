import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    # MongoDB
    MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
    DB_NAME = os.getenv("DB_NAME", "log_monitor")
    COLLECTION_NAME = os.getenv("COLLECTION_NAME", "app_logs")
    
    # LLM
    LLM_API_KEY = os.getenv("LLM_API_KEY")
    LLM_BASE_URL = os.getenv("LLM_BASE_URL")
    LLM_MODEL = os.getenv("LLM_MODEL", "deepseek-ai/DeepSeek-R1")
    
    # App
    REFRESH_RATE = int(os.getenv("REFRESH_RATE", 5))
