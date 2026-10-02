import json

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from backend.app.ai.config import NebiusConfig
from backend.app.ai.contracts import AIRequest
from backend.app.ai.exceptions import (
    AIAuthenticationError,
    AIConfigurationError,
    AIModelUnavailableError,
    AIProviderUnavailableError,
    AIResponseValidationError,
    AITimeoutError,
)
from backend.app.ai.providers import NebiusNemotronProvider
from backend.app.ai.services.inference import AIService
from backend.app.config.settings import Settings
from backend.app.database.repository import InMemoryIncidentRepository
from backend.app.main import create_app
from backend.app.simulator.scenarios import ShopFlowSimulator
from backend.tests.auth_helpers import authenticate

VALID_ANALYSIS = {
    "status": "analysis_complete",
    "current_step": "resolved",
    "summary": "Payment failure evidence was reviewed.",
    "selected_tools": [],
    "evidence": [],
    "hypotheses": [],
    "validated_hypothesis": None,
    "recommended_action": None,
    "risk_level": "READ_ONLY",
    "requires_approval": True,
    "verification_plan": [],
    "confidence": 0.82,
}


def response_for(payload: object, status_code: int = 200) -> httpx.Response:
    return httpx.Response(
        status_code,
        json={"choices": [{"message": {"content": json.dumps(payload)}}]},
    )


def request_for_provider() -> AIRequest:
    return AIRequest(system_instruction="observe", user_input="inspect evidence")


def configured_provider(
    handler: httpx.MockTransport,
    *,
    max_retries: int = 0,
) -> NebiusNemotronProvider:
    return NebiusNemotronProvider(
        NebiusConfig(
            api_key=SecretStr("test-nebius-key"),
            base_url="https://nebius.test/v1/",
            model="nvidia/nemotron-test",
            timeout_seconds=1,
            max_retries=max_retries,
        ),
        transport=handler,
    )


@pytest.mark.asyncio
async def test_provider_sends_real_openai_compatible_request_and_validates_output() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return response_for(VALID_ANALYSIS)

    provider = configured_provider(httpx.MockTransport(handler))
    result = await provider.decide(request_for_provider())

    assert result.summary == VALID_ANALYSIS["summary"]
    assert provider.health().verified is True
    assert seen[0].url == "https://nebius.test/v1/chat/completions"
    assert seen[0].headers["authorization"] == "Bearer test-nebius-key"
    payload = json.loads(seen[0].content)
    assert payload["model"] == "nvidia/nemotron-test"
    assert payload["response_format"] == {"type": "json_object"}


@pytest.mark.asyncio
async def test_provider_grounds_evidence_to_the_supplied_index() -> None:
    payload = {
        **VALID_ANALYSIS,
        "evidence": [{"evidence_id": "evidence-1", "source": "invented", "summary": "invented"}],
    }
    provider = configured_provider(
        httpx.MockTransport(lambda request: response_for(payload)),
    )
    result = await provider.decide(
        AIRequest(
            system_instruction="observe",
            user_input="inspect evidence",
            context={
                "evidence_index": [
                    {
                        "evidence_id": "evidence-1",
                        "source": "ShopFlow / Payment Service",
                        "summary": "Gateway authorization failed",
                    }
                ]
            },
        )
    )

    assert result.evidence[0].source == "ShopFlow / Payment Service"
    assert result.evidence[0].summary == "Gateway authorization failed"

    unknown_payload = {
        **VALID_ANALYSIS,
        "evidence": [{"evidence_id": "not-supplied", "source": "x", "summary": "x"}],
    }
    unknown_provider = configured_provider(
        httpx.MockTransport(lambda request: response_for(unknown_payload)),
    )
    with pytest.raises(AIResponseValidationError):
        await unknown_provider.decide(
            AIRequest(
                system_instruction="observe",
                user_input="inspect evidence",
                context={"evidence_index": []},
            )
        )


@pytest.mark.asyncio
async def test_provider_retries_transient_failure_only_with_bounded_attempts() -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        del request
        nonlocal attempts
        attempts += 1
        return httpx.Response(503) if attempts == 1 else response_for(VALID_ANALYSIS)

    provider = configured_provider(httpx.MockTransport(handler), max_retries=1)
    result = await provider.decide(request_for_provider())

    assert result.status == "analysis_complete"
    assert attempts == 2


