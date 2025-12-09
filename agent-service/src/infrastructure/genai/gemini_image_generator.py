"""Gemini 2.5 Flash Image implementation of ImageGenerator."""

import logging
from io import BytesIO

from google import genai
from google.genai.types import GenerateContentConfig, Modality

from ...config.settings import get_settings
from ...domain.interfaces.image_generator import (
    GeneratedImage,
    ImageGenerationError,
    ImageGenerator,
)

logger = logging.getLogger(__name__)


class GeminiImageGenerator(ImageGenerator):
    """
    Image generator using Gemini 2.5 Flash Image model.
    
    Uses the google-genai SDK to generate images via Vertex AI.
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
        logger.info(f"Initialized GeminiImageGenerator with model: {self._model}")

    async def generate(
        self,
        prompt: str,
        aspect_ratio: str = "1:1",
    ) -> GeneratedImage:
        """
        Generate an image from a text prompt using Gemini.
        
        Args:
            prompt: Text description of the image to generate
            aspect_ratio: Aspect ratio (e.g., "1:1", "16:9")
            
        Returns:
            GeneratedImage with image data and metadata
        """
        try:
            logger.info(f"Generating image with prompt: {prompt[:100]}...")
            
            # Enhance prompt to ensure image generation
            enhanced_prompt = f"Generate an image: {prompt}"
            
            # Generate content with image modality
            response = self._client.models.generate_content(
                model=self._model,
                contents=enhanced_prompt,
                config=GenerateContentConfig(
                    response_modalities=[Modality.TEXT, Modality.IMAGE],
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
            
        except ImageGenerationError:
            raise
        except Exception as e:
            logger.error(f"Image generation failed: {e}")
            raise ImageGenerationError(f"Failed to generate image: {str(e)}", e)

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
