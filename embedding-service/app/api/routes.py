"""API routes for embedding service"""
from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from app.embedding import EmbeddingService
from app.config import settings
from app.database import db
from chunking.base import Chunk
from chunking.strategies import SimpleChunking, RecursiveChunking, SemanticChunking
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["embeddings"])


# Request/Response models
class EmbeddingRequest(BaseModel):
    """Request model for single embedding"""
    text: str = Field(..., min_length=1, description="Text to generate embedding for")
    model: Optional[str] = Field(None, description="Override default model")


class EmbeddingResponse(BaseModel):
    """Response model for single embedding"""
    embedding: List[float]
    dimension: int
    model: str
    text_length: int


class ChunkedEmbeddingRequest(BaseModel):
    """Request model for chunked embedding"""
    text: str = Field(..., min_length=1, description="Text to chunk and embed")
    strategy: str = Field("simple", description="Chunking strategy: simple, recursive, semantic")
    chunk_size: Optional[int] = Field(None, ge=1, description="Override default chunk size")
    chunk_overlap: Optional[int] = Field(None, ge=0, description="Override default chunk overlap")
    model: Optional[str] = Field(None, description="Override default model")


class ChunkedEmbeddingResponse(BaseModel):
    """Response model for chunked embedding"""
    chunks: List[Dict[str, Any]]
    model: str
    dimension: int
    strategy: str
    total_chunks: int


class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    ollama_available: bool
    model: str
    dimension: int


# Dependency injection
def get_embedding_service() -> EmbeddingService:
    """Get embedding service instance"""
    return EmbeddingService()


def get_chunking_strategy(strategy_name: str, chunk_size: int, chunk_overlap: int):
    """Get chunking strategy instance"""
    strategies = {
        "simple": SimpleChunking,
        "recursive": RecursiveChunking,
        "semantic": SemanticChunking,
    }
    
    strategy_class = strategies.get(strategy_name.lower())
    if not strategy_class:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown chunking strategy: {strategy_name}. "
                   f"Available: {', '.join(strategies.keys())}"
        )
    
    return strategy_class(chunk_size=chunk_size, overlap=chunk_overlap)


# Routes
@router.get("/health", response_model=HealthResponse)
async def health_check(
    embedding_service: EmbeddingService = Depends(get_embedding_service)
):
    """Health check endpoint"""
    ollama_available = await embedding_service.health_check()
    
    return HealthResponse(
        status="healthy" if ollama_available else "degraded",
        ollama_available=ollama_available,
        model=embedding_service.model,
        dimension=embedding_service.dimension
    )


@router.post("/embed", response_model=EmbeddingResponse)
async def create_embedding(
    request: EmbeddingRequest,
    embedding_service: EmbeddingService = Depends(get_embedding_service)
):
    """
    Generate embedding for a single text
    
    Args:
        request: Embedding request with text
        embedding_service: Embedding service instance
        
    Returns:
        Embedding response with vector and metadata
    """
    try:
        # Override model if specified
        service = embedding_service
        if request.model:
            service = EmbeddingService(model=request.model)
        
        embedding = await service.generate_embedding(request.text)
        
        return EmbeddingResponse(
            embedding=embedding,
            dimension=len(embedding),
            model=service.model,
            text_length=len(request.text)
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error generating embedding: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate embedding"
        )


