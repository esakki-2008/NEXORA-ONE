"""Phase 5 Investigation & Evidence Intelligence API."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from backend.app.api.dependencies import (
    get_investigation_service,
    get_principal,
    get_security_service,
)
from backend.app.investigation.context import (
    CollectionRequest,
    CorrelationRecord,
    EvidenceRecord,
    InvestigationCancelRequest,
    InvestigationContext,
    InvestigationHypothesis,
    InvestigationStartRequest,
    InvestigationSummary,
    InvestigationTimelineEvent,
    TestHypothesisRequest,
)
from backend.app.investigation.service import InvestigationService
from backend.app.investigation.store import InvestigationNotFoundError
from backend.app.investigation.validators import InvestigationValidationError
from backend.app.security.models import Principal
from backend.app.security.service import SecurityService

router = APIRouter(prefix="/api/investigations", tags=["investigations"])
InvestigationDependency = Annotated[InvestigationService, Depends(get_investigation_service)]


def _not_found(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


def _conflict(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)


def _scope(service: InvestigationService, investigation_id: UUID, principal: Principal) -> None:
    service.get(investigation_id, tenant_id=principal.tenant_id)


def _actor(security: SecurityService, principal: Principal, actor: str, resource: str) -> None:
    try:
        security.require_actor(principal, actor, resource=resource)
    except PermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied"
        ) from exc


@router.post(
    "/incidents/{incident_id}/start",
    response_model=InvestigationContext,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Start an evidence-driven investigation",
)
async def start(
    incident_id: UUID,
    service: InvestigationDependency,
    principal: Annotated[Principal, Depends(get_principal)],
    request: InvestigationStartRequest | None = None,
) -> InvestigationContext:
    try:
        return await service.start(
            incident_id,
            scenario_id=request.scenario_id if request else None,
            request_id=request.request_id if request else None,
            auto_handoff=request.auto_handoff if request else True,
            tenant_id=principal.tenant_id,
        )
    except (LookupError, InvestigationNotFoundError) as exc:
        raise _not_found(str(exc)) from exc
    except InvestigationValidationError as exc:
        raise _conflict(str(exc)) from exc


@router.get("", response_model=list[InvestigationSummary], summary="List investigations")
def list_investigations(
    service: InvestigationDependency,
    principal: Annotated[Principal, Depends(get_principal)],
) -> list[InvestigationSummary]:
    return service.list_contexts(tenant_id=principal.tenant_id)


@router.get(
    "/incidents/{incident_id}",
    response_model=InvestigationContext,
    summary="Get the investigation for an incident",
)
def get_for_incident(
    incident_id: UUID,
    service: InvestigationDependency,
    principal: Annotated[Principal, Depends(get_principal)],
) -> InvestigationContext:
    try:
        return service.get_for_incident(incident_id, tenant_id=principal.tenant_id)
    except InvestigationNotFoundError as exc:
        raise _not_found(str(exc)) from exc


@router.get(
    "/{investigation_id}",
    response_model=InvestigationContext,
    summary="Get investigation context",
)
def get_investigation(
    investigation_id: UUID,
    service: InvestigationDependency,
    principal: Annotated[Principal, Depends(get_principal)],
) -> InvestigationContext:
    try:
        return service.get(investigation_id, tenant_id=principal.tenant_id)
    except InvestigationNotFoundError as exc:
        raise _not_found(str(exc)) from exc


@router.get(
    "/{investigation_id}/evidence",
    response_model=list[EvidenceRecord],
    summary="List normalized evidence with provenance",
)
def evidence(
    investigation_id: UUID,
    service: InvestigationDependency,
    principal: Annotated[Principal, Depends(get_principal)],
) -> list[EvidenceRecord]:
    try:
        _scope(service, investigation_id, principal)
        return service.evidence(investigation_id, tenant_id=principal.tenant_id)
    except InvestigationNotFoundError as exc:
        raise _not_found(str(exc)) from exc


@router.get(
    "/{investigation_id}/correlations",
    response_model=list[CorrelationRecord],
    summary="List explainable evidence correlations",
)
def correlations(
    investigation_id: UUID,
    service: InvestigationDependency,
    principal: Annotated[Principal, Depends(get_principal)],
) -> list[CorrelationRecord]:
    try:
        _scope(service, investigation_id, principal)
        return service.correlations(investigation_id, tenant_id=principal.tenant_id)
    except InvestigationNotFoundError as exc:
        raise _not_found(str(exc)) from exc


@router.get(
    "/{investigation_id}/hypotheses",
    response_model=list[InvestigationHypothesis],
    summary="List server-scored investigation hypotheses",
)
def hypotheses(
    investigation_id: UUID,
    service: InvestigationDependency,
    principal: Annotated[Principal, Depends(get_principal)],
) -> list[InvestigationHypothesis]:
    try:
        _scope(service, investigation_id, principal)
        return service.hypotheses(investigation_id, tenant_id=principal.tenant_id)
    except InvestigationNotFoundError as exc:
        raise _not_found(str(exc)) from exc


@router.get(
    "/{investigation_id}/timeline",
    response_model=list[InvestigationTimelineEvent],
    summary="List investigation timeline events",
)
def timeline(
    investigation_id: UUID,
    service: InvestigationDependency,
    principal: Annotated[Principal, Depends(get_principal)],
) -> list[InvestigationTimelineEvent]:
    try:
        _scope(service, investigation_id, principal)
        return service.timeline(investigation_id, tenant_id=principal.tenant_id)
    except InvestigationNotFoundError as exc:
        raise _not_found(str(exc)) from exc


@router.get(
    "/{investigation_id}/summary",
    response_model=InvestigationSummary,
    summary="Get an investigation summary",
)
def summary(
    investigation_id: UUID,
    service: InvestigationDependency,
    principal: Annotated[Principal, Depends(get_principal)],
) -> InvestigationSummary:
    try:
        _scope(service, investigation_id, principal)
        return service.summary(investigation_id, tenant_id=principal.tenant_id)
    except InvestigationNotFoundError as exc:
        raise _not_found(str(exc)) from exc


@router.post(
    "/{investigation_id}/collect",
    response_model=InvestigationContext,
    summary="Collect additional allow-listed evidence",
)
async def collect(
    investigation_id: UUID,
    service: InvestigationDependency,
    principal: Annotated[Principal, Depends(get_principal)],
    request: CollectionRequest | None = None,
) -> InvestigationContext:
    try:
        _scope(service, investigation_id, principal)
        return await service.collect(
            investigation_id,
            request or CollectionRequest(),
            tenant_id=principal.tenant_id,
        )
    except InvestigationNotFoundError as exc:
        raise _not_found(str(exc)) from exc
    except InvestigationValidationError as exc:
        raise _conflict(str(exc)) from exc


@router.post(
    "/{investigation_id}/test-hypothesis",
    response_model=InvestigationContext,
    summary="Test one hypothesis using bounded read-only probes",
)
async def test_hypothesis(
    investigation_id: UUID,
    request: TestHypothesisRequest,
    service: InvestigationDependency,
    principal: Annotated[Principal, Depends(get_principal)],
) -> InvestigationContext:
    try:
        _scope(service, investigation_id, principal)
        return await service.test_hypothesis(
            investigation_id,
            request,
            tenant_id=principal.tenant_id,
        )
    except InvestigationNotFoundError as exc:
        raise _not_found(str(exc)) from exc
    except LookupError as exc:
        raise _not_found(str(exc)) from exc
    except InvestigationValidationError as exc:
        raise _conflict(str(exc)) from exc


@router.post(
    "/{investigation_id}/handoff",
    response_model=InvestigationContext,
    summary="Hand an evidence-grounded result to Phase 4 orchestration",
)
async def handoff(
    investigation_id: UUID,
    service: InvestigationDependency,
    principal: Annotated[Principal, Depends(get_principal)],
) -> InvestigationContext:
    try:
        _scope(service, investigation_id, principal)
        return await service.handoff(investigation_id, tenant_id=principal.tenant_id)
    except InvestigationNotFoundError as exc:
        raise _not_found(str(exc)) from exc


@router.post(
    "/{investigation_id}/cancel",
    response_model=InvestigationContext,
    summary="Cancel an investigation without executing actions",
)
async def cancel(
    investigation_id: UUID,
    request: InvestigationCancelRequest,
    service: InvestigationDependency,
    principal: Annotated[Principal, Depends(get_principal)],
    security: Annotated[SecurityService, Depends(get_security_service)],
) -> InvestigationContext:
    try:
        _scope(service, investigation_id, principal)
        _actor(security, principal, request.requested_by, f"investigation:{investigation_id}")
        return await service.cancel(
            investigation_id,
            request,
            tenant_id=principal.tenant_id,
        )
    except InvestigationNotFoundError as exc:
        raise _not_found(str(exc)) from exc


__all__ = ["router"]
