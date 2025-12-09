"""FastAPI dependency injection setup."""

import logging

from ..config.settings import get_settings
from ..domain.interfaces.persona_repository import PersonaRepository
from ..domain.interfaces.image_generator import ImageGenerator
from ..infrastructure.repositories.in_memory_persona_repository import InMemoryPersonaRepository
from ..infrastructure.genai.gemini_image_generator import GeminiImageGenerator

logger = logging.getLogger(__name__)

# Singleton instances
_persona_repository: PersonaRepository | None = None
_image_generator: ImageGenerator | None = None


def get_persona_repository() -> PersonaRepository:
    """
    Get the persona repository singleton.
    
    Attempts to use Firestore for persistent storage.
    Falls back to in-memory storage if Firestore is unavailable or disabled.
    
    Returns:
        PersonaRepository implementation
    """
    global _persona_repository
    if _persona_repository is None:
        settings = get_settings()
        
        if settings.use_firestore:
            try:
                # Attempt to import and initialize Firestore repository
                from ..infrastructure.repositories.firestore_persona_repository import (
                    FirestorePersonaRepository,
                )
                _persona_repository = FirestorePersonaRepository()
                logger.info("Using FirestorePersonaRepository for persona persistence")
            except Exception as e:
                # Fall back to in-memory if Firestore fails
                logger.warning(
                    f"Failed to initialize FirestorePersonaRepository, "
                    f"falling back to InMemoryPersonaRepository. Error: {e}"
                )
                _persona_repository = InMemoryPersonaRepository()
                logger.warning(
                    "WARNING: Using in-memory storage - persona data will NOT persist across restarts!"
                )
        else:
            _persona_repository = InMemoryPersonaRepository()
            logger.info("Using InMemoryPersonaRepository (Firestore disabled via settings)")
    
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
