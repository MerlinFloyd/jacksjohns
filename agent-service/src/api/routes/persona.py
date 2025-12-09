"""Persona API endpoints."""

import logging
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from ..dependencies import get_persona_repository, get_memory_service
from ...domain.entities.persona import Persona
from ...domain.interfaces.persona_repository import PersonaRepository
from ...domain.interfaces.memory_service import MemoryService, MemoryScope

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/personas", tags=["personas"])


# Request/Response Models
class PersonaCreate(BaseModel):
    """Request model for creating a persona."""
    name: str = Field(..., min_length=1, max_length=100, description="Persona name")
    personality: str = Field(..., min_length=1, max_length=2000, description="Personality description")
    appearance: str | None = Field(None, max_length=2000, description="Physical appearance for image generation")
    channel_id: str | None = Field(None, description="Discord channel ID")


class PersonaUpdate(BaseModel):
    """Request model for updating a persona."""
    # Note: name is not allowed in update - use rename endpoint instead
    personality: str | None = Field(None, min_length=1, max_length=2000, description="New personality (optional)")
    appearance: str | None = Field(None, max_length=2000, description="Physical appearance for image generation")
    channel_id: str | None = Field(None, description="Discord channel ID")


class PersonaRename(BaseModel):
    """Request model for renaming a persona."""
    new_name: str = Field(..., min_length=1, max_length=100, description="New persona name")


class PersonaResponse(BaseModel):
    """Response model for a persona."""
    name: str
    personality: str
    appearance: str | None
    channel_id: str | None
    created_at: str
    updated_at: str


# Endpoints
@router.post("", response_model=PersonaResponse, status_code=status.HTTP_201_CREATED)
async def create_persona(
    data: PersonaCreate,
    repo: PersonaRepository = Depends(get_persona_repository),
) -> PersonaResponse:
    """
    Create a new AI persona.
    
    Args:
        data: Persona creation data
        repo: Persona repository (injected)
        
    Returns:
        Created persona
    """
    try:
        persona = Persona(
            name=data.name,
            personality=data.personality,
            appearance=data.appearance,
            channel_id=data.channel_id,
        )
        created = await repo.create(persona)
        logger.info(f"Created persona: {created.name}")
        return PersonaResponse(**created.to_dict())
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("", response_model=list[PersonaResponse])
async def list_personas(
    repo: PersonaRepository = Depends(get_persona_repository),
) -> list[PersonaResponse]:
    """
    List all personas.
    
    Returns:
        List of all personas
    """
    personas = await repo.get_all()
    return [PersonaResponse(**p.to_dict()) for p in personas]


@router.get("/{name}", response_model=PersonaResponse)
async def get_persona(
    name: str,
    repo: PersonaRepository = Depends(get_persona_repository),
) -> PersonaResponse:
    """
    Get a persona by name.
    
    Args:
        name: Persona name
        
    Returns:
        Persona details
    """
    persona = await repo.get_by_name(name)
    if persona is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Persona '{name}' not found"
        )
    return PersonaResponse(**persona.to_dict())


@router.patch("/{name}", response_model=PersonaResponse)
async def update_persona(
    name: str,
    data: PersonaUpdate,
    repo: PersonaRepository = Depends(get_persona_repository),
) -> PersonaResponse:
    """
    Update a persona.
    
    Args:
        name: Current persona name
        data: Update data
        
    Returns:
        Updated persona
    """
    persona = await repo.get_by_name(name)
    if persona is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Persona '{name}' not found"
        )
    
    try:
        persona.update(
            personality=data.personality,
            appearance=data.appearance,
            channel_id=data.channel_id,
        )
        updated = await repo.update(name, persona)
        if updated is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Persona '{name}' not found"
            )
        logger.info(f"Updated persona: {name}")
        return PersonaResponse(**updated.to_dict())
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/{name}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_persona(
    name: str,
    repo: PersonaRepository = Depends(get_persona_repository),
) -> None:
    """
    Delete a persona.
    
    Args:
        name: Persona name to delete
    """
    deleted = await repo.delete(name)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Persona '{name}' not found"
        )
    logger.info(f"Deleted persona: {name}")


@router.post("/{name}/rename", response_model=PersonaResponse)
async def rename_persona(
    name: str,
    data: PersonaRename,
    repo: PersonaRepository = Depends(get_persona_repository),
    memory_service: MemoryService | None = Depends(get_memory_service),
) -> PersonaResponse:
    """
    Rename a persona.
    
    This updates:
    1. Persona record in Firestore (new document key)
    2. Memory scopes (migrate memories to new app_name)
    
    Note: The Discord bot handles channel rename separately.
    
    Args:
        name: Current persona name
        data: Rename data with new_name
        
    Returns:
        Updated persona with new name
    """
    # Get existing persona
    persona = await repo.get_by_name(name)
    if persona is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Persona '{name}' not found"
        )
    
    # Check if new name already exists
    existing = await repo.get_by_name(data.new_name)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Persona '{data.new_name}' already exists"
        )
    
    old_name = persona.name
    
    # Update persona name
    try:
        persona.update(name=data.new_name)
        updated = await repo.update(name, persona)
        if updated is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Persona '{name}' not found"
            )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    
    # Migrate memories to new scope (app_name)
    # Note: Memory Bank API doesn't support updating scope keys directly,
    # so we retrieve all memories, create new ones with new scope, and delete old ones
    if memory_service:
        try:
            await _migrate_memories(memory_service, old_name, data.new_name)
        except Exception as e:
            logger.warning(f"Failed to migrate memories during rename: {e}")
            # Don't fail the rename operation, just log the warning
    
    logger.info(f"Renamed persona: {old_name} -> {data.new_name}")
    return PersonaResponse(**updated.to_dict())


async def _migrate_memories(
    memory_service: MemoryService,
    old_persona_name: str,
    new_persona_name: str,
) -> None:
    """
    Migrate memories from old persona name to new persona name.
    
    This is needed because Memory Bank uses app_name as the scope key,
    and we can't update scope keys directly.
    """
    # Get all memories for old persona (shared scope)
    old_scope = MemoryScope(persona_name=old_persona_name)
    old_memories = await memory_service.retrieve_memories(scope=old_scope, limit=1000)
    
    new_scope = MemoryScope(persona_name=new_persona_name)
    
    # Create new memories with new scope and delete old ones
    for memory in old_memories:
        try:
            # Create with new scope
            await memory_service.create_memory(scope=new_scope, fact=memory.fact)
            # Delete old memory
            if memory.id:
                await memory_service.delete_memory(memory.id)
        except Exception as e:
            logger.warning(f"Failed to migrate memory {memory.id}: {e}")
    
    logger.info(f"Migrated {len(old_memories)} shared memories from {old_persona_name} to {new_persona_name}")
    
    # Note: User-specific memories also need to be migrated
    # However, we don't have a way to list all user_ids that have memories
    # This would require iterating through all sessions or storing user_ids separately
    # For now, we only migrate shared memories
