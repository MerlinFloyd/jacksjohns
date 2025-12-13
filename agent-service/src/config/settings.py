"""Application configuration using pydantic-settings."""

from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # GCP Configuration
    gcp_project_id: str = "jacks-johns"
    gcp_region: str = "us-central1"

    # Model Configuration
    gemini_model: str = "gemini-3-pro-preview"
    gemini_image_model: str = "gemini-3-pro-image-preview"

    # Service Configuration
    agent_service_host: str = "0.0.0.0"
    agent_service_port: int = 8000

    # Google Application Credentials (optional - can use ADC)
    google_application_credentials: str | None = None

    # Firestore Configuration
    firestore_database: str = "jacksjohns-bot"  # Named Firestore database
    firestore_collection: str = "personas"
    use_firestore: bool = True  # Set to False to use in-memory storage

    # Agent Engine Configuration (for Sessions and Memory Bank)
    agent_engine_id: str | None = None  # Will be auto-created if not set
    use_agent_engine: bool = True  # Set to False to disable sessions/memory
    agent_engine_display_name: str = "jacksjohns-bot-engine"

    # Retry Configuration
    image_generation_max_retries: int = 3  # Max retries for image generation API calls

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
