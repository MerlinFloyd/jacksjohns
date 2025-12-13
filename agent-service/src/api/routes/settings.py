"""Settings API endpoints for managing generation settings."""

import logging
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from ..dependencies import get_settings_repository
from ...domain.entities.generation_settings import (
    GenerationSettings,
    ChatSettings,
    ImageSettings,
    SafetySetting,
    HarmCategory,
    HarmBlockThreshold,
    DEFAULT_SETTINGS_NAME,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/settings", tags=["settings"])


# Request/Response Models
class SafetySettingModel(BaseModel):
    """Safety setting model for API."""
    category: HarmCategory
    threshold: HarmBlockThreshold = "BLOCK_MEDIUM_AND_ABOVE"


class ChatSettingsModel(BaseModel):
    """Chat settings model for API."""
    temperature: float = Field(0.9, ge=0.0, le=2.0, description="Controls randomness (0.0-2.0)")
    top_p: float = Field(0.95, ge=0.0, le=1.0, description="Nucleus sampling probability (0.0-1.0)")
    top_k: int = Field(0, ge=0, description="Top-K sampling (0 = disabled)")
    max_output_tokens: int = Field(1024, ge=1, description="Maximum response tokens")
    presence_penalty: float = Field(0.0, ge=-2.0, le=2.0, description="Presence penalty (-2.0 to 2.0)")
    frequency_penalty: float = Field(0.0, ge=-2.0, le=2.0, description="Frequency penalty (-2.0 to 2.0)")
    stop_sequences: list[str] = Field(default_factory=list, description="Stop sequences")
    safety_settings: list[SafetySettingModel] | None = Field(None, description="Safety settings")


class ImageSettingsModel(BaseModel):
    """Image settings model for API."""
    aspect_ratio: str = Field("1:1", description="Aspect ratio (1:1, 16:9, 9:16, etc.)")
    output_mime_type: str = Field("image/png", description="Output format (image/png, image/jpeg)")
    negative_prompt: str | None = Field(None, description="What to exclude from images")
    number_of_images: int = Field(1, ge=1, le=4, description="Number of images to generate (1-4)")
    temperature: float = Field(1.0, ge=0.0, le=2.0, description="Controls randomness/creativity (0.0-2.0)")
    person_generation: bool = Field(True, description="Allow person/face generation")
    safety_settings: list[SafetySettingModel] | None = Field(None, description="Safety settings")


class GenerationSettingsResponse(BaseModel):
    """Full generation settings response."""
    name: str
    chat: ChatSettingsModel
    image: ImageSettingsModel
    created_at: str
    updated_at: str


class UpdateChatSettingsRequest(BaseModel):
    """Request to update chat settings."""
    temperature: float | None = Field(None, ge=0.0, le=2.0)
    top_p: float | None = Field(None, ge=0.0, le=1.0)
    top_k: int | None = Field(None, ge=0)
    max_output_tokens: int | None = Field(None, ge=1)
    presence_penalty: float | None = Field(None, ge=-2.0, le=2.0)
    frequency_penalty: float | None = Field(None, ge=-2.0, le=2.0)
    stop_sequences: list[str] | None = None
    safety_settings: list[SafetySettingModel] | None = None


class UpdateImageSettingsRequest(BaseModel):
    """Request to update image settings."""
    aspect_ratio: str | None = None
    output_mime_type: str | None = None
    negative_prompt: str | None = None
    number_of_images: int | None = Field(None, ge=1, le=4)
    temperature: float | None = Field(None, ge=0.0, le=2.0)
    person_generation: bool | None = None
    safety_settings: list[SafetySettingModel] | None = None


class UpdateSettingsRequest(BaseModel):
    """Request to update generation settings."""
    chat: UpdateChatSettingsRequest | None = None
    image: UpdateImageSettingsRequest | None = None


class SettingValueResponse(BaseModel):
    """Response for a single setting value."""
    name: str
    category: Literal["chat", "image"]
    setting: str
    value: Any
    description: str


class SettingsListResponse(BaseModel):
    """Response listing all available settings."""
    settings: list[GenerationSettingsResponse]


# Setting descriptions for help
CHAT_SETTING_DESCRIPTIONS = {
    "temperature": "Controls randomness in responses (0.0 = deterministic, 2.0 = very random)",
    "top_p": "Nucleus sampling - probability mass for token selection (0.0-1.0)",
    "top_k": "Number of top tokens to consider (0 = disabled)",
    "max_output_tokens": "Maximum number of tokens in the response",
    "presence_penalty": "Penalize tokens that already appeared (-2.0 to 2.0)",
    "frequency_penalty": "Penalize frequently used tokens (-2.0 to 2.0)",
    "stop_sequences": "Strings that stop generation when encountered",
    "safety_settings": "Content safety filter settings",
}

IMAGE_SETTING_DESCRIPTIONS = {
    "aspect_ratio": "Output image aspect ratio (1:1, 16:9, 9:16, 3:4, 4:3, etc.)",
    "output_mime_type": "Output format (image/png or image/jpeg)",
    "negative_prompt": "What to exclude from generated images",
    "number_of_images": "Number of images to generate per request (1-4)",
    "temperature": "Controls randomness/creativity in image generation (0.0-2.0)",
    "person_generation": "Whether to allow generating people/faces",
    "safety_settings": "Content safety filter settings",
}


def _settings_to_response(settings: GenerationSettings) -> GenerationSettingsResponse:
    """Convert domain entity to API response."""
    chat_safety = [
        SafetySettingModel(category=s.category, threshold=s.threshold)
        for s in settings.chat.safety_settings
    ]
    image_safety = [
        SafetySettingModel(category=s.category, threshold=s.threshold)
        for s in settings.image.safety_settings
    ]
    
    return GenerationSettingsResponse(
        name=settings.name,
        chat=ChatSettingsModel(
            temperature=settings.chat.temperature,
            top_p=settings.chat.top_p,
            top_k=settings.chat.top_k,
            max_output_tokens=settings.chat.max_output_tokens,
            presence_penalty=settings.chat.presence_penalty,
            frequency_penalty=settings.chat.frequency_penalty,
            stop_sequences=settings.chat.stop_sequences,
            safety_settings=chat_safety,
        ),
        image=ImageSettingsModel(
            aspect_ratio=settings.image.aspect_ratio,
            output_mime_type=settings.image.output_mime_type,
            negative_prompt=settings.image.negative_prompt,
            number_of_images=settings.image.number_of_images,
            temperature=settings.image.temperature,
            person_generation=settings.image.person_generation,
            safety_settings=image_safety,
        ),
        created_at=settings.created_at.isoformat(),
        updated_at=settings.updated_at.isoformat(),
    )


@router.get("", response_model=SettingsListResponse)
async def list_settings(
    settings_repo=Depends(get_settings_repository),
) -> SettingsListResponse:
    """
    List all stored generation settings.
    
    Returns all persona-specific settings and the default settings if they exist.
    """
    if not settings_repo:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Settings service not available",
        )
    
    all_settings = await settings_repo.list_all()
    return SettingsListResponse(
        settings=[_settings_to_response(s) for s in all_settings]
    )


