"""Independent validation and fingerprint utilities for action proposals."""

from __future__ import annotations

import hashlib
import json
from typing import Any
from uuid import UUID

from backend.app.actions.models import Action, ActionParameters
from backend.app.actions.registry import ActionParameterError, ActionRegistry


class ActionValidationError(ValueError):
    """Raised when a proposal or lifecycle transition is unsafe."""


def canonical_json(value: Any) -> str:
    """Serialize only JSON-compatible values deterministically."""

    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    except (TypeError, ValueError) as exc:
        raise ActionValidationError("Action data is not safely serializable") from exc


def action_fingerprint(
    *,
    incident_id: UUID,
    action_name: str,
    normalized_parameters: dict[str, Any],
    risk_level: str,
    expected_impact: str,
    rollback_plan: str,
) -> str:
    payload = {
        "incident_id": str(incident_id),
        "action_name": action_name,
        "normalized_parameters": normalized_parameters,
        "risk_level": risk_level,
        "expected_impact": expected_impact,
        "rollback_plan": rollback_plan,
    }
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def validate_action_parameters(
    registry: ActionRegistry, action_name: str, parameters: dict[str, Any]
) -> tuple[str, ActionParameters]:
    try:
        resolved = registry.resolve_name(action_name)
        _, parsed = registry.validate_parameters(resolved, parameters)
    except (ActionParameterError, ValueError) as exc:
        raise ActionValidationError(str(exc)) from exc
    return resolved, parsed


def validate_action_fingerprint(action: Action) -> None:
    expected = action_fingerprint(
        incident_id=action.incident_id,
        action_name=action.action_name,
        normalized_parameters=action.normalized_parameters,
        risk_level=action.risk_level.value,
        expected_impact=action.expected_impact,
        rollback_plan=action.rollback_plan,
    )
    if expected != action.action_fingerprint:
        raise ActionValidationError(
            "Action fingerprint no longer matches its approved immutable plan"
        )


def validate_incident_binding(action: Action, incident_id: UUID) -> None:
    if action.incident_id != incident_id:
        raise ActionValidationError("Action is bound to a different incident")


__all__ = [
    "ActionValidationError",
    "action_fingerprint",
    "canonical_json",
    "validate_action_fingerprint",
    "validate_action_parameters",
    "validate_incident_binding",
]
