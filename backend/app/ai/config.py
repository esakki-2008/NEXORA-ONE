"""Nebius configuration adapter with secret-safe inspection."""

from pydantic import SecretStr

from backend.app.config.settings import Settings
from backend.app.security.validation import validate_outbound_https_url


class NebiusConfig:
    """Immutable-by-convention provider configuration.

    The API key is retained only in a ``SecretStr`` and is never included in
    health responses, activity metadata, exceptions, or logs.
    """

    def __init__(
        self,
        *,
        api_key: SecretStr | None,
        base_url: str | None,
        model: str | None,
        timeout_seconds: float = 60.0,
        max_retries: int = 2,
    ) -> None:
        self.api_key = api_key
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if max_retries < 0:
            raise ValueError("max_retries must not be negative")
        self.base_url = (
            validate_outbound_https_url(base_url.strip(), label="NEBIUS_BASE_URL")
            if base_url and base_url.strip()
            else None
        )
        self.model = model.strip() if model else None
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries

    @classmethod
    def from_settings(cls, settings: Settings) -> "NebiusConfig":
        return cls(
            api_key=settings.nebius_api_key,
            base_url=settings.nebius_base_url,
            model=settings.nebius_model,
            timeout_seconds=settings.nebius_timeout_seconds,
            max_retries=settings.nebius_max_retries,
        )

    @property
    def missing_fields(self) -> list[str]:
        missing: list[str] = []
        if self.api_key is None or not self.api_key.get_secret_value().strip():
            missing.append("NEBIUS_API_KEY")
        if not self.base_url:
            missing.append("NEBIUS_BASE_URL")
        if not self.model:
            missing.append("NEBIUS_MODEL")
        return missing

    @property
    def is_configured(self) -> bool:
        return not self.missing_fields
