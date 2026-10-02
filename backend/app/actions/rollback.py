"""Explicit rollback policy for registered action before-state snapshots."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from backend.app.actions.models import Action, ActionStatus


@dataclass(frozen=True, slots=True)
class RollbackDecision:
    allowed: bool
    reason: str


class RollbackPolicy:
    """Rollback is possible only for a registered action with captured state."""

    def evaluate(self, action: Action) -> RollbackDecision:
        if action.status is ActionStatus.ROLLED_BACK:
            return RollbackDecision(False, "Action is already rolled back")
        if action.status not in {
            ActionStatus.COMPLETED,
            ActionStatus.FAILED,
            ActionStatus.REQUIRES_HUMAN,
        }:
            return RollbackDecision(False, "Action is not in a rollback-eligible state")
        if not action.rollback_supported:
            return RollbackDecision(False, "Action definition does not support rollback")
        if not action.execution_before_state:
            return RollbackDecision(False, "No before-state was captured for rollback")
        if action.rollback_action != "restore_simulated_action_state":
            return RollbackDecision(False, "Rollback target is not the registered restore handler")
        return RollbackDecision(True, "Registered rollback target and before-state are available")

    @staticmethod
    def metadata(action: Action) -> dict[str, Any]:
        return {
            "rollback_supported": action.rollback_supported,
            "rollback_action": action.rollback_action,
            "rollback_parameters": action.rollback_parameters,
            "rollback_conditions": action.rollback_conditions,
        }


__all__ = ["RollbackDecision", "RollbackPolicy"]
