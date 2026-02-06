from pydantic_settings import BaseSettings
from typing import List, Optional
import os

class Settings(BaseSettings):
    TELEGRAM_BOT_TOKEN: str
    BOT_TELEGRAM_ID: int = 8521381973  # Bober Sikfan bot ID for graph Agent node
    GEMINI_CLIENT_SECRET_PATH: str = "credentials/client_secret.json"
    GEMINI_TOKEN_PATH: str = "credentials/token.json"
    ALLOWED_USER_IDS: str = "[]" # JSON formatted list of strings
    
    # OpenAI Settings (for fallback provider)
    OPENAI_API_KEY: Optional[str] = None
    
    # Admin Settings
    ADMIN_CHAT_ID: Optional[int] = None
    
    # Redis / FalkorDB Settings
    FALKORDB_HOST: str = "localhost"
    FALKORDB_PORT: int = 6379
    FALKORDB_GRAPH_AGENT: str = "agent_memory"
    FALKORDB_GRAPH_GROUP: str = "group_chat_memory"
    REDIS_QUEUE_INCOMING: str = "chat:incoming"
    REDIS_QUEUE_OUTGOING: str = "chat:outgoing"
    REDIS_QUEUE_BRAIN: str = "chat:brain"  # Stream 1 -> Stream 2 Queue
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"  # Ignore unknown env vars

# Global settings instance
try:
    settings = Settings()
except Exception as e:
    # Handle case where .env might not exist yet during initial setup
    print(f"Warning: Could not load settings: {e}")
    settings = None
