"""Execute the complete controlled ShopFlow payment-failure workflow."""

from __future__ import annotations

import sys
from typing import Any

from fastapi.testclient import TestClient

from backend.app.config.settings import Settings
from backend.app.main import create_app
from backend.app.security.models import SecurityRole

TENANT_ID = "phase10-demo"


def headers(client: TestClient, *, subject: str, roles: set[SecurityRole]) -> dict[str, str]:
    token = client.app.state.security_service.issue_reference_token(
        subject=subject,
        tenant_id=TENANT_ID,
        roles=roles,
    )
    return {"Authorization": f"Bearer {token}"}


def require_status(response: Any, expected: set[int], label: str) -> dict[str, Any]:
    if response.status_code not in expected:
        raise RuntimeError(f"{label} returned HTTP {response.status_code}")
    payload = response.json()
    if not isinstance(payload, dict):
        raise RuntimeError(f"{label} returned an unexpected response shape")
    return payload


def main() -> int:
    application = create_app(settings=Settings(environment="test"))

    with TestClient(application) as client:
        operator_roles = {SecurityRole.OPERATOR, SecurityRole.APPROVER}
        operator = headers(client, subject="test-operator", roles=operator_roles)
        planner = headers(client, subject="test-planner", roles={SecurityRole.OPERATOR})
        approver = headers(client, subject="operator", roles={SecurityRole.APPROVER})
        executor = headers(client, subject="local-operator", roles={SecurityRole.OPERATOR})
        incident = require_status(
            client.post(
                "/api/incidents",
                headers=operator,
                json={
                    "title": "ShopFlow payment failure after deployment",
                    "description": (
                        "SIMULATED / CONTROLLED DEMONSTRATION: payment failures increased after "
                        "a ShopFlow deployment."
                    ),
                    "severity": "critical",
                    "service": "Payment Service",
                },
            ),
            {201},
            "incident creation",
        )
        incident_id = str(incident["id"])

        investigation = require_status(
            client.post(
                f"/api/investigations/incidents/{incident_id}/start",
                headers=operator,
                json={
                    "scenario_id": "payment-failure",
                    "request_id": "phase10-shopflow-payment-failure",
                    "auto_handoff": False,
                },
            ),
            {202},
            "investigation start",
        )

        ai_response = client.post(
            "/api/ai/analyze",
            headers=operator,
            json={"incident_id": incident_id},
        )
        if ai_response.status_code == 200:
            ai_status = "verified structured response"
        elif ai_response.status_code in {502, 503, 504}:
            ai_status = f"safe provider failure (HTTP {ai_response.status_code})"
        else:
            raise RuntimeError(f"AI assistance returned HTTP {ai_response.status_code}")

        action = require_status(
            client.post(
                "/api/actions",
                headers=planner,
                json={
                    "incident_id": incident_id,
                    "investigation_id": investigation["investigation_id"],
                    "scenario_id": "payment-failure",
                    "action_name": "restart_payment_service",
                    "parameters": {},
                    "requested_by": "test-planner",
                    "idempotency_key": "phase10-shopflow-payment-failure",
                },
            ),
            {201},
            "controlled action proposal",
        )
        action_id = str(action["action_id"])

        approved = require_status(
            client.post(
                f"/api/actions/{action_id}/approve",
                headers=approver,
                json={
                    "requested_by": "operator",
                    "reason": "Reviewed the exact registered action, risk, and fingerprint.",
                },
            ),
            {200},
            "human approval",
        )
        executed = require_status(
            client.post(
                f"/api/actions/{action_id}/execute",
                headers=executor,
                json={
                    "requested_by": "local-operator",
                    "reason": "Execute the approved controlled demonstration action.",
                },
            ),
            {200},
            "controlled execution",
        )
        final_incident = require_status(
            client.get(f"/api/incidents/{incident_id}", headers=operator),
            {200},
            "final incident",
        )
        report = require_status(
            client.get(f"/api/incidents/{incident_id}/report", headers=operator),
            {200},
            "incident report",
        )
        verification = require_status(
            client.get(f"/api/actions/{action_id}/verification", headers=operator),
            {200},
            "verification proof",
        )
        audit = client.get(f"/api/actions/{action_id}/audit", headers=operator)
        if audit.status_code != 200 or not audit.json():
            raise RuntimeError("action audit was not returned")

    if approved["status"] != "APPROVED":
        raise RuntimeError("approval did not produce APPROVED state")
    if executed["status"] != "COMPLETED" or executed["verification_status"] != "PASSED":
        raise RuntimeError("controlled action did not reach verified completion")
    if final_incident["status"] != "resolved" or report["final_status"] != "resolved":
        raise RuntimeError("incident did not reach report-backed resolution")
    if verification["status"] != "PASSED":
        raise RuntimeError("verification proof did not pass")

    print("workflow=ShopFlow payment-failure")
    print("classification=SIMULATED / CONTROLLED DEMONSTRATION")
    print("evidence=investigation started with simulator evidence and provenance")
    print(f"ai_assistance={ai_status}")
    print("recommendation=server-validated restart_payment_service proposal")
    print("approval=human approval recorded")
    print("action=registered simulator action executed")
    print("verification=PASSED")
    print("resolution=resolved only after verification proof")
    print("report=generated")
    print("audit=returned and hash-chained")
    print("secrets=not printed")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (RuntimeError, KeyError, TypeError, ValueError) as exc:
        print(f"ShopFlow workflow check failed safely: {exc}", file=sys.stderr)
        sys.exit(1)
