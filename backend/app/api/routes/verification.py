"""Phase 8 verification and reliability APIs."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from backend.app.api.dependencies import (
    get_principal,
    get_security_service,
    get_verification_service,
)
from backend.app.security.models import Principal
from backend.app.security.service import SecurityService
from backend.app.verification.models import (
    Verification,
    VerificationCancelRequest,
    VerificationCreateRequest,
    VerificationEvidence,
    VerificationRetryRequest,
    VerificationRunRequest,
    VerificationStatus,
    VerificationSummary,
    VerificationTimelineEvent,
)
from backend.app.verification.service import (
    VerificationConflictError,
    VerificationNotFoundError,
    VerificationService,
)

router = APIRouter(prefix="/api/verification", tags=["verification"])
VerificationDependency = Annotated[VerificationService, Depends(get_verification_service)]


def _not_found(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


def _conflict(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)


def _scope(service: VerificationService, verification_id: UUID, principal: Principal) -> None:
    service.get(verification_id, tenant_id=principal.tenant_id)


def _actor(security: SecurityService, principal: Principal, actor: str, resource: str) -> None:
    try:
        security.require_actor(principal, actor, resource=resource)
    except PermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied"
        ) from exc


@router.get("", response_model=list[Verification], summary="List server-owned verification records")
def list_verifications(
    service: VerificationDependency,
    principal: Annotated[Principal, Depends(get_principal)],
    verification_status: VerificationStatus | None = Query(default=None, alias="status"),
    incident_id: UUID | None = Query(default=None),
    action_id: UUID | None = Query(default=None),
) -> list[Verification]:
    try:
        return service.list(
            status=verification_status,
            incident_id=incident_id,
            action_id=action_id,
            tenant_id=principal.tenant_id,
        )
    except VerificationConflictError as exc:
        raise _conflict(str(exc)) from exc


@router.get(
    "/summary", response_model=VerificationSummary, summary="Get verification reliability posture"
)
def summary(
    service: VerificationDependency,
    principal: Annotated[Principal, Depends(get_principal)],
) -> VerificationSummary:
    return service.summary(tenant_id=principal.tenant_id)


@router.post(
    "",
    response_model=Verification,
    status_code=status.HTTP_201_CREATED,
    summary="Create verification from a known action identity",
)
def create_verification(
    request: VerificationCreateRequest,
    service: VerificationDependency,
    principal: Annotated[Principal, Depends(get_principal)],
    security: Annotated[SecurityService, Depends(get_security_service)],
) -> Verification:
    try:
        effective_request = request
        if request.requested_by is None:
            effective_request = request.model_copy(update={"requested_by": principal.subject})
        else:
            _actor(security, principal, request.requested_by, "verification:create")
        return service.create(effective_request, tenant_id=principal.tenant_id)
    except VerificationNotFoundError as exc:
        raise _not_found(str(exc)) from exc
    except VerificationConflictError as exc:
        raise _conflict(str(exc)) from exc


@router.get(
    "/{verification_id}", response_model=Verification, summary="Get one verification record"
)
def get_verification(
    verification_id: UUID,
    service: VerificationDependency,
    principal: Annotated[Principal, Depends(get_principal)],
) -> Verification:
    try:
        return service.get(verification_id, tenant_id=principal.tenant_id)
    except VerificationNotFoundError as exc:
        raise _not_found(str(exc)) from exc
    except VerificationConflictError as exc:
        raise _conflict(str(exc)) from exc


@router.post(
    "/{verification_id}/run",
    response_model=Verification,
    summary="Run one bounded server-owned verification attempt",
)
async def run_verification(
    verification_id: UUID,
    service: VerificationDependency,
    principal: Annotated[Principal, Depends(get_principal)],
    security: Annotated[SecurityService, Depends(get_security_service)],
    request: VerificationRunRequest | None = None,
) -> Verification:
    try:
        _scope(service, verification_id, principal)
        effective_request = request or VerificationRunRequest(requested_by=principal.subject)
        _actor(
            security, principal, effective_request.requested_by, f"verification:{verification_id}"
        )
        return await service.run(verification_id, effective_request)
    except VerificationNotFoundError as exc:
        raise _not_found(str(exc)) from exc
    except VerificationConflictError as exc:
        raise _conflict(str(exc)) from exc


@router.post(
    "/{verification_id}/retry",
    response_model=Verification,
    summary="Run the next bounded verification attempt",
)
async def retry_verification(
    verification_id: UUID,
    service: VerificationDependency,
    principal: Annotated[Principal, Depends(get_principal)],
    security: Annotated[SecurityService, Depends(get_security_service)],
    request: VerificationRetryRequest | None = None,
) -> Verification:
    try:
        _scope(service, verification_id, principal)
        effective_request = request or VerificationRetryRequest(requested_by=principal.subject)
        _actor(
            security, principal, effective_request.requested_by, f"verification:{verification_id}"
        )
        return await service.retry(verification_id, effective_request)
    except VerificationNotFoundError as exc:
        raise _not_found(str(exc)) from exc
    except VerificationConflictError as exc:
        raise _conflict(str(exc)) from exc


@router.post(
    "/{verification_id}/cancel",
    response_model=Verification,
    summary="Cancel a not-yet-terminal verification safely",
)
def cancel_verification(
    verification_id: UUID,
    request: VerificationCancelRequest,
    service: VerificationDependency,
    principal: Annotated[Principal, Depends(get_principal)],
    security: Annotated[SecurityService, Depends(get_security_service)],
) -> Verification:
    try:
        _scope(service, verification_id, principal)
        _actor(security, principal, request.requested_by, f"verification:{verification_id}")
        return service.cancel(verification_id, request)
    except VerificationNotFoundError as exc:
        raise _not_found(str(exc)) from exc
    except VerificationConflictError as exc:
        raise _conflict(str(exc)) from exc


@router.get(
    "/{verification_id}/evidence",
    response_model=list[VerificationEvidence],
    summary="List provenance-aware evidence for a verification",
)
def verification_evidence(
    verification_id: UUID,
    service: VerificationDependency,
    principal: Annotated[Principal, Depends(get_principal)],
) -> list[VerificationEvidence]:
    try:
        return service.evidence(verification_id, tenant_id=principal.tenant_id)
    except VerificationNotFoundError as exc:
        raise _not_found(str(exc)) from exc
    except VerificationConflictError as exc:
        raise _conflict(str(exc)) from exc


@router.get(
    "/{verification_id}/timeline",
    response_model=list[VerificationTimelineEvent],
    summary="Get the append-only verification activity timeline",
)
def verification_timeline(
    verification_id: UUID,
    service: VerificationDependency,
    principal: Annotated[Principal, Depends(get_principal)],
) -> list[VerificationTimelineEvent]:
    try:
        return service.timeline(verification_id, tenant_id=principal.tenant_id)
    except VerificationNotFoundError as exc:
        raise _not_found(str(exc)) from exc
    except VerificationConflictError as exc:
        raise _conflict(str(exc)) from exc


__all__ = ["router"]
