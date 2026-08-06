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
    # Cloudinary Credentials (Optional)
    # --------------------------------------------------------------------------
    CLOUDINARY_CLOUD_NAME: Optional[str] = Field(default=None, description="Cloudinary cloud name")
    CLOUDINARY_API_KEY: Optional[str] = Field(default=None, description="Cloudinary API key")
    CLOUDINARY_API_SECRET: Optional[str] = Field(default=None, description="Cloudinary API secret")

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

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


# Global settings instance
settings = Settings()
