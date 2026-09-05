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
    GEMI_MODEL: str = "gemini-1.5-pro"

    # App
    ENVIRONMENT: str = "development"
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000"

    # File Upload
    MAX_UPLOAD_SIZE_MB: int = 50
    ALLOWED_UPLOAD_EXTENSIONS: str = ".py,.js,.ts,.jsx,.tsx,.json,.yaml,.yml,.md,.txt,.csv,.zip,.pdf,.png,.jpg,.jpeg,.gif,.html,.css,.sql,.sh,.dockerfile,.toml,.ini,.cfg,.conf,.xml,.java,.kt,.rb,.go,.rs,.cs,.php,.swift,.scala,.clj,.hs,.ml,.fs,.vb,.pl,.r,.m,.lua,.dart,.elm,.ex,.exs,.erl,.hrl,.pp,.tf,.tfvars,.hcl,.nomad,.helm,.k8s,.yaml"
    UPLOAD_DIRECTORY: str = "storage/submissions"

    @property
    def cors_origins_list(self) -> List[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def max_upload_size_bytes(self) -> int:
        return self.MAX_UPLOAD_SIZE_MB * 1024 * 1024

    @property
    def allowed_extensions_list(self) -> List[str]:
        return [ext.strip().lower() for ext in self.ALLOWED_UPLOAD_EXTENSIONS.split(",") if ext.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
