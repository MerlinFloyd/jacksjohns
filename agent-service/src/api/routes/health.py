"""Health check endpoint."""

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check() -> dict:
    """
    Health check endpoint.
    
    Returns:
        Health status
    """
    return {"status": "healthy", "service": "agent-service"}


@router.get("/")
async def root() -> dict:
    """
    Root endpoint.
    
    Returns:
        Service information
    """
    return {
        "service": "agent-service",
        "version": "0.1.0",
        "description": "AI Agent Service for Discord Bot",
    }
