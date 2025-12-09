"""Persona entity - represents an AI persona with name, personality, and appearance."""

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class Persona:
    """
    AI Persona entity.
    
    Represents a customizable AI personality that can be used
    for chat interactions with specific characteristics.
    
    Attributes:
        name: The persona's display name
        personality: Description of personality traits and behavior
        appearance: Physical description for image generation (optional)
        channel_id: Discord channel ID for this persona (optional)
        created_at: When the persona was created
        updated_at: When the persona was last modified
    """

    name: str
    personality: str
    appearance: str | None = None
    channel_id: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        """Validate persona data after initialization."""
        if not self.name or not self.name.strip():
            raise ValueError("Persona name cannot be empty")
        if not self.personality or not self.personality.strip():
            raise ValueError("Persona personality cannot be empty")
        
        # Normalize name (strip whitespace)
        self.name = self.name.strip()
        self.personality = self.personality.strip()
        
        # Normalize optional fields
        if self.appearance is not None:
            self.appearance = self.appearance.strip() if self.appearance.strip() else None
        if self.channel_id is not None:
            self.channel_id = self.channel_id.strip() if self.channel_id.strip() else None

    def update(
        self,
        name: str | None = None,
        personality: str | None = None,
        appearance: str | None = None,
        channel_id: str | None = None,
        clear_appearance: bool = False,
        clear_channel_id: bool = False,
    ) -> None:
        """
        Update persona fields.
        
        Args:
            name: New name (optional)
            personality: New personality description (optional)
            appearance: New appearance description (optional)
            channel_id: New Discord channel ID (optional)
            clear_appearance: If True, set appearance to None
            clear_channel_id: If True, set channel_id to None
        """
        if name is not None:
            if not name.strip():
                raise ValueError("Persona name cannot be empty")
            self.name = name.strip()
        
        if personality is not None:
            if not personality.strip():
                raise ValueError("Persona personality cannot be empty")
            self.personality = personality.strip()
        
        if appearance is not None:
            self.appearance = appearance.strip() if appearance.strip() else None
        elif clear_appearance:
            self.appearance = None
            
        if channel_id is not None:
            self.channel_id = channel_id.strip() if channel_id.strip() else None
        elif clear_channel_id:
            self.channel_id = None
        
        self.updated_at = datetime.now(timezone.utc)

    def to_dict(self) -> dict:
        """Convert persona to dictionary representation."""
        return {
            "name": self.name,
            "personality": self.personality,
            "appearance": self.appearance,
            "channel_id": self.channel_id,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    def get_system_prompt(self) -> str:
        """
        Generate a system prompt for the AI model based on this persona.
        
        Returns:
            System prompt string incorporating the persona's personality.
        """
        return f"""You are {self.name}. {self.personality}

Always stay in character as {self.name}. Respond naturally based on your personality traits.
Be engaging, helpful, and consistent with your character."""
