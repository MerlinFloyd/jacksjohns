"""In-memory implementation of PersonaRepository."""

import logging
from typing import Dict

from ...domain.entities.persona import Persona
from ...domain.interfaces.persona_repository import PersonaRepository

logger = logging.getLogger(__name__)


class InMemoryPersonaRepository(PersonaRepository):
    """
    In-memory implementation of PersonaRepository.
    
    Stores personas in a dictionary for development and testing.
    Data is lost when the service restarts.
    
    Note: This is suitable for initial development. For production,
    implement a persistent storage solution (e.g., Firestore, Redis).
    """

    def __init__(self) -> None:
        """Initialize empty persona storage."""
        self._personas: Dict[str, Persona] = {}

    def _normalize_name(self, name: str) -> str:
        """Normalize persona name for case-insensitive lookup."""
        return name.strip().lower()

    async def create(self, persona: Persona) -> Persona:
        """Create a new persona."""
        key = self._normalize_name(persona.name)
        
        if key in self._personas:
            raise ValueError(f"Persona with name '{persona.name}' already exists")
        
        self._personas[key] = persona
        logger.info(f"Created persona: {persona.name}")
        return persona

    async def get_by_name(self, name: str) -> Persona | None:
        """Get a persona by name."""
        key = self._normalize_name(name)
        return self._personas.get(key)

    async def get_all(self) -> list[Persona]:
        """Get all personas."""
        return list(self._personas.values())

    async def update(self, name: str, persona: Persona) -> Persona | None:
        """Update an existing persona."""
        old_key = self._normalize_name(name)
        
        if old_key not in self._personas:
            return None
        
        # If name changed, we need to update the key
        new_key = self._normalize_name(persona.name)
        
        # Check if new name conflicts with existing persona (other than current)
        if new_key != old_key and new_key in self._personas:
            raise ValueError(f"Persona with name '{persona.name}' already exists")
        
        # Remove old entry and add new one
        del self._personas[old_key]
        self._personas[new_key] = persona
        
        logger.info(f"Updated persona: {name} -> {persona.name}")
        return persona

    async def delete(self, name: str) -> bool:
        """Delete a persona by name."""
        key = self._normalize_name(name)
        
        if key not in self._personas:
            return False
        
        del self._personas[key]
        logger.info(f"Deleted persona: {name}")
        return True

    async def exists(self, name: str) -> bool:
        """Check if a persona exists."""
        key = self._normalize_name(name)
        return key in self._personas