@router.post("/embed-chunked", response_model=ChunkedEmbeddingResponse)
async def create_chunked_embedding(
    request: ChunkedEmbeddingRequest,
    embedding_service: EmbeddingService = Depends(get_embedding_service)
):
    """
    Generate embeddings for chunked text
    
    Args:
        request: Chunked embedding request
        embedding_service: Embedding service instance
        
    Returns:
        Chunked embedding response with chunks and their embeddings
    """
    try:
        # Get chunking strategy
        chunk_size = request.chunk_size or settings.default_chunk_size
        chunk_overlap = request.chunk_overlap or settings.default_chunk_overlap
        
        strategy = get_chunking_strategy(
            request.strategy,
            chunk_size,
            chunk_overlap
        )
        
        # Chunk the text
        chunks = strategy.chunk(request.text)
        
        if not chunks:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No chunks generated from text"
            )
        
        # Override model if specified
        service = embedding_service
        if request.model:
            service = EmbeddingService(model=request.model)
        
        # Generate embeddings for all chunks
        texts = [chunk.text for chunk in chunks]
        embeddings = await service.generate_embeddings_batch(texts)
        
        if len(embeddings) != len(chunks):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Embedding count mismatch: {len(embeddings)} embeddings "
                       f"for {len(chunks)} chunks"
            )
        
        # Combine chunks with embeddings
        chunk_data = [
            {
                "text": chunk.text,
                "embedding": emb,
                "start_index": chunk.start_index,
                "end_index": chunk.end_index,
                "metadata": {**chunk.metadata, "embedding_dimension": len(emb)}
            }
            for chunk, emb in zip(chunks, embeddings)
        ]
        
        return ChunkedEmbeddingResponse(
            chunks=chunk_data,
            model=service.model,
            dimension=service.dimension,
            strategy=request.strategy,
            total_chunks=len(chunks)
        )
        
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error generating chunked embeddings: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate chunked embeddings"
        )


@router.get("/strategies")
async def list_chunking_strategies():
    """List available chunking strategies"""
    return {
        "strategies": [
            {
                "name": "simple",
                "description": "Simple character-based chunking with overlap",
                "parameters": ["chunk_size", "chunk_overlap"]
            },
            {
                "name": "recursive",
                "description": "Recursive chunking on natural boundaries (paragraphs, sentences, words)",
                "parameters": ["chunk_size", "chunk_overlap"]
            },
            {
                "name": "semantic",
                "description": "Semantic chunking (placeholder - uses recursive as fallback)",
                "parameters": ["chunk_size", "chunk_overlap"]
            }
        ]
    }


class MessageInput(BaseModel):
    """Message input for session"""
    role: str = Field(..., description="Message role: 'user' or 'assistant'")
    content: str = Field(..., min_length=1, description="Message content")


class SessionRequest(BaseModel):
    """Request model for saving session"""
    topic: Optional[str] = Field(None, description="Session topic")
    messages: List[MessageInput] = Field(..., min_length=1, description="List of messages")
    generate_embeddings: bool = Field(True, description="Generate embeddings for messages")


class SessionResponse(BaseModel):
    """Response model for saved session"""
    session_id: str
    topic: Optional[str]
    messages_saved: int
    embeddings_generated: int


@router.post("/sessions", response_model=SessionResponse)
async def save_session(
    request: SessionRequest,
    embedding_service: EmbeddingService = Depends(get_embedding_service)
):
    """
    Save a session with messages and optional embeddings
    
    Args:
        request: Session request with topic and messages
        embedding_service: Embedding service instance
        
    Returns:
        Session response with session ID and statistics
    """
    if not db.pool:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection not available. Please set NEON_CONNECTION_STRING."
        )
    
    try:
        # Create session
        session_id = await db.create_session(
            topic=request.topic,
            metadata={"source": "embedding-service-api"}
        )
        
        embeddings_generated = 0
        messages_saved = 0
        
        # Save messages with embeddings
        for msg in request.messages:
            embedding = None
            
            if request.generate_embeddings:
                try:
                    embedding = await embedding_service.generate_embedding(msg.content)
                    embeddings_generated += 1
                except Exception as e:
                    logger.warning(f"Failed to generate embedding for message: {e}")
                    # Continue without embedding
            
            await db.save_message(
                session_id=session_id,
                role=msg.role,
                content=msg.content,
                embedding=embedding
            )
            messages_saved += 1
        
        return SessionResponse(
            session_id=session_id,
            topic=request.topic,
            messages_saved=messages_saved,
            embeddings_generated=embeddings_generated
        )
        
    except Exception as e:
        logger.error(f"Error saving session: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save session: {str(e)}"
        )

