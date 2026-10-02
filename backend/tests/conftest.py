from collections.abc import Callable, Iterator

import pytest
from fastapi.testclient import TestClient

from backend.app.config.settings import Settings
from backend.app.database.repository import InMemoryIncidentRepository
from backend.app.main import create_app
from backend.app.security.models import SecurityRole

TEST_TENANT = "tenant-a"
TEST_OPERATOR = "test-operator"
TEST_PLANNER = "test-planner"


def reference_headers(
    client: TestClient,
    *,
    subject: str = TEST_OPERATOR,
    tenant_id: str = TEST_TENANT,
    roles: set[SecurityRole] | None = None,
) -> dict[str, str]:
    """Issue a server-owned reference token for an explicitly authenticated test request."""

    effective_roles = roles or {SecurityRole.OPERATOR, SecurityRole.APPROVER}
    token = client.app.state.security_service.issue_reference_token(
        subject=subject,
        tenant_id=tenant_id,
        roles=effective_roles,
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def repository() -> InMemoryIncidentRepository:
    return InMemoryIncidentRepository()


@pytest.fixture
def client(repository: InMemoryIncidentRepository) -> Iterator[TestClient]:
    settings = Settings(environment="test", cors_origins="http://testserver")
    application = create_app(repository=repository, settings=settings)
    with TestClient(application) as test_client:
        # The fixture authenticates every request by default. Individual tests
        # can explicitly request another reference principal with the helper.
        test_client.headers.update(reference_headers(test_client))
        test_client.reference_headers = (  # type: ignore[attr-defined]
            lambda **kwargs: reference_headers(test_client, **kwargs)
        )
        yield test_client


@pytest.fixture
def auth_headers() -> Callable[..., dict[str, str]]:
    """Expose the reusable token helper to security-focused tests."""

    return reference_headers
