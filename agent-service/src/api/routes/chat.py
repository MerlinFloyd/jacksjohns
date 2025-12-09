"""Chat API endpoints with session and memory support."""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from google import genai
from google.genai import types as genai_types

from ..dependencies import (
    get_persona_repository,
    get_session_service,
    get_memory_service,
)
from ...config.settings import get_settings
from ...domain.interfaces import (
    PersonaRepository,
    SessionService,
    MemoryService,
    MemoryScope,
    SessionEvent,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/chat", tags=["chat"])


# Request/Response Models
class ChatRequest(BaseModel):
    """Request model for chat messages."""
    persona_name: str = Field(..., description="Name of the persona to chat with")
    user_id: str = Field(..., description="Discord user ID")
    message: str = Field(..., min_length=1, max_length=4000, description="User message")
    session_id: str | None = Field(None, description="Existing session ID (optional)")


class ChatResponse(BaseModel):
    """Response model for chat messages."""
    response: str = Field(..., description="AI response")
    session_id: str = Field(..., description="Session ID for continuing the conversation")
    persona_name: str = Field(..., description="Persona name used")
    memories_used: int = Field(0, description="Number of memories retrieved and used")


class SessionListResponse(BaseModel):
    """Response model for listing sessions."""
    session_id: str
    user_id: str
    persona_name: str
    event_count: int
    created_at: str


class MemoryResponse(BaseModel):
    """Response model for a memory."""
    id: str
    fact: str
    scope: dict[str, str]


# Helper functions
def _build_system_prompt(
    personality: str,
    memories: list[Any],
) -> str:
    """Build the system prompt including personality and memories."""
    prompt_parts = [
        f"You are an AI persona with the following personality:\n{personality}\n",
        "\nIMPORTANT: Stay in character at all times. Respond as this persona would.\n",
    ]
    
    if memories:
        prompt_parts.append("\n--- Your Long-Term Memories ---")
        prompt_parts.append("Use these memories to personalize your responses:\n")
        for mem in memories:
            prompt_parts.append(f"- {mem.fact}")
        prompt_parts.append("\n--- End of Memories ---\n")
    
    return "\n".join(prompt_parts)


async def _generate_response(
    message: str,
    system_prompt: str,
    conversation_history: list[dict[str, str]],
) -> str:
    """Generate AI response using Gemini."""
    settings = get_settings()
    
    client = genai.Client(
        vertexai=True,
        project=settings.gcp_project_id,
        location=settings.gcp_region,
    )
    
    # Build the content list
    contents = []
    
    # Add conversation history
    for msg in conversation_history:
        role = "user" if msg["role"] == "user" else "model"
        contents.append(
            genai_types.Content(
                role=role,
                parts=[genai_types.Part(text=msg["content"])],
            )
        )
    
    # Add current message
    contents.append(
        genai_types.Content(
            role="user",
            parts=[genai_types.Part(text=message)],
        )
    )
    
    # Generate response
    response = client.models.generate_content(
        model=settings.gemini_model,
        contents=contents,
        config=genai_types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=0.9,
            top_p=0.95,
            max_output_tokens=1024,
        ),
    )
    
    return response.text


# Endpoints
@router.post("", response_model=ChatResponse)
async def chat(
    data: ChatRequest,
    persona_repo: PersonaRepository = Depends(get_persona_repository),
    session_service: SessionService = Depends(get_session_service),
    memory_service: MemoryService = Depends(get_memory_service),
) -> ChatResponse:
    """
    Chat with a persona.
    
    This endpoint:
    1. Retrieves the persona's personality
    2. Gets or creates a session for conversation history
    3. Retrieves relevant memories for personalization
    4. Generates an AI response
    5. Stores the interaction in the session
    
    Args:
        data: Chat request data
        
    Returns:
        AI response with session info
    """
    # Get persona
    persona = await persona_repo.get_by_name(data.persona_name)
    if not persona:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Persona '{data.persona_name}' not found",
        )
    
    # Get or create session
    session = None
    if data.session_id and session_service:
        session = await session_service.get_session(
            session_id=data.session_id,
            user_id=data.user_id,
            app_name=data.persona_name,
        )
    
    if not session and session_service:
        session = await session_service.create_session(
            user_id=data.user_id,
            app_name=data.persona_name,
        )
    
    # Get conversation history from session
    conversation_history = []
    if session:
        conversation_history = session.get_conversation_history()
    
    # Retrieve memories - both shared and user-specific
    memories = []
    memories_count = 0
    
    if memory_service:
        try:
            # Get shared persona memories
            shared_scope = MemoryScope(persona_name=data.persona_name)
            shared_memories = await memory_service.retrieve_memories(
                scope=shared_scope,
                query=data.message,
                limit=5,
            )
            memories.extend(shared_memories)
            
            # Get user-specific memories
            user_scope = MemoryScope(
                persona_name=data.persona_name,
                user_id=data.user_id,
            )
            user_memories = await memory_service.retrieve_memories(
                scope=user_scope,
                query=data.message,
                limit=5,
            )
            memories.extend(user_memories)
            memories_count = len(memories)
            
        except Exception as e:
            logger.warning(f"Failed to retrieve memories: {e}")
    
    # Build system prompt with personality and memories
    system_prompt = _build_system_prompt(persona.personality, memories)
    
    # Generate response
    try:
        ai_response = await _generate_response(
            message=data.message,
            system_prompt=system_prompt,
            conversation_history=conversation_history,
        )
    except Exception as e:
        logger.error(f"Failed to generate response: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate AI response",
        )
    
    # Store interaction in session
    if session and session_service:
        try:
            # Add user message
            await session_service.append_event(
                session_id=session.id,
                user_id=data.user_id,
                app_name=data.persona_name,
                event=SessionEvent(role="user", content=data.message),
            )
            
            # Add assistant response
            await session_service.append_event(
                session_id=session.id,
                user_id=data.user_id,
                app_name=data.persona_name,
                event=SessionEvent(role="assistant", content=ai_response),
            )
        except Exception as e:
            logger.warning(f"Failed to store session events: {e}")
    
    logger.info(
        f"Chat completed: persona={data.persona_name}, user={data.user_id}, "
        f"session={session.id if session else 'none'}, memories={memories_count}"
    )
    
    return ChatResponse(
        response=ai_response,
        session_id=session.id if session else "in-memory",
        persona_name=data.persona_name,
        memories_used=memories_count,
    )


