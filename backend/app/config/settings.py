"""Application configuration loaded from environment variables only."""

from functools import lru_cache
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings.

    Secrets are represented as ``SecretStr`` and are never included in normal
    representations. Phase 1 deliberately does not instantiate an external AI
    client; the Nebius fields are reserved for the Phase 3 adapter.
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
    tavily_api_key: SecretStr | None = None

    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    @property
    def cors_origin_list(self) -> list[str]:
        """Return normalized CORS origins without exposing any other settings."""

        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide immutable-by-convention settings instance."""

    return Settings()
