"""API routes."""

from .health import router as health_router
from .persona import router as persona_router
from .image import router as image_router
from .video import router as video_router
from .chat import router as chat_router
from .settings import router as settings_router

__all__ = [
    "health_router",
    "persona_router",
    "image_router",
    "video_router",
    "chat_router",
    "settings_router",
]
