"""Recursive chunking strategy that tries to split on natural boundaries"""
from chunking.base import ChunkingStrategy, Chunk
from typing import List
import re


class RecursiveChunking(ChunkingStrategy):
    """
    Recursive chunking that attempts to split text on natural boundaries
    (paragraphs, sentences, words) before falling back to character-based splitting
    """
    
    # Priority order: try paragraphs first, then sentences, then words
    SEPARATORS = [
        ("\n\n", "paragraph"),  # Double newline (paragraphs)
        ("\n", "line"),          # Single newline (lines)
        (". ", "sentence"),      # Sentence endings
        ("! ", "sentence"),
        ("? ", "sentence"),
        (" ", "word"),           # Word boundaries
    ]
    
    def __init__(self, chunk_size: int = 512, overlap: int = 50):
        """
        Initialize recursive chunking
        
        Args:
            chunk_size: Target characters per chunk
            overlap: Characters to overlap between chunks
        """
        if chunk_size <= 0:
            raise ValueError("chunk_size must be positive")
        if overlap < 0:
            raise ValueError("overlap must be non-negative")
        
        self.chunk_size = chunk_size
        self.overlap = overlap
    
    def _split_text(self, text: str, separator: str) -> List[str]:
        """Split text by separator"""
        if separator == " ":
            # For word boundaries, use regex to preserve separators
            parts = re.split(r'(\s+)', text)
            # Recombine parts with separators
            result = []
            for i in range(0, len(parts) - 1, 2):
                if i + 1 < len(parts):
                    result.append(parts[i] + parts[i + 1])
                else:
                    result.append(parts[i])
            return [r for r in result if r.strip()]
        else:
            parts = text.split(separator)
            # Add separator back to all but last part
            result = []
            for i, part in enumerate(parts):
                if i < len(parts) - 1:
                    result.append(part + separator)
                else:
                    result.append(part)
            return result
    
    def _recursive_chunk(self, text: str, separators: List[tuple], chunk_index: int = 0) -> List[Chunk]:
        """Recursively chunk text using separators"""
        if not text:
            return []
        
        # If text is small enough, return as single chunk
        if len(text) <= self.chunk_size:
            return [Chunk(
                text=text,
                start_index=0,
                end_index=len(text),
                metadata={
                    "chunk_index": chunk_index,
                    "chunk_size": len(text),
                    "strategy": "recursive",
                    "split_type": "none"
                }
            )]
        
        # Try each separator in priority order
        for separator, split_type in separators:
            if separator in text:
                parts = self._split_text(text, separator)
                
                # Check if we can create chunks
                chunks = []
                current_chunk = ""
                current_start = 0
                local_chunk_index = chunk_index
                
                for part in parts:
                    # If adding this part would exceed chunk size
                    if len(current_chunk) + len(part) > self.chunk_size and current_chunk:
                        # Save current chunk
                        chunks.append(Chunk(
                            text=current_chunk,
                            start_index=current_start,
                            end_index=current_start + len(current_chunk),
                            metadata={
                                "chunk_index": local_chunk_index,
                                "chunk_size": len(current_chunk),
                                "strategy": "recursive",
                                "split_type": split_type
                            }
                        ))
                        
                        # Start new chunk with overlap
                        overlap_text = current_chunk[-self.overlap:] if self.overlap > 0 else ""
                        current_chunk = overlap_text + part
                        current_start = current_start + len(current_chunk) - len(overlap_text) - len(part)
                        local_chunk_index += 1
                    else:
                        current_chunk += part
                
                # Add final chunk
                if current_chunk:
                    chunks.append(Chunk(
                        text=current_chunk,
                        start_index=current_start,
                        end_index=current_start + len(current_chunk),
                        metadata={
                            "chunk_index": local_chunk_index,
                            "chunk_size": len(current_chunk),
                            "strategy": "recursive",
                            "split_type": split_type
                        }
                    ))
                
                return chunks
        
        # Fallback: character-based splitting
        return self._fallback_chunk(text, chunk_index)
    
    def _fallback_chunk(self, text: str, chunk_index: int = 0) -> List[Chunk]:
        """Fallback to simple character-based chunking"""
        chunks = []
        start = 0
        local_index = chunk_index
        
        while start < len(text):
            end = min(start + self.chunk_size, len(text))
            chunk_text = text[start:end]
            
            chunks.append(Chunk(
                text=chunk_text,
                start_index=start,
                end_index=end,
                metadata={
                    "chunk_index": local_index,
                    "chunk_size": len(chunk_text),
                    "strategy": "recursive",
                    "split_type": "character"
                }
            ))
            
            local_index += 1
            if end >= len(text):
                break
            start = end - self.overlap
        
        return chunks
    
    def chunk(self, text: str, **kwargs) -> List[Chunk]:
        """
        Recursively chunk text
        
        Args:
            text: Text to chunk
            **kwargs: Override chunk_size and overlap if needed
            
        Returns:
            List of Chunk objects
        """
        chunk_size = kwargs.get('chunk_size', self.chunk_size)
        overlap = kwargs.get('overlap', self.overlap)
        
        # Temporarily override for this call
        original_size = self.chunk_size
        original_overlap = self.overlap
        
        self.chunk_size = chunk_size
        self.overlap = overlap
        
        try:
            result = self._recursive_chunk(text, self.SEPARATORS)
        finally:
            # Restore original values
            self.chunk_size = original_size
            self.overlap = original_overlap
        
        return result


