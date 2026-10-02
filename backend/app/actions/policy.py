"""Server-owned action risk, authorization, and state policy."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from backend.app.actions.models import Action, ActionApprovalState, ActionStatus
from backend.app.models.enums import ApprovalStatus, RiskLevel


@dataclass(frozen=True, slots=True)
class ActionPolicyDecision:
    allowed: bool
    reason: str
    requires_approval: bool = True


class ActionPolicy:
    """Evaluate all privileged action conditions independently of client claims."""

    AUTHORIZED_HUMAN_ACTORS = frozenset(
        {
            "local-operator",
            "Local operator",
            "test-operator",
            "operator",
            "human-operator",
            "system-admin",
        }
    )
    AI_ACTORS = frozenset({"ai", "nemotron", "model", "assistant", "orchestrator-ai"})

    def authorize_actor(self, actor: str) -> ActionPolicyDecision:
        if actor in self.AI_ACTORS:
            return ActionPolicyDecision(False, "AI cannot approve or execute an action")
        if actor not in self.AUTHORIZED_HUMAN_ACTORS:
            return ActionPolicyDecision(False, "Actor is not authorized for controlled actions")
        return ActionPolicyDecision(True, "Actor is an authorized human operator")

    def evaluate_approval(
        self,
        action: Action,
        approval: Any,
        actor: str,
        *,
        fingerprint_valid: bool,
    ) -> ActionPolicyDecision:
        authorization = self.authorize_actor(actor)
        if not authorization.allowed:
            return authorization
        if not fingerprint_valid:
            return ActionPolicyDecision(False, "Action fingerprint integrity check failed")
        if approval is None:
            return ActionPolicyDecision(False, "Explicit approval is required")
        if getattr(approval, "incident_id", None) != action.incident_id:
            return ActionPolicyDecision(False, "Approval is bound to a different incident")
        if getattr(approval, "action_id", None) != action.action_id:
            return ActionPolicyDecision(False, "Approval is bound to a different action")
        if getattr(approval, "status", None) is not ApprovalStatus.PENDING:
            return ActionPolicyDecision(False, "Action approval is no longer pending")
        if approval.expires_at <= datetime.now(UTC):
            return ActionPolicyDecision(False, "Action approval has expired")
        if action.requested_by == actor:
            return ActionPolicyDecision(False, "The requester cannot approve the same action")
        return ActionPolicyDecision(True, "Approval may be recorded")

    def evaluate_execution(
        self,
        action: Action,
        approval: Any,
        actor: str,
        *,
        fingerprint_valid: bool,
        auto_execute: bool,
    ) -> ActionPolicyDecision:
        authorization = self.authorize_actor(actor)
        if not authorization.allowed:
            return authorization
        if not fingerprint_valid:
            return ActionPolicyDecision(False, "Action fingerprint integrity check failed")
        if action.status is not ActionStatus.APPROVED:
            return ActionPolicyDecision(
                False, "Action must be explicitly approved before execution"
            )
        if approval is None or getattr(approval, "status", None) is not ApprovalStatus.APPROVED:
            return ActionPolicyDecision(False, "Approval is not approved")
        if getattr(approval, "incident_id", None) != action.incident_id:
            return ActionPolicyDecision(False, "Approval is bound to a different incident")
        if getattr(approval, "action_id", None) != action.action_id:
            return ActionPolicyDecision(False, "Approval is bound to a different action")
        if approval.expires_at <= datetime.now(UTC):
            return ActionPolicyDecision(False, "Action approval has expired")
        if approval.approved_by == actor and actor == action.requested_by:
            return ActionPolicyDecision(False, "Requester cannot execute its own approval")
        if auto_execute and action.risk_level is RiskLevel.HIGH:
            return ActionPolicyDecision(False, "HIGH-risk actions cannot auto-execute")
        return ActionPolicyDecision(True, "Execution is allowed by server-side policy")

    @staticmethod
    def risk_requires_approval(risk_level: RiskLevel) -> bool:
        return risk_level is not RiskLevel.READ_ONLY

    @staticmethod
    def map_approval_status(status: ApprovalStatus) -> ActionApprovalState:
        return ActionApprovalState(status.value.upper())


__all__ = ["ActionPolicy", "ActionPolicyDecision"]
