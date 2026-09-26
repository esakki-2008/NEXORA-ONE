"""FastAPI dependency providers."""

from typing import Annotated, cast

from fastapi import Depends, Request

from backend.app.database.repository import IncidentRepository
from backend.app.services.incident_service import IncidentService


def get_repository(request: Request) -> IncidentRepository:
    return cast(IncidentRepository, request.app.state.repository)


def get_incident_service(
    repository: Annotated[IncidentRepository, Depends(get_repository)],
) -> IncidentService:
    return IncidentService(repository)
