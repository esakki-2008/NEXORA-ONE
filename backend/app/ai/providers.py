"""Explicitly unconfigured AI providers for the Phase 1 boundary."""

from pydantic import SecretStr

from backend.app.ai.contracts import AIRequest, StructuredAgentDecision


class AIProviderNotConfiguredError(RuntimeError):
    """Raised instead of fabricating an AI answer or silently using another vendor."""


class UnconfiguredAIProvider:
    """Safe default provider used until the Nebius adapter is delivered."""

    async def decide(self, request: AIRequest) -> StructuredAgentDecision:
        del request
        raise AIProviderNotConfiguredError(
            "No AI provider is configured. Nebius Token Factory with NVIDIA Nemotron "
            "is intentionally integrated in Phase 3."
        )


class NebiusNemotronProvider:
    """Configuration-shaped adapter reserved for the real Phase 3 integration.

    This class deliberately performs no network call in Phase 1. Keeping the
    provider contract and configuration together lets Phase 3 add a tested
    HTTP client without changing agent or API boundaries.
    """

    def __init__(
        self,
        *,
        api_key: SecretStr,
        model: str,
        base_url: str,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = base_url

    async def decide(self, request: AIRequest) -> StructuredAgentDecision:
        del request
        raise AIProviderNotConfiguredError(
            "The Nebius/NVIDIA Nemotron transport is not implemented in Phase 1"
        )
