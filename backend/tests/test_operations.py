from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend.app.operations.context import (
    BusinessImpact,
    ImpactLevel,
    OperationalSignal,
    OperationalSignalStatus,
    OperationsDomain,
    Severity,
    SourceMetadata,
    SourceType,
)


def test_operations_default_does_not_infer_health_from_missing_sources(
    client: TestClient,
) -> None:
    response = client.get("/api/operations/snapshot")

    assert response.status_code == 200
    snapshot = response.json()
    assert len(snapshot["domains"]) == 8
    assert snapshot["overall_status"] == "NOT_CONFIGURED"
    assert all(item["status"] == "NOT_CONFIGURED" for item in snapshot["domains"])
    assert snapshot["business_impact"]["impact_level"] == "UNKNOWN"
    assert snapshot["business_impact"]["affected_domains"] == []
    assert snapshot["simulator"] is False


def test_payment_scenario_builds_labeled_cross_domain_snapshot(
    client: TestClient,
) -> None:
    response = client.get("/api/operations/snapshot?scenario_id=payment-failure")

    assert response.status_code == 200
    snapshot = response.json()
    assert snapshot["simulator"] is True
    assert snapshot["source"]["label"] == "SIMULATED / CONTROLLED DEMONSTRATION"
    assert snapshot["business_impact"]["affected_domains"] == ["IT", "REVENUE", "SUPPORT"]
    assert snapshot["business_impact"]["estimated_customer_impact"] == 42
    assert snapshot["business_impact"]["estimated_revenue_impact"] == 149.99
    assert snapshot["business_impact"]["currency"] == "USD"

    domain_status = {item["domain"]: item["status"] for item in snapshot["domains"]}
    assert domain_status["IT"] in {"DEGRADED", "CRITICAL"}
    assert domain_status["REVENUE"] in {"DEGRADED", "CRITICAL"}
    assert domain_status["SUPPORT"] in {"DEGRADED", "CRITICAL"}
    assert domain_status["CLOUD"] == "HEALTHY"

    correlations = snapshot["cross_domain_correlations"]
    assert correlations
    assert any(
        item["source_domain"] == "IT"
        and item["target_domain"] == "REVENUE"
        and "not proof of causation" in item["explanation"]
        for item in correlations
    )
    assert all(item["simulator"] is True for item in correlations)

    priorities = snapshot["priority_items"]
    assert priorities
    assert all(item["factors"] for item in priorities)
    assert any(item["priority"] in {"HIGH", "CRITICAL"} for item in priorities)


def test_all_controlled_scenarios_have_safe_operations_contract(
    client: TestClient,
) -> None:
    scenario_ids = {
        item["scenario_id"] for item in client.get("/api/simulator/scenarios").json()
    }
    assert scenario_ids == {
        "payment-failure",
        "database-failure",
        "latency-spike",
        "bad-deployment",
        "configuration-mismatch",
    }

    for scenario_id in sorted(scenario_ids):
        response = client.get(f"/api/operations/snapshot?scenario_id={scenario_id}")
        assert response.status_code == 200
        payload = response.json()
        assert payload["scenario_id"] == scenario_id
        assert payload["simulator"] is True
        assert len(payload["domains"]) == 8
        configured = [
            item for item in payload["domains"] if item["status"] != "NOT_CONFIGURED"
        ]
        assert configured
        assert all(item["source"]["simulator"] for item in configured)


def test_domain_detail_and_source_health_use_one_snapshot_engine(
    client: TestClient,
) -> None:
    detail = client.get(
        "/api/operations/domains/REVENUE?scenario_id=payment-failure"
    )
    assert detail.status_code == 200
    body = detail.json()
    assert body["health"]["domain"] == "REVENUE"
    assert body["metrics"]
    assert body["signals"]
    assert body["source_status"]["source"]["label"] == "SIMULATED / CONTROLLED DEMONSTRATION"
    assert body["recommended_investigation"]

    health = client.get("/api/operations/health?scenario_id=payment-failure")
    assert health.status_code == 200
    health_body = health.json()
    assert health_body["status"] == "AVAILABLE"
    assert len(health_body["configured_domains"]) == 8
    assert health_body["not_configured_domains"] == []


