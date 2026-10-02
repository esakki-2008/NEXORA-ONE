from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from backend.app.actions.models import Action
from backend.app.verification.checks import CollectedCheck, CollectionResult
from backend.app.verification.engine import VerificationEngine
from backend.app.verification.models import (
    EvidenceTrust,
    VerificationCheckStatus,
    VerificationStatus,
    VerificationStrategy,
)
from backend.app.verification.service import VerificationIntegrityError


def create_incident(client: TestClient, *, service: str = "Payment Service") -> dict[str, Any]:
    response = client.post(
        "/api/incidents",
        json={
            "title": "Verification test incident",
            "description": "Controlled Phase 8 test incident.",
            "severity": "high",
            "service": service,
        },
    )
    assert response.status_code == 201
    return response.json()


def create_action(
    client: TestClient,
    incident_id: str,
    *,
    action_name: str = "restart_payment_service",
    scenario_id: str = "payment-failure",
) -> dict[str, Any]:
    response = client.post(
        "/api/actions",
        json={
            "incident_id": incident_id,
            "scenario_id": scenario_id,
            "action_name": action_name,
            "parameters": {},
            "requested_by": "test-planner",
        },
        headers=client.reference_headers(subject="test-planner"),  # type: ignore[attr-defined]
    )
    assert response.status_code == 201
    return response.json()


def approve(client: TestClient, action_id: str) -> None:
    response = client.post(
        f"/api/actions/{action_id}/approve",
        json={"requested_by": "test-operator", "reason": "Bounded test approval"},
    )
    assert response.status_code == 200


def execute(client: TestClient, action_id: str) -> dict[str, Any]:
    response = client.post(
        f"/api/actions/{action_id}/execute",
        json={"requested_by": "test-operator"},
    )
    assert response.status_code == 200
    return response.json()


def test_successful_recovery_creates_resolution_proof_and_report(client: TestClient) -> None:
    incident = create_incident(client)
    action = create_action(client, incident["id"])
    approve(client, action["action_id"])

    result = execute(client, action["action_id"])

    assert result["status"] == "COMPLETED"
    assert result["verification_status"] == "PASSED"
    verification = client.get(f"/api/verification/{result['verification_id']}").json()
    assert verification["status"] == "PASSED"
    assert verification["incident_id"] == incident["id"]
    assert verification["action_id"] == action["action_id"]
    assert all(item["expected_value"] is not None for item in verification["checks"])
    assert all(item["actual_value"] is not None for item in verification["checks"])
    assert client.get(f"/api/incidents/{incident['id']}").json()["status"] == "resolved"
    report = client.get(f"/api/incidents/{incident['id']}/report").json()
    assert report["verification"][0]["verification_id"] == result["verification_id"]


