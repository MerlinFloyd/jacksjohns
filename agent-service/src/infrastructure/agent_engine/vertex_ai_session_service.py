"""
Vertex AI Session Service implementation.

This implements the SessionService interface using Vertex AI Agent Engine's
Sessions feature for conversation history management.

Based on official Google Cloud documentation:
https://cloud.google.com/vertex-ai/generative-ai/docs/agent-engine/sessions/manage-sessions-api

API signatures (from vertexai._genai.sessions.Sessions):
- create(*, name: str, user_id: str, config=None) -> AgentEngineSessionOperation
- get(*, name: str, config=None) -> Session
- list(*, name: str, config=None) -> Iterator[Session]
- delete(*, name: str, config=None) -> DeleteAgentEngineSessionOperation
- events.append(*, name: str, author: str, invocation_id: str, timestamp: datetime, config=None)

Where:
- For create/list: name = agent_engine resource name
- For get/delete/events.append: name = full session resource name
"""

import datetime
import logging
import time
from typing import Any

import vertexai

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
        # Handle None
        if api_session is None:
            raise ValueError("API session is None")
            
        # Handle dict responses
        if isinstance(api_session, dict):
            session_id = api_session.get("id", "")
            if not session_id and "name" in api_session:
                session_id = api_session["name"].split("/")[-1]
            user_id = api_session.get("user_id", api_session.get("userId", ""))
            state = api_session.get("session_state", api_session.get("sessionState", {})) or {}
            return Session(
                id=session_id,
                user_id=user_id,
                app_name=app_name,
                events=[],
                state=state,
                created_at=datetime.datetime.utcnow(),
                updated_at=datetime.datetime.utcnow(),
            )
        
        # Handle pydantic/object responses (from vertexai._genai.types.common.Session)
        # Extract session ID from resource name
        session_name = getattr(api_session, 'name', None)
        if session_name:
            session_id = session_name.split("/")[-1]
        else:
            session_id = ""
        
        # Extract user_id from the session
        user_id = getattr(api_session, 'user_id', "")
        
        # Get session state
        state = getattr(api_session, 'session_state', {}) or {}
        
        return Session(
            id=session_id,
            user_id=user_id,
            app_name=app_name,
            events=[],
            state=state,
            created_at=datetime.datetime.utcnow(),
            updated_at=datetime.datetime.utcnow(),
        )

    def _wait_for_operation(self, operation: Any, timeout: float = 30.0) -> Any:
        """
        Wait for a long-running operation to complete.
        
        Args:
            operation: The operation object (AgentEngineSessionOperation)
            timeout: Maximum time to wait in seconds
            
        Returns:
            The response from the operation
        """
        # If operation has response directly, return it
        if hasattr(operation, 'response') and operation.response is not None:
            return operation.response
            
        # If operation has done field, check if complete
        if hasattr(operation, 'done') and operation.done:
            if hasattr(operation, 'response'):
                return operation.response
            return operation
            
        # The SDK might handle waiting automatically, return the operation itself
        # and let the caller handle it
        return operation

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
            # Signature: create(*, name: str, user_id: str, config=None) -> AgentEngineSessionOperation
            operation = self._client.agent_engines.sessions.create(
                name=agent_engine_name,
                user_id=user_id,
            )
            
            # The operation returns with response field containing the session
            # or we need to wait for it
            api_session = self._wait_for_operation(operation)
            
            # If api_session is still an operation, get the response
            if hasattr(api_session, 'response') and api_session.response is not None:
                api_session = api_session.response
            
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
            
            # Signature: get(*, name: str, config=None) -> Session
            api_session = self._client.agent_engines.sessions.get(
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
            
            # Signature: events.append(*, name: str, author: str, invocation_id: str, 
            #                          timestamp: datetime, config=None)
            self._client.agent_engines.sessions.events.append(
                name=session_name,
                author=role,
                invocation_id="1",
                timestamp=datetime.datetime.now(tz=datetime.timezone.utc),
                config={
                    "content": {
                        "role": role,
                        "parts": [{"text": event.content}],
                    },
                },
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
            
            # Signature: list(*, name: str, config=None) -> Iterator[Session]
            # To filter by user: config={"filter": "user_id=USER_ID"}
            response = self._client.agent_engines.sessions.list(
                name=agent_engine_name,
                config={"filter": f'user_id="{user_id}"'},
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
            
            # Signature: delete(*, name: str, config=None) -> DeleteAgentEngineSessionOperation
            self._client.agent_engines.sessions.delete(name=session_name)
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
        
        Note: The API doesn't have a direct update method for state.
        State is typically managed during query/streaming calls.
        
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
            # Fetch and return current session
            # State updates happen through agent query calls
            session = await self.get_session(session_id, user_id, app_name)
            if not session:
                raise ValueError(f"Session {session_id} not found")
            
            logger.debug(f"Fetched session {session_id} (state managed by agent)")
            return session
            
        except Exception as e:
            logger.error(f"Failed to get session state {session_id}: {e}")
            raise
