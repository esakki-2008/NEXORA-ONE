"""Unified Phase 6 enterprise operations intelligence routes."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from backend.app.api.dependencies import get_operations_service
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
from backend.app.simulator.runtime import SimulationUnavailableError

router = APIRouter(prefix="/api/operations", tags=["operations"])
OperationsDependency = Annotated[OperationsService, Depends(get_operations_service)]


def _not_found(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


def _conflict(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)


@router.get(
    "/snapshot",
    response_model=OperationalSnapshot,
    summary="Get the unified enterprise operations snapshot",
)
def snapshot(
    service: OperationsDependency,
    scenario_id: str | None = Query(default=None, max_length=100),
    incident_id: UUID | None = Query(default=None),
) -> OperationalSnapshot:
    try:
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
    scenario_id: str | None = Query(default=None, max_length=100),
    incident_id: UUID | None = Query(default=None),
) -> OperationalSnapshot:
    try:
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
    scenario_id: str | None = Query(default=None, max_length=100),
    incident_id: UUID | None = Query(default=None),
) -> list[DomainHealth]:
    try:
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
    scenario_id: str | None = Query(default=None, max_length=100),
    incident_id: UUID | None = Query(default=None),
) -> DomainDetail:
    try:
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
    domain: OperationsDomain | None = Query(default=None),
    scenario_id: str | None = Query(default=None, max_length=100),
    incident_id: UUID | None = Query(default=None),
) -> list[OperationalSignal]:
    try:
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
    scenario_id: str | None = Query(default=None, max_length=100),
    incident_id: UUID | None = Query(default=None),
) -> OperationalSignal:
    try:
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
    request: InvestigateSignalRequest | None = None,
) -> InvestigationLaunch:
    try:
        return await service.investigate_signal(signal_id, request or InvestigateSignalRequest())
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
    scenario_id: str | None = Query(default=None, max_length=100),
    incident_id: UUID | None = Query(default=None),
) -> list[CrossDomainCorrelation]:
    try:
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
    scenario_id: str | None = Query(default=None, max_length=100),
    incident_id: UUID | None = Query(default=None),
) -> list[PriorityItem]:
    try:
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
    scenario_id: str | None = Query(default=None, max_length=100),
    incident_id: UUID | None = Query(default=None),
) -> BusinessImpact:
    try:
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
    scenario_id: str | None = Query(default=None, max_length=100),
    incident_id: UUID | None = Query(default=None),
) -> OperationsHealth:
    try:
        return service.health(scenario_id=scenario_id, incident_id=incident_id)
    except (OperationsNotFoundError, SimulationUnavailableError) as exc:
        raise _not_found(str(exc)) from exc


__all__ = ["router"]
