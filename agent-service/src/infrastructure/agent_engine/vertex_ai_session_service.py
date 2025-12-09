"""
Vertex AI Session Service implementation.

This implements the SessionService interface using Vertex AI Agent Engine's
Sessions feature for conversation history management.

NOTE: Uses the agent_engine object methods (create_session, get_session, etc.)
rather than the low-level client.agent_engines.sessions.* API.
"""

import logging
from datetime import datetime
from typing import Any

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

    def _get_agent_engine(self) -> Any:
        """Get the Agent Engine object for session operations."""
        return self._manager.get_agent_engine()

    def _convert_dict_to_session(
        self,
        session_dict: dict[str, Any],
        app_name: str,
    ) -> Session:
        """Convert API session dict response to our Session dataclass."""
        # The agent_engine.create_session returns a dict like:
        # {"id": "...", "user_id": "...", "app_name": "...", ...}
        session_id = session_dict.get("id", "")
        user_id = session_dict.get("user_id", "")
        
        # Convert events if present
        events = []
        raw_events = session_dict.get("events", [])
        if raw_events:
            for event in raw_events:
                content = event.get("content", {})
                parts = content.get("parts", [])
                text = ""
                for part in parts:
                    if isinstance(part, dict) and "text" in part:
                        text += part["text"]
                    elif hasattr(part, 'text'):
                        text += part.text
                
                events.append(SessionEvent(
                    role=content.get("role", "user"),
                    content=text,
                    timestamp=datetime.utcnow(),
                ))
        
        return Session(
            id=session_id,
            user_id=user_id,
            app_name=app_name,
            events=events,
            state=session_dict.get("state", {}) or {},
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

    def _convert_to_session(
        self,
        api_session: Any,
        app_name: str,
    ) -> Session:
        """Convert API session response to our Session dataclass."""
        # Handle dict responses (from create_session, etc.)
        if isinstance(api_session, dict):
            return self._convert_dict_to_session(api_session, app_name)
        
        # Handle object responses
        # Extract session ID from resource name or id attribute
        if hasattr(api_session, 'id'):
            session_id = api_session.id
        elif hasattr(api_session, 'name'):
            session_id = api_session.name.split("/")[-1]
        else:
            session_id = ""
        
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
                        timestamp=datetime.utcnow(),
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
        try:
            agent_engine = self._get_agent_engine()
            
            # Create session using agent_engine object method
            # Per docs: agent_engine.create_session(user_id="...")
            api_session = agent_engine.create_session(user_id=user_id)
            
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
        try:
            agent_engine = self._get_agent_engine()
            
            # Get session using agent_engine object method
            api_session = agent_engine.get_session(
                user_id=user_id,
                session_id=session_id,
            )
            
            if not api_session:
                return None
                
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
        
        Note: The agent_engine doesn't have a direct append_event method.
        Events are typically added via query/stream_query calls.
        This method will fetch the current session state.
        
        Args:
            session_id: Session ID
            user_id: Discord user ID  
            app_name: Persona name
            event: Event to append
            
        Returns:
            Updated session
        """
        try:
            # For now, just return the current session
            # Events are appended automatically during query calls
            session = await self.get_session(session_id, user_id, app_name)
            if not session:
                raise ValueError(f"Session {session_id} not found")
                
            logger.debug(f"Fetched session {session_id} (events managed by query)")
            return session
            
        except Exception as e:
            logger.error(f"Failed to get session {session_id}: {e}")
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
        try:
            agent_engine = self._get_agent_engine()
            
            # List sessions using agent_engine object method
            response = agent_engine.list_sessions(user_id=user_id)
            
            sessions = []
            if response:
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
        try:
            agent_engine = self._get_agent_engine()
            
            # Delete session using agent_engine object method
            agent_engine.delete_session(
                user_id=user_id,
                session_id=session_id,
            )
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
        
        Note: State updates typically happen during query calls.
        This method fetches the current session.
        
        Args:
            session_id: Session ID
            user_id: Discord user ID
            app_name: Persona name
            state: New state data
            
        Returns:
            Updated session
        """
        try:
            # State is managed by the agent during query calls
            # For now, just fetch and return current session
            session = await self.get_session(session_id, user_id, app_name)
            if not session:
                raise ValueError(f"Session {session_id} not found")
            
            logger.debug(f"Fetched session {session_id} (state managed by agent)")
            return session
            
        except Exception as e:
            logger.error(f"Failed to get session state {session_id}: {e}")
            raise
