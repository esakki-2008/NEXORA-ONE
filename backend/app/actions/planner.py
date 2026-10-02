"""Deterministic action planning from existing investigation/orchestration context."""

from __future__ import annotations

from typing import Any

from backend.app.actions.models import ActionProposal
from backend.app.actions.registry import ActionRegistry, UnknownActionError
from backend.app.actions.validators import action_fingerprint
from backend.app.agents.context import OrchestrationContext
from backend.app.investigation.context import InvestigationContext
from backend.app.models.domain import Incident
from backend.app.simulator.runtime import SimulationUnavailableError


class ActionPlannerError(ValueError):
    """Raised when no safe registered action can be planned."""


class ActionPlanner:
    """Create reviewable proposals; this class never executes an action."""

    def __init__(self, registry: ActionRegistry) -> None:
        self.registry = registry

    def plan(
        self,
        incident: Incident,
        *,
        scenario_id: str | None = None,
        investigation: InvestigationContext | None = None,
        orchestration: OrchestrationContext | None = None,
        action_name: str | None = None,
        recommended_action: str | None = None,
        parameters: dict[str, Any] | None = None,
        root_cause_candidate: str | None = None,
        requested_by: str = "local-operator",
        idempotency_key: str | None = None,
    ) -> ActionProposal:
        effective_scenario: str | None = (
            scenario_id
            or (investigation.scenario_id if investigation is not None else None)
            or (orchestration.scenario_id if orchestration is not None else None)
        )
        candidate, inherited_parameters = self._candidate(
            incident,
            investigation=investigation,
            orchestration=orchestration,
            action_name=action_name,
            recommended_action=recommended_action,
        )
        resolved_name: str | None = None
        try:
            resolved_name = self.registry.resolve_name(candidate)
        except UnknownActionError:
            resolved_name = self._find_registered_name(candidate)
            if resolved_name is None:
                raise ActionPlannerError(
                    "Recommendation does not match a fixed allow-listed action"
                ) from None
        raw_parameters = parameters if parameters is not None else inherited_parameters
        raw_parameters = dict(raw_parameters or {})
        if not raw_parameters:
            raw_parameters = self._server_defaults(resolved_name, incident, effective_scenario)
        try:
            definition, parsed = self.registry.validate_parameters(resolved_name, raw_parameters)
        except ValueError as exc:
            raise ActionPlannerError(str(exc)) from exc
        normalized = parsed.model_dump(mode="json", exclude_none=True)
        if effective_scenario is None:
            raise ActionPlannerError(
                "A controlled simulated action requires an explicit ShopFlow scenario"
            )
        try:
            self.registry.runtime.state(effective_scenario)
        except SimulationUnavailableError as exc:
            raise ActionPlannerError(str(exc)) from exc
        evidence_ids = self._evidence_ids(investigation, orchestration)
        summary = root_cause_candidate or self._planning_summary(
            incident, investigation, orchestration
        )
        rollback_plan = (
            "Restore the exact before-state captured by the registered simulator handler; "
            "rollback remains controlled and may escalate to a human."
            if definition.rollback_supported
            else "No rollback is available for this registered action."
        )
        fingerprint = action_fingerprint(
            incident_id=incident.id,
            action_name=resolved_name,
            normalized_parameters=normalized,
            risk_level=definition.risk_level.value,
            expected_impact=definition.expected_impact,
            rollback_plan=rollback_plan,
        )
        return ActionProposal(
            incident_id=incident.id,
            action_name=resolved_name,
            normalized_parameters=normalized,
            risk_level=definition.risk_level,
            expected_impact=definition.expected_impact,
            rollback_plan=rollback_plan,
            rollback_supported=definition.rollback_supported,
            rollback_action=definition.rollback_action,
            rollback_parameters={},
            rollback_conditions=list(definition.rollback_conditions),
            verification_strategy=definition.verification_strategy,
            action_fingerprint=fingerprint,
            idempotency_key=idempotency_key or f"phase7:{incident.id}:{fingerprint}",
            requested_by=requested_by,
            scenario_id=effective_scenario,
            evidence_ids=evidence_ids,
            planning_summary=(
                f"{summary} Server selected {resolved_name}; risk and verification are "
                "calculated from the registered definition, not from AI or client claims."
            ),
        )

    def _candidate(
        self,
        incident: Incident,
        *,
        investigation: InvestigationContext | None,
        orchestration: OrchestrationContext | None,
        action_name: str | None,
        recommended_action: str | None,
    ) -> tuple[str, dict[str, Any]]:
        if action_name:
            return action_name, {}
        if recommended_action:
            return recommended_action, {}
        if orchestration is not None and orchestration.remediation_plan is not None:
            step = orchestration.remediation_plan.change_step
            if step is not None:
                candidate = str(step.parameters.get("action_name", step.action))
                return candidate, dict(step.parameters.get("parameters", {}))
        if investigation is not None and investigation.recommended_next_step:
            return investigation.recommended_next_step, {}
        service = incident.service.lower()
        if "payment" in service:
            return "restart_payment_service", {}
        if "checkout" in service:
            return "restart_checkout_service", {}
        if "deploy" in incident.title.lower():
            return "rollback_simulated_deployment", {}
        raise ActionPlannerError("No bounded remediation recommendation is available")

    def _find_registered_name(self, candidate: str) -> str | None:
        normalized = candidate.strip().lower().replace("-", "_").replace(" ", "_")
        matches = [name for name in self.registry_names if name in normalized]
        return sorted(matches, key=len, reverse=True)[0] if matches else None

    @property
    def registry_names(self) -> tuple[str, ...]:
        return tuple(item.name for item in self.registry.list_definitions())

    def _server_defaults(
        self, action_name: str, incident: Incident, scenario_id: str | None
    ) -> dict[str, Any]:
        if action_name == "clear_simulated_queue":
            return {
                "queue_name": "payment" if "payment" in incident.service.lower() else "checkout"
            }
        if action_name == "disable_simulated_feature_flag":
            return {
                "feature_name": "payment_retries"
                if "payment" in incident.service.lower()
                else "new_checkout"
            }
        if action_name == "scale_simulated_service":
            return {"service_name": incident.service, "desired_capacity": 4}
        if action_name == "restore_simulated_configuration":
            if scenario_id is None:
                raise ActionPlannerError("Configuration restoration requires a simulator scenario")
            state = self.registry.runtime.state(scenario_id)
            match = next(
                (
                    item
                    for item in state.configurations
                    if item.service == incident.service or item.service in incident.title
                ),
                None,
            )
            if match is None:
                raise ActionPlannerError(
                    "No known-good simulated configuration matches the incident"
                )
            return {"configuration_id": match.key}
        if action_name == "rollback_simulated_deployment":
            if scenario_id is None:
                raise ActionPlannerError("Deployment rollback requires a simulator scenario")
            deployments = self.registry.runtime.state(scenario_id).deployments
            deployment_match = next(
                (item for item in deployments if item.service == incident.service), None
            )
            if deployment_match is None:
                raise ActionPlannerError("No simulated deployment matches the incident")
            return {"deployment_id": str(deployment_match.id)}
        return {}

    @staticmethod
    def _evidence_ids(
        investigation: InvestigationContext | None,
        orchestration: OrchestrationContext | None,
    ) -> list[str]:
        if investigation is not None:
            return list(dict.fromkeys(item.evidence_id for item in investigation.evidence))[:100]
        if orchestration is not None:
            return list(dict.fromkeys(item.id for item in orchestration.evidence))[:100]
        return []

    @staticmethod
    def _planning_summary(
        incident: Incident,
        investigation: InvestigationContext | None,
        orchestration: OrchestrationContext | None,
    ) -> str:
        if orchestration is not None and orchestration.analysis_summary:
            return orchestration.analysis_summary
        if investigation is not None and investigation.recommended_next_step:
            return investigation.recommended_next_step
        return f"Bounded remediation proposal for incident {incident.id}."


__all__ = ["ActionPlanner", "ActionPlannerError"]
