"""Configuration settings for QPE Service"""
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings"""
    
    # FalkorDB Configuration
    falkordb_host: str = "falkordb"
    falkordb_port: int = 6379
    falkordb_password: Optional[str] = None
    falkordb_graph_name: str = "agent_memory"
    
    # Ollama Configuration
    ollama_base_url: str = "http://ollama:11434"
    ollama_model: str = "embeddinggemma:latest"
    embedding_dimension: int = 768
    
    # API Configuration
    api_host: str = "0.0.0.0"
    api_port: int = 8001
    api_title: str = "QPE Service"
    api_version: str = "1.0.0"
    
    # Logging
    log_level: str = "INFO"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# Global settings instance
settings = Settings()
