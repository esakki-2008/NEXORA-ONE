"""Thread-safe in-memory persistence for Phase 4 orchestration records."""

from __future__ import annotations

from datetime import UTC, datetime
from threading import RLock
from typing import TypeVar
from uuid import UUID

from pydantic import BaseModel

from backend.app.agents.context import (
    ActionRecord,
    ApprovalRecord,
    OrchestrationContext,
    RemediationStep,
    VerificationRecord,
)
from backend.app.models.enums import ApprovalStatus


class OrchestrationNotFoundError(LookupError):
    """Raised when a context or approval is not present in the local store."""


StoreModelT = TypeVar("StoreModelT", bound=BaseModel)


class OrchestrationStore:
    """Reference persistence adapter; durable storage remains a later hardening task."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._contexts: dict[UUID, OrchestrationContext] = {}
        self._approvals: dict[UUID, ApprovalRecord] = {}

    @staticmethod
    def _copy(value: StoreModelT) -> StoreModelT:
        return value.model_copy(deep=True)

    def save_context(self, context: OrchestrationContext) -> OrchestrationContext:
        with self._lock:
            self._contexts[context.incident_id] = self._copy(context)
            if context.approval is not None:
                self._approvals[context.approval.approval_id] = self._copy(context.approval)
            return self._copy(context)

    def get_context(self, incident_id: UUID) -> OrchestrationContext | None:
        with self._lock:
            context = self._contexts.get(incident_id)
            return self._copy(context) if context is not None else None

    def require_context(self, incident_id: UUID) -> OrchestrationContext:
        context = self.get_context(incident_id)
        if context is None:
            raise OrchestrationNotFoundError(f"No orchestration context exists for {incident_id}")
        return context

    def list_contexts(self) -> list[OrchestrationContext]:
        with self._lock:
            values = sorted(self._contexts.values(), key=lambda item: item.updated_at, reverse=True)
            return [self._copy(value) for value in values]

    def get_approval(self, approval_id: UUID) -> ApprovalRecord | None:
        with self._lock:
            approval = self._approvals.get(approval_id)
            if approval is None:
                return None
            if approval.status is ApprovalStatus.PENDING and approval.expires_at <= datetime.now(
                UTC
            ):
                approval = approval.model_copy(update={"status": ApprovalStatus.EXPIRED})
                self._approvals[approval_id] = approval
                context = self._contexts.get(approval.incident_id)
                if context is not None and context.approval is not None:
                    self._contexts[approval.incident_id] = context.model_copy(
                        update={"approval": approval}, deep=True
                    )
            return self._copy(approval)

    def require_approval(self, approval_id: UUID) -> ApprovalRecord:
        approval = self.get_approval(approval_id)
        if approval is None:
            raise OrchestrationNotFoundError(f"Approval {approval_id} was not found")
        return approval

    def save_approval(self, approval: ApprovalRecord) -> ApprovalRecord:
        with self._lock:
            self._approvals[approval.approval_id] = self._copy(approval)
            context = self._contexts.get(approval.incident_id)
            if context is not None:
                self._contexts[approval.incident_id] = context.model_copy(
                    update={"approval": approval}, deep=True
                )
            return self._copy(approval)

    def list_approvals(self, status: ApprovalStatus | None = None) -> list[ApprovalRecord]:
        with self._lock:
            approval_ids = list(self._approvals)
            approvals = [
                approval
                for approval_id in approval_ids
                if (approval := self.get_approval(approval_id)) is not None
            ]
            if status is not None:
                approvals = [item for item in approvals if item.status is status]
            approvals.sort(key=lambda item: item.requested_at, reverse=True)
            return approvals

    def list_actions(self) -> list[ActionRecord]:
        actions: list[ActionRecord] = []
        for context in self.list_contexts():
            plan = context.remediation_plan
            if plan is None:
                continue
            approval = context.approval
            for step in plan.steps:
                if not step.is_change:
                    continue
                result = next(
                    (
                        item
                        for item in reversed(context.tool_results)
                        if item.tool_name == step.tool_name
                    ),
                    None,
                )
                if result is None:
                    continue
                actions.append(
                    ActionRecord(
                        execution_id=result.execution_id if result else None,
                        action_id=step.id,
                        incident_id=context.incident_id,
                        action=step.action,
                        risk_level=step.risk_level,
                        approval_status=approval.status if approval else None,
                        status=(result.status if result else step.status),
                        timestamp=result.timestamp if result else step_status_time(step, context),
                        approved_by=approval.approved_by if approval else None,
                        result=result.result if result else {},
                    )
                )
        return sorted(actions, key=lambda item: item.timestamp, reverse=True)

    def list_verifications(self) -> list[VerificationRecord]:
        records: list[VerificationRecord] = []
        for context in self.list_contexts():
            records.extend(context.verification_results)
        return sorted(records, key=lambda item: item.timestamp, reverse=True)


def step_status_time(step: RemediationStep, context: OrchestrationContext) -> datetime:
    """Use the context update time when a change has not executed yet."""

    return context.updated_at


__all__ = ["OrchestrationNotFoundError", "OrchestrationStore"]
