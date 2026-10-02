"""Nebius Token Factory provider for NVIDIA Nemotron.

Nebius exposes an OpenAI-compatible chat-completions transport. NEXORA talks
straight to that HTTP contract through ``httpx``; no alternate model vendor is
used and no provider secret is ever logged or returned.
"""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from typing import Any

import httpx
from pydantic import SecretStr

from backend.app.ai.config import NebiusConfig
from backend.app.ai.contracts import AIRequest
from backend.app.ai.exceptions import (
    AIAuthenticationError,
    AIConfigurationError,
    AIModelUnavailableError,
    AIProviderNotConfiguredError,
    AIProviderUnavailableError,
    AIRequestError,
    AIResponseValidationError,
    AIServiceError,
    AITimeoutError,
)
from backend.app.ai.schemas import (
    AIAnalysisResponse,
    AIHealthResponse,
    AIHealthStatus,
    EvidenceReference,
)
from backend.app.config.settings import Settings


class UnconfiguredAIProvider:
    """Safe provider used explicitly in unit tests or an unconfigured runtime."""

    def health(self) -> AIHealthResponse:
        return AIHealthResponse(
            model="not configured",
            status=AIHealthStatus.NOT_CONFIGURED,
            verified=False,
            message="Nebius AI is not configured.",
        )

    async def decide(self, request: AIRequest) -> AIAnalysisResponse:
        del request
        raise AIProviderNotConfiguredError("Nebius AI is not configured.")


