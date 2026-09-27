"""Safe, typed failures for the Nebius/NVIDIA AI boundary."""


class AIServiceError(RuntimeError):
    """Base class for failures that are safe to surface to an API client."""

    public_message = "NEXORA AI service request failed."
    health_status = "error"


class AIConfigurationError(AIServiceError):
    public_message = "Nebius AI is not configured."
    health_status = "not_configured"


class AIProviderNotConfiguredError(AIConfigurationError):
    """Backward-compatible name for the explicit unconfigured provider port."""


class AIAuthenticationError(AIServiceError):
    public_message = "Nebius authentication failed."
    health_status = "authentication_failed"


class AIModelUnavailableError(AIServiceError):
    public_message = "Configured Nemotron model is unavailable."
    health_status = "model_unavailable"


class AIProviderUnavailableError(AIServiceError):
    public_message = "Nebius AI provider is unavailable."
    health_status = "provider_unavailable"


class AIProviderError(AIServiceError):
    public_message = "Nebius AI provider returned an unexpected response."
    health_status = "error"


class AITimeoutError(AIServiceError):
    public_message = "AI provider request timed out."
    health_status = "timeout"


class AIResponseValidationError(AIServiceError):
    public_message = "AI response validation failed."
    health_status = "error"


class AIRequestError(AIServiceError):
    public_message = "AI provider rejected the request."
    health_status = "error"
