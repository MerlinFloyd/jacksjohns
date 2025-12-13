"""Image generation API endpoints."""

import base64
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from pydantic import BaseModel, Field

from ..dependencies import get_image_generator, get_persona_repository, get_settings_repository
from ...domain.interfaces.image_generator import ImageGenerator, ImageGenerationError
from ...domain.interfaces.persona_repository import PersonaRepository

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/images", tags=["images"])


# Request/Response Models
class ImageGenerateRequest(BaseModel):
    """Request model for image generation."""
    prompt: str = Field(..., min_length=1, max_length=4000, description="Image generation prompt")
    aspect_ratio: str = Field(
        default="1:1",
        description="Aspect ratio (1:1, 3:2, 2:3, 3:4, 4:3, 4:5, 5:4, 9:16, 16:9, 21:9)"
    )
    persona_name: str | None = Field(
        None,
        description="Optional persona name - if provided and persona has appearance, it will be prepended to prompt"
    )


class GeneratedImageData(BaseModel):
    """Single generated image data."""
    image_base64: str = Field(..., description="Base64 encoded image data")
    mime_type: str = Field(..., description="Image MIME type")
    text_response: str | None = Field(None, description="Optional text response from model")


class ImageGenerateResponse(BaseModel):
    """Response model for image generation (JSON format)."""
    images: list[GeneratedImageData] = Field(..., description="List of generated images")
    prompt: str = Field(..., description="Original prompt")
    
    # Legacy fields for backward compatibility (first image only)
    image_base64: str = Field(..., description="Base64 encoded image data (first image)")
    mime_type: str = Field(..., description="Image MIME type (first image)")
    text_response: str | None = Field(None, description="Optional text response from model (first image)")


# Valid aspect ratios
VALID_ASPECT_RATIOS = {"1:1", "3:2", "2:3", "3:4", "4:3", "4:5", "5:4", "9:16", "16:9", "21:9"}


@router.post("/generate", response_model=ImageGenerateResponse)
async def generate_image_json(
    request: ImageGenerateRequest,
    generator: ImageGenerator = Depends(get_image_generator),
    persona_repo: PersonaRepository = Depends(get_persona_repository),
    settings_repo=Depends(get_settings_repository),
) -> ImageGenerateResponse:
    """
    Generate one or more images from a text prompt.
    
    Returns the images as base64-encoded JSON response.
    
    If persona_name is provided and the persona has an appearance defined,
    the appearance will be prepended to the prompt for better character consistency.
    
    Uses persona-specific or default generation settings for aspect ratio, 
    number_of_images, temperature, and other parameters.
    
    Args:
        request: Image generation request
        
    Returns:
        Generated images as base64 with metadata
    """
    # Get generation settings if available
    image_settings = None
    if settings_repo and request.persona_name:
        try:
            gen_settings = await settings_repo.get_or_default(request.persona_name)
            image_settings = gen_settings.image
        except Exception as e:
            logger.warning(f"Failed to get generation settings: {e}")
    
    # Use request aspect_ratio or settings default
    aspect_ratio = request.aspect_ratio
    if aspect_ratio == "1:1" and image_settings and image_settings.aspect_ratio != "1:1":
        # Only use settings default if request used default value
        aspect_ratio = image_settings.aspect_ratio
    
    # Get number_of_images and temperature from settings
    number_of_images = image_settings.number_of_images if image_settings else 1
    temperature = image_settings.temperature if image_settings else 1.0
    
    # Validate aspect ratio
    if aspect_ratio not in VALID_ASPECT_RATIOS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid aspect ratio. Must be one of: {', '.join(VALID_ASPECT_RATIOS)}"
        )
    
    # Build final prompt, optionally including persona appearance
    final_prompt = request.prompt
    if request.persona_name:
        persona = await persona_repo.get_by_name(request.persona_name)
        if persona and persona.appearance:
            final_prompt = f"{persona.appearance}, {request.prompt}"
            logger.info(f"Including persona appearance in prompt: {persona.appearance[:50]}...")
    
    # Add negative prompt from settings if available
    if image_settings and image_settings.negative_prompt:
        final_prompt = f"{final_prompt}. Avoid: {image_settings.negative_prompt}"
    
    try:
        logger.info(
            f"Generating {number_of_images} image(s) for prompt: {final_prompt[:50]}... "
            f"(temp={temperature})"
        )
        result = await generator.generate(
            prompt=final_prompt,
            aspect_ratio=aspect_ratio,
            number_of_images=number_of_images,
            temperature=temperature,
        )
        
        # Convert all images to response format
        images_data = []
        for img in result.images:
            images_data.append(GeneratedImageData(
                image_base64=base64.b64encode(img.data).decode("utf-8"),
                mime_type=img.mime_type,
                text_response=img.text_response,
            ))
        
        total_bytes = sum(len(img.data) for img in result.images)
        logger.info(f"{len(result.images)} image(s) generated successfully ({total_bytes} bytes total)")
        
        # Use first image for legacy fields
        first_image = images_data[0] if images_data else None
        
        return ImageGenerateResponse(
            images=images_data,
            prompt=result.prompt,
            # Legacy fields for backward compatibility
            image_base64=first_image.image_base64 if first_image else "",
            mime_type=first_image.mime_type if first_image else "image/png",
            text_response=first_image.text_response if first_image else None,
        )
        
    except ImageGenerationError as e:
        logger.error(f"Image generation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/generate/raw")
