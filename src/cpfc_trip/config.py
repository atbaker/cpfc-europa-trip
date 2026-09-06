"""Runtime configuration with safe local defaults."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings sourced from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: Literal["development", "test", "production"] = "development"
    api_base_url: str = "http://localhost:8000"
    frontend_origin: str = "http://localhost:3000"
    session_secret: str = "local-development-secret"

    database_url: str = "postgresql+asyncpg://cpfc:cpfc@localhost:5432/cpfc_trip"
    database_migration_url: str = "postgresql+psycopg://cpfc:cpfc@localhost:5432/cpfc_trip"

    temporal_address: str = "localhost:7233"
    temporal_namespace: str = "default"
    temporal_task_queue: str = "cpfc-trip-planner"
    temporal_api_key: str | None = None
    temporal_tls: bool = False
    inactivity_timeout_seconds: int = Field(default=600, ge=5, le=86_400)

    planner_mode: Literal["mock", "openai"] = "mock"
    openai_api_key: str | None = None
    openai_model: str = "gpt-5.6-terra"
    openai_reasoning_effort: Literal["minimal", "low", "medium", "high"] = "medium"

    email_mode: Literal["preview", "resend"] = "preview"
    resend_api_key: str | None = None
    resend_from_email: str = "Crystal Palace Away Days <awaydays@example.com>"

    logfire_enabled: bool = False
    logfire_token: str | None = None

    @model_validator(mode="after")
    def validate_production_secrets(self) -> Settings:
        if self.app_env == "production" and self.session_secret == "local-development-secret":
            raise ValueError("SESSION_SECRET must be changed in production")
        if self.app_env == "production" and not self.temporal_api_key:
            raise ValueError("TEMPORAL_API_KEY is required in production")
        if self.temporal_api_key and not self.temporal_tls:
            raise ValueError("TEMPORAL_TLS must be true when TEMPORAL_API_KEY is set")
        if self.logfire_enabled and not self.logfire_token:
            raise ValueError("LOGFIRE_TOKEN is required when LOGFIRE_ENABLED is true")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
