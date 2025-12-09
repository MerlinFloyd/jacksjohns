"""Abstract interface for session management (conversation history)."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class SessionEvent:
    """
    Represents a single event in a session (message or action).
    
    Attributes:
        role: 'user' or 'assistant' (or 'system' for tool calls)
        content: The message content
        timestamp: When the event occurred
        metadata: Additional event metadata (tool calls, etc.)
    """
    role: str
    content: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Session:
    """
    Represents a conversation session.
    
    Attributes:
        id: Unique session identifier
        user_id: Discord user ID
        app_name: Persona name (used as app_name in Agent Engine)
        events: Chronological list of session events
        state: Temporary session state data
        created_at: Session creation time
        updated_at: Last update time
    """
    id: str
    user_id: str
    app_name: str  # Persona name
    events: list[SessionEvent] = field(default_factory=list)
    state: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    
    def get_conversation_history(self) -> list[dict[str, str]]:
        """Get conversation as a list of {role, content} dicts."""
        return [
            {"role": event.role, "content": event.content}
            for event in self.events
        ]


class SessionService(ABC):
    """
    Abstract interface for session management.
    
    Sessions maintain the history of interactions between a user
    and a persona within a single conversation.
    """

    @abstractmethod
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
        pass

    @abstractmethod
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
        pass

    @abstractmethod
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
        pass

    @abstractmethod
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
        pass

    @abstractmethod
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
        pass

    @abstractmethod
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
        pass
