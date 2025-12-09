"""Persona entity - represents an AI persona with name and personality."""

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class Persona:
    """
    AI Persona entity.
    
    Represents a customizable AI personality that can be used
    for chat interactions with specific characteristics.
    """

    name: str
    personality: str
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

    def update(self, name: str | None = None, personality: str | None = None) -> None:
        """
        Update persona fields.
        
        Args:
            name: New name (optional)
            personality: New personality description (optional)
        """
        if name is not None:
            if not name.strip():
                raise ValueError("Persona name cannot be empty")
            self.name = name.strip()
        
        if personality is not None:
            if not personality.strip():
                raise ValueError("Persona personality cannot be empty")
            self.personality = personality.strip()
        
        self.updated_at = datetime.now(timezone.utc)

    def to_dict(self) -> dict:
        """Convert persona to dictionary representation."""
        return {
            "name": self.name,
            "personality": self.personality,
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
