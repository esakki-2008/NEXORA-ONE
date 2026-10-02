"""FastAPI dependency providers."""

from typing import Annotated, cast

from fastapi import Depends, HTTPException, Request, status

from backend.app.actions.service import ActionService
from backend.app.agents.orchestrator import AgentOrchestrator
from backend.app.ai.services.inference import AIService
from backend.app.database.repository import IncidentRepository
from backend.app.investigation.service import InvestigationService
from backend.app.operations.service import OperationsService
from backend.app.security.models import Permission, Principal
from backend.app.security.service import SecurityService
from backend.app.services.incident_service import IncidentService
from backend.app.verification.service import VerificationService


def get_security_service(request: Request) -> SecurityService:
    return cast(SecurityService, request.app.state.security_service)


def get_principal(request: Request) -> Principal:
    principal = getattr(request.state, "principal", None)
    if not isinstance(principal, Principal):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication is required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return principal


def require_permission(request: Request, permission: Permission) -> Principal:
    principal = get_principal(request)
    security = get_security_service(request)
    try:
        security.require_permission(principal, permission)
    except PermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied"
        ) from exc
    return principal


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


def get_action_service(request: Request) -> ActionService:
    return cast(ActionService, request.app.state.action_service)


def get_verification_service(request: Request) -> VerificationService:
    return cast(VerificationService, request.app.state.verification_service)