@router.post("/end-session")
async def end_session(
    persona_name: str,
    user_id: str,
    session_id: str,
    generate_memories: bool = True,
    session_service: SessionService = Depends(get_session_service),
    memory_service: MemoryService = Depends(get_memory_service),
) -> dict[str, Any]:
    """
    End a chat session and optionally generate memories.
    
    This is called when a conversation ends to:
    1. Generate long-term memories from the conversation
    2. Clean up the session
    
    Args:
        persona_name: Persona name
        user_id: Discord user ID
        session_id: Session ID to end
        generate_memories: Whether to extract memories from the conversation
        
    Returns:
        Status and memory generation results
    """
    if not session_service:
        return {"status": "no_session_service", "memories_generated": 0}
    
    # Get the session
    session = await session_service.get_session(
        session_id=session_id,
        user_id=user_id,
        app_name=persona_name,
    )
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{session_id}' not found",
        )
    
    memories_generated = 0
    
    # Generate memories from the conversation
    if generate_memories and memory_service and session.events:
        try:
            conversation_history = session.get_conversation_history()
            
            # Generate user-specific memories
            user_scope = MemoryScope(
                persona_name=persona_name,
                user_id=user_id,
            )
            memories = await memory_service.generate_memories(
                scope=user_scope,
                conversation_history=conversation_history,
            )
            memories_generated = len(memories)
            
            logger.info(
                f"Generated {memories_generated} memories from session {session_id}"
            )
        except Exception as e:
            logger.warning(f"Failed to generate memories: {e}")
    
    # Delete the session
    await session_service.delete_session(
        session_id=session_id,
        user_id=user_id,
        app_name=persona_name,
    )
    
    return {
        "status": "completed",
        "session_id": session_id,
        "memories_generated": memories_generated,
    }


@router.get("/sessions", response_model=list[SessionListResponse])
async def list_sessions(
    persona_name: str,
    user_id: str,
    session_service: SessionService = Depends(get_session_service),
) -> list[SessionListResponse]:
    """
    List all sessions for a user-persona combination.
    
    Args:
        persona_name: Persona name
        user_id: Discord user ID
        
    Returns:
        List of sessions
    """
    if not session_service:
        return []
    
    sessions = await session_service.list_sessions(
        user_id=user_id,
        app_name=persona_name,
    )
    
    return [
        SessionListResponse(
            session_id=s.id,
            user_id=s.user_id,
            persona_name=s.app_name,
            event_count=len(s.events),
            created_at=s.created_at.isoformat(),
        )
        for s in sessions
    ]


@router.get("/memories", response_model=list[MemoryResponse])
async def list_memories(
    persona_name: str,
    user_id: str | None = None,
    query: str | None = None,
    limit: int = 20,
    memory_service: MemoryService = Depends(get_memory_service),
) -> list[MemoryResponse]:
    """
    List memories for a persona (and optionally user).
    
    Args:
        persona_name: Persona name
        user_id: Optional user ID for user-specific memories
        query: Optional query for similarity search
        limit: Maximum number of memories to return
        
    Returns:
        List of memories
    """
    if not memory_service:
        return []
    
    scope = MemoryScope(persona_name=persona_name, user_id=user_id)
    
    memories = await memory_service.retrieve_memories(
        scope=scope,
        query=query,
        limit=limit,
    )
    
    return [
        MemoryResponse(
            id=m.id,
            fact=m.fact,
            scope=m.scope,
        )
        for m in memories
    ]


@router.post("/memories")
async def create_memory(
    persona_name: str,
    fact: str,
    user_id: str | None = None,
    memory_service: MemoryService = Depends(get_memory_service),
) -> MemoryResponse:
    """
    Create a memory directly.
    
    Use this to manually add important facts about a persona or user.
    
    Args:
        persona_name: Persona name
        fact: The fact/memory to store
        user_id: Optional user ID for user-specific memory
        
    Returns:
        Created memory
    """
    if not memory_service:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Memory service not available",
        )
    
    scope = MemoryScope(persona_name=persona_name, user_id=user_id)
    
    memory = await memory_service.create_memory(scope=scope, fact=fact)
    
    return MemoryResponse(
        id=memory.id,
        fact=memory.fact,
        scope=memory.scope,
    )
