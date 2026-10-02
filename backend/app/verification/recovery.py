"""Bounded, allow-listed recovery decisions for failed verification."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from backend.app.actions.models import Action
from backend.app.verification.models import VerificationCheckStatus, VerificationStatus


@dataclass(frozen=True, slots=True)
class RecoveryDecision:
    allowed: bool
    recommended: bool
    action_name: str | None
    reason: str
    requires_approval: bool
    next_step: str


class RecoveryPolicy:
    """Select only an existing Phase 7 action; never invent a command."""

    MAX_RECOVERY_ACTIONS = 1
    ALLOW_LIST = frozenset(
        {
            "restart_payment_service",
            "restart_checkout_service",
            "rollback_simulated_deployment",
            "clear_simulated_queue",
            "disable_simulated_feature_flag",
            "restore_simulated_configuration",
            "scale_simulated_service",
        }
    )

    def select(
        self,
        action: Action,
        status: VerificationStatus,
        failed_checks: Iterable[str],
    ) -> RecoveryDecision:
        failed = list(failed_checks)
        if status is VerificationStatus.PASSED:
            return RecoveryDecision(
                allowed=False,
                recommended=False,
                action_name=None,
                reason="No recovery is required after a passed verification.",
                requires_approval=False,
                next_step="Keep the passed verification as the resolution proof.",
            )
        if action.action_name not in self.ALLOW_LIST:
            return RecoveryDecision(
                allowed=False,
                recommended=False,
                action_name=None,
                reason="Recovery target is not present in the Phase 7 action registry.",
                requires_approval=True,
                next_step="Escalate to a human operator; no recovery action is permitted.",
            )

        recovery_action = action.action_name
        if action.action_name == "rollback_simulated_deployment":
            reason = "Deployment verification failed; review the registered rollback action."
        elif any("queue" in item.lower() for item in failed):
            reason = "Queue verification failed; review the registered queue remediation."
        elif any("configuration" in item.lower() for item in failed):
            reason = "Configuration verification failed; review the known-good restore action."
        else:
            reason = "Post-action verification did not prove the expected simulator state."
        return RecoveryDecision(
            allowed=True,
            recommended=True,
            action_name=recovery_action,
            reason=reason,
            requires_approval=True,
            next_step=(
                f"Request explicit human approval before running {recovery_action}; "
                "do not loop automatically."
            ),
        )


def check_has_failure(status: VerificationCheckStatus) -> bool:
    return status is not VerificationCheckStatus.PASSED


__all__ = ["RecoveryDecision", "RecoveryPolicy", "check_has_failure"]
