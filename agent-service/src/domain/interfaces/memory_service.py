"""Abstract interface for memory storage (long-term memories across sessions)."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class Memory:
    """
    Represents a long-term memory entry.
    
    Attributes:
        id: Unique identifier for the memory
        fact: The actual memory content/fact
        scope: Dictionary defining the memory scope (persona_name, user_id, etc.)
    """
    id: str
    fact: str
    scope: dict[str, str]


@dataclass
class MemoryScope:
    """
    Defines the scope for memory storage and retrieval.
    
    Our scoping strategy:
    - Shared persona memories: scope = {app_name: persona_name}
    - Per-user memories: scope = {app_name: persona_name, user_id: discord_user_id}
    """
    persona_name: str
    user_id: str | None = None
    
    def to_dict(self) -> dict[str, str]:
        """Convert to scope dictionary for API calls."""
        scope = {"app_name": self.persona_name}
        if self.user_id:
            scope["user_id"] = self.user_id
        return scope


class MemoryService(ABC):
    """
    Abstract interface for long-term memory management.
    
    Memory Bank stores personalized information that can be accessed
    across multiple sessions for a particular user/persona combination.
    """

    @abstractmethod
    async def generate_memories(
        self,
        scope: MemoryScope,
        conversation_history: list[dict[str, str]],
    ) -> list[Memory]:
        """
        Generate and store memories from a conversation.
        
        This extracts meaningful facts from the conversation and stores them
        as long-term memories.
        
        Args:
            scope: Memory scope (persona + optional user)
            conversation_history: List of messages [{role: str, content: str}]
            
        Returns:
            List of generated memories
        """
        pass

    @abstractmethod
    async def generate_memories_from_session(
        self,
        scope: MemoryScope,
        session_id: str,
    ) -> list[Memory]:
        """
        Generate memories from an existing Vertex AI session.
        
        This is more efficient than passing conversation history directly
        as Vertex AI can access the session events directly.
        
        Args:
            scope: Memory scope (persona + optional user)
            session_id: Full session resource name or session ID
            
        Returns:
            List of generated memories
        """
        pass

    @abstractmethod
    async def retrieve_memories(
        self,
        scope: MemoryScope,
        query: str | None = None,
        limit: int = 10,
    ) -> list[Memory]:
        """
        Retrieve memories for a given scope.
        
        Args:
            scope: Memory scope to retrieve from
            query: Optional query for similarity search
            limit: Maximum number of memories to return
            
        Returns:
            List of relevant memories
        """
        pass

    @abstractmethod
    async def create_memory(
        self,
        scope: MemoryScope,
        fact: str,
    ) -> Memory:
        """
        Create a single memory directly.
        
        Use this when the agent explicitly wants to save something.
        
        Args:
            scope: Memory scope
            fact: The fact/memory to store
            
        Returns:
            Created memory
        """
        pass

    @abstractmethod
    async def delete_memory(self, memory_id: str) -> bool:
        """
        Delete a specific memory.
        
        Args:
            memory_id: ID of memory to delete
            
        Returns:
            True if deleted, False if not found
        """
        pass
