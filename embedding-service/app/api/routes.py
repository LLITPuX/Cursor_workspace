"""API routes for embedding service"""
from fastapi import APIRouter, HTTPException, Depends, status, Query
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


class EmbeddingGenerationResponse(BaseModel):
    """Response model for embedding generation"""
    session_id: Optional[str] = None
    messages_processed: int
    embeddings_generated: int
    errors: int
    success_rate: float


class EmbeddingStatsResponse(BaseModel):
    """Response model for embedding statistics"""
    total_sessions: int
    sessions_with_embeddings: int
    sessions_without_embeddings: int
    total_messages: int
    messages_with_embeddings: int
    messages_without_embeddings: int


class VectorSearchRequest(BaseModel):
    """Request model for vector search"""
    query_text: str = Field(..., min_length=1, description="Text to search for")
    limit: int = Field(10, ge=1, le=100, description="Maximum number of results")
    similarity_threshold: float = Field(0.0, ge=0.0, le=1.0, description="Minimum similarity score")
    session_id: Optional[str] = Field(None, description="Filter by session ID")
    role: Optional[str] = Field(None, description="Filter by role ('user' or 'assistant')")


class VectorSearchResponse(BaseModel):
    """Response model for vector search"""
    results: List[Dict[str, Any]]
    query_text: str
    limit: int
    total_results: int


class EntityNodeSearchRequest(BaseModel):
    """Request model for entity node search"""
    query_text: str = Field(..., min_length=1, description="Text to search for")
    types: Optional[List[str]] = Field(None, description="Filter by entity types")
    limit: int = Field(10, ge=1, le=100, description="Maximum number of results")
    similarity_threshold: float = Field(0.0, ge=0.0, le=1.0, description="Minimum similarity score")
    active_only: bool = Field(True, description="Only return active nodes")


class CriticalRulesResponse(BaseModel):
    """Response model for critical rules"""
    rules: List[Dict[str, Any]]
    total_count: int


class EntityChildrenRequest(BaseModel):
    """Request model for getting entity children"""
    entity_id: str = Field(..., description="Parent entity ID")
    relation_type: str = Field("contains", description="Type of relation")
    child_type: Optional[str] = Field(None, description="Filter by child type")


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
        
        # Get active embedding model
        active_model = await db.get_active_embedding_model()
        embedding_model_id = active_model['id'] if active_model else None
        
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
            
            # Use save_message_with_model if model_id is available
            if embedding_model_id:
                await db.save_message_with_model(
                    session_id=session_id,
                    role=msg.role,
                    content=msg.content,
                    embedding=embedding,
                    embedding_model_id=embedding_model_id
                )
            else:
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


@router.post("/sessions/{session_id}/generate-embeddings", response_model=EmbeddingGenerationResponse)
async def generate_embeddings_for_session(
    session_id: str,
    embedding_service: EmbeddingService = Depends(get_embedding_service)
):
    """
    Generate embeddings for all messages in a specific session that don't have embeddings
    
    Args:
        session_id: Session ID to process
        embedding_service: Embedding service instance
        
    Returns:
        Embedding generation response with statistics
    """
    if not db.pool:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection not available. Please set NEON_CONNECTION_STRING."
        )
    
    # Check if session exists
    if not await db.session_exists(session_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found"
        )
    
    try:
        # Get messages without embeddings for this session
        messages = await db.get_messages_without_embeddings(session_id=session_id)
        
        if not messages:
            return EmbeddingGenerationResponse(
                session_id=session_id,
                messages_processed=0,
                embeddings_generated=0,
                errors=0,
                success_rate=100.0
            )
        
        # Get active embedding model
        active_model = await db.get_active_embedding_model()
        embedding_model_id = active_model['id'] if active_model else None
        
        # Process messages
        embeddings_generated = 0
        errors = 0
        
        for msg in messages:
            try:
                embedding = await embedding_service.generate_embedding(msg['content'])
                updated = await db.update_message_embedding(msg['id'], embedding)
                
                # Update embedding_model_id if available
                if updated and embedding_model_id:
                    try:
                        await db.execute(
                            """
                            UPDATE messages
                            SET embedding_model_id = $1
                            WHERE id = $2 AND embedding_model_id IS NULL
                            """,
                            embedding_model_id,
                            msg['id']
                        )
                    except Exception as e:
                        logger.warning(f"Failed to update embedding_model_id for message {msg['id']}: {e}")
                
                if updated:
                    embeddings_generated += 1
                else:
                    errors += 1
                    logger.warning(f"Failed to update embedding for message {msg['id']}")
                    
            except Exception as e:
                errors += 1
                logger.error(f"Error generating embedding for message {msg['id']}: {e}")
        
        success_rate = (embeddings_generated / len(messages) * 100) if messages else 0.0
        
        return EmbeddingGenerationResponse(
            session_id=session_id,
            messages_processed=len(messages),
            embeddings_generated=embeddings_generated,
            errors=errors,
            success_rate=round(success_rate, 2)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating embeddings for session {session_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate embeddings: {str(e)}"
        )


@router.post("/sessions/generate-embeddings/all", response_model=EmbeddingGenerationResponse)
async def generate_embeddings_for_all_sessions(
    limit: Optional[int] = Query(None, description="Limit number of messages to process"),
    embedding_service: EmbeddingService = Depends(get_embedding_service)
):
    """
    Generate embeddings for all messages without embeddings across all sessions
    
    Args:
        limit: Optional limit on number of messages to process
        embedding_service: Embedding service instance
        
    Returns:
        Embedding generation response with statistics
    """
    if not db.pool:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection not available. Please set NEON_CONNECTION_STRING."
        )
    
    try:
        # Get all messages without embeddings
        messages = await db.get_messages_without_embeddings(limit=limit)
        
        if not messages:
            return EmbeddingGenerationResponse(
                messages_processed=0,
                embeddings_generated=0,
                errors=0,
                success_rate=100.0
            )
        
        # Get active embedding model
        active_model = await db.get_active_embedding_model()
        embedding_model_id = active_model['id'] if active_model else None
        
        # Process messages
        embeddings_generated = 0
        errors = 0
        
        for msg in messages:
            try:
                embedding = await embedding_service.generate_embedding(msg['content'])
                updated = await db.update_message_embedding(msg['id'], embedding)
                
                # Update embedding_model_id if available
                if updated and embedding_model_id:
                    try:
                        await db.execute(
                            """
                            UPDATE messages
                            SET embedding_model_id = $1
                            WHERE id = $2 AND embedding_model_id IS NULL
                            """,
                            embedding_model_id,
                            msg['id']
                        )
                    except Exception as e:
                        logger.warning(f"Failed to update embedding_model_id for message {msg['id']}: {e}")
                
                if updated:
                    embeddings_generated += 1
                else:
                    errors += 1
                    logger.warning(f"Failed to update embedding for message {msg['id']}")
                    
            except Exception as e:
                errors += 1
                logger.error(f"Error generating embedding for message {msg['id']}: {e}")
        
        success_rate = (embeddings_generated / len(messages) * 100) if messages else 0.0
        
        return EmbeddingGenerationResponse(
            messages_processed=len(messages),
            embeddings_generated=embeddings_generated,
            errors=errors,
            success_rate=round(success_rate, 2)
        )
        
    except Exception as e:
        logger.error(f"Error generating embeddings for all sessions: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate embeddings: {str(e)}"
        )


