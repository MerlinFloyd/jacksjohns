"""Video generation API endpoints."""

import logging
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from ..dependencies import get_video_generator, get_persona_repository, get_settings_repository
from ...domain.interfaces.video_generator import VideoGenerator, VideoGenerationError
from ...domain.interfaces.persona_repository import PersonaRepository

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/videos", tags=["videos"])


# Request/Response Models
class VideoGenerateRequest(BaseModel):
    """Request model for video generation."""
    prompt: str = Field(..., min_length=1, max_length=4000, description="Video generation prompt")
    aspect_ratio: Literal["16:9", "9:16"] = Field(
        default="16:9",
        description="Aspect ratio (16:9 for landscape, 9:16 for portrait)"
    )
    duration_seconds: Literal[4, 6, 8] = Field(
        default=8,
        description="Video duration in seconds (4, 6, or 8)"
    )
    resolution: Literal["720p", "1080p"] = Field(
        default="720p",
        description="Video resolution (720p or 1080p)"
    )
    generate_audio: bool = Field(
        default=True,
        description="Whether to generate audio with the video"
    )
    persona_name: str | None = Field(
        None,
        description="Optional persona name - if provided, persona appearance and personality will be included in prompt"
    )


class VideoGenerateResponse(BaseModel):
    """Response model for video generation."""
    video_url: str = Field(..., description="Public URL to access the video")
    gcs_uri: str = Field(..., description="GCS URI where the video is stored")
    mime_type: str = Field(..., description="Video MIME type")
    duration_seconds: int = Field(..., description="Video duration in seconds")
    resolution: str = Field(..., description="Video resolution")
    aspect_ratio: str = Field(..., description="Video aspect ratio")
    prompt: str = Field(..., description="Original prompt")
    has_audio: bool = Field(..., description="Whether the video has audio")


# Valid parameters
VALID_ASPECT_RATIOS = {"16:9", "9:16"}
VALID_DURATIONS = {4, 6, 8}
VALID_RESOLUTIONS = {"720p", "1080p"}


@router.post("/generate", response_model=VideoGenerateResponse)
async def generate_video(
    request: VideoGenerateRequest,
    generator: VideoGenerator = Depends(get_video_generator),
    persona_repo: PersonaRepository = Depends(get_persona_repository),
    settings_repo=Depends(get_settings_repository),
) -> VideoGenerateResponse:
    """
    Generate a video from a text prompt using Veo 3.1.
    
    This is a long-running operation that may take 1-3 minutes to complete.
    The video is stored in GCS and a public URL is returned.
    
    If persona_name is provided and the persona has appearance/personality defined,
    these will be included in the prompt for better character consistency.
    
    Args:
        request: Video generation request
        
    Returns:
        Generated video URL and metadata
    """
    # Get generation settings if available
    video_settings = None
    if settings_repo and request.persona_name:
        try:
            gen_settings = await settings_repo.get_or_default(request.persona_name)
            video_settings = gen_settings.video
        except Exception as e:
            logger.warning(f"Failed to get generation settings: {e}")
    
    # Use request values or fall back to settings defaults
    aspect_ratio = request.aspect_ratio
    duration_seconds = request.duration_seconds
    resolution = request.resolution
    generate_audio = request.generate_audio
    
    # Override from settings if request used defaults
    if video_settings:
        if request.aspect_ratio == "16:9" and video_settings.aspect_ratio != "16:9":
            aspect_ratio = video_settings.aspect_ratio
        if request.duration_seconds == 8 and video_settings.duration_seconds != 8:
            duration_seconds = video_settings.duration_seconds
        if request.resolution == "720p" and video_settings.resolution != "720p":
            resolution = video_settings.resolution
        # Use settings for audio if not explicitly set
        generate_audio = video_settings.generate_audio if request.generate_audio else request.generate_audio
    
    # Validate parameters
    if aspect_ratio not in VALID_ASPECT_RATIOS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid aspect ratio. Must be one of: {', '.join(VALID_ASPECT_RATIOS)}"
        )
    if duration_seconds not in VALID_DURATIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid duration. Must be one of: {', '.join(str(d) for d in VALID_DURATIONS)}"
        )
    if resolution not in VALID_RESOLUTIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid resolution. Must be one of: {', '.join(VALID_RESOLUTIONS)}"
        )
    
    # Build final prompt, including persona appearance and personality
    final_prompt = request.prompt
    persona_context_parts = []
    
    if request.persona_name:
        persona = await persona_repo.get_by_name(request.persona_name)
        if persona:
            # Include appearance for visual consistency
            if persona.appearance:
                persona_context_parts.append(f"Character appearance: {persona.appearance}")
                logger.info(f"Including persona appearance in video prompt: {persona.appearance[:50]}...")
            
            # Include a summary of personality for behavioral consistency
            if persona.personality:
                # Take first ~200 chars of personality for context
                personality_summary = persona.personality[:200]
                if len(persona.personality) > 200:
                    personality_summary += "..."
                persona_context_parts.append(f"Character personality: {personality_summary}")
                logger.info(f"Including persona personality in video prompt")
    
    # Combine persona context with user prompt
    if persona_context_parts:
        context = ". ".join(persona_context_parts)
        final_prompt = f"{context}. Video description: {request.prompt}"
    
    # Add negative prompt from settings if available
    negative_prompt = None
    person_generation = "allow_adult"
    seed = None
    
    if video_settings:
        negative_prompt = video_settings.negative_prompt
        person_generation = video_settings.person_generation
        seed = video_settings.seed
    
    try:
        logger.info(
            f"Generating video for prompt: {final_prompt[:100]}... "
            f"(duration={duration_seconds}s, resolution={resolution}, audio={generate_audio})"
        )
        
        result = await generator.generate(
            prompt=final_prompt,
            aspect_ratio=aspect_ratio,
            duration_seconds=duration_seconds,
            resolution=resolution,
            generate_audio=generate_audio,
            negative_prompt=negative_prompt,
            person_generation=person_generation,
            seed=seed,
        )
        
        logger.info(f"Video generated successfully: {result.public_url}")
        
        return VideoGenerateResponse(
            video_url=result.public_url,
            gcs_uri=result.gcs_uri,
            mime_type=result.mime_type,
            duration_seconds=result.duration_seconds,
            resolution=result.resolution,
            aspect_ratio=aspect_ratio,
            prompt=request.prompt,  # Return original prompt, not the enhanced one
            has_audio=result.has_audio,
        )
        
    except VideoGenerationError as e:
        logger.error(f"Video generation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
