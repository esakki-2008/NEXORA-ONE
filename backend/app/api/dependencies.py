"""FastAPI dependency providers."""

from typing import Annotated, cast

from fastapi import Depends, Request

from backend.app.agents.orchestrator import AgentOrchestrator
from backend.app.ai.services.inference import AIService
from backend.app.database.repository import IncidentRepository
from backend.app.investigation.service import InvestigationService
from backend.app.operations.service import OperationsService
from backend.app.services.incident_service import IncidentService


def get_repository(request: Request) -> IncidentRepository:
    return cast(IncidentRepository, request.app.state.repository)


def get_incident_service(
    repository: Annotated[IncidentRepository, Depends(get_repository)],
) -> IncidentService:
    return IncidentService(repository)


def get_ai_service(request: Request) -> AIService:
    return cast(AIService, request.app.state.ai_service)


def get_orchestrator(request: Request) -> AgentOrchestrator:
    return cast(AgentOrchestrator, request.app.state.orchestrator)


def get_investigation_service(request: Request) -> InvestigationService:
    return cast(InvestigationService, request.app.state.investigation_service)


def get_operations_service(request: Request) -> OperationsService:
    return cast(OperationsService, request.app.state.operations_service)