async def generate_image_raw(
    request: ImageGenerateRequest,
    generator: ImageGenerator = Depends(get_image_generator),
    persona_repo: PersonaRepository = Depends(get_persona_repository),
    settings_repo=Depends(get_settings_repository),
) -> Response:
    """
    Generate an image from a text prompt.
    
    Returns the raw image bytes directly (first image only).
    
    If persona_name is provided and the persona has an appearance defined,
    the appearance will be prepended to the prompt for better character consistency.
    
    Uses persona-specific or default generation settings for aspect ratio and other parameters.
    Note: This endpoint only returns the first image even if number_of_images > 1.
    
    Args:
        request: Image generation request
        
    Returns:
        Raw image bytes (first image)
    """
    # Get generation settings if available
    image_settings = None
    if settings_repo and request.persona_name:
        try:
            gen_settings = await settings_repo.get_or_default(request.persona_name)
            image_settings = gen_settings.image
        except Exception as e:
            logger.warning(f"Failed to get generation settings: {e}")
    
    # Use request aspect_ratio or settings default
    aspect_ratio = request.aspect_ratio
    if aspect_ratio == "1:1" and image_settings and image_settings.aspect_ratio != "1:1":
        # Only use settings default if request used default value
        aspect_ratio = image_settings.aspect_ratio
    
    # Get temperature from settings (only generate 1 image for raw endpoint)
    temperature = image_settings.temperature if image_settings else 1.0
    
    # Validate aspect ratio
    if aspect_ratio not in VALID_ASPECT_RATIOS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid aspect ratio. Must be one of: {', '.join(VALID_ASPECT_RATIOS)}"
        )
    
    # Build final prompt, optionally including persona appearance
    final_prompt = request.prompt
    if request.persona_name:
        persona = await persona_repo.get_by_name(request.persona_name)
        if persona and persona.appearance:
            final_prompt = f"{persona.appearance}, {request.prompt}"
            logger.info(f"Including persona appearance in prompt: {persona.appearance[:50]}...")
    
    # Add negative prompt from settings if available
    if image_settings and image_settings.negative_prompt:
        final_prompt = f"{final_prompt}. Avoid: {image_settings.negative_prompt}"
    
    try:
        logger.info(f"Generating raw image for prompt: {final_prompt[:50]}... (temp={temperature})")
        result = await generator.generate(
            prompt=final_prompt,
            aspect_ratio=aspect_ratio,
            number_of_images=1,  # Raw endpoint only returns one image
            temperature=temperature,
        )
        
        first_image = result.first
        if not first_image:
            raise ImageGenerationError("No image generated")
        
        logger.info(f"Raw image generated successfully ({len(first_image.data)} bytes)")
        
        return Response(
            content=first_image.data,
            media_type=first_image.mime_type,
            headers={
                "X-Prompt": request.prompt[:100],
                "X-Text-Response": first_image.text_response or "",
            }
        )
        
    except ImageGenerationError as e:
        logger.error(f"Image generation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
