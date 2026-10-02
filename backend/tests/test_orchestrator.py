from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from backend.app.agents.policies import ToolPolicy
from backend.app.ai.schemas import (
    AIAnalysisResponse,
    AIAnalysisStatus,
    AIAnalysisStep,
    AIHealthResponse,
    HypothesisSummary,
    RecommendedAction,
)
from backend.app.ai.services.inference import AIService
from backend.app.config.settings import Settings
from backend.app.database.repository import InMemoryIncidentRepository
from backend.app.main import create_app
from backend.app.models.enums import RiskLevel
from backend.app.simulator.runtime import ShopFlowSimulationRuntime
from backend.app.simulator.scenarios import ShopFlowSimulator
from backend.app.tools.contracts import ToolExecutionStatus
from backend.app.tools.runtime import ToolRuntime, build_simulation_tool_registry
from backend.tests.auth_helpers import authenticate


class DeterministicAI:
    def __init__(self, log_id: str, *, action: str = "restart_payment_service") -> None:
        self.log_id = log_id
        self.action = action

    def health(self) -> AIHealthResponse:
        return AIHealthResponse(
            model="test-nemotron",
            status="configured",
            verified=True,
            message="Test provider",
        )

    async def decide(self, request) -> AIAnalysisResponse:
        del request
        return AIAnalysisResponse(
            status=AIAnalysisStatus.ANALYSIS_COMPLETE,
            current_step=AIAnalysisStep.REMEDIATION_PROPOSED,
            summary="Payment evidence supports a bounded simulator response.",
            selected_tools=[],
            evidence=[],
            hypotheses=[
                HypothesisSummary(
                    title="Payment retry configuration is degraded",
                    description="The payment service has a supported simulator hypothesis.",
                    confidence=0.92,
                    supporting_evidence=[self.log_id],
                )
            ],
            validated_hypothesis=None,
            recommendation=RecommendedAction(
                action=self.action,
                rationale="The fixed test recommendation is still subject to server policy.",
                risk_level=RiskLevel.HIGH,
                requires_approval=True,
            ),
            risk_level=RiskLevel.HIGH,
            requires_approval=True,
            verification_plan=[],
            confidence=0.92,
        )


def make_application(*, ai_enabled: bool = True) -> tuple[TestClient, InMemoryIncidentRepository]:
    repository = InMemoryIncidentRepository()
    simulator = ShopFlowSimulator()
    log_id = str(simulator.load_scenario("payment-failure").state.logs[0].id)
    provider = DeterministicAI(log_id)
    ai_service = AIService(
        provider=provider,
        repository=repository,
        simulator=simulator,
    )
    if not ai_enabled:
        application = create_app(
            repository=repository,
            settings=Settings(environment="test"),
        )
    else:
        application = create_app(
            repository=repository,
            settings=Settings(environment="test"),
            ai_service=ai_service,
        )
    return authenticate(TestClient(application)), repository


