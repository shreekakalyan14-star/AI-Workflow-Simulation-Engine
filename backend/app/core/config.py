"""
Central application configuration.

All settings are loaded from environment variables (see .env.example).
Nothing here is hard-coded so the service can be re-pointed at a different
database / auth issuer when it is integrated into the larger
AI Internship Simulator platform.
"""
from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database
    DATABASE_URL: str = "postgresql://aiwse:aiwse_password@localhost:5432/aiwse_db"

    # Auth (validation only — tokens are issued by the parent platform / Module 1)
    JWT_SECRET_KEY: str = "change-me-to-the-shared-signing-secret"
    JWT_ALGORITHM: str = "HS256"

    # AI provider
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-1.5-pro"

    # App
    ENVIRONMENT: str = "development"
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000"

    @property
    def cors_origins_list(self) -> List[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
