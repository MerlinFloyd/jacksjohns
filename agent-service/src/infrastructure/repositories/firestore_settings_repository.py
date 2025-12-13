"""Firestore implementation of SettingsRepository."""

import logging
from datetime import datetime, timezone

from google.cloud import firestore
from google.cloud.firestore_v1 import AsyncClient

from ...domain.entities.generation_settings import (
    GenerationSettings,
    get_default_settings,
)
from ...domain.interfaces.settings_repository import SettingsRepository
from ...config.settings import get_settings

logger = logging.getLogger(__name__)


class FirestoreSettingsRepository(SettingsRepository):
    """
    Firestore implementation of SettingsRepository.
    
    Stores generation settings in a Firestore collection with the document ID
    being the lowercase settings name (persona name or "default").
    """

    def __init__(
        self,
        database_name: str | None = None,
        collection_name: str = "generation_settings",
    ) -> None:
        """
        Initialize Firestore settings repository.
        
        Args:
            database_name: Override the default database name from settings
            collection_name: Collection name for settings documents
        """
        settings = get_settings()
        self._database = database_name or settings.firestore_database
        self._collection = collection_name
        self._client: AsyncClient | None = None
        logger.info(
            f"FirestoreSettingsRepository initialized with "
            f"database: {self._database}, collection: {self._collection}"
        )

    @property
    def client(self) -> AsyncClient:
        """Get or create the async Firestore client."""
        if self._client is None:
            self._client = firestore.AsyncClient(database=self._database)
        return self._client

    def _normalize_name(self, name: str) -> str:
        """Normalize settings name for case-insensitive lookup."""
        return name.strip().lower()

    def _settings_to_doc(self, settings: GenerationSettings) -> dict:
        """Convert GenerationSettings entity to Firestore document."""
        data = settings.to_dict()
        # Convert ISO strings back to datetime for Firestore
        data["created_at"] = settings.created_at
        data["updated_at"] = settings.updated_at
        return data

    def _doc_to_settings(self, doc_data: dict) -> GenerationSettings:
        """Convert Firestore document to GenerationSettings entity."""
        # Handle Firestore timestamps - they come as datetime objects
        created_at = doc_data.get("created_at")
        updated_at = doc_data.get("updated_at")
        
        # Ensure timezone awareness
        if created_at and hasattr(created_at, 'tzinfo') and created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        if updated_at and hasattr(updated_at, 'tzinfo') and updated_at.tzinfo is None:
            updated_at = updated_at.replace(tzinfo=timezone.utc)
        
        # Update the dict with proper datetime objects
        if created_at:
            doc_data["created_at"] = created_at
        if updated_at:
            doc_data["updated_at"] = updated_at
        
        return GenerationSettings.from_dict(doc_data)

    async def get(self, name: str) -> GenerationSettings | None:
        """
        Get settings by name from Firestore.
        
        Args:
            name: Settings name (case-insensitive)
            
        Returns:
            GenerationSettings if found, None otherwise
        """
        key = self._normalize_name(name)
        doc = await self.client.collection(self._collection).document(key).get()
        
        if not doc.exists:
            return None
        
        return self._doc_to_settings(doc.to_dict())

    async def get_or_default(self, name: str) -> GenerationSettings:
        """
        Get settings by name, or return default settings if not found.
        
        First checks for persona-specific settings, then falls back to
        default settings if they exist, otherwise returns new default settings.
        
        Args:
            name: Settings name (persona name or "default")
            
        Returns:
            GenerationSettings (existing or default)
        """
        # Try to get the specific settings
        settings = await self.get(name)
        if settings:
            return settings
        
        # If not "default", try to get default settings
        if self._normalize_name(name) != "default":
            default_settings = await self.get("default")
            if default_settings:
                # Return a copy with the requested name
                return GenerationSettings(
                    name=name,
                    chat=default_settings.chat,
                    image=default_settings.image,
                )
        
        # Return fresh default settings
        return GenerationSettings(name=name)

    async def save(self, settings: GenerationSettings) -> GenerationSettings:
        """
        Save settings (create or update) in Firestore.
        
        Args:
            settings: GenerationSettings to save
            
        Returns:
            Saved GenerationSettings
        """
        key = self._normalize_name(settings.name)
        doc_ref = self.client.collection(self._collection).document(key)
        
        # Update the timestamp
        settings.updated_at = datetime.now(timezone.utc)
        
        await doc_ref.set(self._settings_to_doc(settings))
        logger.info(f"Saved settings in Firestore: {settings.name}")
        return settings

    async def delete(self, name: str) -> bool:
        """
        Delete settings from Firestore.
        
        Args:
            name: Settings name to delete
            
        Returns:
            True if deleted, False if not found
        """
        key = self._normalize_name(name)
        doc_ref = self.client.collection(self._collection).document(key)
        doc = await doc_ref.get()
        
        if not doc.exists:
            return False
        
        await doc_ref.delete()
        logger.info(f"Deleted settings from Firestore: {name}")
        return True

    async def list_all(self) -> list[GenerationSettings]:
        """
        List all settings from Firestore.
        
        Returns:
            List of all GenerationSettings
        """
        docs = self.client.collection(self._collection).stream()
        settings_list = []
        async for doc in docs:
            try:
                settings_list.append(self._doc_to_settings(doc.to_dict()))
            except Exception as e:
                logger.error(f"Error parsing settings document {doc.id}: {e}")
                continue
        return settings_list
