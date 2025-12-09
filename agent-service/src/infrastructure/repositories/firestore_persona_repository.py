"""Firestore implementation of PersonaRepository."""

import logging
from datetime import datetime, timezone

from google.cloud import firestore
from google.cloud.firestore_v1 import AsyncClient

from ...domain.entities.persona import Persona
from ...domain.interfaces.persona_repository import PersonaRepository
from ...config.settings import get_settings

logger = logging.getLogger(__name__)


class FirestorePersonaRepository(PersonaRepository):
    """
    Firestore implementation of PersonaRepository.
    
    Stores personas in a Firestore collection with the document ID
    being the lowercase persona name for case-insensitive lookups.
    
    Data is persisted across service restarts, making this suitable
    for production use.
    """

    def __init__(self, collection_name: str | None = None) -> None:
        """
        Initialize Firestore persona repository.
        
        Args:
            collection_name: Override the default collection name from settings
        """
        settings = get_settings()
        self._collection = collection_name or settings.firestore_collection
        self._client: AsyncClient | None = None
        logger.info(f"FirestorePersonaRepository initialized with collection: {self._collection}")

    @property
    def client(self) -> AsyncClient:
        """Get or create the async Firestore client."""
        if self._client is None:
            self._client = firestore.AsyncClient()
        return self._client

    def _normalize_name(self, name: str) -> str:
        """Normalize persona name for case-insensitive lookup."""
        return name.strip().lower()

    def _persona_to_doc(self, persona: Persona) -> dict:
        """Convert Persona entity to Firestore document."""
        return {
            "name": persona.name,
            "personality": persona.personality,
            "created_at": persona.created_at,
            "updated_at": persona.updated_at,
        }

    def _doc_to_persona(self, doc_data: dict) -> Persona:
        """Convert Firestore document to Persona entity."""
        # Handle Firestore timestamps - they come as datetime objects
        created_at = doc_data["created_at"]
        updated_at = doc_data["updated_at"]
        
        # Ensure timezone awareness
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        if updated_at.tzinfo is None:
            updated_at = updated_at.replace(tzinfo=timezone.utc)
        
        return Persona(
            name=doc_data["name"],
            personality=doc_data["personality"],
            created_at=created_at,
            updated_at=updated_at,
        )

    async def create(self, persona: Persona) -> Persona:
        """
        Create a new persona in Firestore.
        
        Args:
            persona: Persona entity to create
            
        Returns:
            Created persona
            
        Raises:
            ValueError: If persona with same name already exists
        """
        key = self._normalize_name(persona.name)
        doc_ref = self.client.collection(self._collection).document(key)
        
        doc = await doc_ref.get()
        if doc.exists:
            raise ValueError(f"Persona with name '{persona.name}' already exists")
        
        await doc_ref.set(self._persona_to_doc(persona))
        logger.info(f"Created persona in Firestore: {persona.name}")
        return persona

    async def get_by_name(self, name: str) -> Persona | None:
        """
        Get a persona by name from Firestore.
        
        Args:
            name: Persona name (case-insensitive)
            
        Returns:
            Persona if found, None otherwise
        """
        key = self._normalize_name(name)
        doc = await self.client.collection(self._collection).document(key).get()
        
        if not doc.exists:
            return None
        
        return self._doc_to_persona(doc.to_dict())

    async def get_all(self) -> list[Persona]:
        """
        Get all personas from Firestore.
        
        Returns:
            List of all personas
        """
        docs = self.client.collection(self._collection).stream()
        personas = []
        async for doc in docs:
            try:
                personas.append(self._doc_to_persona(doc.to_dict()))
            except Exception as e:
                logger.error(f"Error parsing persona document {doc.id}: {e}")
                continue
        return personas

    async def update(self, name: str, persona: Persona) -> Persona | None:
        """
        Update an existing persona in Firestore.
        
        Args:
            name: Current name of persona to update
            persona: Updated persona data
            
        Returns:
            Updated persona if found, None otherwise
            
        Raises:
            ValueError: If new name conflicts with existing persona
        """
        old_key = self._normalize_name(name)
        new_key = self._normalize_name(persona.name)
        
        old_doc_ref = self.client.collection(self._collection).document(old_key)
        old_doc = await old_doc_ref.get()
        
        if not old_doc.exists:
            return None
        
        # Check name conflict if renaming
        if new_key != old_key:
            new_doc = await self.client.collection(self._collection).document(new_key).get()
            if new_doc.exists:
                raise ValueError(f"Persona with name '{persona.name}' already exists")
            
            # Delete old document and create new one with new key
            await old_doc_ref.delete()
            await self.client.collection(self._collection).document(new_key).set(
                self._persona_to_doc(persona)
            )
        else:
            # Same key, just update the document
            await old_doc_ref.update(self._persona_to_doc(persona))
        
        logger.info(f"Updated persona in Firestore: {name} -> {persona.name}")
        return persona

    async def delete(self, name: str) -> bool:
        """
        Delete a persona from Firestore.
        
        Args:
            name: Persona name to delete
            
        Returns:
            True if deleted, False if not found
        """
        key = self._normalize_name(name)
        doc_ref = self.client.collection(self._collection).document(key)
        doc = await doc_ref.get()
        
        if not doc.exists:
            return False
        
        await doc_ref.delete()
        logger.info(f"Deleted persona from Firestore: {name}")
        return True

    async def exists(self, name: str) -> bool:
        """
        Check if a persona exists in Firestore.
        
        Args:
            name: Persona name to check
            
        Returns:
            True if exists, False otherwise
        """
        key = self._normalize_name(name)
        doc = await self.client.collection(self._collection).document(key).get()
        return doc.exists
