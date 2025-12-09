"""Abstract interface for image generation."""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class GeneratedImage:
    """Result of an image generation request."""

    data: bytes
    mime_type: str
    prompt: str
    text_response: str | None = None


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
    ) -> GeneratedImage:
        """
        Generate an image from a text prompt.
        
        Args:
            prompt: Text description of the image to generate
            aspect_ratio: Aspect ratio (e.g., "1:1", "16:9")
            
        Returns:
            GeneratedImage with image data and metadata
            
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