def test_failed_verification_rolls_back_and_preserves_human_review(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    incident = create_incident(client)
    action = create_action(client, incident["id"])
    approve(client, action["action_id"])
    runtime = client.app.state.simulation_runtime

    monkeypatch.setattr(
        runtime,
        "verify_phase7_action",
        lambda **_: {"verified": False, "checks": {"forced": False}},
    )
    result = execute(client, action["action_id"])

    assert result["status"] == "ROLLED_BACK"
    assert result["rollback_verification_status"] == "PASSED"
    assert result["verification_status"] in {"INCONCLUSIVE", "RECOVERY_REQUIRED"}
    assert client.get(f"/api/incidents/{incident['id']}").json()["status"] == "requires_human"
    assert client.get(f"/api/incidents/{incident['id']}/report").status_code == 404


def test_retry_can_succeed_without_an_automatic_infinite_loop(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    incident = create_incident(client)
    action = create_action(client, incident["id"])
    approve(client, action["action_id"])
    runtime = client.app.state.simulation_runtime
    original = runtime.verify_phase7_action
    calls = 0

    def fail_once(**kwargs: Any) -> dict[str, Any]:
        nonlocal calls
        calls += 1
        if calls == 1:
            return {"verified": False, "checks": {"forced": False}}
        return original(**kwargs)

    monkeypatch.setattr(runtime, "verify_phase7_action", fail_once)
    result = execute(client, action["action_id"])
    verification_id = result["verification_id"]
    fixture = runtime._fixtures["payment-failure"]
    runtime._recover_service_state(fixture, "Payment Service")

    retried = client.post(
        f"/api/verification/{verification_id}/retry",
        json={"requested_by": "test-operator", "reason": "Retry after bounded observation"},
    )
    assert retried.status_code == 200
    body = retried.json()
    assert body["status"] == "PASSED"
    assert body["attempt"] == 2
    assert calls == 2


def test_permanent_failure_reaches_human_escalation_at_attempt_bound(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    incident = create_incident(client)
    action = create_action(client, incident["id"])
    approve(client, action["action_id"])
    runtime = client.app.state.simulation_runtime
    monkeypatch.setattr(
        runtime,
        "verify_phase7_action",
        lambda **_: {"verified": False, "checks": {"forced": False}},
    )
    result = execute(client, action["action_id"])
    verification_id = result["verification_id"]

    for expected_status in ("RECOVERY_REQUIRED", "REQUIRES_HUMAN"):
        response = client.post(
            f"/api/verification/{verification_id}/retry",
            json={"requested_by": "test-operator"},
        )
        assert response.status_code == 200
        assert response.json()["status"] == expected_status
    final = client.post(
        f"/api/verification/{verification_id}/retry",
        json={"requested_by": "test-operator"},
    )
    assert final.status_code == 409
    assert client.get(f"/api/verification/{verification_id}").json()["status"] == "REQUIRES_HUMAN"


class StaticCollector:
    def __init__(self, checks: tuple[CollectedCheck, ...]) -> None:
        self.checks = checks

    async def collect(self, action: Action, expected_state: dict[str, Any]) -> CollectionResult:
        del action, expected_state
        return CollectionResult(
            actual_state={"source": "static-test"},
            checks=self.checks,
            aggregate_verified=True,
            collector_evidence=(),
        )


def evaluate_with_checks(
    client: TestClient,
    checks: tuple[CollectedCheck, ...],
    *,
    max_age_seconds: int = 300,
):
    incident = create_incident(client)
    action_data = create_action(client, incident["id"])
    action = Action.model_validate(action_data)
    engine = VerificationEngine(
        client.app.state.action_registry,
        client.app.state.simulation_runtime,
        collector=StaticCollector(checks),
        max_evidence_age_seconds=max_age_seconds,
    )
    return engine.evaluate(
        action,
        verification_id=uuid4(),
        expected_state={"checks": [{"strategy": "SERVICE_HEALTH"}]},
        attempt=1,
    )


@pytest.mark.asyncio
async def test_contradictory_missing_and_stale_evidence_are_not_proof(client: TestClient) -> None:
    now = datetime.now(UTC)
    passed = CollectedCheck(
        strategy=VerificationStrategy.SERVICE_HEALTH,
        name="health_passed",
        expected_value="healthy",
        actual_value="healthy",
        status=VerificationCheckStatus.PASSED,
        comparison="EQUALS",
        observed_at=now,
        trust=EvidenceTrust.SIMULATED,
    )
    failed = CollectedCheck(
        strategy=VerificationStrategy.ERROR_RATE,
        name="error_contradiction",
        expected_value={"threshold": 0.05},
        actual_value={"payment.failure_rate": 0.2},
        status=VerificationCheckStatus.FAILED,
        comparison="ALL_LESS_THAN 0.05",
        observed_at=now,
        trust=EvidenceTrust.SIMULATED,
    )
    contradictory = await evaluate_with_checks(client, (passed, failed))
    assert contradictory.status is VerificationStatus.INCONCLUSIVE
    assert contradictory.contradictory_evidence is True

    unavailable = CollectedCheck(
        strategy=VerificationStrategy.ERROR_RATE,
        name="missing_metric",
        expected_value={"threshold": 0.05},
        actual_value=None,
        status=VerificationCheckStatus.UNAVAILABLE,
        comparison="READ_UNAVAILABLE",
        observed_at=None,
        trust=EvidenceTrust.UNAVAILABLE,
        failure_reason="No metric",
    )
    missing = await evaluate_with_checks(client, (passed, unavailable))
    assert missing.status is VerificationStatus.INCONCLUSIVE
    assert missing.missing_evidence is True

    stale = replace(passed, observed_at=now - timedelta(seconds=120))
    stale_result = await evaluate_with_checks(client, (stale,), max_age_seconds=10)
    assert stale_result.status is VerificationStatus.INCONCLUSIVE
    assert stale_result.missing_evidence is True


def test_negative_security_controls_reject_client_state_and_tampering(client: TestClient) -> None:
    incident = create_incident(client)
    action = create_action(client, incident["id"])
    created = client.post(
        "/api/verification",
        json={"action_id": action["action_id"], "status": "PASSED"},
    )
    assert created.status_code == 422
    created = client.post("/api/verification", json={"action_id": action["action_id"]})
    assert created.status_code == 201
    verification_id = created.json()["verification_id"]

    unauthorized = client.post(
        f"/api/verification/{verification_id}/run",
        json={"requested_by": "attacker", "confidence": 1.0},
    )
    assert unauthorized.status_code == 422
    unauthorized = client.post(
        f"/api/verification/{verification_id}/run",
        json={"requested_by": "attacker"},
        headers=client.reference_headers(subject="attacker"),  # type: ignore[attr-defined]
    )
    assert unauthorized.status_code == 409

    service = client.app.state.verification_service
    record = service.get(UUID(verification_id))
    tampered = record.model_copy(update={"confidence": 1.0}, deep=True)
    with pytest.raises(VerificationIntegrityError):
        service.store.save(tampered)


def test_cancelled_action_cannot_be_verified(client: TestClient) -> None:
    incident = create_incident(client)
    action = create_action(client, incident["id"])
    created = client.post("/api/verification", json={"action_id": action["action_id"]})
    assert created.status_code == 201
    cancelled = client.post(
        f"/api/actions/{action['action_id']}/cancel",
        json={"requested_by": "test-operator", "reason": "Stop before execution"},
    )
    assert cancelled.status_code == 200
    response = client.post(
        f"/api/verification/{created.json()['verification_id']}/run",
        json={"requested_by": "test-operator"},
    )
    assert response.status_code == 409
