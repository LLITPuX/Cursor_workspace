"""API routes for QPE Service"""
from fastapi import APIRouter, HTTPException, Depends, status
from typing import List
from app.models.request import ProcessQueryRequest, ProcessAssistantResponseRequest
from app.models.response import (
    ProcessQueryResponse,
    ProcessAssistantResponseResponse,
    HealthResponse,
    EntityModel
)
from app.embedding import EmbeddingService
from app.config import settings
from falkordb import FalkorDB
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/qpe", tags=["qpe"])


# Dependency injection
def get_embedding_service() -> EmbeddingService:
    """Get embedding service instance"""
    return EmbeddingService()


def get_falkordb_client():
    """Get FalkorDB client instance"""
    try:
        client = FalkorDB(
            host=settings.falkordb_host,
            port=settings.falkordb_port,
            password=settings.falkordb_password
        )
        return client
    except Exception as e:
        logger.error(f"Failed to connect to FalkorDB: {e}")
        return None


# Mock classification functions (will be replaced in later stages)
def mock_classify_sentiment(text: str) -> str:
    """Mock sentiment classification"""
    # TODO: Replace with DeBERTa v3 in Stage 3
    return "neutral"


def mock_classify_intents(text: str) -> List[str]:
    """Mock intent classification"""
    # TODO: Replace with DeBERTa v3 in Stage 3
    return ["information_seeking"]


def mock_classify_complexity(text: str) -> str:
    """Mock complexity classification"""
    # TODO: Replace with DeBERTa v3 in Stage 3
    return "simple_question"


def mock_extract_entities(text: str) -> List[EntityModel]:
    """Mock entity extraction"""
    # TODO: Replace with GLINER v2.1 in Stage 4
    return []


def mock_classify_response_type(text: str) -> str:
    """Mock response type classification"""
    # TODO: Replace with DeBERTa v3 in Stage 3
    return "explanation"


def mock_classify_response_complexity(text: str) -> str:
    """Mock response complexity classification"""
    # TODO: Replace with DeBERTa v3 in Stage 3
    return "simple"


# Routes
@router.get("/health", response_model=HealthResponse)
async def health_check(
    embedding_service: EmbeddingService = Depends(get_embedding_service)
):
    """Health check endpoint"""
    ollama_available = await embedding_service.health_check()
    
    # Check FalkorDB connection
    falkordb_available = False
    try:
        client = get_falkordb_client()
        if client:
            graph = client.select_graph(settings.falkordb_graph_name)
            falkordb_available = True
    except Exception as e:
        logger.warning(f"FalkorDB health check failed: {e}")
    
    return HealthResponse(
        status="healthy" if (ollama_available and falkordb_available) else "degraded",
        ollama_available=ollama_available,
        falkordb_available=falkordb_available,
        model=embedding_service.model,
        dimension=embedding_service.dimension
    )


@router.post("/process-query", response_model=ProcessQueryResponse)
async def process_query(
    request: ProcessQueryRequest,
    embedding_service: EmbeddingService = Depends(get_embedding_service)
):
    """
    Process user query:
    - Classify sentiment, intents, complexity
    - Extract entities
    - Generate embedding
    
    Args:
        request: Query request with text
        embedding_service: Embedding service instance
        
    Returns:
        Processed query response with classifications, entities, and embedding
    """
    try:
        # Generate embedding
        embedding = await embedding_service.generate_embedding(request.query)
        
        # Mock classifications (will be replaced in Stage 3)
        sentiment = mock_classify_sentiment(request.query)
        intents = mock_classify_intents(request.query)
        complexity = mock_classify_complexity(request.query)
        
        # Mock entity extraction (will be replaced in Stage 4)
        entities = mock_extract_entities(request.query)
        
        return ProcessQueryResponse(
            query=request.query,
            classifications={
                "sentiment": sentiment,
                "intents": intents,
                "complexity": complexity
            },
            entities=entities,
            embedding=embedding
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error processing query: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process query"
        )


@router.post("/process-assistant-response", response_model=ProcessAssistantResponseResponse)
async def process_assistant_response(
    request: ProcessAssistantResponseRequest,
    embedding_service: EmbeddingService = Depends(get_embedding_service)
):
    """
    Process assistant response:
    - Classify response type and complexity
    - Extract entities from analysis and response parts
    - Generate embeddings for each part
    
    Args:
        request: Assistant response request with text and structure
        embedding_service: Embedding service instance
        
    Returns:
        Processed response with classifications, entities, and embeddings
    """
    try:
        # Generate embeddings for each part
        analysis_text = request.structure.get("analysis", "")
        response_text = request.structure.get("response", "")
        questions_text = request.structure.get("questions", "")
        
        embeddings = {}
        
        if analysis_text:
            embeddings["analysis"] = await embedding_service.generate_embedding(analysis_text)
        if response_text:
            embeddings["response"] = await embedding_service.generate_embedding(response_text)
        if questions_text:
            embeddings["questions"] = await embedding_service.generate_embedding(questions_text)
        
        # Mock classifications (will be replaced in Stage 3)
        response_type = mock_classify_response_type(request.response)
        complexity = mock_classify_response_complexity(request.response)
        
        # Mock entity extraction (will be replaced in Stage 4)
        analysis_entities = mock_extract_entities(analysis_text) if analysis_text else []
        response_entities = mock_extract_entities(response_text) if response_text else []
        
        return ProcessAssistantResponseResponse(
            response=request.response,
            structure=request.structure,
            response_type=response_type,
            complexity=complexity,
            analysis_entities=analysis_entities,
            response_entities=response_entities,
            embeddings=embeddings
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error processing assistant response: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process assistant response"
        )
