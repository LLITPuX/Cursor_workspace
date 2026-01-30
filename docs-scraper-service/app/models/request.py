"""Request models for API."""

from pydantic import BaseModel, HttpUrl, Field
from typing import Optional


class ScrapeRequest(BaseModel):
    """Request model for scraping."""
    base_url: HttpUrl = Field(..., description="Base URL to start scraping from")
    project_name: str = Field(..., description="Project name for storage")
    url_filter: Optional[str] = Field(None, description="URL filter pattern (e.g., '/docs')")
    max_depth: int = Field(10, ge=1, le=20, description="Maximum depth to follow links")
    follow_external: bool = Field(False, description="Whether to follow external links")


class ProjectListResponse(BaseModel):
    """Response model for project list."""
    projects: list[str]


class ProjectFilesResponse(BaseModel):
    """Response model for project files."""
    project_name: str
    files: list[str]


class GeminiScrapeRequest(BaseModel):
    """Request model for scraping Gemini sessions."""
    url: str
    filename: Optional[str] = None
