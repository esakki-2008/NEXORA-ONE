"""Phase 7 controlled autonomous action APIs."""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from backend.app.actions.audit import AuditEvent
from backend.app.actions.models import (
    Action,
    ActionCancelRequest,
    ActionCreateRequest,
    ActionDecisionRequest,
    ActionRejectRequest,
    ActionStatus,
    ActionVerificationRecord,
)
from backend.app.actions.planner import ActionPlannerError
from backend.app.actions.service import ActionConflictError, ActionNotFoundError, ActionService
from backend.app.api.dependencies import get_action_service

router = APIRouter(prefix="/api/actions", tags=["actions"])
ActionDependency = Annotated[ActionService, Depends(get_action_service)]


def _not_found(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


def _conflict(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)


@router.get("/registry", response_model=list[dict[str, Any]], summary="List allow-listed actions")
def registry(service: ActionDependency) -> list[dict[str, Any]]:
    return service.definitions()


@router.get("", response_model=list[Action], summary="List controlled actions")
def list_actions(
    service: ActionDependency,
    action_status: ActionStatus | None = Query(default=None, alias="status"),
) -> list[Action]:
    return service.list_actions(action_status)


@router.post(
    "",
    response_model=Action,
    status_code=status.HTTP_201_CREATED,
    summary="Create a server-validated action proposal",
)
def create_action(request: ActionCreateRequest, service: ActionDependency) -> Action:
    try:
        return service.create(request)
    except ActionNotFoundError as exc:
        raise _not_found(str(exc)) from exc
    except ActionConflictError as exc:
        raise _conflict(str(exc)) from exc
    except ActionPlannerError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc


@router.get("/{action_id}", response_model=Action, summary="Get one controlled action")
def get_action(action_id: UUID, service: ActionDependency) -> Action:
    try:
        return service.get(action_id)
    except ActionNotFoundError as exc:
        raise _not_found(str(exc)) from exc
    except ActionConflictError as exc:
        raise _conflict(str(exc)) from exc


@router.post(
    "/{action_id}/approve",
    response_model=Action,
    summary="Approve one exact action fingerprint",
)
def approve_action(
    action_id: UUID, request: ActionDecisionRequest, service: ActionDependency
) -> Action:
    try:
        return service.approve(action_id, request)
    except ActionNotFoundError as exc:
        raise _not_found(str(exc)) from exc
    except ActionConflictError as exc:
        raise _conflict(str(exc)) from exc


@router.post(
    "/{action_id}/reject",
    response_model=Action,
    summary="Reject an action and escalate safely",
)
def reject_action(
    action_id: UUID, request: ActionRejectRequest, service: ActionDependency
) -> Action:
    try:
        return service.reject(action_id, request)
    except ActionNotFoundError as exc:
        raise _not_found(str(exc)) from exc
    except ActionConflictError as exc:
        raise _conflict(str(exc)) from exc


@router.post(
    "/{action_id}/execute",
    response_model=Action,
    summary="Execute an approved registered simulator action",
)
async def execute_action(
    action_id: UUID, request: ActionDecisionRequest, service: ActionDependency
) -> Action:
    try:
        return await service.execute(action_id, request)
    except ActionNotFoundError as exc:
        raise _not_found(str(exc)) from exc
    except ActionConflictError as exc:
        raise _conflict(str(exc)) from exc


@router.post(
    "/{action_id}/cancel",
    response_model=Action,
    summary="Cancel an action before execution",
)
def cancel_action(
    action_id: UUID, request: ActionCancelRequest, service: ActionDependency
) -> Action:
    try:
        return service.cancel(action_id, request)
    except ActionNotFoundError as exc:
        raise _not_found(str(exc)) from exc
    except ActionConflictError as exc:
        raise _conflict(str(exc)) from exc


@router.post(
    "/{action_id}/rollback",
    response_model=Action,
    summary="Rollback a registered action using captured simulator state",
)
def rollback_action(
    action_id: UUID, request: ActionDecisionRequest, service: ActionDependency
) -> Action:
    try:
        return service.rollback(action_id, request)
    except ActionNotFoundError as exc:
        raise _not_found(str(exc)) from exc
    except ActionConflictError as exc:
        raise _conflict(str(exc)) from exc


@router.get(
    "/{action_id}/audit",
    response_model=list[AuditEvent],
    summary="Get the append-only action audit trail",
)
def action_audit(action_id: UUID, service: ActionDependency) -> list[AuditEvent]:
    try:
        return service.audit(action_id)
    except ActionNotFoundError as exc:
        raise _not_found(str(exc)) from exc
    except ActionConflictError as exc:
        raise _conflict(str(exc)) from exc


@router.get(
    "/{action_id}/verification",
    response_model=ActionVerificationRecord,
    summary="Get action verification state and evidence",
)
def action_verification(action_id: UUID, service: ActionDependency) -> ActionVerificationRecord:
    try:
        return service.verification(action_id)
    except ActionNotFoundError as exc:
        raise _not_found(str(exc)) from exc
    except ActionConflictError as exc:
        raise _conflict(str(exc)) from exc


__all__ = ["router"]
