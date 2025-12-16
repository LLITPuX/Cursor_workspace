"""Base classes for chunking strategies"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any
from pydantic import BaseModel


class Chunk(BaseModel):
    """Represents a text chunk"""
    text: str
    start_index: int
    end_index: int
    metadata: Dict[str, Any] = {}


class ChunkingStrategy(ABC):
    """Base class for chunking strategies"""
    
    @abstractmethod
    def chunk(self, text: str, **kwargs) -> List[Chunk]:
        """
        Split text into chunks
        
        Args:
            text: Text to chunk
            **kwargs: Additional strategy-specific parameters
            
        Returns:
            List of Chunk objects
        """
        pass
    
    def __call__(self, text: str, **kwargs) -> List[Chunk]:
        """Make strategy callable"""
        return self.chunk(text, **kwargs)

