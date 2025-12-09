"""Chat API endpoints with session and memory support."""

import logging
from dataclasses import dataclass
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from google import genai
from google.genai import types as genai_types

from ..dependencies import (
    get_persona_repository,
    get_session_service,
    get_memory_service,
    get_channel_session_repository,
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


# Channel chat system prompt addition
CHANNEL_CHAT_INSTRUCTIONS = """
You are in a Discord channel where multiple users may be chatting.
The user's display name will be included with their message in format: [DisplayName]: message

RESPOND when:
- Someone directly addresses you by name
- Someone asks a question that seems directed at you
- The conversation naturally invites your input
- Someone is clearly expecting a response from you
- The message is a direct question or request

DO NOT RESPOND when:
- Users are chatting among themselves without involving you
- The message is a simple acknowledgment like "ok", "thanks", "lol"
- You've recently responded and the conversation has moved on without you
- The message is clearly directed at another user

If you determine you should NOT respond, return ONLY the text "[NO_RESPONSE]" (exactly as written).
Otherwise, respond normally in character.
"""


# Request/Response Models
class ChatRequest(BaseModel):
    """Request model for chat messages."""
    persona_name: str = Field(..., description="Name of the persona to chat with")
    user_id: str = Field(..., description="Discord user ID")
    message: str = Field(..., min_length=1, max_length=4000, description="User message")
    session_id: str | None = Field(None, description="Existing session ID (optional)")
    # New fields for channel chat mode
    user_display_name: str | None = Field(None, description="User's display name in Discord")
    is_channel_chat: bool = Field(False, description="Whether this is from a persona channel (enables selective response)")
    channel_id: str | None = Field(None, description="Discord channel ID for session persistence")


class ChatResponse(BaseModel):
    """Response model for chat messages."""
    response: str = Field(..., description="AI response")
    session_id: str = Field(..., description="Session ID for continuing the conversation")
    persona_name: str = Field(..., description="Persona name used")
    memories_used: int = Field(0, description="Number of memories retrieved and used")
    memories_saved: int = Field(0, description="Number of memories saved during this interaction")
    should_respond: bool = Field(True, description="Whether the bot should send this response")


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


class DeleteMemoriesResponse(BaseModel):
    """Response model for deleting memories."""
    deleted_count: int
    persona_name: str
    user_id: str | None


class ErrorInterpretRequest(BaseModel):
    """Request model for error interpretation."""
    error_message: str = Field(..., description="The error message to interpret")
    error_context: str | None = Field(None, description="Additional context about what was being attempted")
    persona_name: str | None = Field(None, description="If provided, respond in character as this persona")


class ErrorInterpretResponse(BaseModel):
    """Response model for error interpretation."""
    interpretation: str = Field(..., description="User-friendly interpretation of the error")


# Memory tool instructions to add to system prompts
MEMORY_TOOL_INSTRUCTIONS = """
--- Memory Tool ---
You have access to a save_memory tool. Use it when:
- The user explicitly asks you to remember something (e.g., "Remember that...", "Don't forget...")
- The user shares important personal information they'll want you to recall later
- Examples: their name, preferences, allergies, important dates, relationships

IMPORTANT: When saving a memory, ALWAYS write it in THIRD PERSON about THE USER.
- Correct: "The user has blue hair", "The user loves pizza", "The user's birthday is March 5th"
- Wrong: "I have blue hair", "I love pizza", "My birthday is March 5th"
Only save genuinely important facts, not every detail of the conversation.
"""


# Helper functions
def _build_system_prompt(
    personality: str,
    memories: list[Any],
) -> str:
    """Build the system prompt including personality and memories."""
    prompt_parts = [
        f"You are an AI persona with the following personality:\n{personality}\n",
        "\nIMPORTANT: Stay in character at all times. Respond as this persona would.\n",
        MEMORY_TOOL_INSTRUCTIONS,
    ]
    
    if memories:
        prompt_parts.append("\n--- Facts About The User ---")
        prompt_parts.append("These are facts you remember about THE USER you are talking to. Use them to personalize your responses:\n")
        for mem in memories:
            prompt_parts.append(f"- {mem.fact}")
        prompt_parts.append("\n--- End of User Facts ---\n")
    
    return "\n".join(prompt_parts)


def _build_channel_system_prompt(
    persona_name: str,
    personality: str,
    memories: list[Any],
) -> str:
    """Build the system prompt for channel chat mode with selective response."""
    prompt_parts = [
        f"You are {persona_name}. {personality}\n",
        "\nIMPORTANT: Stay in character at all times. Respond as this persona would.\n",
        CHANNEL_CHAT_INSTRUCTIONS.replace("{persona_name}", persona_name),
        MEMORY_TOOL_INSTRUCTIONS,
    ]
    
    if memories:
        prompt_parts.append("\n--- Facts About The User ---")
        prompt_parts.append("These are facts you remember about THE USER you are talking to. Use them to personalize your responses:\n")
        for mem in memories:
            prompt_parts.append(f"- {mem.fact}")
        prompt_parts.append("\n--- End of User Facts ---\n")
    
    return "\n".join(prompt_parts)


@dataclass
class GenerateResponseResult:
    """Result from generating a response, including any memories to save."""
    text: str
    memories_to_save: list[str]  # List of facts to save as memories


async def _generate_response(
    message: str,
    system_prompt: str,
    conversation_history: list[dict[str, str]],
    enable_memory_tool: bool = True,
) -> GenerateResponseResult:
    """Generate AI response using Gemini with optional memory tool.
    
    Args:
        message: The user's message
        system_prompt: System prompt for the persona
        conversation_history: Previous messages in the conversation
        enable_memory_tool: Whether to enable the save_memory tool
        
    Returns:
        GenerateResponseResult with response text and any memories to save
    """
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
    
    # Define the save_memory tool
    save_memory_tool = genai_types.Tool(
        function_declarations=[
            genai_types.FunctionDeclaration(
                name="save_memory",
                description=(
                    "Save an important fact about the user to long-term memory. "
                    "Use this when the user explicitly asks you to remember something, "
                    "or shares important personal information they want you to recall later. "
                    "Examples: 'Remember that I love pizza', 'Don't forget my birthday is March 5th', "
                    "'My name is Alex', 'I'm allergic to peanuts'."
                ),
                parameters=genai_types.Schema(
                    type=genai_types.Type.OBJECT,
                    properties={
                        "fact": genai_types.Schema(
                            type=genai_types.Type.STRING,
                            description=(
                                "The fact to remember about the user. "
                                "ALWAYS write in THIRD PERSON about the user (e.g., 'The user loves pizza', 'The user has blue hair'). "
                                "Be concise but complete."
                            ),
                        ),
                    },
                    required=["fact"],
                ),
            )
        ]
    )
    
    # Build config with optional tool
    config = genai_types.GenerateContentConfig(
        system_instruction=system_prompt,
        temperature=0.9,
        top_p=0.95,
        max_output_tokens=1024,
    )
    
    if enable_memory_tool:
        config.tools = [save_memory_tool]
    
    # Generate response
    response = client.models.generate_content(
        model=settings.gemini_model,
        contents=contents,
        config=config,
    )
    
    # Extract text and any function calls
    response_text = ""
    memories_to_save = []
    
    if response.candidates and response.candidates[0].content.parts:
        for part in response.candidates[0].content.parts:
            # Check for text content
            if hasattr(part, 'text') and part.text:
                response_text += part.text
            # Check for function calls
            if hasattr(part, 'function_call') and part.function_call:
                fc = part.function_call
                if fc.name == "save_memory":
                    # Extract the fact from the function call args
                    fact = fc.args.get("fact", "")
                    if fact:
                        memories_to_save.append(fact)
                        logger.info(f"LLM requested to save memory: {fact[:50]}...")
    
    # If no text was found but we have a response, try response.text
    if not response_text and response.text:
        response_text = response.text
    
    return GenerateResponseResult(
        text=response_text,
        memories_to_save=memories_to_save,
    )


async def _interpret_error(
    error_message: str,
    error_context: str | None,
    persona_personality: str | None,
    persona_name: str | None,
) -> str:
    """Have the LLM interpret an error message for the user."""
    settings = get_settings()
    
    client = genai.Client(
        vertexai=True,
        project=settings.gcp_project_id,
        location=settings.gcp_region,
    )
    
    system_prompt = """You are helping a user understand an error that occurred.
Explain what went wrong in simple, friendly terms and suggest how to fix it if possible.
Be concise (1-2 sentences). Don't use technical jargon."""
    
    if persona_personality and persona_name:
        system_prompt += f"\n\nRespond in character as {persona_name}: {persona_personality}"
    
    user_message = f"Error: {error_message}"
    if error_context:
        user_message += f"\n\nContext: {error_context}"
    
    try:
        response = client.models.generate_content(
            model=settings.gemini_model,
            contents=[
                genai_types.Content(
                    role="user",
                    parts=[genai_types.Part(text=user_message)],
                )
            ],
            config=genai_types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=0.7,
                max_output_tokens=256,
            ),
        )
        # Ensure we return a non-None string
        text = response.text
        if text is None:
            # Try to extract text from parts if .text is None
            if response.candidates and response.candidates[0].content.parts:
                text = response.candidates[0].content.parts[0].text or ""
            else:
                text = f"Something went wrong: {error_message}"
        return text
    except Exception as e:
        logger.error(f"Failed to interpret error: {e}")
        return f"Something went wrong: {error_message}"


