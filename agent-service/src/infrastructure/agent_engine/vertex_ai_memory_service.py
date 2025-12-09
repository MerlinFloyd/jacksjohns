"""
Vertex AI Memory Bank Service implementation.

This implements the MemoryService interface using Vertex AI Agent Engine's
Memory Bank feature for persistent, long-term memory storage.

Correct API signatures (from vertexai._genai.agent_engines):
- create_memory(*, name: str, fact: str, scope: dict[str, str], config=None) -> AgentEngineMemoryOperation
- retrieve_memories(*, name: str, scope: dict[str, str], similarity_search_params=None, ...) -> Iterator[RetrievedMemory]
- generate_memories(*, name: str, direct_contents_source=None, vertex_session_source=None, scope=None, ...) -> AgentEngineGenerateMemoriesOperation

Where similarity_search_params is a dict with: {"search_query": str, "top_k": int}
And direct_contents_source is a dict with: {"events": [{"content": Content}]}
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
            # Convert conversation to events for direct_contents_source
            # Format: {"events": [{"content": Content}]}
            events = []
            for msg in conversation_history:
                role = "user" if msg["role"] == "user" else "model"
                events.append({
                    "content": genai_types.Content(
                        role=role,
                        parts=[genai_types.Part(text=msg["content"])]
                    )
                })
            
            # Call GenerateMemories API with direct_contents_source
            agent_engine_name = self._get_agent_engine_name()
            
            operation = self._client.agent_engines.generate_memories(
                name=agent_engine_name,
                direct_contents_source={"events": events},
                scope=scope.to_dict(),
            )
            
            # The operation returns with response field containing GenerateMemoriesResponse
            # GenerateMemoriesResponse has generated_memories list
            response = operation
            if hasattr(operation, 'response') and operation.response is not None:
                response = operation.response
            
            # Convert response to Memory objects
            # Response structure: response.generated_memories -> list of GenerateMemoriesResponseGeneratedMemory
            # Each has .memory with the actual Memory object
            memories = []
            if response:
                # Try generated_memories first (correct field name from API)
                gen_mems = getattr(response, 'generated_memories', None) or []
                for gen_mem in gen_mems:
                    # Extract the actual memory from the generated memory wrapper
                    mem = getattr(gen_mem, 'memory', gen_mem)
                    if mem:
                        memories.append(Memory(
                            id=getattr(mem, 'name', "") or "",
                            fact=getattr(mem, 'fact', "") or str(mem),
                            scope=scope.to_dict(),
                        ))
            
            logger.info(
                f"Generated {len(memories)} memories for scope={scope.to_dict()}"
            )
            return memories
            
        except Exception as e:
            logger.error(f"Failed to generate memories: {e}")
            raise

    async def generate_memories_from_session(
        self,
        scope: MemoryScope,
        session_id: str,
    ) -> list[Memory]:
        """
        Generate memories from an existing Vertex AI session.
        
        Uses vertex_session_source which allows Vertex AI to fetch
        session events directly, more efficient than passing history manually.
        
        Args:
            scope: Memory scope (persona + optional user)
            session_id: Full session resource name or session ID
            
        Returns:
            List of generated memories
        """
        self._ensure_initialized()
        
        try:
            agent_engine_name = self._get_agent_engine_name()
            
            # Build full session resource name if only ID provided
            if not session_id.startswith("projects/"):
                session_name = f"{agent_engine_name}/sessions/{session_id}"
            else:
                session_name = session_id
            
            logger.info(f"Generating memories from session: {session_name}")
            
            # Call GenerateMemories API with vertex_session_source
            operation = self._client.agent_engines.generate_memories(
                name=agent_engine_name,
                vertex_session_source={"session": session_name},
                scope=scope.to_dict(),
            )
            
            # The operation returns with response field containing GenerateMemoriesResponse
            # GenerateMemoriesResponse has generated_memories list
            response = operation
            if hasattr(operation, 'response') and operation.response is not None:
                response = operation.response
            
            # Convert response to Memory objects
            # Response structure: response.generated_memories -> list of GenerateMemoriesResponseGeneratedMemory
            # Each has .memory with the actual Memory object
            memories = []
            if response:
                # Try generated_memories first (correct field name from API)
                gen_mems = getattr(response, 'generated_memories', None) or []
                for gen_mem in gen_mems:
                    # Extract the actual memory from the generated memory wrapper
                    mem = getattr(gen_mem, 'memory', gen_mem)
                    if mem:
                        memories.append(Memory(
                            id=getattr(mem, 'name', "") or "",
                            fact=getattr(mem, 'fact', "") or str(mem),
                            scope=scope.to_dict(),
                        ))
            
            logger.info(
                f"Generated {len(memories)} memories from session for scope={scope.to_dict()}"
            )
            return memories
            
        except Exception as e:
            logger.error(f"Failed to generate memories from session: {e}")
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
            
            # Use similarity search if query provided, otherwise simple retrieval
            # Correct format: similarity_search_params={"search_query": str, "top_k": int}
            if query:
                response = self._client.agent_engines.retrieve_memories(
                    name=agent_engine_name,
                    scope=scope.to_dict(),
                    similarity_search_params={
                        "search_query": query,
                        "top_k": limit,
                    },
                )
            else:
                response = self._client.agent_engines.retrieve_memories(
                    name=agent_engine_name,
                    scope=scope.to_dict(),
                )
            
            # Response is an iterator of RetrieveMemoriesResponseRetrievedMemory
            # Each item has a 'memory' attribute with the actual memory
            memories = []
            for retrieved_mem in response:
                # Handle both dict and object responses
                if isinstance(retrieved_mem, dict):
                    mem = retrieved_mem.get('memory', retrieved_mem)
                    memories.append(Memory(
                        id=mem.get('name', ""),
                        fact=mem.get('fact', str(mem)),
                        scope=scope.to_dict(),
                    ))
                else:
                    # Object response - memory is in .memory attribute
                    mem = getattr(retrieved_mem, 'memory', retrieved_mem)
                    memories.append(Memory(
                        id=getattr(mem, 'name', "") or "",
                        fact=getattr(mem, 'fact', "") or str(mem),
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
            
            # Correct signature: create_memory(*, name: str, fact: str, scope: dict[str, str])
            operation = self._client.agent_engines.create_memory(
                name=agent_engine_name,
                fact=fact,
                scope=scope.to_dict(),
            )
            
            # Operation may have a response attribute with the created memory
            response = operation
            if hasattr(operation, 'response') and operation.response is not None:
                response = operation.response
            
            # Extract memory ID from response
            memory_id = ""
            if hasattr(response, 'name'):
                memory_id = response.name or ""
            elif isinstance(response, dict):
                memory_id = response.get('name', "")
            
            memory = Memory(
                id=memory_id,
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
