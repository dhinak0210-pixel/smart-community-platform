"""Free tier specific configuration for Smart Community Platform."""

import os
from typing import Optional, List
from pydantic_settings import BaseSettings


class FreeSettings(BaseSettings):
    DATABASE_URL: str = "sqlite:///./test.sqlite"
    SECRET_KEY: str = "default-free-tier-secret-key-32-chars-min"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    CLOUDINARY_CLOUD_NAME: str = "demo"
    CLOUDINARY_API_KEY: str = "123456789"
    CLOUDINARY_API_SECRET: str = "secret"

    GROQ_API_KEY: Optional[str] = None
    HUGGINGFACE_API_KEY: Optional[str] = None

    RESEND_API_KEY: Optional[str] = None
    EMAIL_FROM: str = "noreply@smartcommunity.app"
    EMAIL_FROM_NAME: str = "Smart Community Platform"
    EMAIL_USER: Optional[str] = None
    EMAIL_PASSWORD: Optional[str] = None
    EMAIL_HOST: str = "smtp.gmail.com"
    EMAIL_PORT: int = 587

    FRONTEND_URL: str = "https://smartcommunity.vercel.app"
    CORS_ORIGINS: str = "https://smartcommunity.vercel.app,http://localhost:3000,http://127.0.0.1:3000"

    ENVIRONMENT: str = "production"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    ML_MODE: str = "lightweight"
    ML_DEVICE: str = "cpu"
    ML_CONFIDENCE_THRESHOLD: float = 0.75
    ML_AUTO_APPLY_THRESHOLD: float = 0.85
    HUGGINGFACE_MODEL_CACHE_DIR: str = "./ml_models"

    AGENT_REPORTER_INTERVAL_MINUTES: int = 5
    AGENT_RESOLVER_INTERVAL_HOURS: int = 6
    AGENT_ANALYST_DAY_OF_WEEK: int = 6
    AGENT_ANALYST_HOUR: int = 2
    AGENT_VOLUNTEER_INTERVAL_HOURS: int = 1
    AGENT_MAX_RETRIES: int = 3
    AGENT_ESCALATION_DAYS: int = 7
    AGENT_AUTO_CLOSE_DAYS: int = 7
    AGENT_MIN_VOLUNTEER_MATCH_SCORE: float = 0.6
    SYSTEM_USER_ID: int = 1

    MAX_IMAGE_SIZE_MB: int = 5
    MAX_IMAGES_PER_ISSUE: int = 5
    ALLOWED_IMAGE_TYPES: str = "jpg,jpeg,png,webp"

    @property
    def is_free_tier(self) -> bool:
        return self.ML_MODE == "lightweight"

    @property
    def use_groq(self) -> bool:
        return bool(self.GROQ_API_KEY)

    @property
    def use_hf_api(self) -> bool:
        return bool(self.HUGGINGFACE_API_KEY)

    @property
    def cors_origins_list(self) -> List[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    class Config:
        env_file = ".env"
        extra = "ignore"
        case_sensitive = False


free_settings = FreeSettings()
