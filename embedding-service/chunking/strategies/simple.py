"""Simple character-based chunking strategy"""
from chunking.base import ChunkingStrategy, Chunk
from typing import List


class SimpleChunking(ChunkingStrategy):
    """
    Simple chunking strategy that splits text by character count
    with optional overlap between chunks
    """
    
    def __init__(self, chunk_size: int = 512, overlap: int = 50):
        """
        Initialize simple chunking
        
        Args:
            chunk_size: Maximum characters per chunk
            overlap: Number of characters to overlap between chunks
        """
        if chunk_size <= 0:
            raise ValueError("chunk_size must be positive")
        if overlap < 0:
            raise ValueError("overlap must be non-negative")
        if overlap >= chunk_size:
            raise ValueError("overlap must be less than chunk_size")
        
        self.chunk_size = chunk_size
        self.overlap = overlap
    
    def chunk(self, text: str, **kwargs) -> List[Chunk]:
        """
        Split text into chunks
        
        Args:
            text: Text to chunk
            **kwargs: Override chunk_size and overlap if needed
            
        Returns:
            List of Chunk objects
        """
        chunk_size = kwargs.get('chunk_size', self.chunk_size)
        overlap = kwargs.get('overlap', self.overlap)
        
        if not text:
            return []
        
        chunks = []
        start = 0
        chunk_index = 0
        
        while start < len(text):
            end = min(start + chunk_size, len(text))
            chunk_text = text[start:end]
            
            chunks.append(Chunk(
                text=chunk_text,
                start_index=start,
                end_index=end,
                metadata={
                    "chunk_index": chunk_index,
                    "chunk_size": len(chunk_text),
                    "strategy": "simple"
                }
            ))
            
            chunk_index += 1
            
            # Move start position, accounting for overlap
            if end >= len(text):
                break
            start = end - overlap
        
        return chunks

