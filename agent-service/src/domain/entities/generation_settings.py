"""Generation settings entity - configurable AI model settings for chat and image generation."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal


# Safety setting types
HarmCategory = Literal[
    "HARM_CATEGORY_HATE_SPEECH",
    "HARM_CATEGORY_DANGEROUS_CONTENT",
    "HARM_CATEGORY_HARASSMENT",
    "HARM_CATEGORY_SEXUALLY_EXPLICIT",
]

HarmBlockThreshold = Literal[
    "BLOCK_NONE",
    "BLOCK_LOW_AND_ABOVE",
    "BLOCK_MEDIUM_AND_ABOVE",
    "BLOCK_ONLY_HIGH",
    "OFF",
]


@dataclass
class SafetySetting:
    """Individual safety setting for a harm category."""
    category: HarmCategory
    threshold: HarmBlockThreshold = "BLOCK_MEDIUM_AND_ABOVE"


@dataclass
class ChatSettings:
    """
    Settings for chat/text generation with Gemini models.
    
    These settings control how the model generates text responses.
    """
    # Temperature: Controls randomness (0.0 = deterministic, 2.0 = very random)
    temperature: float = 0.9
    
    # Top-P (nucleus sampling): Probability mass for token selection
    top_p: float = 0.95
    
    # Top-K: Number of top tokens to consider (0 = disabled)
    top_k: int = 0
    
    # Maximum output tokens for responses
    max_output_tokens: int = 1024
    
    # Presence penalty: Penalize tokens that already appeared (-2.0 to 2.0)
    presence_penalty: float = 0.0
    
    # Frequency penalty: Penalize frequently used tokens (-2.0 to 2.0)
    frequency_penalty: float = 0.0
    
    # Stop sequences: Stop generation when these strings are encountered
    stop_sequences: list[str] = field(default_factory=list)
    
    # Safety settings for content filtering
    safety_settings: list[SafetySetting] = field(default_factory=lambda: [
        SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="BLOCK_MEDIUM_AND_ABOVE"),
        SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="BLOCK_MEDIUM_AND_ABOVE"),
        SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="BLOCK_MEDIUM_AND_ABOVE"),
        SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="BLOCK_MEDIUM_AND_ABOVE"),
    ])
    
    def __post_init__(self) -> None:
        """Validate settings after initialization."""
        if not 0.0 <= self.temperature <= 2.0:
            raise ValueError("temperature must be between 0.0 and 2.0")
        if not 0.0 <= self.top_p <= 1.0:
            raise ValueError("top_p must be between 0.0 and 1.0")
        if self.top_k < 0:
            raise ValueError("top_k must be non-negative")
        if self.max_output_tokens < 1:
            raise ValueError("max_output_tokens must be at least 1")
        if not -2.0 <= self.presence_penalty <= 2.0:
            raise ValueError("presence_penalty must be between -2.0 and 2.0")
        if not -2.0 <= self.frequency_penalty <= 2.0:
            raise ValueError("frequency_penalty must be between -2.0 and 2.0")


@dataclass
class ImageSettings:
    """
    Settings for image generation with Gemini/Imagen models.
    
    These settings control how images are generated.
    """
    # Default aspect ratio for generated images
    aspect_ratio: str = "1:1"
    
    # Output format (mime type)
    output_mime_type: str = "image/png"
    
    # Negative prompt: What to exclude from generated images
    negative_prompt: str | None = None
    
    # Number of images to generate (1-4)
    number_of_images: int = 1
    
    # Allow person/face generation (may require allowlist)
    person_generation: bool = True
    
    # Safety settings for image generation
    safety_settings: list[SafetySetting] = field(default_factory=lambda: [
        SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="BLOCK_MEDIUM_AND_ABOVE"),
        SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="BLOCK_MEDIUM_AND_ABOVE"),
        SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="BLOCK_MEDIUM_AND_ABOVE"),
        SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="BLOCK_MEDIUM_AND_ABOVE"),
    ])
    
    # Valid aspect ratios
    VALID_ASPECT_RATIOS = {"1:1", "3:2", "2:3", "3:4", "4:3", "4:5", "5:4", "9:16", "16:9", "21:9"}
    
    def __post_init__(self) -> None:
        """Validate settings after initialization."""
        if self.aspect_ratio not in self.VALID_ASPECT_RATIOS:
            raise ValueError(f"aspect_ratio must be one of: {', '.join(self.VALID_ASPECT_RATIOS)}")
        if not 1 <= self.number_of_images <= 4:
            raise ValueError("number_of_images must be between 1 and 4")


@dataclass
class GenerationSettings:
    """
    Complete generation settings for a persona or guild.
    
    Combines chat and image generation settings into a single
    configuration object that can be stored and retrieved.
    
    Settings are stored per-persona (by name) or as guild defaults.
    """
    # Unique identifier (persona name or "default" for guild-wide)
    name: str
    
    # Chat generation settings
    chat: ChatSettings = field(default_factory=ChatSettings)
    
    # Image generation settings
    image: ImageSettings = field(default_factory=ImageSettings)
    
    # Metadata
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def __post_init__(self) -> None:
        """Validate settings after initialization."""
        if not self.name or not self.name.strip():
            raise ValueError("Settings name cannot be empty")
        self.name = self.name.strip().lower()
    
    def update_chat(self, **kwargs) -> None:
        """Update chat settings with provided values."""
        for key, value in kwargs.items():
            if hasattr(self.chat, key):
                setattr(self.chat, key, value)
        self.chat.__post_init__()  # Revalidate
        self.updated_at = datetime.now(timezone.utc)
    
    def update_image(self, **kwargs) -> None:
        """Update image settings with provided values."""
        for key, value in kwargs.items():
            if hasattr(self.image, key):
                setattr(self.image, key, value)
        self.image.__post_init__()  # Revalidate
        self.updated_at = datetime.now(timezone.utc)
    
    def to_dict(self) -> dict:
        """Convert settings to dictionary representation."""
        return {
            "name": self.name,
            "chat": {
                "temperature": self.chat.temperature,
                "top_p": self.chat.top_p,
                "top_k": self.chat.top_k,
                "max_output_tokens": self.chat.max_output_tokens,
                "presence_penalty": self.chat.presence_penalty,
                "frequency_penalty": self.chat.frequency_penalty,
                "stop_sequences": self.chat.stop_sequences,
                "safety_settings": [
                    {"category": s.category, "threshold": s.threshold}
                    for s in self.chat.safety_settings
                ],
            },
            "image": {
                "aspect_ratio": self.image.aspect_ratio,
                "output_mime_type": self.image.output_mime_type,
                "negative_prompt": self.image.negative_prompt,
                "number_of_images": self.image.number_of_images,
                "person_generation": self.image.person_generation,
                "safety_settings": [
                    {"category": s.category, "threshold": s.threshold}
                    for s in self.image.safety_settings
                ],
            },
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "GenerationSettings":
        """Create settings from dictionary representation."""
        chat_data = data.get("chat", {})
        image_data = data.get("image", {})
        
        # Parse safety settings
        chat_safety = [
            SafetySetting(category=s["category"], threshold=s["threshold"])
            for s in chat_data.get("safety_settings", [])
        ]
        image_safety = [
            SafetySetting(category=s["category"], threshold=s["threshold"])
            for s in image_data.get("safety_settings", [])
        ]
        
        chat_settings = ChatSettings(
            temperature=chat_data.get("temperature", 0.9),
            top_p=chat_data.get("top_p", 0.95),
            top_k=chat_data.get("top_k", 0),
            max_output_tokens=chat_data.get("max_output_tokens", 1024),
            presence_penalty=chat_data.get("presence_penalty", 0.0),
            frequency_penalty=chat_data.get("frequency_penalty", 0.0),
            stop_sequences=chat_data.get("stop_sequences", []),
            safety_settings=chat_safety if chat_safety else ChatSettings().safety_settings,
        )
        
        image_settings = ImageSettings(
            aspect_ratio=image_data.get("aspect_ratio", "1:1"),
            output_mime_type=image_data.get("output_mime_type", "image/png"),
            negative_prompt=image_data.get("negative_prompt"),
            number_of_images=image_data.get("number_of_images", 1),
            person_generation=image_data.get("person_generation", True),
            safety_settings=image_safety if image_safety else ImageSettings().safety_settings,
        )
        
        # Parse timestamps
        created_at = data.get("created_at")
        updated_at = data.get("updated_at")
        
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        if isinstance(updated_at, str):
            updated_at = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
        
        return cls(
            name=data["name"],
            chat=chat_settings,
            image=image_settings,
            created_at=created_at or datetime.now(timezone.utc),
            updated_at=updated_at or datetime.now(timezone.utc),
        )


# Default settings name for guild-wide defaults
DEFAULT_SETTINGS_NAME = "default"


def get_default_settings() -> GenerationSettings:
    """Get the default generation settings."""
    return GenerationSettings(name=DEFAULT_SETTINGS_NAME)
