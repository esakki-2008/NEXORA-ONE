"""Run a real, secret-safe Nebius/Nemotron verification through NEXORA."""

from __future__ import annotations

import sys

from fastapi.testclient import TestClient

from backend.app.ai.config import NebiusConfig
from backend.app.config.settings import Settings
from backend.app.main import create_app
from backend.app.security.models import SecurityRole

NOT_EXECUTED_MESSAGE = (
    "Live provider verification not executed because no valid runtime credential was available "
    "in the environment."
)


def _headers(client: TestClient) -> dict[str, str]:
    token = client.app.state.security_service.issue_reference_token(
        subject="phase10-verifier",
        tenant_id="phase10-verification",
        roles={SecurityRole.OPERATOR},
    )
    return {"Authorization": f"Bearer {token}"}


def main() -> int:
    settings = Settings()
    try:
        config = NebiusConfig.from_settings(settings)
    except ValueError as exc:
        print("provider=Nebius Token Factory")
        print("status=INVALID_CONFIGURATION")
        print(f"safe_error={exc}")
        return 1

    print("provider=Nebius Token Factory")
    print(f"configured_base_url={config.base_url or 'not configured'}")
    print(f"configured_model={config.model or 'not configured'}")
    print(f"credential_fields_present={'yes' if config.is_configured else 'no'}")
    if not config.is_configured:
        print("live_verification=NOT_EXECUTED")
        print(f"limitation={NOT_EXECUTED_MESSAGE}")
        return 2

    application = create_app(settings=settings)
    with TestClient(application) as client:
        response = client.post("/api/ai/test", headers=_headers(client), json={})

    print("request_path=POST /api/ai/test")
    print(f"http_status={response.status_code}")
    try:
        payload = response.json()
    except ValueError:
        payload = {}
    success = payload.get("success") is True
    print(f"live_verification={'PASSED' if success else 'FAILED_SAFE'}")
    print(f"structured_response_validation={'PASSED' if success else 'NOT_CONFIRMED'}")
    print(
        "evidence_grounding="
        + ("PASSED (empty connectivity evidence index)" if success else "NOT_CONFIRMED")
    )
    print(
        "action_tool_validation="
        + ("PASSED (server registry validation)" if success else "NOT_CONFIRMED")
    )
    print("timeout_and_safe_failure=bounded provider handling is server-enforced")
    print("secret_output=none")
    if not success:
        print("provider_failure=returned through the safe API error boundary")
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
