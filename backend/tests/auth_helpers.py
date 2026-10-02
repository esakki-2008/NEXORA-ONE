from fastapi.testclient import TestClient

from backend.app.security.models import SecurityRole


def auth_headers(
    client: TestClient,
    *,
    subject: str = "test-operator",
    tenant_id: str = "tenant-a",
    roles: set[SecurityRole] | None = None,
) -> dict[str, str]:
    effective_roles = roles or {SecurityRole.OPERATOR, SecurityRole.APPROVER}
    token = client.app.state.security_service.issue_reference_token(
        subject=subject,
        tenant_id=tenant_id,
        roles=effective_roles,
    )
    return {"Authorization": f"Bearer {token}"}


def authenticate(
    client: TestClient,
    *,
    subject: str = "test-operator",
    tenant_id: str = "tenant-a",
    roles: set[SecurityRole] | None = None,
) -> TestClient:
    client.headers.update(
        auth_headers(
            client,
            subject=subject,
            tenant_id=tenant_id,
            roles=roles,
        )
    )
    return client
