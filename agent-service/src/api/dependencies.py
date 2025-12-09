"""FastAPI dependency injection setup."""

import logging
from typing import TYPE_CHECKING

from ..config.settings import get_settings
from ..domain.interfaces.persona_repository import PersonaRepository
from ..domain.interfaces.image_generator import ImageGenerator
from ..domain.interfaces.memory_service import MemoryService
from ..domain.interfaces.session_service import SessionService
from ..infrastructure.repositories.in_memory_persona_repository import InMemoryPersonaRepository
from ..infrastructure.genai.gemini_image_generator import GeminiImageGenerator

if TYPE_CHECKING:
    from ..infrastructure.repositories.channel_session_repository import ChannelSessionRepository

logger = logging.getLogger(__name__)

# Singleton instances
_persona_repository: PersonaRepository | None = None
_image_generator: ImageGenerator | None = None
_memory_service: MemoryService | None = None
_session_service: SessionService | None = None
_channel_session_repository: "ChannelSessionRepository | None" = None
_agent_engine_manager = None
_agent_engine_initialized = False


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


async def _initialize_agent_engine() -> None:
    """Initialize the Agent Engine manager and services."""
    global _agent_engine_manager, _memory_service, _session_service, _agent_engine_initialized
    
    if _agent_engine_initialized:
        return
        
    settings = get_settings()
    
    if not settings.use_agent_engine:
        logger.info("Agent Engine disabled via settings")
        _agent_engine_initialized = True
        return
    
    try:
        from ..infrastructure.agent_engine import (
            AgentEngineManager,
            VertexAiMemoryService,
            VertexAiSessionService,
        )
        
        # Create the manager
        _agent_engine_manager = AgentEngineManager(
            project_id=settings.gcp_project_id,
            location=settings.gcp_region,
            agent_engine_id=settings.agent_engine_id,
        )
        
        # Get or create the Agent Engine instance
        agent_engine_id = await _agent_engine_manager.get_or_create_agent_engine(
            display_name=settings.agent_engine_display_name,
        )
        
        logger.info(f"Agent Engine initialized: {agent_engine_id}")
        
        # Create services
        _memory_service = VertexAiMemoryService(_agent_engine_manager)
        _session_service = VertexAiSessionService(_agent_engine_manager)
        
        logger.info("Memory and Session services initialized")
        
    except Exception as e:
        logger.warning(
            f"Failed to initialize Agent Engine services: {e}. "
            "Memory and Session features will be disabled."
        )
    
    _agent_engine_initialized = True


def get_memory_service() -> MemoryService | None:
    """
    Get the memory service singleton.
    
    Returns:
        MemoryService implementation or None if not available
    """
    return _memory_service


def get_session_service() -> SessionService | None:
    """
    Get the session service singleton.
    
    Returns:
        SessionService implementation or None if not available
    """
    return _session_service


def get_channel_session_repository() -> "ChannelSessionRepository | None":
    """
    Get the channel session repository singleton.
    
    Returns:
        ChannelSessionRepository implementation or None if Firestore is disabled
    """
    global _channel_session_repository
    
    if _channel_session_repository is None:
        settings = get_settings()
        
        if settings.use_firestore:
            try:
                from ..infrastructure.repositories.channel_session_repository import (
                    ChannelSessionRepository,
                )
                _channel_session_repository = ChannelSessionRepository()
                logger.info("ChannelSessionRepository initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize ChannelSessionRepository: {e}")
                return None
        else:
            logger.info("ChannelSessionRepository disabled (Firestore disabled)")
            return None
    
    return _channel_session_repository


async def initialize_services() -> None:
    """
    Initialize all services.
    
    This should be called during application startup.
    """
    await _initialize_agent_engine()
    logger.info("All services initialized")


def reset_dependencies() -> None:
    """Reset all dependencies (useful for testing)."""
    global _persona_repository, _image_generator, _memory_service, _session_service
    global _agent_engine_manager, _agent_engine_initialized, _channel_session_repository
    _persona_repository = None
    _image_generator = None
    _memory_service = None
    _session_service = None
    _channel_session_repository = None
    _agent_engine_manager = None
    _agent_engine_initialized = False