@router.post("/rag/search-messages", response_model=VectorSearchResponse)
async def vector_search_messages(
    request: VectorSearchRequest,
    embedding_service: EmbeddingService = Depends(get_embedding_service)
):
    """
    Perform vector similarity search on messages (RAG)
    
    Args:
        request: Vector search request
        embedding_service: Embedding service instance
        
    Returns:
        Search results with similarity scores
    """
    if not db.pool:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection not available. Please set NEON_CONNECTION_STRING."
        )
    
    try:
        # Generate embedding for query text
        query_embedding = await embedding_service.generate_embedding(request.query_text)
        
        # Perform vector search
        results = await db.vector_search_messages(
            query_embedding=query_embedding,
            limit=request.limit,
            session_id=request.session_id,
            role=request.role,
            similarity_threshold=request.similarity_threshold
        )
        
        return VectorSearchResponse(
            results=results,
            query_text=request.query_text,
            limit=request.limit,
            total_results=len(results)
        )
        
    except Exception as e:
        logger.error(f"Error performing vector search: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to perform vector search: {str(e)}"
        )


@router.post("/rag/search-entities", response_model=VectorSearchResponse)
async def vector_search_entities(
    request: EntityNodeSearchRequest,
    embedding_service: EmbeddingService = Depends(get_embedding_service)
):
    """
    Perform vector similarity search on entity nodes (RAG)
    
    Args:
        request: Entity search request
        embedding_service: Embedding service instance
        
    Returns:
        Search results with similarity scores
    """
    if not db.pool:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection not available. Please set NEON_CONNECTION_STRING."
        )
    
    try:
        # Generate embedding for query text
        query_embedding = await embedding_service.generate_embedding(request.query_text)
        
        # Perform vector search
        results = await db.vector_search_entity_nodes(
            query_embedding=query_embedding,
            types=request.types,
            limit=request.limit,
            similarity_threshold=request.similarity_threshold,
            active_only=request.active_only
        )
        
        return VectorSearchResponse(
            results=results,
            query_text=request.query_text,
            limit=request.limit,
            total_results=len(results)
        )
        
    except Exception as e:
        logger.error(f"Error performing entity search: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to perform entity search: {str(e)}"
        )


@router.get("/rules/critical", response_model=CriticalRulesResponse)
async def get_critical_rules():
    """
    Get all critical rules from CriticalRules system node
    
    Returns:
        List of critical rules
    """
    if not db.pool:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection not available. Please set NEON_CONNECTION_STRING."
        )
    
    try:
        rules = await db.get_critical_rules()
        return CriticalRulesResponse(
            rules=rules,
            total_count=len(rules)
        )
    except Exception as e:
        logger.error(f"Error loading critical rules: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to load critical rules: {str(e)}"
        )


