from uuid import uuid4

from fastapi.testclient import TestClient


def test_application_starts_and_health_works(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["service"] == "NEXORA ONE API"
    assert payload["environment"] == "test"


def test_create_and_retrieve_incident(client: TestClient) -> None:
    request = {
        "title": "Checkout error rate increased",
        "description": "Users are seeing failed checkout requests.",
        "severity": "high",
        "service": "Checkout Service",
    }

    created_response = client.post("/api/incidents", json=request)
    assert created_response.status_code == 201
    incident = created_response.json()
    assert incident["title"] == request["title"]
    assert incident["status"] == "open"
    assert incident["agent_state"] == "INCIDENT_RECEIVED"

    incident_id = incident["id"]
    get_response = client.get(f"/api/incidents/{incident_id}")
    assert get_response.status_code == 200
    assert get_response.json()["id"] == incident_id

    list_response = client.get("/api/incidents")
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1


def test_incident_activity_is_a_real_audit_event(client: TestClient) -> None:
    created = client.post(
        "/api/incidents",
        json={
            "title": "Payment authorization errors",
            "description": "Authorization failures are above threshold.",
            "severity": "critical",
            "service": "Payment Service",
        },
    ).json()

    response = client.get(f"/api/incidents/{created['id']}/activity")
    assert response.status_code == 200
    events = response.json()
    assert len(events) == 1
    assert events[0]["event_type"] == "incident.created"
    assert events[0]["metadata"]["source"] == "api"


def test_invalid_incident_input_is_rejected(client: TestClient) -> None:
    response = client.post(
        "/api/incidents",
        json={
            "title": "x",
            "description": "",
            "severity": "urgent",
            "service": "Checkout Service",
            "unexpected": "reject me",
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"]


def test_nested_resources_validate_missing_incidents(client: TestClient) -> None:
    missing_id = uuid4()

    for resource in ("activity", "evidence", "hypotheses", "report"):
        response = client.get(f"/api/incidents/{missing_id}/{resource}")
        assert response.status_code == 404


def test_report_is_not_fabricated_before_generation(client: TestClient) -> None:
    created = client.post(
        "/api/incidents",
        json={
            "title": "A report is not ready",
            "description": "No investigation has run.",
            "severity": "low",
            "service": "Support System",
        },
    ).json()

    response = client.get(f"/api/incidents/{created['id']}/report")
    assert response.status_code == 404