def test_incident_signal_is_connected_to_operations(
    client: TestClient,
) -> None:
    created = client.post(
        "/api/incidents",
        json={
            "title": "Recorded payment incident",
            "description": "Payment errors are above the recorded threshold.",
            "severity": "high",
            "service": "Payment Service",
        },
    ).json()
    incident_id = created["id"]

    snapshot = client.get(f"/api/operations/snapshot?incident_id={incident_id}")
    assert snapshot.status_code == 200
    payload = snapshot.json()
    assert payload["incident_id"] == incident_id
    assert any(
        item["related_incident_id"] == incident_id for item in payload["critical_signals"]
    ) or any(
        item["related_incident_id"] == incident_id
        for item in client.get(f"/api/operations/signals?incident_id={incident_id}").json()
    )
    assert payload["domains"][0]["source"]["source_type"] == "INCIDENT_SYSTEM"
    assert payload["simulator"] is False


def test_operations_signal_opens_phase5_investigation_without_action_execution(
    client: TestClient,
) -> None:
    signals = client.get("/api/operations/signals?scenario_id=payment-failure").json()
    signal = next(item for item in signals if item["domain"] == "REVENUE")
    launch = client.post(
        f"/api/operations/signals/{signal['signal_id']}/investigate",
        json={
            "scenario_id": "payment-failure",
            "request_id": "operations-test-payment-001",
            "auto_handoff": False,
        },
    )

    assert launch.status_code == 202
    body = launch.json()
    assert body["simulator"] is True
    assert body["source"]["label"] == "SIMULATED / CONTROLLED DEMONSTRATION"
    assert UUID(body["incident_id"])
    investigation = client.get(f"/api/investigations/{body['investigation_id']}")
    assert investigation.status_code == 200
    context = investigation.json()
    assert context["source_type"] == "SIMULATED / CONTROLLED DEMONSTRATION"
    assert context["orchestrator_handoff"]["status"] in {
        "NOT_READY",
        "READY",
        "REQUIRES_HUMAN",
        "HANDED_OFF",
        "FAILED",
    }
    handoff = client.post(f"/api/investigations/{body['investigation_id']}/handoff")
    assert handoff.status_code == 200
    handoff_body = handoff.json()
    assert handoff_body["orchestrator_handoff"]["status"] in {
        "HANDED_OFF",
        "REQUIRES_HUMAN",
        "FAILED",
    }
    assert handoff_body["incident"]["status"] != "resolved"


def test_operations_investigation_request_is_idempotent(
    client: TestClient,
) -> None:
    signal = next(
        item
        for item in client.get("/api/operations/signals?scenario_id=payment-failure").json()
        if item["domain"] == "REVENUE"
    )
    request = {
        "scenario_id": "payment-failure",
        "request_id": "operations-idempotency-001",
        "auto_handoff": False,
    }
    first = client.post(
        f"/api/operations/signals/{signal['signal_id']}/investigate", json=request
    )
    second = client.post(
        f"/api/operations/signals/{signal['signal_id']}/investigate", json=request
    )

    assert first.status_code == 202
    assert second.status_code == 202
    assert second.json()["incident_id"] == first.json()["incident_id"]
    assert second.json()["investigation_id"] == first.json()["investigation_id"]


def test_operations_rejects_invalid_financial_values_and_domains() -> None:
    source = SourceMetadata(
        source_type=SourceType.SIMULATOR,
        source_name="controlled test source",
        label="SIMULATED / CONTROLLED DEMONSTRATION",
        simulator=True,
    )
    with pytest.raises(ValidationError):
        BusinessImpact(
            impact_level=ImpactLevel.HIGH,
            affected_domains=[OperationsDomain.REVENUE],
            affected_services=["Payment Service"],
            estimated_revenue_impact=-1,
            operational_scope="invalid",
            explanation=["negative values are rejected"],
            source=source,
            simulator=True,
        )

    with pytest.raises(ValidationError):
        OperationalSignal(
            signal_id="signal-invalid",
            domain="UNKNOWN_DOMAIN",
            kind="test",
            title="Invalid domain",
            summary="This must fail validation.",
            status=OperationalSignalStatus.ACTIVE,
            severity=Severity.HIGH,
            source=source,
            simulator=True,
        )


def test_unknown_scenario_is_not_treated_as_real_data(client: TestClient) -> None:
    response = client.get("/api/operations/snapshot?scenario_id=not-a-scenario")
    assert response.status_code == 404
    assert "not available" in response.json()["detail"] or "not found" in response.json()["detail"]
