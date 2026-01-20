"""Request models for QPE Service"""
from pydantic import BaseModel, Field
from typing import Optional, Dict


class ProcessQueryRequest(BaseModel):
    """Request model for processing user query"""
    query: str = Field(..., min_length=1, description="User query text")


class ProcessAssistantResponseRequest(BaseModel):
    """Request model for processing assistant response"""
    response: str = Field(..., min_length=1, description="Assistant response text")
    structure: Dict[str, str] = Field(
        ...,
        description="Structured parts of the response",
        example={
            "analysis": "Analysis and actions taken",
            "response": "Main response text",
            "questions": "Optional questions for clarification"
        }
    )
