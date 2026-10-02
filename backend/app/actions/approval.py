"""Phase 7 approval adapter built on the existing Phase 4 ApprovalRecord."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from threading import RLock
from uuid import UUID

from backend.app.actions.models import Action, ActionApproval, ActionApprovalState
from backend.app.agents.context import ApprovalRecord
from backend.app.models.domain import utc_now
from backend.app.models.enums import ApprovalStatus


class ApprovalService:
    """Reuse the Phase 4 approval record while binding it to a Phase 7 action."""

    def __init__(self, *, ttl_minutes: int = 30) -> None:
        self.ttl = timedelta(minutes=ttl_minutes)
        self._lock = RLock()
        self._approvals: dict[UUID, ApprovalRecord] = {}

    def request(self, action: Action) -> ApprovalRecord:
        with self._lock:
            approval = ApprovalRecord(
                incident_id=action.incident_id,
                action_id=action.action_id,
                requested_action=action.action_name,
                risk_level=action.risk_level,
                reason=action.planning_summary,
                expected_impact=action.expected_impact,
                rollback_plan=action.rollback_plan,
                expires_at=datetime.now(UTC) + self.ttl,
            )
            self._approvals[approval.approval_id] = approval
            return approval.model_copy(deep=True)

    def get(self, approval_id: UUID) -> ApprovalRecord | None:
        with self._lock:
            approval = self._approvals.get(approval_id)
            if approval is None:
                return None
            if approval.status is ApprovalStatus.PENDING and approval.expires_at <= datetime.now(
                UTC
            ):
                approval = approval.model_copy(update={"status": ApprovalStatus.EXPIRED})
                self._approvals[approval_id] = approval
            return approval.model_copy(deep=True)

    def save(self, approval: ApprovalRecord) -> ApprovalRecord:
        with self._lock:
            self._approvals[approval.approval_id] = approval.model_copy(deep=True)
            return approval.model_copy(deep=True)

    def approve(self, approval: ApprovalRecord, actor: str, reason: str | None) -> ApprovalRecord:
        if approval.status is not ApprovalStatus.PENDING:
            raise ValueError("Approval is no longer pending")
        if approval.expires_at <= datetime.now(UTC):
            expired = approval.model_copy(update={"status": ApprovalStatus.EXPIRED})
            self.save(expired)
            raise ValueError("Approval has expired")
        updated = approval.model_copy(
            update={
                "status": ApprovalStatus.APPROVED,
                "approved_by": actor,
                "approved_at": utc_now(),
                "decision_reason": reason,
            }
        )
        return self.save(updated)

    def reject(self, approval: ApprovalRecord, actor: str, reason: str | None) -> ApprovalRecord:
        if approval.status is not ApprovalStatus.PENDING:
            raise ValueError("Approval is no longer pending")
        updated = approval.model_copy(
            update={
                "status": ApprovalStatus.REJECTED,
                "rejected_by": actor,
                "rejected_at": utc_now(),
                "decision_reason": reason,
            }
        )
        return self.save(updated)

    def cancel(self, approval: ApprovalRecord, actor: str, reason: str | None) -> ApprovalRecord:
        if approval.status is not ApprovalStatus.PENDING:
            return approval
        updated = approval.model_copy(
            update={
                "status": ApprovalStatus.CANCELLED,
                "rejected_by": actor,
                "rejected_at": utc_now(),
                "decision_reason": reason,
            }
        )
        return self.save(updated)

    @staticmethod
    def view(approval: ApprovalRecord) -> ActionApproval:
        return ActionApproval(
            approval_id=approval.approval_id,
            incident_id=approval.incident_id,
            action_id=approval.action_id,
            status=ActionApprovalState(approval.status.value.upper()),
            risk_level=approval.risk_level,
            requested_action=approval.requested_action,
            requested_at=approval.requested_at,
            expires_at=approval.expires_at,
            approved_by=approval.approved_by,
            approved_at=approval.approved_at,
            decision_reason=approval.decision_reason,
        )


__all__ = ["ApprovalService"]