@router.get("/available")
async def list_available_settings() -> dict[str, Any]:
    """
    List all available settings with their descriptions and valid values.
    
    This endpoint helps users understand what settings can be configured.
    """
    return {
        "chat": {
            name: {
                "description": desc,
                "type": _get_setting_type("chat", name),
            }
            for name, desc in CHAT_SETTING_DESCRIPTIONS.items()
        },
        "image": {
            name: {
                "description": desc,
                "type": _get_setting_type("image", name),
            }
            for name, desc in IMAGE_SETTING_DESCRIPTIONS.items()
        },
        "valid_aspect_ratios": list(ImageSettings.VALID_ASPECT_RATIOS),
        "valid_harm_categories": [
            "HARM_CATEGORY_HATE_SPEECH",
            "HARM_CATEGORY_DANGEROUS_CONTENT",
            "HARM_CATEGORY_HARASSMENT",
            "HARM_CATEGORY_SEXUALLY_EXPLICIT",
        ],
        "valid_harm_thresholds": [
            "BLOCK_NONE",
            "BLOCK_LOW_AND_ABOVE",
            "BLOCK_MEDIUM_AND_ABOVE",
            "BLOCK_ONLY_HIGH",
            "OFF",
        ],
    }


def _get_setting_type(category: str, name: str) -> dict[str, Any]:
    """Get type information for a setting."""
    if category == "chat":
        types = {
            "temperature": {"type": "float", "min": 0.0, "max": 2.0, "default": 0.9},
            "top_p": {"type": "float", "min": 0.0, "max": 1.0, "default": 0.95},
            "top_k": {"type": "int", "min": 0, "default": 0},
            "max_output_tokens": {"type": "int", "min": 1, "default": 1024},
            "presence_penalty": {"type": "float", "min": -2.0, "max": 2.0, "default": 0.0},
            "frequency_penalty": {"type": "float", "min": -2.0, "max": 2.0, "default": 0.0},
            "stop_sequences": {"type": "list[string]", "default": []},
            "safety_settings": {"type": "list[SafetySetting]"},
        }
    else:
        types = {
            "aspect_ratio": {"type": "string", "default": "1:1"},
            "output_mime_type": {"type": "string", "default": "image/png"},
            "negative_prompt": {"type": "string", "default": None},
            "number_of_images": {"type": "int", "min": 1, "max": 4, "default": 1},
            "temperature": {"type": "float", "min": 0.0, "max": 2.0, "default": 1.0},
            "person_generation": {"type": "bool", "default": True},
            "safety_settings": {"type": "list[SafetySetting]"},
        }
    return types.get(name, {"type": "unknown"})


