"""Interface for generation settings persistence."""

from abc import ABC, abstractmethod

from ..entities.generation_settings import GenerationSettings


class SettingsRepository(ABC):
    """
    Abstract interface for storing and retrieving generation settings.
    
    Settings are stored by name (persona name or "default" for guild-wide).
    """

    @abstractmethod
    async def get(self, name: str) -> GenerationSettings | None:
        """
        Get settings by name.
        
        Args:
            name: Settings name (persona name or "default")
            
        Returns:
            GenerationSettings if found, None otherwise
        """
        pass

    @abstractmethod
    async def get_or_default(self, name: str) -> GenerationSettings:
        """
        Get settings by name, or return default settings if not found.
        
        Args:
            name: Settings name (persona name or "default")
            
        Returns:
            GenerationSettings (existing or default)
        """
        pass

    @abstractmethod
    async def save(self, settings: GenerationSettings) -> GenerationSettings:
        """
        Save settings (create or update).
        
        Args:
            settings: GenerationSettings to save
            
        Returns:
            Saved GenerationSettings
        """
        pass

    @abstractmethod
    async def delete(self, name: str) -> bool:
        """
        Delete settings by name.
        
        Args:
            name: Settings name to delete
            
        Returns:
            True if deleted, False if not found
        """
        pass

    @abstractmethod
    async def list_all(self) -> list[GenerationSettings]:
        """
        List all stored settings.
        
        Returns:
            List of all GenerationSettings
        """
        pass