def create_payment_incident(client: TestClient) -> str:
    response = client.post(
        "/api/incidents",
        json={
            "title": "Payment authorization incident",
            "description": "Payment authorization failures increased after a release.",
            "severity": "high",
            "service": "Payment Service",
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_full_orchestration_waits_for_approval_and_resolves_only_after_verification() -> None:
    client, repository = make_application()
    with client:
        incident_id = create_payment_incident(client)
        start = client.post(
            f"/api/orchestrator/incidents/{incident_id}/start",
            json={"scenario_id": "payment-failure", "request_id": "start-1"},
        )
        assert start.status_code == 202
        pending = start.json()
        assert pending["current_state"] == "WAITING_FOR_APPROVAL"
        assert pending["runtime_status"] == "WAITING"
        assert pending["source_type"] == "synthetic_demo_data"
        assert pending["approval"]["status"] == "pending"
        assert [item["to_state"] for item in pending["transition_history"]] == [
            "INCIDENT_RECEIVED",
            "OBSERVING",
            "INVESTIGATING",
            "HYPOTHESIS_GENERATED",
            "VALIDATING",
            "REMEDIATION_PROPOSED",
            "WAITING_FOR_APPROVAL",
        ]
        assert not any(
            item["tool_name"] == "execute_safe_action" for item in pending["tool_results"]
        )

        approval_id = pending["approval"]["approval_id"]
        approved = client.post(
            f"/api/orchestrator/approvals/{approval_id}/approve",
            json={"decided_by": "test-operator", "reason": "Approved in test"},
        )
        assert approved.status_code == 200
        resolved = approved.json()
        assert resolved["current_state"] == "RESOLVED"
        assert resolved["runtime_status"] == "COMPLETED"
        assert resolved["verification_outcome"] == "VERIFIED"
        assert resolved["incident"]["status"] == "resolved"
        assert resolved["incident"]["agent_state"] == "RESOLVED"
        assert any(
            item["tool_name"] == "execute_safe_action" and item["status"] == "SUCCESS"
            for item in resolved["tool_results"]
        )
        assert len(resolved["verification_results"]) == 4
        assert repository.get_report(UUID(incident_id)) is not None

        duplicate = client.post(
            f"/api/orchestrator/approvals/{approval_id}/approve",
            json={"decided_by": "test-operator"},
        )
        assert duplicate.status_code == 409
        assert len(client.get("/api/orchestrator/actions").json()) == 1


def test_rejected_approval_escalates_without_executing_a_change() -> None:
    client, _ = make_application()
    with client:
        incident_id = create_payment_incident(client)
        pending = client.post(
            f"/api/orchestrator/incidents/{incident_id}/start",
            json={"scenario_id": "payment-failure"},
        ).json()
        response = client.post(
            f"/api/orchestrator/approvals/{pending['approval']['approval_id']}/reject",
            json={"decided_by": "test-operator", "reason": "Need human review"},
        )
        assert response.status_code == 200
        context = response.json()
        assert context["current_state"] == "REQUIRES_HUMAN"
        assert context["approval"]["status"] == "rejected"
        assert not any(
            result["tool_name"] == "execute_safe_action" for result in context["tool_results"]
        )
        assert client.get("/api/orchestrator/actions").json() == []


def test_expired_approval_escalates_without_execution() -> None:
    client, _ = make_application()
    with client:
        incident_id = create_payment_incident(client)
        pending = client.post(
            f"/api/orchestrator/incidents/{incident_id}/start",
            json={"scenario_id": "payment-failure"},
        ).json()
        approval_id = UUID(pending["approval"]["approval_id"])
        orchestrator = client.app.state.orchestrator
        expired = orchestrator.store.require_approval(approval_id).model_copy(
            update={"expires_at": datetime.now(UTC) - timedelta(minutes=1)}
        )
        orchestrator.store.save_approval(expired)

        response = client.post(
            f"/api/orchestrator/approvals/{approval_id}/approve",
            json={"decided_by": "test-operator"},
        )
        assert response.status_code == 200
        context = response.json()
        assert context["current_state"] == "REQUIRES_HUMAN"
        assert context["approval"]["status"] == "expired"
        assert client.get("/api/orchestrator/actions").json() == []


def test_cancellation_is_a_safe_terminal_transition() -> None:
    client, _ = make_application()
    with client:
        incident_id = create_payment_incident(client)
        pending = client.post(
            f"/api/orchestrator/incidents/{incident_id}/start",
            json={"scenario_id": "payment-failure"},
        ).json()
        response = client.post(
            f"/api/orchestrator/incidents/{incident_id}/cancel",
            json={"requested_by": "test-operator", "reason": "Stop the demonstration"},
        )
        assert response.status_code == 200
        context = response.json()
        assert context["current_state"] == "CANCELLED"
        assert context["runtime_status"] == "CANCELLED"
        assert context["approval"]["status"] == "cancelled"
        assert pending["approval"]["approval_id"] == context["approval"]["approval_id"]
        assert client.get("/api/orchestrator/actions").json() == []


def test_verification_failure_prevents_resolution() -> None:
    client, _ = make_application()
    with client:
        incident_id = create_payment_incident(client)
        pending = client.post(
            f"/api/orchestrator/incidents/{incident_id}/start",
            json={"scenario_id": "payment-failure"},
        ).json()
        runtime: ShopFlowSimulationRuntime = client.app.state.simulation_runtime
        original_action = runtime.execute_safe_action

        def action_without_recovery(**kwargs):
            result = original_action(**kwargs)
            fixture = runtime._fixtures["payment-failure"]
            for service in fixture.state.services:
                if service.name == "Payment Service":
                    service.status = "down"
            return result

        runtime.execute_safe_action = action_without_recovery
        response = client.post(
            f"/api/orchestrator/approvals/{pending['approval']['approval_id']}/approve",
            json={"decided_by": "test-operator"},
        )
        assert response.status_code == 200
        context = response.json()
        assert context["current_state"] == "REQUIRES_HUMAN"
        assert context["verification_outcome"] == "NOT_VERIFIED"
        assert client.get(f"/api/incidents/{incident_id}/report").status_code == 404


@pytest.mark.asyncio
async def test_strict_argument_validation_and_server_policy() -> None:
    runtime = ShopFlowSimulationRuntime()
    tool_runtime = ToolRuntime(build_simulation_tool_registry(runtime), ToolPolicy())
    invalid = await tool_runtime.execute(
        "get_logs",
        {"service": "Payment Service", "since": 180, "unexpected": "reject"},
        scenario_id="payment-failure",
    )
    assert invalid.status is ToolExecutionStatus.REJECTED
    assert invalid.evidence == []

    unapproved = await tool_runtime.execute(
        "execute_safe_action",
        {"action_name": "restart_payment_service", "parameters": {}},
        scenario_id="payment-failure",
    )
    assert unapproved.status is ToolExecutionStatus.REJECTED
    assert unapproved.result["requires_approval"] is True


def test_unconfigured_ai_escalates_without_fake_inference() -> None:
    client, _ = make_application(ai_enabled=False)
    with client:
        incident_id = create_payment_incident(client)
        response = client.post(
            f"/api/orchestrator/incidents/{incident_id}/start",
            json={"scenario_id": "payment-failure"},
        )
        assert response.status_code == 202
        context = response.json()
        assert context["current_state"] == "REQUIRES_HUMAN"
        assert context["errors"] == ["Nebius AI is not configured."]
        assert context["approval"] is None
        assert context["analysis_summary"] is None


def test_server_policy_rejects_unapproved_high_risk_tool_and_strict_arguments() -> None:
    client, _ = make_application()
    with client:
        response = client.post(
            "/api/orchestrator/incidents/00000000-0000-0000-0000-000000000001/start",
            json={"scenario_id": "payment-failure"},
        )
        assert response.status_code == 404

        tool_definitions = client.get("/api/orchestrator/tools").json()
        action_definition = next(
            item for item in tool_definitions if item["name"] == "execute_safe_action"
        )
        assert action_definition["requires_approval"] is True
        assert action_definition["risk_level"] == "HIGH"
        assert {
            "restart_payment_service",
            "rollback_simulated_deployment",
        } == set(action_definition["input_schema"]["properties"]["action_name"]["enum"])
