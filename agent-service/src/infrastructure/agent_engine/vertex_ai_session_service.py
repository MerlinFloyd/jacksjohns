"""
Vertex AI Session Service implementation.

This implements the SessionService interface using Vertex AI Agent Engine's
Sessions feature for conversation history management.
"""

import logging
from datetime import datetime
from typing import Any

import vertexai
from google.genai import types as genai_types

from ...domain.interfaces.session_service import Session, SessionEvent, SessionService
from .agent_engine_manager import AgentEngineManager

logger = logging.getLogger(__name__)


class VertexAiSessionService(SessionService):
    """
    Vertex AI Sessions implementation of SessionService.
    
    Sessions maintain the history of interactions between a user
    and a persona within a single conversation.
    """

    def __init__(self, agent_engine_manager: AgentEngineManager):
        """
        Initialize the Vertex AI Session Service.
        
        Args:
            agent_engine_manager: Manager for Agent Engine instance
        """
        self._manager = agent_engine_manager
        self._client: vertexai.Client | None = None
        
    def _ensure_initialized(self) -> None:
        """Ensure the client is initialized."""
        if not self._client:
            self._client = self._manager.get_client()
            
    def _get_agent_engine_name(self) -> str:
        """Get the full Agent Engine resource name."""
        name = self._manager.agent_engine_resource_name
        if not name:
            raise ValueError(
                "Agent Engine not initialized. Call agent_engine_manager.get_or_create_agent_engine() first."
            )
        return name

    def _convert_to_session(
        self,
        api_session: Any,
        app_name: str,
    ) -> Session:
        """Convert API session response to our Session dataclass."""
        # Extract session ID from resource name
        session_id = api_session.name.split("/")[-1] if hasattr(api_session, 'name') else ""
        
        # Extract user_id from the session
        user_id = getattr(api_session, 'user_id', "")
        
        # Convert events
        events = []
        if hasattr(api_session, 'events') and api_session.events:
            for event in api_session.events:
                if hasattr(event, 'content') and event.content:
                    content_parts = event.content.parts if hasattr(event.content, 'parts') else []
                    text = ""
                    for part in content_parts:
                        if hasattr(part, 'text'):
                            text += part.text
                    
                    events.append(SessionEvent(
                        role=event.content.role if hasattr(event.content, 'role') else "user",
                        content=text,
                        timestamp=datetime.utcnow(),  # API may not provide timestamp
                    ))
        
        return Session(
            id=session_id,
            user_id=user_id,
            app_name=app_name,
            events=events,
            state=getattr(api_session, 'state', {}) or {},
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

    async def create_session(
        self,
        user_id: str,
        app_name: str,
        initial_state: dict[str, Any] | None = None,
    ) -> Session:
        """
        Create a new session for a user-persona conversation.
        
        Args:
            user_id: Discord user ID
            app_name: Persona name
            initial_state: Optional initial session state
            
        Returns:
            Created session
        """
        self._ensure_initialized()
        
        try:
            agent_engine_name = self._get_agent_engine_name()
            
            # Create session via API
            api_session = self._client.agent_engines.create_session(
                parent=agent_engine_name,
                session=genai_types.Session(
                    user_id=user_id,
                    state=initial_state or {},
                ),
            )
            
            session = self._convert_to_session(api_session, app_name)
            logger.info(
                f"Created session {session.id} for user={user_id}, persona={app_name}"
            )
            return session
            
        except Exception as e:
            logger.error(f"Failed to create session: {e}")
            raise

    async def get_session(
        self,
        session_id: str,
        user_id: str,
        app_name: str,
    ) -> Session | None:
        """
        Get an existing session.
        
        Args:
            session_id: Session ID
            user_id: Discord user ID
            app_name: Persona name
            
        Returns:
            Session if found, None otherwise
        """
        self._ensure_initialized()
        
        try:
            agent_engine_name = self._get_agent_engine_name()
            session_name = f"{agent_engine_name}/sessions/{session_id}"
            
            api_session = self._client.agent_engines.get_session(
                name=session_name,
            )
            
            return self._convert_to_session(api_session, app_name)
            
        except Exception as e:
            logger.debug(f"Session {session_id} not found: {e}")
            return None

    async def append_event(
        self,
        session_id: str,
        user_id: str,
        app_name: str,
        event: SessionEvent,
    ) -> Session:
        """
        Append an event to a session.
        
        Args:
            session_id: Session ID
            user_id: Discord user ID  
            app_name: Persona name
            event: Event to append
            
        Returns:
            Updated session
        """
        self._ensure_initialized()
        
        try:
            agent_engine_name = self._get_agent_engine_name()
            session_name = f"{agent_engine_name}/sessions/{session_id}"
            
            # Create the event content
            role = "user" if event.role == "user" else "model"
            content = genai_types.Content(
                role=role,
                parts=[genai_types.Part(text=event.content)],
            )
            
            # Append event to session
            self._client.agent_engines.append_event(
                name=session_name,
                event=genai_types.SessionEvent(
                    content=content,
                ),
            )
            
            # Fetch updated session
            session = await self.get_session(session_id, user_id, app_name)
            if not session:
                raise ValueError(f"Session {session_id} not found after append")
                
            logger.debug(f"Appended event to session {session_id}")
            return session
            
        except Exception as e:
            logger.error(f"Failed to append event to session {session_id}: {e}")
            raise

    async def list_sessions(
        self,
        user_id: str,
        app_name: str,
    ) -> list[Session]:
        """
        List all sessions for a user-persona combination.
        
        Args:
            user_id: Discord user ID
            app_name: Persona name
            
        Returns:
            List of sessions
        """
        self._ensure_initialized()
        
        try:
            agent_engine_name = self._get_agent_engine_name()
            
            # List sessions filtered by user_id
            response = self._client.agent_engines.list_sessions(
                parent=agent_engine_name,
                filter=f'user_id="{user_id}"',
            )
            
            sessions = []
            for api_session in response:
                sessions.append(self._convert_to_session(api_session, app_name))
            
            logger.debug(
                f"Listed {len(sessions)} sessions for user={user_id}, persona={app_name}"
            )
            return sessions
            
        except Exception as e:
            logger.error(f"Failed to list sessions: {e}")
            raise

    async def delete_session(
        self,
        session_id: str,
        user_id: str,
        app_name: str,
    ) -> bool:
        """
        Delete a session.
        
        Args:
            session_id: Session ID
            user_id: Discord user ID
            app_name: Persona name
            
        Returns:
            True if deleted, False if not found
        """
        self._ensure_initialized()
        
        try:
            agent_engine_name = self._get_agent_engine_name()
            session_name = f"{agent_engine_name}/sessions/{session_id}"
            
            self._client.agent_engines.delete_session(name=session_name)
            logger.info(f"Deleted session {session_id}")
            return True
            
        except Exception as e:
            logger.warning(f"Failed to delete session {session_id}: {e}")
            return False

    async def update_state(
        self,
        session_id: str,
        user_id: str,
        app_name: str,
        state: dict[str, Any],
    ) -> Session:
        """
        Update session state.
        
        Args:
            session_id: Session ID
            user_id: Discord user ID
            app_name: Persona name
            state: New state data
            
        Returns:
            Updated session
        """
        self._ensure_initialized()
        
        try:
            agent_engine_name = self._get_agent_engine_name()
            session_name = f"{agent_engine_name}/sessions/{session_id}"
            
            # Update session with new state
            api_session = self._client.agent_engines.update_session(
                session=genai_types.Session(
                    name=session_name,
                    state=state,
                ),
            )
            
            session = self._convert_to_session(api_session, app_name)
            logger.debug(f"Updated state for session {session_id}")
            return session
            
        except Exception as e:
            logger.error(f"Failed to update session state {session_id}: {e}")
            raise
