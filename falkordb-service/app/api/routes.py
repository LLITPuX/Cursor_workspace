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
from app.classification import (
    get_sentiment_classifier,
    get_intent_classifier,
    get_complexity_classifier,
    get_response_type_classifier,
    get_response_complexity_classifier
)
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


# Classification functions with fallback to defaults
def classify_sentiment(text: str) -> str:
    """
    Classify sentiment of user query using DeBERTa v3
    
    Args:
        text: User query text
        
    Returns:
        Sentiment label with fallback to "neutral"
    """
    try:
        classifier = get_sentiment_classifier()
        return classifier.classify(text)
    except Exception as e:
        logger.warning(f"Sentiment classification failed, using default: {e}")
        return "neutral"


def classify_intents(text: str) -> List[str]:
    """
    Classify intents of user query using DeBERTa v3 (multi-label)
    
    Args:
        text: User query text
        
    Returns:
        List of intent labels with fallback to ["information_seeking"]
    """
    try:
        classifier = get_intent_classifier()
        return classifier.classify(text)
    except Exception as e:
        logger.warning(f"Intent classification failed, using default: {e}")
        return ["information_seeking"]


def classify_complexity(text: str) -> str:
    """
    Classify complexity of user query using DeBERTa v3
    
    Args:
        text: User query text
        
    Returns:
        Complexity label with fallback to "simple_question"
    """
    try:
        classifier = get_complexity_classifier()
        return classifier.classify(text)
    except Exception as e:
        logger.warning(f"Complexity classification failed, using default: {e}")
        return "simple_question"


def mock_extract_entities(text: str) -> List[EntityModel]:
    """Mock entity extraction (will be replaced with GLINER v2.1 in Stage 4)"""
    # TODO: Replace with GLINER v2.1 in Stage 4
    return []


def classify_response_type(text: str) -> str:
    """
    Classify type of assistant response using DeBERTa v3
    
    Args:
        text: Assistant response text
        
    Returns:
        Response type label with fallback to "explanation"
    """
    try:
        classifier = get_response_type_classifier()
        return classifier.classify(text)
    except Exception as e:
        logger.warning(f"Response type classification failed, using default: {e}")
        return "explanation"


def classify_response_complexity(text: str) -> str:
    """
    Classify complexity of assistant response using DeBERTa v3
    
    Args:
        text: Assistant response text
        
    Returns:
        Complexity label with fallback to "simple"
    """
    try:
        classifier = get_response_complexity_classifier()
        return classifier.classify(text)
    except Exception as e:
        logger.warning(f"Response complexity classification failed, using default: {e}")
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
        
        # Classify using DeBERTa v3
        sentiment = classify_sentiment(request.query)
        intents = classify_intents(request.query)
        complexity = classify_complexity(request.query)
        
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
        
        # Classify using DeBERTa v3
        response_type = classify_response_type(request.response)
        complexity = classify_response_complexity(request.response)
        
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
