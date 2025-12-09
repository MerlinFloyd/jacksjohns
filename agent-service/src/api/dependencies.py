"""FastAPI dependency injection setup."""

from functools import lru_cache

from ..domain.interfaces.persona_repository import PersonaRepository
from ..domain.interfaces.image_generator import ImageGenerator
from ..infrastructure.repositories.in_memory_persona_repository import InMemoryPersonaRepository
from ..infrastructure.genai.gemini_image_generator import GeminiImageGenerator


# Singleton instances
_persona_repository: PersonaRepository | None = None
_image_generator: ImageGenerator | None = None


def get_persona_repository() -> PersonaRepository:
    """
    Get the persona repository singleton.
    
    Returns:
        PersonaRepository implementation
    """
    global _persona_repository
    if _persona_repository is None:
        _persona_repository = InMemoryPersonaRepository()
    return _persona_repository


def get_image_generator() -> ImageGenerator:
    """
    Get the image generator singleton.
    
    Returns:
        ImageGenerator implementation
    """
    global _image_generator
    if _image_generator is None:
        _image_generator = GeminiImageGenerator()
    return _image_generator


def reset_dependencies() -> None:
    """Reset all dependencies (useful for testing)."""
    global _persona_repository, _image_generator
    _persona_repository = None
    _image_generator = None