@pytest.mark.asyncio
async def test_provider_rejects_authentication_and_malformed_structured_response() -> None:
    auth_provider = configured_provider(
        httpx.MockTransport(lambda request: httpx.Response(401)),
    )
    with pytest.raises(AIAuthenticationError):
        await auth_provider.decide(request_for_provider())
    assert auth_provider.health().verified is False
    assert "test-nebius-key" not in auth_provider.health().model
    assert "test-nebius-key" not in auth_provider.health().message

    malformed_provider = configured_provider(
        httpx.MockTransport(lambda request: response_for({"summary": "missing required fields"})),
    )
    with pytest.raises(AIResponseValidationError):
        await malformed_provider.decide(request_for_provider())


@pytest.mark.asyncio
async def test_provider_classifies_model_provider_and_timeout_failures() -> None:
    model_provider = configured_provider(
        httpx.MockTransport(lambda request: httpx.Response(404)),
    )
    with pytest.raises(AIModelUnavailableError):
        await model_provider.decide(request_for_provider())

    unavailable_provider = configured_provider(
        httpx.MockTransport(lambda request: httpx.Response(502)),
    )
    with pytest.raises(AIProviderUnavailableError):
        await unavailable_provider.decide(request_for_provider())

    timeout_attempts = 0

    def timeout_handler(request: httpx.Request) -> httpx.Response:
        del request
        nonlocal timeout_attempts
        timeout_attempts += 1
        raise httpx.ReadTimeout("provider timed out")

    timeout_provider = configured_provider(
        httpx.MockTransport(timeout_handler),
        max_retries=1,
    )
    with pytest.raises(AITimeoutError):
        await timeout_provider.decide(request_for_provider())
    assert timeout_attempts == 2


@pytest.mark.asyncio
async def test_missing_configuration_never_falls_back_to_fake_output() -> None:
    provider = NebiusNemotronProvider(
        NebiusConfig(
            api_key=None,
            base_url="https://nebius.test/v1/",
            model="nvidia/nemotron-test",
        )
    )

    assert provider.health().verified is False
    assert provider.health().status == "not_configured"
    with pytest.raises(AIConfigurationError):
        await provider.decide(request_for_provider())


def test_ai_routes_use_mocked_provider_and_expose_only_safe_events() -> None:
    settings = Settings(
        environment="test",
        cors_origins="http://testserver",
        nebius_api_key=SecretStr("route-secret"),
        nebius_base_url="https://nebius.test/v1/",
        nebius_model="nvidia/nemotron-test",
    )
    provider = NebiusNemotronProvider.from_settings(
        settings,
        transport=httpx.MockTransport(lambda request: response_for(VALID_ANALYSIS)),
    )
    service = AIService(
        provider=provider,
        repository=InMemoryIncidentRepository(),
        simulator=ShopFlowSimulator(),
    )
    application = create_app(settings=settings, ai_service=service)

    with authenticate(TestClient(application)) as client:
        health = client.get("/api/ai/health")
        assert health.status_code == 200
        assert health.json()["verified"] is False
        assert "route-secret" not in health.text

        test_response = client.post("/api/ai/test", json={})
        assert test_response.status_code == 200
        assert test_response.json()["success"] is True
        assert "route-secret" not in test_response.text

        analysis = client.post(
            "/api/ai/analyze",
            json={"scenario_id": "payment-failure"},
        )
        assert analysis.status_code == 200
        assert analysis.json()["summary"] == VALID_ANALYSIS["summary"]

        activity = client.get("/api/ai/activity")
        assert activity.status_code == 200
        assert any(event["event_type"] == "ai.response.validated" for event in activity.json())
        assert "route-secret" not in activity.text


def test_analysis_request_requires_exactly_one_evidence_source(client: TestClient) -> None:
    response = client.post("/api/ai/analyze", json={})
    assert response.status_code == 422

    response = client.post(
        "/api/ai/analyze",
        json={
            "scenario_id": "payment-failure",
            "incident_id": "00000000-0000-0000-0000-000000000001",
        },
    )
    assert response.status_code == 422
