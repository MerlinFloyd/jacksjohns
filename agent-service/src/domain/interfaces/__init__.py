"""Domain interfaces (ports) - abstract contracts for infrastructure."""

from .persona_repository import PersonaRepository
from .image_generator import ImageGenerator

__all__ = ["PersonaRepository", "ImageGenerator"]
