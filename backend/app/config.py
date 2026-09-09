from functools import lru_cache
from secrets import token_urlsafe

from pydantic import AliasChoices, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "CareerPilot API"
    environment: str = "development"
    database_url: str = "postgresql+psycopg://db_user:db_password@localhost:5432/careerpilot"
    frontend_url: str = "http://localhost:5173"
    jwt_secret_key: str = Field(
        default_factory=lambda: token_urlsafe(32),
        validation_alias=AliasChoices("JWT_SECRET", "JWT_SECRET_KEY"),
    )
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    resume_upload_dir: str = "uploads/resumes"
    resume_max_size_mb: int = Field(default=10, ge=1, le=50)
    ai_provider: str | None = None
    ai_api_key: str | None = None
    ai_api_url: str | None = None
    ai_model: str = "careerpilot-local"
    ai_timeout_seconds: float = 15.0

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @model_validator(mode="after")
    def validate_security_settings(self) -> "Settings":
        if self.environment.lower() in {"production", "prod"}:
            if len(self.jwt_secret_key) < 32:
                raise ValueError("JWT_SECRET_KEY must be a unique random value of at least 32 characters in production")
            if not self.frontend_url.startswith("https://"):
                raise ValueError("FRONTEND_URL must use HTTPS in production")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
