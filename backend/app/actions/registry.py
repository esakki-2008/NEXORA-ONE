"""The only executable action registry for Phase 7.

The registry contains seven explicit public definitions. A caller can never
supply a callable, module name, shell command, or arbitrary handler key.
"""

from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable
from typing import Any

from pydantic import ValidationError

from backend.app.actions.models import (
    PUBLIC_ACTION_NAMES,
    ActionDefinition,
    ActionParameters,
    ConfigurationParameters,
    DeploymentParameters,
    FeatureFlagParameters,
    NoParameters,
    QueueParameters,
    ScaleServiceParameters,
)
from backend.app.models.enums import RiskLevel
from backend.app.simulator.runtime import ShopFlowSimulationRuntime


class ActionRegistryError(ValueError):
    """Base class for allow-list or parameter failures."""


class UnknownActionError(ActionRegistryError):
    """Raised when an action is not one of the seven registered names."""


class ActionParameterError(ActionRegistryError):
    """Raised when a dedicated action parameter model rejects input."""


ActionHandlerResult = tuple[dict[str, Any], list[dict[str, Any]]]
ActionHandler = Callable[
    [ShopFlowSimulationRuntime, str, ActionParameters, str],
    ActionHandlerResult | Awaitable[ActionHandlerResult],
]


def _run_named_action(
    runtime: ShopFlowSimulationRuntime,
    scenario_id: str,
    parameters: ActionParameters,
    idempotency_key: str,
    action_name: str,
) -> ActionHandlerResult:
    return runtime.execute_phase7_action(
        scenario_id=scenario_id,
        action_name=action_name,
        parameters=parameters.model_dump(mode="json"),
        idempotency_key=idempotency_key,
    )


def _handler(action_name: str) -> ActionHandler:
    """Bind a constant action name; no user input selects a runtime method."""

    def execute(
        runtime: ShopFlowSimulationRuntime,
        scenario_id: str,
        parameters: ActionParameters,
        idempotency_key: str,
    ) -> ActionHandlerResult:
        return _run_named_action(runtime, scenario_id, parameters, idempotency_key, action_name)

    return execute


_DEFINITIONS: tuple[ActionDefinition, ...] = (
    ActionDefinition(
        name="restart_payment_service",
        description="Restart the simulated ShopFlow payment service.",
        parameter_model=NoParameters,
        risk_level=RiskLevel.MEDIUM,
        allowed_domains=("IT", "REVENUE"),
        expected_impact="Restore simulated payment service health and reduce payment failures.",
        rollback_supported=True,
        verification_strategy="Verify Payment Service is healthy and payment metrics recover.",
        authorization_requirements=("human_operator", "incident_binding", "approved_fingerprint"),
        handler_name="restart_payment_service",
        rollback_action="restore_simulated_action_state",
        rollback_conditions=("verification_failed", "explicit_human_rollback"),
    ),
    ActionDefinition(
        name="rollback_simulated_deployment",
        description="Rollback one known simulated ShopFlow deployment.",
        parameter_model=DeploymentParameters,
        risk_level=RiskLevel.HIGH,
        allowed_domains=("IT",),
        expected_impact="Return a named simulated deployment to its previous state.",
        rollback_supported=True,
        verification_strategy="Verify the named simulated deployment and service state.",
        authorization_requirements=("human_operator", "incident_binding", "approved_fingerprint"),
        handler_name="rollback_simulated_deployment",
        rollback_action="restore_simulated_action_state",
        rollback_conditions=("verification_failed", "explicit_human_rollback"),
    ),
    ActionDefinition(
        name="restart_checkout_service",
        description="Restart the simulated ShopFlow checkout service.",
        parameter_model=NoParameters,
        risk_level=RiskLevel.MEDIUM,
        allowed_domains=("IT", "SUPPORT", "REVENUE"),
        expected_impact="Restore simulated checkout service health.",
        rollback_supported=True,
        verification_strategy=(
            "Verify Checkout Service is healthy and checkout error metrics recover."
        ),
        authorization_requirements=("human_operator", "incident_binding", "approved_fingerprint"),
        handler_name="restart_checkout_service",
        rollback_action="restore_simulated_action_state",
        rollback_conditions=("verification_failed", "explicit_human_rollback"),
    ),
    ActionDefinition(
        name="clear_simulated_queue",
        description="Clear one allow-listed simulated processing queue.",
        parameter_model=QueueParameters,
        risk_level=RiskLevel.HIGH,
        allowed_domains=("IT", "SUPPLY_CHAIN"),
        expected_impact="Remove queued synthetic work from the selected simulator queue.",
        rollback_supported=True,
        verification_strategy="Verify the selected simulated queue depth is zero.",
        authorization_requirements=("human_operator", "incident_binding", "approved_fingerprint"),
        handler_name="clear_simulated_queue",
        rollback_action="restore_simulated_action_state",
        rollback_conditions=("verification_failed", "explicit_human_rollback"),
    ),
    ActionDefinition(
        name="disable_simulated_feature_flag",
        description="Disable one allow-listed simulated feature flag.",
        parameter_model=FeatureFlagParameters,
        risk_level=RiskLevel.MEDIUM,
        allowed_domains=("IT", "REVENUE"),
        expected_impact="Disable the selected synthetic feature flag for controlled recovery.",
        rollback_supported=True,
        verification_strategy="Verify the selected simulated feature flag is disabled.",
        authorization_requirements=("human_operator", "incident_binding", "approved_fingerprint"),
        handler_name="disable_simulated_feature_flag",
        rollback_action="restore_simulated_action_state",
        rollback_conditions=("verification_failed", "explicit_human_rollback"),
    ),
    ActionDefinition(
        name="restore_simulated_configuration",
        description="Restore one synthetic configuration to its known-good value.",
        parameter_model=ConfigurationParameters,
        risk_level=RiskLevel.MEDIUM,
        allowed_domains=("IT", "CLOUD"),
        expected_impact="Restore a bounded simulated configuration without exposing secrets.",
        rollback_supported=True,
        verification_strategy=(
            "Verify the selected simulated configuration equals its known-good value."
        ),
        authorization_requirements=("human_operator", "incident_binding", "approved_fingerprint"),
        handler_name="restore_simulated_configuration",
        rollback_action="restore_simulated_action_state",
        rollback_conditions=("verification_failed", "explicit_human_rollback"),
    ),
    ActionDefinition(
        name="scale_simulated_service",
        description="Change the bounded capacity of one simulated service.",
        parameter_model=ScaleServiceParameters,
        risk_level=RiskLevel.HIGH,
        allowed_domains=("IT", "CLOUD"),
        expected_impact="Change only the in-memory capacity value for a simulated service.",
        rollback_supported=True,
        verification_strategy="Verify the simulated service capacity equals the requested value.",
        authorization_requirements=("human_operator", "incident_binding", "approved_fingerprint"),
        handler_name="scale_simulated_service",
        rollback_action="restore_simulated_action_state",
        rollback_conditions=("verification_failed", "explicit_human_rollback"),
    ),
)

