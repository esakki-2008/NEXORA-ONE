"""Unified Phase 6 enterprise operations intelligence routes."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from backend.app.api.dependencies import (
    get_operations_service,
    get_principal,
    get_security_service,
)
from backend.app.operations.context import (
    BusinessImpact,
    CrossDomainCorrelation,
    DomainDetail,
    DomainHealth,
    InvestigateSignalRequest,
    InvestigationLaunch,
    OperationalSignal,
    OperationalSnapshot,
    OperationsDomain,
    OperationsHealth,
    PriorityItem,
)
from backend.app.operations.service import (
    OperationsNotFoundError,
    OperationsService,
    OperationsValidationError,
)
from backend.app.security.models import Principal
from backend.app.security.service import SecurityService
from backend.app.simulator.runtime import SimulationUnavailableError

router = APIRouter(prefix="/api/operations", tags=["operations"])
OperationsDependency = Annotated[OperationsService, Depends(get_operations_service)]


def _not_found(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


def _conflict(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)


def _scope_incident(
    service: OperationsService, incident_id: UUID | None, principal: Principal
) -> None:
    if incident_id is None:
        return
    incident = service.repository.get_incident(incident_id)
    if incident is None or incident.tenant_id != principal.tenant_id:
        raise OperationsNotFoundError(f"Incident {incident_id} was not found")


@router.get(
    "/snapshot",
    response_model=OperationalSnapshot,
    summary="Get the unified enterprise operations snapshot",
)
def snapshot(
    service: OperationsDependency,
    principal: Annotated[Principal, Depends(get_principal)],
    scenario_id: str | None = Query(default=None, max_length=100),
    incident_id: UUID | None = Query(default=None),
) -> OperationalSnapshot:
    try:
        _scope_incident(service, incident_id, principal)
        return service.snapshot(scenario_id=scenario_id, incident_id=incident_id)
    except (OperationsNotFoundError, SimulationUnavailableError) as exc:
        raise _not_found(str(exc)) from exc


@router.post(
    "/refresh",
    response_model=OperationalSnapshot,
    summary="Refresh the server-generated operations snapshot",
)
def refresh(
    service: OperationsDependency,
    principal: Annotated[Principal, Depends(get_principal)],
    scenario_id: str | None = Query(default=None, max_length=100),
    incident_id: UUID | None = Query(default=None),
) -> OperationalSnapshot:
    try:
        _scope_incident(service, incident_id, principal)
        return service.snapshot(scenario_id=scenario_id, incident_id=incident_id)
    except (OperationsNotFoundError, SimulationUnavailableError) as exc:
        raise _not_found(str(exc)) from exc


@router.get(
    "/domains",
    response_model=list[DomainHealth],
    summary="List health for all eight enterprise domains",
)
def domains(
    service: OperationsDependency,
    principal: Annotated[Principal, Depends(get_principal)],
    scenario_id: str | None = Query(default=None, max_length=100),
    incident_id: UUID | None = Query(default=None),
) -> list[DomainHealth]:
    try:
        _scope_incident(service, incident_id, principal)
        return service.domains(scenario_id=scenario_id, incident_id=incident_id)
    except (OperationsNotFoundError, SimulationUnavailableError) as exc:
        raise _not_found(str(exc)) from exc


@router.get(
    "/domains/{domain}",
    response_model=DomainDetail,
    summary="Inspect one enterprise domain",
)
def domain(
    domain: OperationsDomain,
    service: OperationsDependency,
    principal: Annotated[Principal, Depends(get_principal)],
    scenario_id: str | None = Query(default=None, max_length=100),
    incident_id: UUID | None = Query(default=None),
) -> DomainDetail:
    try:
        _scope_incident(service, incident_id, principal)
        return service.domain(
            domain,
            scenario_id=scenario_id,
            incident_id=incident_id,
        )
    except (OperationsNotFoundError, SimulationUnavailableError) as exc:
        raise _not_found(str(exc)) from exc


@router.get(
    "/signals",
    response_model=list[OperationalSignal],
    summary="List server-generated operational signals",
)
def signals(
    service: OperationsDependency,
    principal: Annotated[Principal, Depends(get_principal)],
    domain: OperationsDomain | None = Query(default=None),
    scenario_id: str | None = Query(default=None, max_length=100),
    incident_id: UUID | None = Query(default=None),
) -> list[OperationalSignal]:
    try:
        _scope_incident(service, incident_id, principal)
        return service.signals(
            domain=domain,
            scenario_id=scenario_id,
            incident_id=incident_id,
        )
    except (OperationsNotFoundError, SimulationUnavailableError) as exc:
        raise _not_found(str(exc)) from exc


@router.get(
    "/signals/{signal_id}",
    response_model=OperationalSignal,
    summary="Retrieve one operational signal",
)
def signal(
    signal_id: str,
    service: OperationsDependency,
    principal: Annotated[Principal, Depends(get_principal)],
    scenario_id: str | None = Query(default=None, max_length=100),
    incident_id: UUID | None = Query(default=None),
) -> OperationalSignal:
    try:
        _scope_incident(service, incident_id, principal)
        return service.signal(
            signal_id,
            scenario_id=scenario_id,
            incident_id=incident_id,
        )
    except (OperationsNotFoundError, SimulationUnavailableError) as exc:
        raise _not_found(str(exc)) from exc


@router.post(
    "/signals/{signal_id}/investigate",
    response_model=InvestigationLaunch,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Open a Phase 5 investigation for a signal",
)
async def investigate(
    signal_id: str,
    service: OperationsDependency,
    principal: Annotated[Principal, Depends(get_principal)],
    security: Annotated[SecurityService, Depends(get_security_service)],
    request: InvestigateSignalRequest | None = None,
) -> InvestigationLaunch:
    try:
        effective_request = request or InvestigateSignalRequest()
        if effective_request.requested_by is not None:
            try:
                security.require_actor(
                    principal,
                    effective_request.requested_by,
                    resource=f"operations:signal:{signal_id}",
                )
            except PermissionError as exc:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Permission denied",
                ) from exc
        effective_request = effective_request.model_copy(update={"requested_by": principal.subject})
        return await service.investigate_signal(
            signal_id,
            effective_request,
            tenant_id=principal.tenant_id,
        )
    except (OperationsNotFoundError, SimulationUnavailableError) as exc:
        raise _not_found(str(exc)) from exc
    except OperationsValidationError as exc:
        raise _conflict(str(exc)) from exc


@router.get(
    "/correlations",
    response_model=list[CrossDomainCorrelation],
    summary="List cross-domain related-signal relationships",
)
def correlations(
    service: OperationsDependency,
    principal: Annotated[Principal, Depends(get_principal)],
    scenario_id: str | None = Query(default=None, max_length=100),
    incident_id: UUID | None = Query(default=None),
) -> list[CrossDomainCorrelation]:
    try:
        _scope_incident(service, incident_id, principal)
        return service.correlations(scenario_id=scenario_id, incident_id=incident_id)
    except (OperationsNotFoundError, SimulationUnavailableError) as exc:
        raise _not_found(str(exc)) from exc


@router.get(
    "/priorities",
    response_model=list[PriorityItem],
    summary="List explainable enterprise priority items",
)
def priorities(
    service: OperationsDependency,
    principal: Annotated[Principal, Depends(get_principal)],
    scenario_id: str | None = Query(default=None, max_length=100),
    incident_id: UUID | None = Query(default=None),
) -> list[PriorityItem]:
    try:
        _scope_incident(service, incident_id, principal)
        return service.priorities(scenario_id=scenario_id, incident_id=incident_id)
    except (OperationsNotFoundError, SimulationUnavailableError) as exc:
        raise _not_found(str(exc)) from exc


@router.get(
    "/business-impact",
    response_model=BusinessImpact,
    summary="Calculate deterministic business impact",
)
def business_impact(
    service: OperationsDependency,
    principal: Annotated[Principal, Depends(get_principal)],
    scenario_id: str | None = Query(default=None, max_length=100),
    incident_id: UUID | None = Query(default=None),
) -> BusinessImpact:
    try:
        _scope_incident(service, incident_id, principal)
        return service.business_impact(scenario_id=scenario_id, incident_id=incident_id)
    except (OperationsNotFoundError, SimulationUnavailableError) as exc:
        raise _not_found(str(exc)) from exc


@router.get(
    "/health",
    response_model=OperationsHealth,
    summary="Get operations source availability",
)
def health(
    service: OperationsDependency,
    principal: Annotated[Principal, Depends(get_principal)],
    scenario_id: str | None = Query(default=None, max_length=100),
    incident_id: UUID | None = Query(default=None),
) -> OperationsHealth:
    try:
        _scope_incident(service, incident_id, principal)
        return service.health(scenario_id=scenario_id, incident_id=incident_id)
    except (OperationsNotFoundError, SimulationUnavailableError) as exc:
        raise _not_found(str(exc)) from exc


__all__ = ["router"]
