"""Central orchestrator, approvals, action, verification, and timeline routes."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from backend.app.agents.context import (
    ActionRecord,
    ApprovalDecisionRequest,
    ApprovalRecord,
    CancellationRequest,
    HypothesisRecord,
    OrchestrationActivity,
    OrchestrationContext,
    OrchestrationStartRequest,
    OrchestratorOverview,
    VerificationRecord,
)
from backend.app.agents.orchestrator import AgentOrchestrator, OrchestratorOperationError
from backend.app.agents.store import OrchestrationNotFoundError
from backend.app.api.dependencies import get_orchestrator
from backend.app.models.enums import ApprovalStatus
from backend.app.tools.contracts import ToolDefinition

router = APIRouter(prefix="/api/orchestrator", tags=["orchestrator"])
OrchestratorDependency = Annotated[AgentOrchestrator, Depends(get_orchestrator)]


def _not_found(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


def _conflict(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)


@router.get(
    "/overview",
    response_model=OrchestratorOverview,
    summary="Get Command Center orchestrator overview",
)
def overview(orchestrator: OrchestratorDependency) -> OrchestratorOverview:
    return orchestrator.overview()


@router.get(
    "/tools", response_model=list[ToolDefinition], summary="List controlled tool definitions"
)
def tools(orchestrator: OrchestratorDependency) -> list[ToolDefinition]:
    return orchestrator.tool_definitions()


@router.get("/agents", summary="List registered specialist modules")
def agents(orchestrator: OrchestratorDependency) -> list[dict[str, object]]:
    return [item.model_dump(mode="json") for item in orchestrator.overview().specialists]


@router.post(
    "/incidents/{incident_id}/start",
    response_model=OrchestrationContext,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Start or resume central incident orchestration",
)
async def start(
    incident_id: UUID,
    orchestrator: OrchestratorDependency,
    request: OrchestrationStartRequest | None = None,
) -> OrchestrationContext:
    try:
        return await orchestrator.start(
            incident_id,
            scenario_id=request.scenario_id if request else None,
            request_id=request.request_id if request else None,
        )
    except OrchestrationNotFoundError as exc:
        raise _not_found(str(exc)) from exc


@router.get(
    "/incidents/{incident_id}",
    response_model=OrchestrationContext,
    summary="Get the full orchestration context",
)
def context(incident_id: UUID, orchestrator: OrchestratorDependency) -> OrchestrationContext:
    try:
        return orchestrator.context(incident_id)
    except OrchestrationNotFoundError as exc:
        raise _not_found(str(exc)) from exc


@router.get(
    "/incidents/{incident_id}/activity",
    response_model=list[OrchestrationActivity],
    summary="Get auditable orchestrator activity",
)
def activity(
    incident_id: UUID, orchestrator: OrchestratorDependency
) -> list[OrchestrationActivity]:
    try:
        return orchestrator.activity(incident_id)
    except OrchestrationNotFoundError as exc:
        raise _not_found(str(exc)) from exc


@router.get(
    "/incidents/{incident_id}/hypotheses",
    response_model=list[HypothesisRecord],
    summary="Get structured hypotheses and lifecycle status",
)
def hypotheses(incident_id: UUID, orchestrator: OrchestratorDependency) -> list[HypothesisRecord]:
    try:
        return orchestrator.hypotheses(incident_id)
    except OrchestrationNotFoundError as exc:
        raise _not_found(str(exc)) from exc


@router.get("/approvals", response_model=list[ApprovalRecord], summary="List approval requests")
def approvals(
    orchestrator: OrchestratorDependency,
    approval_status: ApprovalStatus | None = Query(default=None, alias="status"),
) -> list[ApprovalRecord]:
    return orchestrator.approvals(approval_status)


@router.post(
    "/incidents/{incident_id}/cancel",
    response_model=OrchestrationContext,
    summary="Cancel active orchestration without executing a tool",
)
async def cancel(
    incident_id: UUID,
    request: CancellationRequest,
    orchestrator: OrchestratorDependency,
) -> OrchestrationContext:
    try:
        return await orchestrator.cancel(incident_id, request)
    except OrchestrationNotFoundError as exc:
        raise _not_found(str(exc)) from exc
    except OrchestratorOperationError as exc:
        raise _conflict(str(exc)) from exc


@router.post(
    "/approvals/{approval_id}/approve",
    response_model=OrchestrationContext,
    summary="Approve one pending action through the server policy gate",
)
async def approve(
    approval_id: UUID,
    request: ApprovalDecisionRequest,
    orchestrator: OrchestratorDependency,
) -> OrchestrationContext:
    try:
        return await orchestrator.approve(approval_id, request)
    except OrchestrationNotFoundError as exc:
        raise _not_found(str(exc)) from exc
    except OrchestratorOperationError as exc:
        raise _conflict(str(exc)) from exc


@router.post(
    "/approvals/{approval_id}/reject",
    response_model=OrchestrationContext,
    summary="Reject one pending action and escalate to a human",
)
async def reject(
    approval_id: UUID,
    request: ApprovalDecisionRequest,
    orchestrator: OrchestratorDependency,
) -> OrchestrationContext:
    try:
        return await orchestrator.reject(approval_id, request)
    except OrchestrationNotFoundError as exc:
        raise _not_found(str(exc)) from exc
    except OrchestratorOperationError as exc:
        raise _conflict(str(exc)) from exc


@router.get(
    "/actions", response_model=list[ActionRecord], summary="List controlled action executions"
)
def actions(orchestrator: OrchestratorDependency) -> list[ActionRecord]:
    return orchestrator.actions()


@router.get(
    "/verifications",
    response_model=list[VerificationRecord],
    summary="List post-action verification records",
)
def verifications(orchestrator: OrchestratorDependency) -> list[VerificationRecord]:
    return orchestrator.verifications()
