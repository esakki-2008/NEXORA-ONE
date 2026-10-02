"""Application configuration loaded from environment variables only."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings.

    Secrets are represented as ``SecretStr`` and are never included in normal
    representations. Nebius fields configure the server-only Phase 3 provider;
    no frontend setting is read for the provider credential.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "NEXORA ONE API"
    environment: Literal["development", "test", "staging", "production"] = "development"
    debug: bool = False
    database_url: str = "sqlite:///./data/nexora.db"

    nebius_api_key: SecretStr | None = None
    nebius_model: str | None = None
    nebius_base_url: str | None = None
    nebius_timeout_seconds: float = Field(default=60.0, gt=0, le=300)
    nebius_max_retries: int = Field(default=2, ge=0, le=5)
    tavily_api_key: SecretStr | None = None

    verification_max_attempts: int = Field(default=3, ge=1, le=3)
    verification_retry_delay_seconds: float = Field(default=0.01, ge=0.0, le=1.0)
    verification_max_evidence_age_seconds: int = Field(default=300, ge=1, le=86_400)

    # Phase 9 reference security boundary. A missing secret creates an
    # ephemeral server-only signing key; production must provide this value
    # from a secret manager instead of committing it.
    security_auth_secret: SecretStr | None = None
    security_token_ttl_seconds: int = Field(default=900, ge=60, le=86_400)
    security_max_request_bytes: int = Field(default=262_144, ge=16_384, le=2_097_152)

    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    @property
    def cors_origin_list(self) -> list[str]:
        """Return normalized CORS origins without exposing any other settings."""

        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide immutable-by-convention settings instance."""

    return Settings()
