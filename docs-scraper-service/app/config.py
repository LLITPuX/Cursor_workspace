"""Configuration for docs scraper service."""

from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    """Application settings."""
    
    # API Configuration
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8002
    API_TITLE: str = "Docs Scraper Service"
    API_VERSION: str = "1.0.0"
    
    # Storage Configuration
    DOCS_ROOT: Path = Path("/app/docs")
    
    # Scraper Configuration
    DEFAULT_TIMEOUT: int = 30000  # milliseconds
    DEFAULT_WAIT_TIME: int = 1000  # milliseconds between requests
    MAX_CONCURRENT: int = 3  # max concurrent page loads
    
    # Playwright Configuration
    HEADLESS: bool = True
    VIEWPORT_WIDTH: int = 1920
    VIEWPORT_HEIGHT: int = 1080
    
    # Logging
    LOG_LEVEL: str = "INFO"
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
