"""API routes for docs scraper service."""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from app.models.request import ScrapeRequest, ProjectListResponse, ProjectFilesResponse
from app.models.response import ScrapeResponse
from app.scraper import DocsScraper
from app.storage import Storage
from app.config import settings
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/scraper", tags=["scraper"])

storage = Storage()


async def run_scraper_task(request: ScrapeRequest):
    """Background task for running scraper."""
    try:
        scraper = DocsScraper(
            base_url=str(request.base_url),
            project_name=request.project_name,
            url_filter=request.url_filter,
            max_depth=request.max_depth,
            follow_external=request.follow_external
        )
        
        result = await scraper.scrape()
        
        # Save all pages
        for page in result['pages']:
            await storage.save_document(
                project_name=request.project_name,
                filename=page['filename'],
                content=page['content'],
                metadata={'url': page['url'], 'title': page['title']}
            )
        
        # Save index
        await storage.save_index(request.project_name, result['pages'])
        
        logger.info(f"Scraping completed for {request.project_name}: {result['success']} pages")
        
    except Exception as e:
        logger.error(f"Error in scraper task: {e}", exc_info=True)


@router.post("/scrape", response_model=ScrapeResponse)
async def scrape_docs(
    request: ScrapeRequest,
    background_tasks: BackgroundTasks
):
    """
    Start scraping documentation.
    
    This endpoint starts a background task to scrape documentation.
    """
    try:
        # Add scraping task to background
        background_tasks.add_task(run_scraper_task, request)
        
        return ScrapeResponse(
            success=True,
            project_name=request.project_name,
            pages_scraped=0,
            pages_failed=0,
            message=f"Scraping started for {request.project_name}. Check status later."
        )
    except Exception as e:
        logger.error(f"Error starting scraper: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/projects", response_model=ProjectListResponse)
async def list_projects():
    """List all scraped projects."""
    try:
        projects = storage.list_projects()
        return ProjectListResponse(projects=projects)
    except Exception as e:
        logger.error(f"Error listing projects: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/projects/{project_name}/files", response_model=ProjectFilesResponse)
async def list_project_files(project_name: str):
    """List all files in a project."""
    try:
        files = storage.list_project_files(project_name)
        file_names = [f.name for f in files]
        return ProjectFilesResponse(project_name=project_name, files=file_names)
    except Exception as e:
        logger.error(f"Error listing files for {project_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy", "service": "docs-scraper"}
