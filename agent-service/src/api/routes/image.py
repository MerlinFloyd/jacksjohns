"""Image generation API endpoints."""

import base64
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from pydantic import BaseModel, Field

from ..dependencies import get_image_generator
from ...domain.interfaces.image_generator import ImageGenerator, ImageGenerationError

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


class ImageGenerateResponse(BaseModel):
    """Response model for image generation (JSON format)."""
    image_base64: str = Field(..., description="Base64 encoded image data")
    mime_type: str = Field(..., description="Image MIME type")
    prompt: str = Field(..., description="Original prompt")
    text_response: str | None = Field(None, description="Optional text response from model")


# Valid aspect ratios
VALID_ASPECT_RATIOS = {"1:1", "3:2", "2:3", "3:4", "4:3", "4:5", "5:4", "9:16", "16:9", "21:9"}


@router.post("/generate", response_model=ImageGenerateResponse)
async def generate_image_json(
    request: ImageGenerateRequest,
    generator: ImageGenerator = Depends(get_image_generator),
) -> ImageGenerateResponse:
    """
    Generate an image from a text prompt.
    
    Returns the image as base64-encoded JSON response.
    
    Args:
        request: Image generation request
        
    Returns:
        Generated image as base64 with metadata
    """
    # Validate aspect ratio
    if request.aspect_ratio not in VALID_ASPECT_RATIOS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid aspect ratio. Must be one of: {', '.join(VALID_ASPECT_RATIOS)}"
        )
    
    try:
        logger.info(f"Generating image for prompt: {request.prompt[:50]}...")
        result = await generator.generate(
            prompt=request.prompt,
            aspect_ratio=request.aspect_ratio,
        )
        
        # Encode image to base64
        image_base64 = base64.b64encode(result.data).decode("utf-8")
        
        logger.info(f"Image generated successfully ({len(result.data)} bytes)")
        
        return ImageGenerateResponse(
            image_base64=image_base64,
            mime_type=result.mime_type,
            prompt=result.prompt,
            text_response=result.text_response,
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
) -> Response:
    """
    Generate an image from a text prompt.
    
    Returns the raw image bytes directly.
    
    Args:
        request: Image generation request
        
    Returns:
        Raw image bytes
    """
    # Validate aspect ratio
    if request.aspect_ratio not in VALID_ASPECT_RATIOS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid aspect ratio. Must be one of: {', '.join(VALID_ASPECT_RATIOS)}"
        )
    
    try:
        logger.info(f"Generating raw image for prompt: {request.prompt[:50]}...")
        result = await generator.generate(
            prompt=request.prompt,
            aspect_ratio=request.aspect_ratio,
        )
        
        logger.info(f"Raw image generated successfully ({len(result.data)} bytes)")
        
        return Response(
            content=result.data,
            media_type=result.mime_type,
            headers={
                "X-Prompt": request.prompt[:100],
                "X-Text-Response": result.text_response or "",
            }
        )
        
    except ImageGenerationError as e:
        logger.error(f"Image generation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
