"""Abstract interface for persona storage."""

from abc import ABC, abstractmethod

from ..entities.persona import Persona


class PersonaRepository(ABC):
    """
    Abstract repository interface for Persona persistence.
    
    Following the Repository pattern from Clean Architecture,
    this interface defines the contract for persona storage
    without specifying the implementation details.
    """

    @abstractmethod
    async def create(self, persona: Persona) -> Persona:
        """
        Create a new persona.
        
        Args:
            persona: Persona entity to create
            
        Returns:
            Created persona
            
        Raises:
            ValueError: If persona with same name already exists
        """
        pass

    @abstractmethod
    async def get_by_name(self, name: str) -> Persona | None:
        """
        Get a persona by name.
        
        Args:
            name: Persona name (case-insensitive)
            
        Returns:
            Persona if found, None otherwise
        """
        pass

    @abstractmethod
    async def get_all(self) -> list[Persona]:
        """
        Get all personas.
        
        Returns:
            List of all personas
        """
        pass

    @abstractmethod
    async def update(self, name: str, persona: Persona) -> Persona | None:
        """
        Update an existing persona.
        
        Args:
            name: Current name of persona to update
            persona: Updated persona data
            
        Returns:
            Updated persona if found, None otherwise
        """
        pass

    @abstractmethod
    async def delete(self, name: str) -> bool:
        """
        Delete a persona by name.
        
        Args:
            name: Persona name to delete
            
        Returns:
            True if deleted, False if not found
        """
        pass

    @abstractmethod
    async def exists(self, name: str) -> bool:
        """
        Check if a persona exists.
        
        Args:
            name: Persona name to check
            
        Returns:
            True if exists, False otherwise
        """
        pass
