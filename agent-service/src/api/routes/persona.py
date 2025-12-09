"""Persona API endpoints."""

import logging
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from ..dependencies import get_persona_repository
from ...domain.entities.persona import Persona
from ...domain.interfaces.persona_repository import PersonaRepository

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/personas", tags=["personas"])


# Request/Response Models
class PersonaCreate(BaseModel):
    """Request model for creating a persona."""
    name: str = Field(..., min_length=1, max_length=100, description="Persona name")
    personality: str = Field(..., min_length=1, max_length=2000, description="Personality description")


class PersonaUpdate(BaseModel):
    """Request model for updating a persona."""
    name: str | None = Field(None, min_length=1, max_length=100, description="New name (optional)")
    personality: str | None = Field(None, min_length=1, max_length=2000, description="New personality (optional)")


class PersonaResponse(BaseModel):
    """Response model for a persona."""
    name: str
    personality: str
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
        persona = Persona(name=data.name, personality=data.personality)
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
        persona.update(name=data.name, personality=data.personality)
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
