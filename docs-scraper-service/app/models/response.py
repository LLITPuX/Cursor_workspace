"""Response models for API."""

from pydantic import BaseModel
from typing import Optional


class ScrapeResponse(BaseModel):
    """Response model for scraping operation."""
    success: bool
    project_name: str
    pages_scraped: int
    pages_failed: int
    message: str
    failed_urls: Optional[list[str]] = None