@router.get("/{name}", response_model=GenerationSettingsResponse)
async def get_settings(
    name: str,
    settings_repo=Depends(get_settings_repository),
) -> GenerationSettingsResponse:
    """
    Get generation settings for a persona or default.
    
    Args:
        name: Settings name (persona name or "default")
        
    Returns:
        Generation settings (existing or default values)
    """
    if not settings_repo:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Settings service not available",
        )
    
    settings = await settings_repo.get_or_default(name)
    return _settings_to_response(settings)


@router.put("/{name}", response_model=GenerationSettingsResponse)
async def update_settings(
    name: str,
    request: UpdateSettingsRequest,
    settings_repo=Depends(get_settings_repository),
) -> GenerationSettingsResponse:
    """
    Update generation settings for a persona or default.
    
    Creates settings if they don't exist, updates if they do.
    Only provided fields will be updated.
    
    Args:
        name: Settings name (persona name or "default")
        request: Settings to update
        
    Returns:
        Updated generation settings
    """
    if not settings_repo:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Settings service not available",
        )
    
    # Get existing or default settings
    settings = await settings_repo.get_or_default(name)
    
    # Update chat settings if provided
    if request.chat:
        chat_updates = {}
        if request.chat.temperature is not None:
            chat_updates["temperature"] = request.chat.temperature
        if request.chat.top_p is not None:
            chat_updates["top_p"] = request.chat.top_p
        if request.chat.top_k is not None:
            chat_updates["top_k"] = request.chat.top_k
        if request.chat.max_output_tokens is not None:
            chat_updates["max_output_tokens"] = request.chat.max_output_tokens
        if request.chat.presence_penalty is not None:
            chat_updates["presence_penalty"] = request.chat.presence_penalty
        if request.chat.frequency_penalty is not None:
            chat_updates["frequency_penalty"] = request.chat.frequency_penalty
        if request.chat.stop_sequences is not None:
            chat_updates["stop_sequences"] = request.chat.stop_sequences
        if request.chat.safety_settings is not None:
            chat_updates["safety_settings"] = [
                SafetySetting(category=s.category, threshold=s.threshold)
                for s in request.chat.safety_settings
            ]
        
        if chat_updates:
            try:
                settings.update_chat(**chat_updates)
            except ValueError as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid chat setting: {str(e)}",
                )
    
    # Update image settings if provided
    if request.image:
        image_updates = {}
        if request.image.aspect_ratio is not None:
            image_updates["aspect_ratio"] = request.image.aspect_ratio
        if request.image.output_mime_type is not None:
            image_updates["output_mime_type"] = request.image.output_mime_type
        if request.image.negative_prompt is not None:
            image_updates["negative_prompt"] = request.image.negative_prompt
        if request.image.number_of_images is not None:
            image_updates["number_of_images"] = request.image.number_of_images
        if request.image.temperature is not None:
            image_updates["temperature"] = request.image.temperature
        if request.image.person_generation is not None:
            image_updates["person_generation"] = request.image.person_generation
        if request.image.safety_settings is not None:
            image_updates["safety_settings"] = [
                SafetySetting(category=s.category, threshold=s.threshold)
                for s in request.image.safety_settings
            ]
        
        if image_updates:
            try:
                settings.update_image(**image_updates)
            except ValueError as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid image setting: {str(e)}",
                )
    
    # Save and return
    saved = await settings_repo.save(settings)
    logger.info(f"Updated settings for: {name}")
    return _settings_to_response(saved)


