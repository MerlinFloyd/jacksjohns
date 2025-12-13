"""FastAPI application entry point."""

import logging
import sys

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config.settings import get_settings
from .api.routes import health_router, persona_router, image_router, video_router, chat_router, settings_router
from .api.dependencies import initialize_services

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# Create FastAPI application
app = FastAPI(
    title="Agent Service",
    description="AI Agent Service for Discord Bot - Provides persona management, image generation, and chat with memory",
    version="0.2.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS middleware (allow all for development)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health_router)
app.include_router(persona_router)
app.include_router(image_router)
app.include_router(video_router)
app.include_router(chat_router)
app.include_router(settings_router)


@app.on_event("startup")
async def startup_event() -> None:
    """Application startup event."""
    settings = get_settings()
    logger.info("=" * 50)
    logger.info("Agent Service Starting")
    logger.info(f"Project: {settings.gcp_project_id}")
    logger.info(f"Region: {settings.gcp_region}")
    logger.info(f"Gemini Model: {settings.gemini_model}")
    logger.info(f"Image Model: {settings.gemini_image_model}")
    logger.info(f"Video Model: {settings.veo_video_model}")
    logger.info(f"Video Output Bucket: {settings.video_output_bucket}")
    logger.info(f"Agent Engine Enabled: {settings.use_agent_engine}")
    if settings.agent_engine_id:
        logger.info(f"Agent Engine ID: {settings.agent_engine_id}")
    logger.info("=" * 50)
    
    # Initialize Agent Engine services (Sessions and Memory Bank)
    await initialize_services()


@app.on_event("shutdown")
async def shutdown_event() -> None:
    """Application shutdown event."""
    logger.info("Agent Service Shutting Down")


if __name__ == "__main__":
    import uvicorn
    
    settings = get_settings()
    uvicorn.run(
        "src.main:app",
        host=settings.agent_service_host,
        port=settings.agent_service_port,
        reload=True,
    )
