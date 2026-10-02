"""Phase 7 controlled action security, lifecycle, and regression coverage."""

import asyncio
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

REGISTRY_NAMES = {
    "restart_payment_service",
    "rollback_simulated_deployment",
    "restart_checkout_service",
    "clear_simulated_queue",
    "disable_simulated_feature_flag",
    "restore_simulated_configuration",
    "scale_simulated_service",
}


def create_incident(client: TestClient, *, service: str = "Payment Service") -> dict[str, object]:
    return client.post(
        "/api/incidents",
        json={
            "title": f"{service} controlled action test",
            "description": "Synthetic incident used to validate the Phase 7 boundary.",
            "severity": "high",
            "service": service,
        },
    ).json()


def create_action(
    client: TestClient,
    incident_id: str,
    *,
    action_name: str = "restart_payment_service",
    parameters: dict[str, object] | None = None,
    requested_by: str = "phase7-planner",
    scenario_id: str = "payment-failure",
) -> dict[str, object]:
    response = client.post(
        "/api/actions",
        json={
            "incident_id": incident_id,
            "scenario_id": scenario_id,
            "action_name": action_name,
            "parameters": parameters or {},
            "requested_by": requested_by,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def approve_and_execute(
    client: TestClient, action: dict[str, object], *, actor: str = "Local operator"
) -> dict[str, object]:
    action_id = action["action_id"]
    approval = client.post(
        f"/api/actions/{action_id}/approve",
        json={"requested_by": actor, "reason": "Reviewed exact simulator plan and fingerprint."},
    )
    assert approval.status_code == 200, approval.text
    execution = client.post(
        f"/api/actions/{action_id}/execute",
        json={"requested_by": actor, "reason": "Execute after explicit approval."},
    )
    assert execution.status_code == 200, execution.text
    return execution.json()


def test_action_registry_contains_only_the_seven_allow_listed_actions(client: TestClient) -> None:
    response = client.get("/api/actions/registry")

    assert response.status_code == 200
    assert {item["name"] for item in response.json()} == REGISTRY_NAMES
    assert all("handler" not in item and "callable" not in item for item in response.json())


def test_unknown_action_and_malformed_parameters_are_rejected_safely(client: TestClient) -> None:
    incident = create_incident(client)
    unknown = client.post(
        "/api/actions",
        json={
            "incident_id": incident["id"],
            "scenario_id": "payment-failure",
            "action_name": "run_shell_command",
            "parameters": {"command": "rm -rf /"},
            "requested_by": "phase7-planner",
        },
    )
    assert unknown.status_code == 422
    assert "allow-listed" in unknown.json()["detail"]

    malformed = client.post(
        "/api/actions",
        json={
            "incident_id": incident["id"],
            "scenario_id": "payment-failure",
            "action_name": "clear_simulated_queue",
            "parameters": {"queue_name": "payment", "command": "shell"},
            "requested_by": "phase7-planner",
        },
    )
    assert malformed.status_code == 422


def test_action_requires_simulator_binding_and_incident_binding(client: TestClient) -> None:
    incident = create_incident(client)
    missing_scenario = client.post(
        "/api/actions",
        json={
            "incident_id": incident["id"],
            "action_name": "restart_payment_service",
            "requested_by": "phase7-planner",
        },
    )
    assert missing_scenario.status_code == 422
    assert "ShopFlow scenario" in missing_scenario.json()["detail"]

    unknown_scenario = client.post(
        "/api/actions",
        json={
            "incident_id": incident["id"],
            "scenario_id": "not-a-shopflow-fixture",
            "action_name": "restart_payment_service",
            "requested_by": "phase7-planner",
        },
    )
    assert unknown_scenario.status_code == 422
    assert "not available" in unknown_scenario.json()["detail"]

    wrong_investigation = client.post(
        "/api/actions",
        json={
            "incident_id": incident["id"],
            "investigation_id": str(uuid4()),
            "scenario_id": "payment-failure",
            "action_name": "restart_payment_service",
            "requested_by": "phase7-planner",
        },
    )
    assert wrong_investigation.status_code == 404


def test_ai_cannot_approve_or_execute_and_high_risk_never_auto_executes(
    client: TestClient,
) -> None:
    incident = create_incident(client)
    action = create_action(
        client,
        str(incident["id"]),
        action_name="scale_simulated_service",
        parameters={"service_name": "Payment Service", "desired_capacity": 4},
    )
    ai_approval = client.post(
        f"/api/actions/{action['action_id']}/approve",
        json={"requested_by": "ai", "reason": "Model requested it."},
    )
    assert ai_approval.status_code == 409
    assert "AI cannot" in ai_approval.json()["detail"]

    approved = client.post(
        f"/api/actions/{action['action_id']}/approve",
        json={"requested_by": "Local operator", "reason": "Human reviewed."},
    )
    assert approved.status_code == 200
    auto_execution = client.post(
        f"/api/actions/{action['action_id']}/execute",
        json={"requested_by": "Local operator", "auto_execute": True},
    )
    assert auto_execution.status_code == 409
    assert "HIGH-risk" in auto_execution.json()["detail"]


def test_payment_failure_flow_resolves_only_after_execution_verification_and_report(
    client: TestClient,
) -> None:
    incident = create_incident(client)
    action = create_action(client, str(incident["id"]))
    executed = approve_and_execute(client, action)

    assert executed["status"] == "COMPLETED"
    assert executed["verification_status"] == "PASSED"
    assert executed["action_fingerprint"]

    incident_after = client.get(f"/api/incidents/{incident['id']}")
    assert incident_after.status_code == 200
    assert incident_after.json()["status"] == "resolved"
    report = client.get(f"/api/incidents/{incident['id']}/report")
    assert report.status_code == 200
    assert report.json()["final_status"] == "resolved"

    verification = client.get(f"/api/actions/{action['action_id']}/verification")
    assert verification.status_code == 200
    assert verification.json()["status"] == "PASSED"
    audit = client.get(f"/api/actions/{action['action_id']}/audit")
    assert audit.status_code == 200
    events = audit.json()
    assert len(events) >= 7
    assert all(event["event_hash"] for event in events)
    assert client.get(f"/api/actions/{action['action_id']}").json()["status"] == "COMPLETED"


def test_idempotency_and_duplicate_execution_do_not_repeat_the_simulator_change(
    client: TestClient,
) -> None:
    incident = create_incident(client)
    request = {
        "incident_id": incident["id"],
        "scenario_id": "payment-failure",
        "action_name": "restart_payment_service",
        "parameters": {},
        "requested_by": "phase7-planner",
        "idempotency_key": "same-proposal-key",
    }
    first = client.post("/api/actions", json=request)
    second = client.post("/api/actions", json=request)
    assert first.status_code == second.status_code == 201
    assert first.json()["action_id"] == second.json()["action_id"]

    action = approve_and_execute(client, first.json())
    duplicate = client.post(
        f"/api/actions/{action['action_id']}/execute",
        json={"requested_by": "Local operator"},
    )
    assert duplicate.status_code == 200
    assert duplicate.json()["status"] == "COMPLETED"
    assert duplicate.json()["execution_attempts"] == action["execution_attempts"]


def test_changed_approved_fingerprint_is_rejected(client: TestClient) -> None:
    incident = create_incident(client)
    action = create_action(client, str(incident["id"]))
    approval = client.post(
        f"/api/actions/{action['action_id']}/approve",
        json={"requested_by": "Local operator", "reason": "Approved exact action."},
    )
    assert approval.status_code == 200

    service = client.app.state.action_service
    action_uuid = UUID(str(action["action_id"]))
    stored = service._actions[action_uuid]
    service._actions[action_uuid] = stored.model_copy(
        update={"normalized_parameters": {"unexpected": "mutation"}}
    )
    execute = client.post(
        f"/api/actions/{action['action_id']}/execute",
        json={"requested_by": "Local operator"},
    )
    assert execute.status_code == 409
    assert "fingerprint" in execute.json()["detail"]


def test_rejection_cancellation_and_unauthorized_operator_escalate_safely(
    client: TestClient,
) -> None:
    incident = create_incident(client)
    action = create_action(client, str(incident["id"]))
    unauthorized = client.post(
        f"/api/actions/{action['action_id']}/cancel",
        json={"requested_by": "attacker", "reason": "try"},
    )
    assert unauthorized.status_code == 409
    assert "not authorized" in unauthorized.json()["detail"]

    rejected = client.post(
        f"/api/actions/{action['action_id']}/reject",
        json={"requested_by": "Local operator", "reason": "Insufficient evidence."},
    )
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "REJECTED"
    assert client.get(f"/api/incidents/{incident['id']}").json()["status"] == "requires_human"


def test_explicit_rollback_is_verified_and_does_not_claim_resolution(client: TestClient) -> None:
    incident = create_incident(client)
    action = create_action(client, str(incident["id"]))
    executed = approve_and_execute(client, action)
    assert executed["status"] == "COMPLETED"

    rollback = client.post(
        f"/api/actions/{action['action_id']}/rollback",
        json={"requested_by": "Local operator", "reason": "Demonstrate controlled restore."},
    )
    assert rollback.status_code == 200, rollback.text
    assert rollback.json()["status"] == "ROLLED_BACK"
    assert rollback.json()["rollback_verification_status"] == "PASSED"
    assert client.get(f"/api/incidents/{incident['id']}").json()["status"] == "requires_human"


def test_verification_failure_uses_registered_rollback_and_escalates(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    incident = create_incident(client)
    action = create_action(client, str(incident["id"]))
    approved = client.post(
        f"/api/actions/{action['action_id']}/approve",
        json={"requested_by": "Local operator", "reason": "Human review complete."},
    )
    assert approved.status_code == 200

    runtime = client.app.state.simulation_runtime

    def fail_verification(**_: object) -> dict[str, object]:
        return {"verified": False, "checks": {"forced": False}}

    monkeypatch.setattr(runtime, "verify_phase7_action", fail_verification)
    execution = client.post(
        f"/api/actions/{action['action_id']}/execute",
        json={"requested_by": "Local operator"},
    )
    assert execution.status_code == 200
    assert execution.json()["status"] == "ROLLED_BACK"
    assert execution.json()["rollback_verification_status"] == "PASSED"
    assert client.get(f"/api/incidents/{incident['id']}").json()["status"] == "requires_human"


def test_execution_timeout_is_bounded_and_escalates_without_simulator_mutation(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    incident = create_incident(client)
    action = create_action(client, str(incident["id"]))
    approved = client.post(
        f"/api/actions/{action['action_id']}/approve",
        json={"requested_by": "Local operator", "reason": "Human review complete."},
    )
    assert approved.status_code == 200

    action_service = client.app.state.action_service
    action_service.executor.timeout_seconds = 0.01

    async def slow_handler(
        *_: object, **__: object
    ) -> tuple[dict[str, object], list[dict[str, object]]]:
        await asyncio.sleep(0.1)
        return {}, []

    monkeypatch.setattr(action_service.registry, "execute", slow_handler)
    execution = client.post(
        f"/api/actions/{action['action_id']}/execute",
        json={"requested_by": "Local operator"},
    )
    assert execution.status_code == 200
    assert execution.json()["status"] == "REQUIRES_HUMAN"
    assert execution.json()["execution_attempts"] == 2
    assert execution.json()["verification_status"] == "REQUIRES_HUMAN"


def test_each_registered_action_uses_the_same_bounded_simulator_boundary(
    client: TestClient,
) -> None:
    cases = [
        ("restart_payment_service", "payment-failure", {}, "Payment Service"),
        ("restart_checkout_service", "latency-spike", {}, "Checkout Service"),
        ("rollback_simulated_deployment", "bad-deployment", None, "Payment Service"),
        ("clear_simulated_queue", "payment-failure", {"queue_name": "payment"}, "Payment Service"),
        (
            "disable_simulated_feature_flag",
            "payment-failure",
            {"feature_name": "payment_retries"},
            "Payment Service",
        ),
        (
            "restore_simulated_configuration",
            "configuration-mismatch",
            {"configuration_id": "gateway.endpoint"},
            "Payment Service",
        ),
        (
            "scale_simulated_service",
            "payment-failure",
            {"service_name": "Payment Service", "desired_capacity": 4},
            "Payment Service",
        ),
    ]
    for action_name, scenario_id, parameters, service in cases:
        if parameters is None:
            fixture = client.get(f"/api/simulator/scenarios/{scenario_id}").json()
            parameters = {"deployment_id": fixture["state"]["deployments"][0]["id"]}
        incident = create_incident(client, service=service)
        action = create_action(
            client,
            str(incident["id"]),
            action_name=action_name,
            parameters=parameters,
            scenario_id=scenario_id,
        )
        executed = approve_and_execute(client, action)
        assert executed["status"] == "COMPLETED"
        assert executed["verification_status"] == "PASSED"
        assert executed["execution_result"]["production_change"] is False
