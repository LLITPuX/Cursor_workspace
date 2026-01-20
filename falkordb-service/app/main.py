"""Main FastAPI application for QPE Service"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.api.routes import router
import logging

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title=settings.api_title,
    version=settings.api_version,
    description="Query Processing Engine (QPE) Service for agent memory system"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(router)


@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    logger.info("Starting QPE Service...")
    logger.info(f"FalkorDB: {settings.falkordb_host}:{settings.falkordb_port}")
    logger.info(f"Ollama: {settings.ollama_base_url}")
    logger.info(f"Embedding model: {settings.ollama_model}")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("Shutting down QPE Service...")


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "QPE Service",
        "version": settings.api_version,
        "status": "running"
    }
