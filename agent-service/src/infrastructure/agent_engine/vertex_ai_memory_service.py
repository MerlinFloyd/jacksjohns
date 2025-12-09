"""
Vertex AI Memory Bank Service implementation.

This implements the MemoryService interface using Vertex AI Agent Engine's
Memory Bank feature for persistent, long-term memory storage.
"""

import logging
from typing import Any

import vertexai
from google.genai import types as genai_types

from ...domain.interfaces.memory_service import Memory, MemoryScope, MemoryService
from .agent_engine_manager import AgentEngineManager

logger = logging.getLogger(__name__)


class VertexAiMemoryService(MemoryService):
    """
    Vertex AI Memory Bank implementation of MemoryService.
    
    Memory Bank stores personalized information that can be accessed
    across multiple sessions. This implementation uses the Vertex AI
    Agent Engine SDK to interact with Memory Bank.
    """

    def __init__(self, agent_engine_manager: AgentEngineManager):
        """
        Initialize the Vertex AI Memory Service.
        
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

    async def generate_memories(
        self,
        scope: MemoryScope,
        conversation_history: list[dict[str, str]],
    ) -> list[Memory]:
        """
        Generate and store memories from a conversation.
        
        Uses the Memory Bank's GenerateMemories API to extract meaningful
        facts from the conversation and store them as long-term memories.
        
        Args:
            scope: Memory scope (persona + optional user)
            conversation_history: List of messages [{role: str, content: str}]
            
        Returns:
            List of generated memories
        """
        self._ensure_initialized()
        
        if not conversation_history:
            logger.debug("Empty conversation history, no memories to generate")
            return []
        
        try:
            # Convert conversation to Content format
            contents = []
            for msg in conversation_history:
                role = "user" if msg["role"] == "user" else "model"
                contents.append(
                    genai_types.Content(
                        role=role,
                        parts=[genai_types.Part(text=msg["content"])]
                    )
                )
            
            # Call GenerateMemories API
            agent_engine_name = self._get_agent_engine_name()
            
            response = self._client.agent_engines.generate_memories(
                name=agent_engine_name,
                vertex_session_source=genai_types.VertexSessionSource(
                    contents=contents,
                ),
                scope=scope.to_dict(),
            )
            
            # Convert response to Memory objects
            memories = []
            if response and hasattr(response, 'memories'):
                for mem in response.memories:
                    memories.append(Memory(
                        id=mem.name if hasattr(mem, 'name') else "",
                        fact=mem.fact if hasattr(mem, 'fact') else str(mem),
                        scope=scope.to_dict(),
                    ))
            
            logger.info(
                f"Generated {len(memories)} memories for scope={scope.to_dict()}"
            )
            return memories
            
        except Exception as e:
            logger.error(f"Failed to generate memories: {e}")
            raise

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
        self._ensure_initialized()
        
        try:
            agent_engine_name = self._get_agent_engine_name()
            
            # Use similarity search if query provided, otherwise list all
            if query:
                response = self._client.agent_engines.retrieve_memories(
                    name=agent_engine_name,
                    scope=scope.to_dict(),
                    similarity_search_params=genai_types.SimilaritySearchParams(
                        query=query,
                        top_k=limit,
                    ),
                )
            else:
                response = self._client.agent_engines.retrieve_memories(
                    name=agent_engine_name,
                    scope=scope.to_dict(),
                )
            
            # Convert response to Memory objects
            memories = []
            if response and hasattr(response, 'memories'):
                for mem in response.memories:
                    memories.append(Memory(
                        id=mem.name if hasattr(mem, 'name') else "",
                        fact=mem.fact if hasattr(mem, 'fact') else str(mem),
                        scope=scope.to_dict(),
                    ))
            
            logger.debug(
                f"Retrieved {len(memories)} memories for scope={scope.to_dict()}"
            )
            return memories[:limit]
            
        except Exception as e:
            logger.error(f"Failed to retrieve memories: {e}")
            raise

    async def create_memory(
        self,
        scope: MemoryScope,
        fact: str,
    ) -> Memory:
        """
        Create a single memory directly.
        
        Args:
            scope: Memory scope
            fact: The fact/memory to store
            
        Returns:
            Created memory
        """
        self._ensure_initialized()
        
        try:
            agent_engine_name = self._get_agent_engine_name()
            
            response = self._client.agent_engines.create_memory(
                parent=agent_engine_name,
                memory=genai_types.Memory(
                    fact=fact,
                    scope=scope.to_dict(),
                ),
            )
            
            memory = Memory(
                id=response.name if hasattr(response, 'name') else "",
                fact=fact,
                scope=scope.to_dict(),
            )
            
            logger.info(f"Created memory: {fact[:50]}... for scope={scope.to_dict()}")
            return memory
            
        except Exception as e:
            logger.error(f"Failed to create memory: {e}")
            raise

    async def delete_memory(self, memory_id: str) -> bool:
        """
        Delete a specific memory.
        
        Args:
            memory_id: ID of memory to delete
            
        Returns:
            True if deleted, False if not found
        """
        self._ensure_initialized()
        
        try:
            self._client.agent_engines.delete_memory(name=memory_id)
            logger.info(f"Deleted memory: {memory_id}")
            return True
        except Exception as e:
            logger.warning(f"Failed to delete memory {memory_id}: {e}")
            return False
