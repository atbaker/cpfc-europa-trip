from typing import Literal, Self

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    app_env: Literal["development", "test", "preview", "production"] = "development"
    frontend_origin: str = "http://localhost:3000"
    additional_frontend_origins: str = ""
    static_export_dir: str = ""
    preview_username: str = ""
    preview_password: SecretStr = SecretStr("")
    database_url: str = "postgresql+asyncpg://cpfc:cpfc@localhost:5432/cpfc"
    contact_encryption_key: SecretStr = SecretStr("")
    session_secret: SecretStr = SecretStr("")
    temporal_address: str = "localhost:7233"
    temporal_namespace: str = "default"
    temporal_task_queue: str = "cpfc-trip-v3"
    temporal_api_key: SecretStr = SecretStr("")
    temporal_tls: bool = False
    worker_build_id: str = ""
    planner_mode: Literal["live", "recorded"] = "live"
    email_mode: Literal["preview", "resend"] = "preview"
    searchapi_api_key: SecretStr = SecretStr("")
    searchapi_enabled: bool = True
    google_cloud_project: str = ""
    google_cloud_location: Literal["eu"] = "eu"
    google_auth_mode: Literal["adc", "gcloud", "api_key"] = "adc"
    gemini_api_key: SecretStr = SecretStr("")
    google_gcloud_configuration: str = ""
    google_gcloud_account: str = ""
    resend_api_key: SecretStr = SecretStr("")
    resend_from_email: str = ""
    resend_webhook_secret: SecretStr = SecretStr("")
    inactivity_timeout_seconds: int = 600
    cloud_sql_instance: str = ""
    database_user: str = ""
    database_name: str = "cpfc"

    @model_validator(mode="after")
    def production(self) -> Self:
        if self.google_auth_mode == "api_key" and not self.gemini_api_key.get_secret_value():
            raise ValueError("Gemini API key is required for api_key authentication")
        if self.app_env == "preview" and (
            not self.preview_username or not self.preview_password.get_secret_value()
        ):
            raise ValueError("Preview requires access credentials")
        if self.app_env == "production":
            if self.google_auth_mode != "adc" or not self.google_cloud_project:
                raise ValueError(
                    "Production requires a Google Cloud project and ADC runtime identity"
                )
            if self.planner_mode != "live" or self.email_mode != "resend":
                raise ValueError("Production requires live planning and Resend")
            if not self.temporal_tls or not self.worker_build_id:
                raise ValueError("Production requires Temporal TLS and an immutable build ID")
        return self
