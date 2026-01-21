"""Embedding generation service using Ollama"""
import httpx
import asyncio
from typing import List, Optional
from app.config import settings
import logging

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Service for generating embeddings via Ollama API"""
    
    def __init__(self, base_url: Optional[str] = None, model: Optional[str] = None):
        """
        Initialize embedding service
        
        Args:
            base_url: Ollama API base URL (defaults to settings)
            model: Model name (defaults to settings)
        """
        self.base_url = base_url or settings.ollama_base_url
        self.model = model or settings.ollama_model
        self.dimension = settings.embedding_dimension
    
    async def generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for a single text
        
        Args:
            text: Text to embed
            
        Returns:
            List of floats representing the embedding vector
        """
        if not text.strip():
            raise ValueError("Text cannot be empty")
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.base_url}/api/embeddings",
                    json={
                        "model": self.model,
                        "prompt": text
                    }
                )
                response.raise_for_status()
                data = response.json()
                
                embedding = data.get("embedding", [])
                
                if not embedding:
                    raise ValueError(f"No embedding returned from Ollama API")
                
                if len(embedding) != self.dimension:
                    error_msg = (
                        f"Embedding dimension mismatch: expected {self.dimension}, "
                        f"got {len(embedding)}. Model may be misconfigured."
                    )
                    logger.error(error_msg)
                    raise ValueError(error_msg)
                
                return embedding
                
        except httpx.HTTPError as e:
            logger.error(f"HTTP error generating embedding: {e}")
            raise
        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            raise
    
    async def generate_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for multiple texts using parallel processing
        
        Args:
            texts: List of texts to embed
            
        Returns:
            List of embedding vectors in the same order as input texts
        """
        if not texts:
            return []
        
        # Use asyncio.gather for parallel processing
        # Ollama API doesn't support batch processing, but we can make parallel requests
        try:
            embeddings = await asyncio.gather(*[
                self.generate_embedding(text) for text in texts
            ])
            return embeddings
        except Exception as e:
            logger.error(f"Error in batch embedding generation: {e}")
            raise
    
    async def health_check(self) -> bool:
        """
        Check if Ollama service is available and model is loaded
        
        Returns:
            True if service is available and model is loaded, False otherwise
        """
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                # Check if Ollama is available
                response = await client.get(f"{self.base_url}/api/tags")
                if response.status_code != 200:
                    return False
                
                # Check if model is loaded
                data = response.json()
                models = data.get("models", [])
                model_names = [model.get("name", "") for model in models]
                
                if self.model not in model_names:
                    logger.warning(
                        f"Model {self.model} not found in Ollama. "
                        f"Available models: {model_names}"
                    )
                    return False
                
                # Test embedding generation with a small text
                try:
                    test_embedding = await self.generate_embedding("test")
                    if not test_embedding or len(test_embedding) != self.dimension:
                        logger.warning("Health check: test embedding generation failed")
                        return False
                except Exception as e:
                    logger.warning(f"Health check: test embedding failed: {e}")
                    return False
                
                return True
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False
