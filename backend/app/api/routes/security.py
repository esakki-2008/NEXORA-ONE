"""Reference security session and administrator-only event APIs."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status

from backend.app.api.dependencies import get_principal, get_security_service
from backend.app.security.models import (
    Permission,
    Principal,
    SecurityEventList,
    SecurityEventType,
    SecuritySession,
)
from backend.app.security.security_events import SecurityEventIntegrityError
from backend.app.security.service import SecurityService

router = APIRouter(prefix="/api/security", tags=["security"])
SecurityDependency = Annotated[SecurityService, Depends(get_security_service)]
PrincipalDependency = Annotated[Principal, Depends(get_principal)]


@router.get("/session", response_model=SecuritySession, summary="Get the authenticated session")
def session(principal: PrincipalDependency, service: SecurityDependency) -> SecuritySession:
    return service.session(principal)


@router.get(
    "/events",
    response_model=SecurityEventList,
    summary="List tenant-scoped security events for administrators",
)
def security_events(
    request: Request,
    principal: PrincipalDependency,
    service: SecurityDependency,
) -> SecurityEventList:
    del request
    try:
        service.require_permission(principal, Permission.VIEW_SECURITY_EVENTS)
        service.events.require_integrity()
    except PermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied"
        ) from exc
    except SecurityEventIntegrityError as exc:
        service.record_event(
            SecurityEventType.TAMPERED_RECORD_DETECTED,
            actor=principal.subject,
            tenant_id=principal.tenant_id,
            resource="security-events",
            source="security.events",
            metadata={"reason": "hash_chain_invalid"},
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Security event integrity validation failed",
        ) from exc
    events = service.events.list(tenant_id=principal.tenant_id)
    return SecurityEventList(items=events, total=len(events))


@router.get("/config", summary="Inspect safe server security configuration")
def security_config(
    request: Request,
    principal: PrincipalDependency,
    service: SecurityDependency,
) -> dict[str, object]:
    try:
        service.require_permission(principal, Permission.MANAGE_SECURITY)
    except PermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied"
        ) from exc
    settings = request.app.state.settings
    return {
        "environment": settings.environment,
        "cors_origins": settings.cors_origin_list,
        "max_request_bytes": settings.security_max_request_bytes,
        "token_ttl_seconds": settings.security_token_ttl_seconds,
        "rate_limit_buckets": [name for name, _ in service.policy.sensitive_rules],
        "secrets_in_response": False,
    }


@router.get("/integrity", summary="Check the protected security event chain")
def security_integrity(
    principal: PrincipalDependency,
    service: SecurityDependency,
) -> dict[str, object]:
    try:
        service.require_permission(principal, Permission.VIEW_SECURITY_EVENTS)
        valid = service.events.verify()
    except PermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied"
        ) from exc
    return {"valid": valid, "scope": "security-events", "tenant_id": principal.tenant_id}


__all__ = ["router"]
