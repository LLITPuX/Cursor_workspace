from pydantic_settings import BaseSettings
from typing import List
import os

class Settings(BaseSettings):
    TELEGRAM_BOT_TOKEN: str
    GEMINI_CLIENT_SECRET_PATH: str = "credentials/client_secret.json"
    GEMINI_TOKEN_PATH: str = "credentials/token.json"
    ALLOWED_USER_IDS: List[int]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

# Global settings instance
try:
    settings = Settings()
except Exception as e:
    # Handle case where .env might not exist yet during initial setup
    print(f"Warning: Could not load settings: {e}")
    settings = None
