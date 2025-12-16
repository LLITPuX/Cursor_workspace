"""Configuration settings for the embedding service"""
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings"""
    
    # Neon Database
    neon_connection_string: str
    
    # Ollama Configuration
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "embeddinggemma:latest"
    embedding_dimension: int = 768
    
    # Chunking Defaults
    default_chunk_size: int = 512
    default_chunk_overlap: int = 50
    
    # API Configuration
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_title: str = "Embedding Service"
    api_version: str = "1.0.0"
    
    # Logging
    log_level: str = "INFO"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# Global settings instance
settings = Settings()

