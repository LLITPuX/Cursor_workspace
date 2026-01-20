"""Embedding generation service using Ollama"""
import httpx
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
                    logger.warning(
                        f"Embedding dimension mismatch: expected {self.dimension}, "
                        f"got {len(embedding)}"
                    )
                
                return embedding
                
        except httpx.HTTPError as e:
            logger.error(f"HTTP error generating embedding: {e}")
            raise
        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            raise
    
    async def generate_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for multiple texts
        
        Args:
            texts: List of texts to embed
            
        Returns:
            List of embedding vectors
        """
        if not texts:
            return []
        
        # Ollama API doesn't support batch processing, so we process sequentially
        # This could be optimized with asyncio.gather for parallel requests
        embeddings = []
        async with httpx.AsyncClient(timeout=60.0) as client:
            for text in texts:
                try:
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
                        raise ValueError(f"No embedding returned for text: {text[:50]}...")
                    
                    if len(embedding) != self.dimension:
                        logger.warning(
                            f"Embedding dimension mismatch: expected {self.dimension}, "
                            f"got {len(embedding)}"
                        )
                    
                    embeddings.append(embedding)
                    
                except httpx.HTTPError as e:
                    logger.error(f"HTTP error generating embedding for text: {e}")
                    raise
                except Exception as e:
                    logger.error(f"Error generating embedding: {e}")
                    raise
        
        return embeddings
    
    async def health_check(self) -> bool:
        """
        Check if Ollama service is available
        
        Returns:
            True if service is available, False otherwise
        """
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                return response.status_code == 200
        except Exception:
            return False