@router.patch("/{name}/chat/{setting_name}")
async def set_chat_setting(
    name: str,
    setting_name: str,
    value: Any,
    settings_repo=Depends(get_settings_repository),
) -> SettingValueResponse:
    """
    Set a single chat setting value.
    
    Args:
        name: Settings name (persona name or "default")
        setting_name: Name of the setting to update
        value: New value for the setting
        
    Returns:
        Updated setting value
    """
    if not settings_repo:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Settings service not available",
        )
    
    if setting_name not in CHAT_SETTING_DESCRIPTIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown chat setting: {setting_name}. Valid settings: {', '.join(CHAT_SETTING_DESCRIPTIONS.keys())}",
        )
    
    settings = await settings_repo.get_or_default(name)
    
    try:
        settings.update_chat(**{setting_name: value})
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    
    await settings_repo.save(settings)
    
    return SettingValueResponse(
        name=name,
        category="chat",
        setting=setting_name,
        value=getattr(settings.chat, setting_name),
        description=CHAT_SETTING_DESCRIPTIONS[setting_name],
    )


@router.patch("/{name}/image/{setting_name}")
async def set_image_setting(
    name: str,
    setting_name: str,
    value: Any,
    settings_repo=Depends(get_settings_repository),
) -> SettingValueResponse:
    """
    Set a single image setting value.
    
    Args:
        name: Settings name (persona name or "default")
        setting_name: Name of the setting to update
        value: New value for the setting
        
    Returns:
        Updated setting value
    """
    if not settings_repo:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Settings service not available",
        )
    
    if setting_name not in IMAGE_SETTING_DESCRIPTIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown image setting: {setting_name}. Valid settings: {', '.join(IMAGE_SETTING_DESCRIPTIONS.keys())}",
        )
    
    settings = await settings_repo.get_or_default(name)
    
    try:
        settings.update_image(**{setting_name: value})
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    
    await settings_repo.save(settings)
    
    return SettingValueResponse(
        name=name,
        category="image",
        setting=setting_name,
        value=getattr(settings.image, setting_name),
        description=IMAGE_SETTING_DESCRIPTIONS[setting_name],
    )


@router.delete("/{name}")
async def delete_settings(
    name: str,
    settings_repo=Depends(get_settings_repository),
) -> dict[str, Any]:
    """
    Delete custom settings for a persona.
    
    After deletion, the persona will use default settings.
    
    Args:
        name: Settings name to delete
        
    Returns:
        Deletion status
    """
    if not settings_repo:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Settings service not available",
        )
    
    deleted = await settings_repo.delete(name)
    
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Settings for '{name}' not found",
        )
    
    logger.info(f"Deleted settings for: {name}")
    return {"status": "deleted", "name": name}


@router.post("/{name}/reset")
async def reset_settings(
    name: str,
    settings_repo=Depends(get_settings_repository),
) -> GenerationSettingsResponse:
    """
    Reset settings to defaults for a persona.
    
    This deletes any custom settings and returns the default values.
    
    Args:
        name: Settings name to reset
        
    Returns:
        Default generation settings
    """
    if not settings_repo:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Settings service not available",
        )
    
    # Delete existing settings
    await settings_repo.delete(name)
    
    # Return default settings (but don't save them)
    settings = GenerationSettings(name=name)
    logger.info(f"Reset settings for: {name}")
    return _settings_to_response(settings)
