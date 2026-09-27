from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from backend.app.config.settings import Settings
from backend.app.database.repository import InMemoryIncidentRepository
from backend.app.main import create_app


@pytest.fixture
def repository() -> InMemoryIncidentRepository:
    return InMemoryIncidentRepository()


@pytest.fixture
def client(repository: InMemoryIncidentRepository) -> Iterator[TestClient]:
    settings = Settings(environment="test", cors_origins="http://testserver")
    application = create_app(repository=repository, settings=settings)
    with TestClient(application) as test_client:
        yield test_client
