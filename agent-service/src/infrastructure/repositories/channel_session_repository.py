"""Firestore repository for channel session mappings."""

import logging
from datetime import datetime, timezone
from dataclasses import dataclass

from google.cloud import firestore
from google.cloud.firestore_v1 import AsyncClient

from ...config.settings import get_settings

logger = logging.getLogger(__name__)


@dataclass
class ChannelSession:
    """
    Represents a channel-to-session mapping.
    
    Used to persist session IDs for persona channels so conversations
    continue across bot restarts.
    """
    channel_id: str
    session_id: str
    persona_name: str
    user_id: str  # The user_id used when creating the Vertex AI session
    created_at: datetime
    updated_at: datetime


class ChannelSessionRepository:
    """
    Firestore repository for channel session mappings.
    
    Stores channel_id -> session_id mappings to persist shared
    channel sessions across bot restarts.
    """

    COLLECTION = "channel_sessions"

    def __init__(self, database_name: str | None = None) -> None:
        """
        Initialize channel session repository.
        
        Args:
            database_name: Override the default database name from settings
        """
        settings = get_settings()
        self._database = database_name or settings.firestore_database
        self._client: AsyncClient | None = None
        logger.info(
            f"ChannelSessionRepository initialized with database: {self._database}"
        )

    @property
    def client(self) -> AsyncClient:
        """Get or create the async Firestore client."""
        if self._client is None:
            self._client = firestore.AsyncClient(database=self._database)
        return self._client

    def _to_doc(self, session: ChannelSession) -> dict:
        """Convert ChannelSession to Firestore document."""
        return {
            "channel_id": session.channel_id,
            "session_id": session.session_id,
            "persona_name": session.persona_name,
            "user_id": session.user_id,
            "created_at": session.created_at,
            "updated_at": session.updated_at,
        }

    def _from_doc(self, doc_data: dict) -> ChannelSession:
        """Convert Firestore document to ChannelSession."""
        created_at = doc_data["created_at"]
        updated_at = doc_data["updated_at"]
        
        # Ensure timezone awareness
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        if updated_at.tzinfo is None:
            updated_at = updated_at.replace(tzinfo=timezone.utc)
        
        return ChannelSession(
            channel_id=doc_data["channel_id"],
            session_id=doc_data["session_id"],
            persona_name=doc_data["persona_name"],
            user_id=doc_data.get("user_id", "channel"),  # Default for backward compatibility
            created_at=created_at,
            updated_at=updated_at,
        )

    async def get_session(self, channel_id: str) -> ChannelSession | None:
        """
        Get session mapping for a channel.
        
        Args:
            channel_id: Discord channel ID
            
        Returns:
            ChannelSession if found, None otherwise
        """
        doc = await self.client.collection(self.COLLECTION).document(channel_id).get()
        
        if not doc.exists:
            return None
        
        return self._from_doc(doc.to_dict())

    async def get_session_id(self, channel_id: str) -> str | None:
        """
        Get just the session ID for a channel.
        
        Args:
            channel_id: Discord channel ID
            
        Returns:
            Session ID if found, None otherwise
        """
        session = await self.get_session(channel_id)
        return session.session_id if session else None

    async def set_session(
        self,
        channel_id: str,
        session_id: str,
        persona_name: str,
        user_id: str,
    ) -> ChannelSession:
        """
        Store or update session mapping for a channel.
        
        Args:
            channel_id: Discord channel ID
            session_id: Vertex AI session ID
            persona_name: Name of the persona for this channel
            user_id: The user_id used when creating the Vertex AI session
            
        Returns:
            Created or updated ChannelSession
        """
        doc_ref = self.client.collection(self.COLLECTION).document(channel_id)
        existing = await doc_ref.get()
        
        now = datetime.now(timezone.utc)
        
        if existing.exists:
            # Update existing - preserve the original user_id
            existing_session = self._from_doc(existing.to_dict())
            session = ChannelSession(
                channel_id=channel_id,
                session_id=session_id,
                persona_name=persona_name,
                user_id=existing_session.user_id,  # Keep original user_id
                created_at=existing_session.created_at,
                updated_at=now,
            )
        else:
            # Create new
            session = ChannelSession(
                channel_id=channel_id,
                session_id=session_id,
                persona_name=persona_name,
                user_id=user_id,
                created_at=now,
                updated_at=now,
            )
        
        await doc_ref.set(self._to_doc(session))
        logger.info(f"Stored session {session_id} for channel {channel_id} (user: {user_id})")
        return session

    async def delete_session(self, channel_id: str) -> bool:
        """
        Delete session mapping for a channel.
        
        Args:
            channel_id: Discord channel ID
            
        Returns:
            True if deleted, False if not found
        """
        doc_ref = self.client.collection(self.COLLECTION).document(channel_id)
        doc = await doc_ref.get()
        
        if not doc.exists:
            return False
        
        await doc_ref.delete()
        logger.info(f"Deleted session mapping for channel {channel_id}")
        return True

    async def get_by_persona(self, persona_name: str) -> list[ChannelSession]:
        """
        Get all channel sessions for a persona.
        
        Args:
            persona_name: Persona name
            
        Returns:
            List of channel sessions
        """
        query = self.client.collection(self.COLLECTION).where(
            "persona_name", "==", persona_name
        )
        
        sessions = []
        async for doc in query.stream():
            try:
                sessions.append(self._from_doc(doc.to_dict()))
            except Exception as e:
                logger.error(f"Error parsing channel session {doc.id}: {e}")
        
        return sessions

    async def delete_by_persona(self, persona_name: str) -> int:
        """
        Delete all channel sessions for a persona.
        
        Args:
            persona_name: Persona name
            
        Returns:
            Number of sessions deleted
        """
        sessions = await self.get_by_persona(persona_name)
        
        for session in sessions:
            await self.delete_session(session.channel_id)
        
        logger.info(f"Deleted {len(sessions)} sessions for persona {persona_name}")
        return len(sessions)