class NebiusNemotronProvider:
    """Bounded Nebius Token Factory client for an NVIDIA Nemotron model."""

    def __init__(
        self,
        config: NebiusConfig | None = None,
        *,
        api_key: SecretStr | None = None,
        model: str | None = None,
        base_url: str | None = None,
        timeout_seconds: float = 60.0,
        max_retries: int = 2,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.config = config or NebiusConfig(
            api_key=api_key,
            model=model,
            base_url=base_url,
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
        )
        self._transport = transport
        self._verified = False
        self._last_status: AIHealthStatus | None = None
        self._last_message: str | None = None
        self._last_verified_at: datetime | None = None

    @classmethod
    def from_settings(
        cls,
        settings: Settings,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> NebiusNemotronProvider:
        return cls(NebiusConfig.from_settings(settings), transport=transport)

    @property
    def api_key(self) -> SecretStr | None:
        return self.config.api_key

    @property
    def model(self) -> str | None:
        return self.config.model

    @property
    def base_url(self) -> str | None:
        return self.config.base_url

    @property
    def endpoint(self) -> str | None:
        if not self.config.base_url:
            return None
        base_url = self.config.base_url.rstrip("/")
        if base_url.endswith("/chat/completions"):
            return base_url
        return f"{base_url}/chat/completions"

    def health(self) -> AIHealthResponse:
        if not self.config.is_configured:
            return AIHealthResponse(
                model=self.config.model or "not configured",
                status=AIHealthStatus.NOT_CONFIGURED,
                verified=False,
                message="Nebius AI is not configured.",
            )

        if self._last_status is not None and self._last_status != AIHealthStatus.CONFIGURED:
            return AIHealthResponse(
                model=self.config.model or "configured",
                status=self._last_status,
                verified=False,
                message=self._last_message or "Nebius AI provider verification failed.",
            )

        return AIHealthResponse(
            model=self.config.model or "configured",
            status=AIHealthStatus.CONFIGURED,
            verified=self._verified,
            message=(
                "Nebius Token Factory verification succeeded."
                if self._verified
                else "Provider configuration is present; connectivity has not been verified."
            ),
            last_verified_at=self._last_verified_at,
        )

    def _mark_failure(self, error: AIServiceError) -> None:
        self._verified = False
        self._last_status = AIHealthStatus(error.health_status)
        self._last_message = error.public_message

    def _mark_success(self) -> None:
        self._verified = True
        self._last_status = AIHealthStatus.CONFIGURED
        self._last_message = "Nebius Token Factory verification succeeded."
        self._last_verified_at = datetime.now(UTC)

    async def decide(self, request: AIRequest) -> AIAnalysisResponse:
        if not self.config.is_configured:
            error: AIServiceError = AIConfigurationError("Nebius AI is not configured.")
            self._mark_failure(error)
            raise error

        api_key = self.config.api_key
        model = self.config.model
        endpoint = self.endpoint
        if api_key is None or model is None or endpoint is None:
            error = AIConfigurationError("Nebius AI configuration is incomplete.")
            self._mark_failure(error)
            raise error

        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": request.system_instruction},
                {"role": "user", "content": request.user_input},
            ],
            "temperature": 0,
            "max_tokens": 2_000,
            "stream": False,
            "response_format": {"type": "json_object"},
        }
        headers = {
            "Authorization": f"Bearer {api_key.get_secret_value()}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        for attempt in range(self.config.max_retries + 1):
            try:
                async with httpx.AsyncClient(
                    timeout=httpx.Timeout(self.config.timeout_seconds),
                    transport=self._transport,
                ) as client:
                    response = await client.post(endpoint, headers=headers, json=payload)
            except httpx.TimeoutException as exc:
                if attempt < self.config.max_retries:
                    await asyncio.sleep(min(0.2 * (attempt + 1), 1.0))
                    continue
                error = AITimeoutError("AI provider request timed out.")
                self._mark_failure(error)
                raise error from exc
            except httpx.NetworkError as exc:
                if attempt < self.config.max_retries:
                    await asyncio.sleep(min(0.2 * (attempt + 1), 1.0))
                    continue
                error = AIProviderUnavailableError("Nebius AI provider is unavailable.")
                self._mark_failure(error)
                raise error from exc
            except httpx.RequestError as exc:
                error = AIProviderUnavailableError("Nebius AI provider is unavailable.")
                self._mark_failure(error)
                raise error from exc

            if response.status_code in (401, 403):
                error = AIAuthenticationError("Nebius authentication failed.")
                self._mark_failure(error)
                raise error
            if response.status_code == 404 or (
                response.status_code == 400 and self._is_model_error(response)
            ):
                error = AIModelUnavailableError("Configured Nemotron model is unavailable.")
                self._mark_failure(error)
                raise error
            if response.status_code in (408, 429, 500, 502, 503, 504):
                if attempt < self.config.max_retries:
                    await asyncio.sleep(min(0.2 * (attempt + 1), 1.0))
                    continue
                error = (
                    AITimeoutError("AI provider request timed out.")
                    if response.status_code == 408
                    else AIProviderUnavailableError("Nebius AI provider is unavailable.")
                )
                self._mark_failure(error)
                raise error
            if response.status_code >= 400:
                error = AIRequestError("Nebius AI provider rejected the request.")
                self._mark_failure(error)
                raise error

            try:
                response_payload = response.json()
            except (ValueError, json.JSONDecodeError) as exc:
                error = AIResponseValidationError("AI response validation failed.")
                self._mark_failure(error)
                raise error from exc

            try:
                content = self._extract_content(response_payload)
                output = self._parse_json_content(content)
                result = AIAnalysisResponse.model_validate(output)
                result = self._ground_evidence(result, request.context)
            except AIResponseValidationError as exc:
                self._mark_failure(exc)
                raise
            except Exception as exc:
                error = AIResponseValidationError("AI response validation failed.")
                self._mark_failure(error)
                raise error from exc

            self._mark_success()
            return result

        error = AIProviderUnavailableError("Nebius AI provider is unavailable.")
        self._mark_failure(error)
        raise error

    @staticmethod
    def _is_model_error(response: httpx.Response) -> bool:
        try:
            payload = response.json()
        except (ValueError, json.JSONDecodeError):
            return False
        if not isinstance(payload, dict):
            return False
        error_payload = payload.get("error", payload)
        if not isinstance(error_payload, (dict, str)):
            return False
        error_text = json.dumps(error_payload, ensure_ascii=True).lower()
        return any(
            marker in error_text
            for marker in ("model_not_found", "model unavailable", "unknown model", "invalid model")
        )

    @staticmethod
    def _ground_evidence(
        result: AIAnalysisResponse,
        context: dict[str, Any],
    ) -> AIAnalysisResponse:
        """Allow only evidence IDs supplied by NEXORA and copy trusted fields."""

        raw_index = context.get("evidence_index", [])
        if not isinstance(raw_index, list):
            raise AIResponseValidationError("AI response validation failed.")
        evidence_index: dict[str, EvidenceReference] = {}
        for item in raw_index:
            if not isinstance(item, dict):
                raise AIResponseValidationError("AI response validation failed.")
            try:
                reference = EvidenceReference.model_validate(item)
            except Exception as exc:
                raise AIResponseValidationError("AI response validation failed.") from exc
            evidence_index[reference.evidence_id] = reference

        grounded_evidence: list[EvidenceReference] = []
        for reference in result.evidence:
            trusted_reference = evidence_index.get(reference.evidence_id)
            if trusted_reference is None:
                raise AIResponseValidationError("AI response cited unavailable evidence.")
            grounded_evidence.append(trusted_reference)

        for hypothesis in result.hypotheses:
            cited_ids = hypothesis.supporting_evidence + hypothesis.contradicting_evidence
            if any(evidence_id not in evidence_index for evidence_id in cited_ids):
                raise AIResponseValidationError("AI response cited unavailable evidence.")

        return result.model_copy(update={"evidence": grounded_evidence})

    @staticmethod
    def _extract_content(response_payload: Any) -> str | dict[str, Any]:
        if not isinstance(response_payload, dict):
            raise AIResponseValidationError("AI response validation failed.")
        choices = response_payload.get("choices")
        if not isinstance(choices, list) or not choices:
            raise AIResponseValidationError("AI response validation failed.")
        first_choice = choices[0]
        if not isinstance(first_choice, dict):
            raise AIResponseValidationError("AI response validation failed.")
        message = first_choice.get("message")
        if not isinstance(message, dict):
            raise AIResponseValidationError("AI response validation failed.")
        if message.get("refusal"):
            raise AIResponseValidationError("AI response validation failed.")
        content = message.get("content")
        if not isinstance(content, (str, dict)):
            raise AIResponseValidationError("AI response validation failed.")
        return content

    @staticmethod
    def _parse_json_content(content: str | dict[str, Any]) -> dict[str, Any]:
        if isinstance(content, dict):
            return content
        normalized = content.strip()
        if normalized.startswith("```"):
            lines = normalized.splitlines()
            if lines and lines[0].strip().lower() in {"```", "```json"}:
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            normalized = "\n".join(lines).strip()
        try:
            parsed = json.loads(normalized)
        except json.JSONDecodeError as exc:
            raise AIResponseValidationError("AI response validation failed.") from exc
        if not isinstance(parsed, dict):
            raise AIResponseValidationError("AI response validation failed.")
        return parsed