_HANDLER_MAP: dict[str, ActionHandler] = {
    definition.name: _handler(definition.name) for definition in _DEFINITIONS
}


class ActionRegistry:
    """Immutable-by-convention public registry plus explicit simulator dispatch."""

    def __init__(self, runtime: ShopFlowSimulationRuntime) -> None:
        self.runtime = runtime
        self._definitions = {definition.name: definition for definition in _DEFINITIONS}
        if tuple(sorted(self._definitions)) != tuple(sorted(PUBLIC_ACTION_NAMES)):
            raise RuntimeError("Phase 7 action registry is incomplete")

    def get(self, action_name: str) -> ActionDefinition:
        if not isinstance(action_name, str):
            raise UnknownActionError("Action name must be a string")
        try:
            return self._definitions[action_name]
        except KeyError as exc:
            raise UnknownActionError(f"Action {action_name!r} is not allow-listed") from exc

    def resolve_name(self, action_name: str) -> str:
        """Accept only a deterministic spelling of a registered action."""

        if not isinstance(action_name, str):
            raise UnknownActionError("Action name must be a string")
        normalized = action_name.strip().lower().replace("-", "_").replace(" ", "_")
        self.get(normalized)
        return normalized

    def list_definitions(self) -> list[ActionDefinition]:
        return [self._definitions[name] for name in sorted(self._definitions)]

    def validate_parameters(
        self, action_name: str, parameters: dict[str, Any] | None
    ) -> tuple[ActionDefinition, ActionParameters]:
        definition = self.get(action_name)
        raw = parameters or {}
        if not isinstance(raw, dict):
            raise ActionParameterError("Action parameters must be an object")
        try:
            parsed = definition.parameter_model.model_validate(raw)
        except ValidationError as exc:
            raise ActionParameterError(
                f"Invalid parameters for {action_name}: {self._public_validation_error(exc)}"
            ) from exc
        return definition, parsed

    async def execute(
        self,
        action_name: str,
        *,
        scenario_id: str,
        parameters: ActionParameters,
        idempotency_key: str,
    ) -> ActionHandlerResult:
        definition = self.get(action_name)
        handler = _HANDLER_MAP[definition.name]
        result = handler(self.runtime, scenario_id, parameters, idempotency_key)
        if inspect.isawaitable(result):
            return await result
        return result

    def restore(
        self,
        *,
        action_name: str,
        scenario_id: str,
        parameters: ActionParameters,
        before_state: dict[str, Any],
        idempotency_key: str,
    ) -> ActionHandlerResult:
        """Dispatch the one fixed rollback primitive, never a caller-supplied action."""

        self.get(action_name)
        return self.runtime.restore_phase7_action(
            scenario_id=scenario_id,
            action_name=action_name,
            parameters=parameters.model_dump(mode="json"),
            before_state=before_state,
            idempotency_key=idempotency_key,
        )

    @staticmethod
    def _public_validation_error(error: ValidationError) -> str:
        first = error.errors()[0]
        location = ".".join(str(item) for item in first.get("loc", ())) or "parameters"
        return f"{location}: {first.get('msg', 'invalid value')}"


__all__ = [
    "ActionParameterError",
    "ActionRegistry",
    "ActionRegistryError",
    "UnknownActionError",
]
