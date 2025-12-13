"""Abstract interface for video generation."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Literal


@dataclass
class GeneratedVideo:
    """Result of a video generation request."""

    # GCS URI where the video is stored (e.g., gs://bucket/path/video.mp4)
    gcs_uri: str
    
    # Public URL to access the video
    public_url: str
    
    # MIME type of the video
    mime_type: str
    
    # Duration of the video in seconds
    duration_seconds: int
    
    # Resolution of the video
    resolution: str
    
    # Original prompt used for generation
    prompt: str
    
    # Whether audio was generated
    has_audio: bool


class VideoGenerator(ABC):
    """
    Abstract interface for video generation.
    
    This interface defines the contract for video generation
    services, allowing different implementations to be swapped
    without changing application code.
    """

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        aspect_ratio: Literal["16:9", "9:16"] = "16:9",
        duration_seconds: Literal[4, 6, 8] = 8,
        resolution: Literal["720p", "1080p"] = "720p",
        generate_audio: bool = True,
        negative_prompt: str | None = None,
        person_generation: Literal["allow_adult", "dont_allow"] = "allow_adult",
        seed: int | None = None,
    ) -> GeneratedVideo:
        """
        Generate a video from a text prompt.
        
        Args:
            prompt: Text description of the video to generate
            aspect_ratio: Aspect ratio ("16:9" or "9:16")
            duration_seconds: Video duration (4, 6, or 8 seconds)
            resolution: Video resolution ("720p" or "1080p")
            generate_audio: Whether to generate audio with the video
            negative_prompt: What to exclude from the video
            person_generation: Person generation policy
            seed: Seed for reproducible generation
            
        Returns:
            GeneratedVideo with video URL and metadata
            
        Raises:
            VideoGenerationError: If generation fails
        """
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """
        Check if the video generation service is healthy.
        
        Returns:
            True if service is available, False otherwise
        """
        pass


class VideoGenerationError(Exception):
    """Exception raised when video generation fails."""

    def __init__(self, message: str, original_error: Exception | None = None):
        super().__init__(message)
        self.original_error = original_error
