"""Abstract interface for image generation."""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class GeneratedImage:
    """Result of a single image generation."""

    data: bytes
    mime_type: str
    prompt: str
    text_response: str | None = None


@dataclass
class GeneratedImages:
    """Result of an image generation request (may contain multiple images)."""

    images: list[GeneratedImage]
    prompt: str
    
    @property
    def first(self) -> GeneratedImage | None:
        """Get the first generated image, or None if empty."""
        return self.images[0] if self.images else None


class ImageGenerator(ABC):
    """
    Abstract interface for image generation.
    
    This interface defines the contract for image generation
    services, allowing different implementations (e.g., Gemini,
    Imagen) to be swapped without changing application code.
    """

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        aspect_ratio: str = "1:1",
        number_of_images: int = 1,
        temperature: float = 1.0,
    ) -> GeneratedImages:
        """
        Generate one or more images from a text prompt.
        
        Args:
            prompt: Text description of the image to generate
            aspect_ratio: Aspect ratio (e.g., "1:1", "16:9")
            number_of_images: Number of images to generate (1-4)
            temperature: Controls randomness (0.0-2.0, default 1.0)
            
        Returns:
            GeneratedImages with image data and metadata
            
        Raises:
            ImageGenerationError: If generation fails
        """
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """
        Check if the image generation service is healthy.
        
        Returns:
            True if service is available, False otherwise
        """
        pass


class ImageGenerationError(Exception):
    """Exception raised when image generation fails."""

    def __init__(self, message: str, original_error: Exception | None = None):
        super().__init__(message)
        self.original_error = original_error