# Endpoints
@router.post("", response_model=ChatResponse)
async def chat(
    data: ChatRequest,
    persona_repo: PersonaRepository = Depends(get_persona_repository),
    session_service: SessionService = Depends(get_session_service),
    memory_service: MemoryService = Depends(get_memory_service),
    channel_session_repo=Depends(get_channel_session_repository),
) -> ChatResponse:
    """
    Chat with a persona.
    
    This endpoint:
    1. Retrieves the persona's personality
    2. Gets or creates a session for conversation history
    3. Retrieves relevant memories for personalization
    4. Generates an AI response
    5. Stores the interaction in the session
    
    For channel chat mode (is_channel_chat=True):
    - Uses channel_id for session persistence
    - Includes user display names in messages
    - Enables selective response (bot decides whether to respond)
    
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
    
    # Determine session ID - check channel session first if channel_id provided
    session_id = data.session_id
    if data.channel_id and channel_session_repo:
        stored_session = await channel_session_repo.get_session(data.channel_id)
        if stored_session:
            session_id = stored_session.session_id
    
    # Get or create session
    session = None
    if session_id and session_service:
        session = await session_service.get_session(
            session_id=session_id,
            user_id=data.user_id,
            app_name=data.persona_name,
        )
    
    if not session and session_service:
        session = await session_service.create_session(
            user_id=data.user_id,
            app_name=data.persona_name,
        )
        # Store channel session mapping if channel_id provided
        if data.channel_id and channel_session_repo and session:
            await channel_session_repo.set_session(
                channel_id=data.channel_id,
                session_id=session.id,
                persona_name=data.persona_name,
                user_id=data.user_id,
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
    
    # Build system prompt and format message based on mode
    if data.is_channel_chat:
        system_prompt = _build_channel_system_prompt(
            persona_name=persona.name,
            personality=persona.personality,
            memories=memories,
        )
        # Include user display name in message
        display_name = data.user_display_name or f"User {data.user_id[:8]}"
        formatted_message = f"[{display_name}]: {data.message}"
    else:
        system_prompt = _build_system_prompt(persona.personality, memories)
        formatted_message = data.message
    
    # Generate response (with memory tool enabled)
    try:
        response_result = await _generate_response(
            message=formatted_message,
            system_prompt=system_prompt,
            conversation_history=conversation_history,
            enable_memory_tool=True,
        )
        ai_response = response_result.text
        memories_to_save = response_result.memories_to_save
    except Exception as e:
        logger.error(f"Failed to generate response: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate AI response",
        )
    
    # Check for selective response (channel chat mode)
    should_respond = True
    if data.is_channel_chat:
        if ai_response.strip() == "[NO_RESPONSE]" or not ai_response.strip():
            should_respond = False
            ai_response = ""
    
    # Save any memories the LLM requested to save
    memories_saved = 0
    if memories_to_save and memory_service:
        user_scope = MemoryScope(
            persona_name=data.persona_name,
            user_id=data.user_id,
        )
        for fact in memories_to_save:
            try:
                await memory_service.create_memory(scope=user_scope, fact=fact)
                memories_saved += 1
                logger.info(f"Saved memory for user {data.user_id}: {fact[:50]}...")
            except Exception as e:
                logger.warning(f"Failed to save memory '{fact[:30]}...': {e}")
    
    # Store interaction in session (even if not responding, for context)
    if session and session_service:
        try:
            # Add user message (with display name if channel mode)
            await session_service.append_event(
                session_id=session.id,
                user_id=data.user_id,
                app_name=data.persona_name,
                event=SessionEvent(role="user", content=formatted_message),
            )
            
            # Add assistant response (only if responding)
            if should_respond and ai_response:
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
        f"session={session.id if session else 'none'}, memories_used={memories_count}, "
        f"memories_saved={memories_saved}, should_respond={should_respond}"
    )
    
    return ChatResponse(
        response=ai_response,
        session_id=session.id if session else "in-memory",
        persona_name=data.persona_name,
        memories_used=memories_count,
        memories_saved=memories_saved,
        should_respond=should_respond,
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
    
    # Generate memories from the session using vertex_session_source
    # This is more efficient as Vertex AI fetches session events directly
    if generate_memories and memory_service:
        try:
            # Generate user-specific memories from the session
            user_scope = MemoryScope(
                persona_name=persona_name,
                user_id=user_id,
            )
            memories = await memory_service.generate_memories_from_session(
                scope=user_scope,
                session_id=session_id,
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


@router.post("/channel-sessions/{channel_id}/generate-memories")
async def generate_channel_memories(
    channel_id: str,
    user_id: str | None = None,
    channel_session_repo=Depends(get_channel_session_repository),
    memory_service: MemoryService = Depends(get_memory_service),
) -> dict[str, Any]:
    """
    Generate memories from a channel session WITHOUT ending the session.
    
    This allows extracting long-term memories from an ongoing conversation
    while keeping the session alive for continued interaction.
    
    Args:
        channel_id: Discord channel ID
        user_id: Optional user ID to scope memories to (if not provided, uses session's user_id)
        
    Returns:
        Status and list of generated memories
    """
    if not channel_session_repo:
        return {"status": "no_repository", "memories_generated": 0, "memories": []}
    
    # Get the session mapping
    session_mapping = await channel_session_repo.get_session(channel_id)
    
    if not session_mapping:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No session found for channel '{channel_id}'",
        )
    
    if not memory_service:
        return {"status": "no_memory_service", "memories_generated": 0, "memories": []}
    
    try:
        # Use the provided user_id or fall back to session's user_id
        effective_user_id = user_id or session_mapping.user_id
        
        # Generate user-specific memories from the session
        user_scope = MemoryScope(
            persona_name=session_mapping.persona_name,
            user_id=effective_user_id,
        )
        memories = await memory_service.generate_memories_from_session(
            scope=user_scope,
            session_id=session_mapping.session_id,
        )
        
        logger.info(
            f"Generated {len(memories)} memories from channel {channel_id}, "
            f"session {session_mapping.session_id}, user {effective_user_id}"
        )
        
        return {
            "status": "completed",
            "channel_id": channel_id,
            "session_id": session_mapping.session_id,
            "persona_name": session_mapping.persona_name,
            "user_id": effective_user_id,
            "memories_generated": len(memories),
            "memories": [
                {"id": m.id, "fact": m.fact, "scope": m.scope}
                for m in memories
            ],
        }
        
    except Exception as e:
        logger.error(f"Failed to generate memories from channel {channel_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate memories: {str(e)}",
        )


@router.delete("/channel-sessions/{channel_id}")
async def delete_channel_session(
    channel_id: str,
    channel_session_repo=Depends(get_channel_session_repository),
    session_service: SessionService = Depends(get_session_service),
) -> dict[str, Any]:
    """
    Delete a channel session mapping and the associated session.
    
    Args:
        channel_id: Discord channel ID
        
    Returns:
        Status of the deletion
    """
    if not channel_session_repo:
        return {"status": "no_repository", "deleted": False}
    
    # Get the session mapping first
    session_mapping = await channel_session_repo.get_session(channel_id)
    
    if not session_mapping:
        return {"status": "not_found", "deleted": False}
    
    # Delete the session from Vertex AI if session service is available
    if session_service and session_mapping.session_id:
        try:
            await session_service.delete_session(
                session_id=session_mapping.session_id,
                user_id=session_mapping.user_id,
                app_name=session_mapping.persona_name,
            )
        except Exception as e:
            logger.warning(f"Failed to delete Vertex AI session: {e}")
    
    # Delete the mapping
    deleted = await channel_session_repo.delete_session(channel_id)
    
    return {"status": "deleted" if deleted else "not_found", "deleted": deleted}


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


class DeleteSingleMemoryResponse(BaseModel):
    """Response model for deleting a single memory."""
    deleted: bool
    memory_id: str


@router.delete("/memories/id/{memory_id}", response_model=DeleteSingleMemoryResponse)
async def delete_single_memory(
    memory_id: str,
    memory_service: MemoryService = Depends(get_memory_service),
) -> DeleteSingleMemoryResponse:
    """
    Delete a single memory by its ID.
    
    Args:
        memory_id: Full memory resource name/ID
        
    Returns:
        Whether the memory was deleted
    """
    if not memory_service:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Memory service not available",
        )
    
    try:
        success = await memory_service.delete_memory(memory_id)
        logger.info(f"Delete memory {memory_id}: {'success' if success else 'not found'}")
        return DeleteSingleMemoryResponse(deleted=success, memory_id=memory_id)
    except Exception as e:
        logger.error(f"Failed to delete memory {memory_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete memory: {str(e)}",
        )


@router.delete("/memories/{persona_name}", response_model=DeleteMemoriesResponse)
async def delete_persona_memories(
    persona_name: str,
    user_id: str | None = None,
    memory_service: MemoryService = Depends(get_memory_service),
) -> DeleteMemoriesResponse:
    """
    Delete all memories for a persona (or specific user's memories).
    
    Args:
        persona_name: Persona name
        user_id: If provided, only delete memories for this user
        
    Returns:
        Count of deleted memories
    """
    if not memory_service:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Memory service not available",
        )
    
    scope = MemoryScope(persona_name=persona_name, user_id=user_id)
    
    # Retrieve all memories for this scope
    memories = await memory_service.retrieve_memories(
        scope=scope,
        limit=1000,  # Get as many as possible
    )
    
    deleted_count = 0
    for memory in memories:
        if memory.id:
            try:
                success = await memory_service.delete_memory(memory.id)
                if success:
                    deleted_count += 1
            except Exception as e:
                logger.warning(f"Failed to delete memory {memory.id}: {e}")
    
    logger.info(f"Deleted {deleted_count} memories for persona={persona_name}, user={user_id}")
    
    return DeleteMemoriesResponse(
        deleted_count=deleted_count,
        persona_name=persona_name,
        user_id=user_id,
    )


@router.post("/interpret-error", response_model=ErrorInterpretResponse)
async def interpret_error(
    data: ErrorInterpretRequest,
    persona_repo: PersonaRepository = Depends(get_persona_repository),
) -> ErrorInterpretResponse:
    """
    Have the LLM interpret an error message for the user.
    
    Returns a user-friendly explanation of what went wrong and how to fix it.
    Optionally responds in character if a persona_name is provided.
    
    Args:
        data: Error interpretation request
        
    Returns:
        User-friendly error interpretation
    """
    persona_personality = None
    persona_name = None
    
    if data.persona_name:
        persona = await persona_repo.get_by_name(data.persona_name)
        if persona:
            persona_personality = persona.personality
            persona_name = persona.name
    
    interpretation = await _interpret_error(
        error_message=data.error_message,
        error_context=data.error_context,
        persona_personality=persona_personality,
        persona_name=persona_name,
    )
    
    return ErrorInterpretResponse(interpretation=interpretation)
