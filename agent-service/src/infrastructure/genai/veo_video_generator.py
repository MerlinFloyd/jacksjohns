"""Veo 3.1 video generation implementation using Vertex AI."""

import asyncio
import logging
import time
from typing import Literal

from google import genai
from google.api_core.exceptions import ResourceExhausted
from google.genai.types import GenerateVideosConfig
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    before_sleep_log,
    retry_if_exception,
)

from ...config.settings import get_settings
from ...domain.interfaces.video_generator import (
    GeneratedVideo,
    VideoGenerator,
    VideoGenerationError,
)

logger = logging.getLogger(__name__)


def _is_rate_limit_error(exception: BaseException) -> bool:
    """
    Check if the exception is a rate limit (429 RESOURCE_EXHAUSTED) error.
    
    Returns True only for rate limit errors that should be retried.
    """
    if isinstance(exception, ResourceExhausted):
        return True
    
    error_str = str(exception).lower()
    return "429" in error_str or "resource_exhausted" in error_str


class VeoVideoGenerator(VideoGenerator):
    """
    Video generator using Veo 3.1 model via Vertex AI.
    
    Uses the google-genai SDK to generate videos via Vertex AI.
    Videos are stored in a GCS bucket and public URLs are returned.
    """

    def __init__(self) -> None:
        """Initialize the Veo video generator."""
        settings = get_settings()
        
        # Initialize client with Vertex AI
        self._client = genai.Client(
            vertexai=True,
            project=settings.gcp_project_id,
            location=settings.gcp_region,
        )
        self._model = settings.veo_video_model
        self._max_retries = settings.video_generation_max_retries
        self._poll_interval = settings.video_generation_poll_interval
        self._output_bucket = settings.video_output_bucket
        self._project_id = settings.gcp_project_id
        
        logger.info(
            f"Initialized VeoVideoGenerator with model: {self._model}, "
            f"output_bucket: {self._output_bucket}, "
            f"max_retries: {self._max_retries}"
        )

    def _get_output_gcs_uri(self, prefix: str = "videos") -> str:
        """Generate a GCS URI for video output with timestamp prefix."""
        timestamp = int(time.time() * 1000)
        return f"gs://{self._output_bucket}/{prefix}/{timestamp}"

    def _gcs_uri_to_public_url(self, gcs_uri: str) -> str:
        """Convert a GCS URI to a public HTTPS URL."""
        # gs://bucket/path/to/file.mp4 -> https://storage.googleapis.com/bucket/path/to/file.mp4
        if gcs_uri.startswith("gs://"):
            path = gcs_uri[5:]  # Remove "gs://"
            return f"https://storage.googleapis.com/{path}"
        return gcs_uri

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
        Generate a video from a text prompt using Veo 3.1.
        
        The video is generated asynchronously and stored in GCS.
        This method polls the operation until completion.
        
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
        """
        try:
            logger.info(
                f"Generating video with prompt: {prompt[:100]}... "
                f"(duration={duration_seconds}s, resolution={resolution}, audio={generate_audio})"
            )
            
            # Generate unique output path
            output_gcs_uri = self._get_output_gcs_uri()
            
            # Build config
            config_params = {
                "aspect_ratio": aspect_ratio,
                "output_gcs_uri": output_gcs_uri,
                "number_of_videos": 1,
                "duration_seconds": duration_seconds,
                "generate_audio": generate_audio,
                "person_generation": person_generation,
            }
            
            # Add resolution for Veo 3 models
            if "veo-3" in self._model:
                config_params["resolution"] = resolution
            
            # Add optional parameters
            if negative_prompt:
                config_params["negative_prompt"] = negative_prompt
            if seed is not None:
                config_params["seed"] = seed
            
            config = GenerateVideosConfig(**config_params)
            
            # Start video generation (this returns a long-running operation)
            operation = await self._start_generation_with_retry(prompt, config)
            
            # Poll for completion
            video_result = await self._poll_operation(operation)
            
            # Extract video URI from result
            if not video_result or not video_result.generated_videos:
                raise VideoGenerationError("No video was generated")
            
            generated_video = video_result.generated_videos[0]
            gcs_uri = generated_video.video.uri if generated_video.video else None
            
            if not gcs_uri:
                raise VideoGenerationError("Video generation completed but no URI was returned")
            
            mime_type = generated_video.video.mime_type if generated_video.video else "video/mp4"
            
            # Convert to public URL
            public_url = self._gcs_uri_to_public_url(gcs_uri)
            
            logger.info(f"Video generated successfully: {public_url}")
            
            return GeneratedVideo(
                gcs_uri=gcs_uri,
                public_url=public_url,
                mime_type=mime_type,
                duration_seconds=duration_seconds,
                resolution=resolution,
                prompt=prompt,
                has_audio=generate_audio,
            )
            
        except VideoGenerationError:
            raise
        except Exception as e:
            logger.error(f"Video generation failed: {e}")
            raise VideoGenerationError(f"Failed to generate video: {str(e)}", e)

    async def _start_generation_with_retry(self, prompt: str, config: GenerateVideosConfig):
        """Start video generation with retry logic for rate limit errors."""
        retry_decorator = retry(
            retry=retry_if_exception(_is_rate_limit_error),
            stop=stop_after_attempt(self._max_retries + 1),
            wait=wait_exponential(multiplier=1, min=1, max=30),
            before_sleep=before_sleep_log(logger, logging.WARNING),
            reraise=True,
        )
        
        @retry_decorator
        def _start():
            return self._client.models.generate_videos(
                model=self._model,
                prompt=prompt,
                config=config,
            )
        
        # Run synchronous SDK call in thread pool
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _start)

    async def _poll_operation(self, operation):
        """
        Poll a long-running operation until completion.
        
        Args:
            operation: The operation to poll
            
        Returns:
            The operation result when complete
            
        Raises:
            VideoGenerationError: If the operation fails or times out
        """
        max_wait_time = 600  # 10 minutes max
        start_time = time.time()
        
        logger.info(f"Polling video generation operation (max {max_wait_time}s)...")
        
        while not operation.done:
            elapsed = time.time() - start_time
            if elapsed > max_wait_time:
                raise VideoGenerationError(
                    f"Video generation timed out after {max_wait_time} seconds"
                )
            
            logger.debug(f"Video generation in progress... ({int(elapsed)}s elapsed)")
            await asyncio.sleep(self._poll_interval)
            
            # Get updated operation status
            loop = asyncio.get_event_loop()
            operation = await loop.run_in_executor(
                None, 
                lambda: self._client.operations.get(operation)
            )
        
        elapsed = time.time() - start_time
        logger.info(f"Video generation completed in {int(elapsed)} seconds")
        
        # Check for errors
        if hasattr(operation, 'error') and operation.error:
            raise VideoGenerationError(f"Video generation failed: {operation.error}")
        
        # Check for RAI filtered content
        if hasattr(operation, 'result'):
            result = operation.result
            if hasattr(result, 'rai_media_filtered_count') and result.rai_media_filtered_count > 0:
                reasons = getattr(result, 'rai_media_filtered_reasons', [])
                reason_str = reasons[0] if reasons else "content policy violation"
                raise VideoGenerationError(
                    f"Video was filtered due to content policy: {reason_str}"
                )
            return result
        
        return operation.response if hasattr(operation, 'response') else None

    async def health_check(self) -> bool:
        """Check if the Veo service is available."""
        try:
            # Just verify we can access the model
            # We don't actually generate a video for health check
            return self._client is not None
        except Exception as e:
            logger.warning(f"Health check failed: {e}")
            return False