@router.get("/entities/{entity_id}/children")
async def get_entity_children(
    entity_id: str,
    relation_type: str = Query("contains", description="Type of relation"),
    child_type: Optional[str] = Query(None, description="Filter by child type")
):
    """
    Get child entities linked to a parent entity
    
    Args:
        entity_id: Parent entity UUID
        relation_type: Type of relation (default: 'contains')
        child_type: Optional filter by child type
        
    Returns:
        List of child entities
    """
    if not db.pool:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection not available. Please set NEON_CONNECTION_STRING."
        )
    
    try:
        children = await db.get_entity_children(
            entity_id=entity_id,
            relation_type=relation_type,
            child_type=child_type
        )
        return {
            "entity_id": entity_id,
            "relation_type": relation_type,
            "children": children,
            "total_count": len(children)
        }
    except Exception as e:
        logger.error(f"Error loading entity children: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to load entity children: {str(e)}"
        )


@router.post("/messages/{message_id}/link-entity")
async def link_message_to_entity(
    message_id: str,
    entity_id: str = Query(..., description="Entity UUID"),
    relation_type: str = Query(..., description="Relation type: 'uses', 'applies', 'executed_in'")
):
    """
    Create a link between a message and an entity
    
    Args:
        message_id: Message UUID
        entity_id: Entity UUID
        relation_type: Type of relation
        
    Returns:
        Link ID
    """
    if not db.pool:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection not available. Please set NEON_CONNECTION_STRING."
        )
    
    if relation_type not in ['uses', 'applies', 'executed_in']:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="relation_type must be one of: 'uses', 'applies', 'executed_in'"
        )
    
    try:
        link_id = await db.create_message_entity_link(
            message_id=message_id,
            entity_id=entity_id,
            relation_type=relation_type
        )
        return {
            "link_id": link_id,
            "message_id": message_id,
            "entity_id": entity_id,
            "relation_type": relation_type
        }
    except Exception as e:
        logger.error(f"Error creating message-entity link: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create link: {str(e)}"
        )


@router.post("/sessions/{session_id}/link-entity")
async def link_session_to_entity(
    session_id: str,
    entity_id: str = Query(..., description="Entity UUID"),
    relation_type: str = Query(..., description="Relation type: 'executed_in', 'uses'")
):
    """
    Create a link between a session and an entity
    
    Args:
        session_id: Session UUID
        entity_id: Entity UUID
        relation_type: Type of relation
        
    Returns:
        Link ID
    """
    if not db.pool:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection not available. Please set NEON_CONNECTION_STRING."
        )
    
    if relation_type not in ['executed_in', 'uses']:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="relation_type must be one of: 'executed_in', 'uses'"
        )
    
    try:
        link_id = await db.create_session_entity_link(
            session_id=session_id,
            entity_id=entity_id,
            relation_type=relation_type
        )
        return {
            "link_id": link_id,
            "session_id": session_id,
            "entity_id": entity_id,
            "relation_type": relation_type
        }
    except Exception as e:
        logger.error(f"Error creating session-entity link: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create link: {str(e)}"
        )


@router.get("/sessions/stats", response_model=EmbeddingStatsResponse)
async def get_embedding_stats():
    """
    Get statistics about sessions and embeddings
    
    Returns:
        Statistics about sessions and messages with/without embeddings
    """
    if not db.pool:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection not available. Please set NEON_CONNECTION_STRING."
        )
    
    try:
        # Get total sessions
        total_sessions_row = await db.fetchrow("SELECT COUNT(*) as count FROM sessions")
        total_sessions = total_sessions_row['count'] if total_sessions_row else 0
        
        # Get sessions with embeddings
        sessions_with_embeddings_row = await db.fetchrow("""
            SELECT COUNT(DISTINCT session_id) as count
            FROM messages
            WHERE embedding_v2 IS NOT NULL
        """)
        sessions_with_embeddings = sessions_with_embeddings_row['count'] if sessions_with_embeddings_row else 0
        
        # Get total messages
        total_messages_row = await db.fetchrow("SELECT COUNT(*) as count FROM messages")
        total_messages = total_messages_row['count'] if total_messages_row else 0
        
        # Get messages with embeddings
        messages_with_embeddings_row = await db.fetchrow("""
            SELECT COUNT(*) as count
            FROM messages
            WHERE embedding_v2 IS NOT NULL
        """)
        messages_with_embeddings = messages_with_embeddings_row['count'] if messages_with_embeddings_row else 0
        
        return EmbeddingStatsResponse(
            total_sessions=total_sessions,
            sessions_with_embeddings=sessions_with_embeddings,
            sessions_without_embeddings=total_sessions - sessions_with_embeddings,
            total_messages=total_messages,
            messages_with_embeddings=messages_with_embeddings,
            messages_without_embeddings=total_messages - messages_with_embeddings
        )
        
    except Exception as e:
        logger.error(f"Error getting embedding stats: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get statistics: {str(e)}"
        )

