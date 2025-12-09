"""API routes."""

from .health import router as health_router
from .persona import router as persona_router
from .image import router as image_router

__all__ = ["health_router", "persona_router", "image_router"]
