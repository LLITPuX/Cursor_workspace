"""Response models for QPE Service"""
from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any


class EntityModel(BaseModel):
    """Entity extracted from text"""
    text: str = Field(..., description="Entity text")
    type: str = Field(..., description="Entity type")
    start: int = Field(..., description="Start position in text")
    end: int = Field(..., description="End position in text")


class ProcessQueryResponse(BaseModel):
    """Response model for processed query"""
    query: str = Field(..., description="Original query")
    classifications: Dict[str, Any] = Field(
        ...,
        description="Classification results",
        example={
            "sentiment": "neutral",
            "intents": ["information_seeking"],
            "complexity": "simple_question"
        }
    )
    entities: List[EntityModel] = Field(
        default_factory=list,
        description="Extracted entities"
    )
    embedding: List[float] = Field(..., description="Query embedding vector")


class ProcessAssistantResponseResponse(BaseModel):
    """Response model for processed assistant response"""
    response: str = Field(..., description="Original response")
    structure: Dict[str, str] = Field(
        ...,
        description="Structured parts of the response"
    )
    response_type: str = Field(
        ...,
        description="Response type: explanation|code_proposal|analysis|question"
    )
    complexity: str = Field(
        ...,
        description="Response complexity: simple|detailed|architectural"
    )
    analysis_entities: List[EntityModel] = Field(
        default_factory=list,
        description="Entities extracted from analysis part"
    )
    response_entities: List[EntityModel] = Field(
        default_factory=list,
        description="Entities extracted from response part"
    )
    embeddings: Dict[str, List[float]] = Field(
        ...,
        description="Embeddings for each part",
        example={
            "analysis": [0.123, ...],
            "response": [0.456, ...],
            "questions": [0.789, ...]  # optional
        }
    )


class HealthResponse(BaseModel):
    """Health check response"""
    status: str = Field(..., description="Service status")
    ollama_available: bool = Field(..., description="Ollama service availability")
    falkordb_available: bool = Field(..., description="FalkorDB availability")
    model: str = Field(..., description="Embedding model name")
    dimension: int = Field(..., description="Embedding dimension")
