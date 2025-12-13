"""Gemini 2.5 Flash Image implementation of ImageGenerator."""

import asyncio
import logging

from google import genai
from google.api_core.exceptions import ResourceExhausted
from google.genai.types import GenerateContentConfig, Modality
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    before_sleep_log,
    retry_if_exception,
)

from ...config.settings import get_settings
from ...domain.interfaces.image_generator import (
    GeneratedImage,
    GeneratedImages,
    ImageGenerationError,
    ImageGenerator,
)

logger = logging.getLogger(__name__)


def _is_rate_limit_error(exception: BaseException) -> bool:
    """
    Check if the exception is a rate limit (429 RESOURCE_EXHAUSTED) error.
    
    Returns True only for rate limit errors that should be retried.
    Other errors (like invalid prompts, auth errors, etc.) will not be retried.
    """
    # Check for Google's ResourceExhausted exception
    if isinstance(exception, ResourceExhausted):
        return True
    
    # Also check for generic exceptions with rate limit indicators in the message
    error_str = str(exception).lower()
    return "429" in error_str or "resource_exhausted" in error_str


class GeminiImageGenerator(ImageGenerator):
    """
    Image generator using Gemini 2.5 Flash Image model.
    
    Uses the google-genai SDK to generate images via Vertex AI.
    Implements exponential backoff retry for rate limit errors (429 RESOURCE_EXHAUSTED).
    """

    def __init__(self) -> None:
        """Initialize the Gemini client."""
        settings = get_settings()
        
        # Initialize client with Vertex AI
        self._client = genai.Client(
            vertexai=True,
            project=settings.gcp_project_id,
            location=settings.gcp_region,
        )
        self._model = settings.gemini_image_model
        self._max_retries = settings.image_generation_max_retries
        logger.info(
            f"Initialized GeminiImageGenerator with model: {self._model}, "
            f"max_retries: {self._max_retries}"
        )

    async def generate(
        self,
        prompt: str,
        aspect_ratio: str = "1:1",
        number_of_images: int = 1,
        temperature: float = 1.0,
    ) -> GeneratedImages:
        """
        Generate one or more images from a text prompt using Gemini.
        
        Args:
            prompt: Text description of the image to generate
            aspect_ratio: Aspect ratio (e.g., "1:1", "16:9")
            number_of_images: Number of images to generate (1-4)
            temperature: Controls randomness (0.0-2.0, default 1.0)
            
        Returns:
            GeneratedImages with image data and metadata
            
        Note:
            This method implements exponential backoff retry for rate limit
            (429 RESOURCE_EXHAUSTED) errors. The number of retries is configurable
            via the IMAGE_GENERATION_MAX_RETRIES environment variable (default: 3).
            
            Retry timing: 1s -> 2s -> 4s -> 8s (max), with jitter.
            
            Since Gemini's generate_content API doesn't support generating multiple
            images in a single call, we generate them sequentially when number_of_images > 1.
        """
        try:
            # Clamp number_of_images to valid range
            num_images = max(1, min(4, number_of_images))
            
            # Generate images sequentially (Gemini API doesn't support batch generation)
            images: list[GeneratedImage] = []
            for i in range(num_images):
                logger.info(f"Generating image {i + 1}/{num_images}...")
                image = self._generate_single_with_retry(prompt, aspect_ratio, temperature)
                images.append(image)
                
                # Small delay between requests to avoid rate limiting
                if i < num_images - 1:
                    await asyncio.sleep(0.5)
            
            logger.info(f"Successfully generated {len(images)} image(s)")
            return GeneratedImages(images=images, prompt=prompt)
            
        except ImageGenerationError:
            raise
        except Exception as e:
            logger.error(f"Image generation failed: {e}")
            raise ImageGenerationError(f"Failed to generate image: {str(e)}", e)

    def _generate_single_with_retry(
        self, prompt: str, aspect_ratio: str, temperature: float
    ) -> GeneratedImage:
        """
        Execute a single image generation API call with retry logic for rate limit errors.
        
        Uses exponential backoff: waits 1s after first failure, then 2s, 4s, up to 8s max.
        Only retries on 429 RESOURCE_EXHAUSTED errors; other errors are raised immediately.
        """
        # Build the retry decorator with instance configuration
        retry_decorator = retry(
            retry=retry_if_exception(_is_rate_limit_error),
            stop=stop_after_attempt(self._max_retries + 1),  # +1 because first attempt isn't a retry
            wait=wait_exponential(multiplier=1, min=1, max=8),
            before_sleep=before_sleep_log(logger, logging.WARNING),
            reraise=True,
        )
        
        @retry_decorator
        def _call_api() -> GeneratedImage:
            logger.info(f"Generating image with prompt: {prompt[:100]}... (temp={temperature})")
            
            # Enhance prompt to ensure image generation
            enhanced_prompt = f"Generate an image: {prompt}"
            
            # Generate content with image modality and temperature
            response = self._client.models.generate_content(
                model=self._model,
                contents=enhanced_prompt,
                config=GenerateContentConfig(
                    response_modalities=[Modality.TEXT, Modality.IMAGE],
                    temperature=temperature,
                ),
            )
            
            # Extract image and text from response
            image_data: bytes | None = None
            mime_type: str = "image/png"
            text_response: str | None = None
            
            if response.candidates and response.candidates[0].content.parts:
                for part in response.candidates[0].content.parts:
                    if hasattr(part, 'text') and part.text:
                        text_response = part.text
                    elif hasattr(part, 'inline_data') and part.inline_data:
                        image_data = part.inline_data.data
                        if hasattr(part.inline_data, 'mime_type'):
                            mime_type = part.inline_data.mime_type or "image/png"
            
            if image_data is None:
                raise ImageGenerationError(
                    f"No image generated. Model response: {text_response or 'No response'}"
                )
            
            logger.info(f"Successfully generated image ({len(image_data)} bytes)")
            
            return GeneratedImage(
                data=image_data,
                mime_type=mime_type,
                prompt=prompt,
                text_response=text_response,
            )
        
        return _call_api()

    async def health_check(self) -> bool:
        """Check if the Gemini service is available."""
        try:
            # Simple check - try to get model info
            response = self._client.models.generate_content(
                model=self._model,
                contents="Say 'ok'",
                config=GenerateContentConfig(
                    response_modalities=[Modality.TEXT],
                ),
            )
            return response is not None
        except Exception as e:
            logger.warning(f"Health check failed: {e}")
            return False
