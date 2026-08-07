"""Application configuration management using Pydantic Settings.

Loads environment variables from .env file and performs type validation.
"""

from typing import List, Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central settings class for Smart Community Platform."""

    # --------------------------------------------------------------------------
    # Application Settings
    # --------------------------------------------------------------------------
    APP_NAME: str = Field(default="Smart Community Platform", description="Name of the application")
    APP_ENV: str = Field(default="development", description="Application runtime environment")
    DEBUG: bool = Field(default=True, description="Enable or disable debug mode")
    HOST: str = Field(default="0.0.0.0", description="Server host address")
    PORT: int = Field(default=8001, description="Server listening port")
    CORS_ORIGINS: List[str] = Field(
        default=["http://localhost:8001", "http://127.0.0.1:8001", "http://localhost:8000"],
        description="Allowed origins for Cross-Origin Resource Sharing",
    )

    # --------------------------------------------------------------------------
    # Database Settings
    # --------------------------------------------------------------------------
    DATABASE_URL: str = Field(
        default="postgresql://postgres:postgres@localhost:5432/smart_community",
        description="PostgreSQL connection string",
    )

    # --------------------------------------------------------------------------
    # Authentication & Security
    # --------------------------------------------------------------------------
    SECRET_KEY: str = Field(
        default="supersecretdefaultkey_change_in_production_environment_123456",
        description="JWT secret key for encoding/decoding tokens",
    )
    ALGORITHM: str = Field(default="HS256", description="JWT signing algorithm")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=60, description="JWT token validity period in minutes")
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(default=7, description="Refresh token validity period in days")

    # --------------------------------------------------------------------------
    # Cloudinary Credentials & Upload Settings
    # --------------------------------------------------------------------------
    CLOUDINARY_CLOUD_NAME: Optional[str] = Field(default=None, description="Cloudinary cloud name")
    CLOUDINARY_API_KEY: Optional[str] = Field(default=None, description="Cloudinary API key")
    CLOUDINARY_API_SECRET: Optional[str] = Field(default=None, description="Cloudinary API secret")
    MAX_IMAGE_SIZE_MB: int = Field(default=5, description="Maximum image upload size in MB")
    ALLOWED_IMAGE_TYPES: List[str] = Field(default=["jpg", "jpeg", "png", "webp"], description="Allowed image extensions")
    MAX_IMAGES_PER_ISSUE: int = Field(default=5, description="Max images per issue")

    # --------------------------------------------------------------------------
    # Email Settings (Optional)
    # --------------------------------------------------------------------------
    MAIL_USERNAME: Optional[str] = Field(default=None, description="SMTP email username")
    MAIL_PASSWORD: Optional[str] = Field(default=None, description="SMTP email password")
    MAIL_FROM: str = Field(default="noreply@smartcommunity.org", description="Sender email address")
    MAIL_PORT: int = Field(default=587, description="SMTP port")
    MAIL_SERVER: str = Field(default="smtp.gmail.com", description="SMTP server host")
    MAIL_STARTTLS: bool = Field(default=True, description="Use STARTTLS")
    MAIL_SSL_TLS: bool = Field(default=False, description="Use SSL/TLS")

    # --------------------------------------------------------------------------
    # AI & External APIs (Phase 2/3)
    # --------------------------------------------------------------------------
    GROQ_API_KEY: Optional[str] = Field(default=None, description="Groq API key for LLM services")
    HUGGINGFACE_MODEL_CACHE_DIR: str = Field(default="./ml_models", description="Local cache directory for HuggingFace models")
    YOLO_MODEL_PATH: str = Field(default="./ml_models/yolov8n.pt", description="Path to YOLOv8 model weights")
    ML_CONFIDENCE_THRESHOLD: float = Field(default=0.75, description="Threshold for AI confidence ratings")
    ML_AUTO_APPLY_THRESHOLD: float = Field(default=0.85, description="Threshold for auto-applying AI classifications")
    ML_BATCH_SIZE: int = Field(default=8, description="Batch size for ML inference tasks")
    ML_DEVICE: str = Field(default="cpu", description="Inference device (cpu or cuda)")
    FRONTEND_URL: str = Field(default="http://localhost:8001", description="Frontend base URL")

    # --------------------------------------------------------------------------
    # AI Agents Settings
    # --------------------------------------------------------------------------
    AGENT_REPORTER_INTERVAL_MINUTES: int = Field(default=5, description="Reporter agent schedule in minutes")
    AGENT_RESOLVER_INTERVAL_HOURS: int = Field(default=6, description="Resolver agent schedule in hours")
    AGENT_ANALYST_DAY_OF_WEEK: int = Field(default=6, description="Analyst agent day of week (6=Sunday)")
    AGENT_ANALYST_HOUR: int = Field(default=2, description="Analyst agent hour (2am)")
    AGENT_VOLUNTEER_INTERVAL_HOURS: int = Field(default=1, description="Volunteer agent schedule in hours")
    AGENT_COMMUNITY_MAX_TOKENS: int = Field(default=300, description="Community agent response max tokens")
    AGENT_MAX_RETRIES: int = Field(default=3, description="Max retries per agent operation")
    AGENT_ESCALATION_DAYS: int = Field(default=7, description="Days before in_progress escalation")
    AGENT_AUTO_CLOSE_DAYS: int = Field(default=7, description="Days before pending_citizen auto close")
    AGENT_MIN_VOLUNTEER_MATCH_SCORE: float = Field(default=0.6, description="Minimum match score threshold")
    SYSTEM_USER_ID: int = Field(default=1, description="Special system user ID for agent actions")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


# Global settings instance
settings = Settings()
