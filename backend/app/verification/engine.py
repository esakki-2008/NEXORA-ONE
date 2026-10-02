"""Deterministic verification planning, collection, and comparison engine."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from backend.app.actions.models import Action
from backend.app.actions.registry import ActionRegistry
from backend.app.simulator.runtime import (
    ShopFlowSimulationRuntime,
    SimulationActionError,
    SimulationUnavailableError,
)
from backend.app.verification.checks import (
    SimulatorVerificationCollector,
)
from backend.app.verification.confidence import calculate_confidence
from backend.app.verification.models import (
    EvidenceTrust,
    VerificationCheck,
    VerificationCheckStatus,
    VerificationConfidenceFactors,
    VerificationEvidence,
    VerificationStatus,
    VerificationStrategy,
)


class VerificationEngineError(RuntimeError):
    """Raised when server-owned verification planning cannot be built."""


@dataclass(frozen=True, slots=True)
class VerificationAttempt:
    status: VerificationStatus
    actual_state: dict[str, Any]
    checks: tuple[VerificationCheck, ...]
    evidence: tuple[VerificationEvidence, ...]
    confidence: float
    confidence_factors: VerificationConfidenceFactors
    failure_reason: str | None
    failed_checks: tuple[str, ...]
    contradictory_evidence: bool
    missing_evidence: bool


class VerificationEngine:
    """Build expected state and compare it with current simulator observations."""

    def __init__(
        self,
        registry: ActionRegistry,
        runtime: ShopFlowSimulationRuntime,
        *,
        tool_runtime: Any = None,
        collector: SimulatorVerificationCollector | None = None,
        max_evidence_age_seconds: int = 300,
    ) -> None:
        self.registry = registry
        self.runtime = runtime
        self.max_evidence_age_seconds = max_evidence_age_seconds
        self.collector = collector or SimulatorVerificationCollector(runtime, tool_runtime)

    def expected_state(self, action: Action) -> dict[str, Any]:
        """Calculate expected state exclusively from the registry and simulator."""

        if action.scenario_id is None:
            raise VerificationEngineError("Action is not bound to a ShopFlow scenario")
        definition = self.registry.get(action.action_name)
        parameters = dict(action.normalized_parameters)
        checks: list[dict[str, Any]] = []
        target: dict[str, Any] = dict(action.execution_result.get("verification_target", {}))

        if action.action_name == "restart_payment_service":
            service = "Payment Service"
            checks.extend(
                [
                    self._spec(
                        VerificationStrategy.SERVICE_HEALTH,
                        "payment_service_health",
                        "healthy",
                        {"service": service},
                    ),
                    self._spec(
                        VerificationStrategy.ERROR_RATE,
                        "payment_error_rate",
                        {"threshold": 0.05},
                        {
                            "service": service,
                            "metric_names": ["payment.failure_rate"],
                            "threshold": 0.05,
                        },
                    ),
                    self._spec(
                        VerificationStrategy.TRANSACTION_SUCCESS,
                        "recent_payment_transaction_success",
                        {"minimum": 1},
                        {"service": service},
                    ),
                ]
            )
            target = target or {"service": service, "status": "healthy"}
        elif action.action_name == "restart_checkout_service":
            service = "Checkout Service"
            checks.append(
                self._spec(
                    VerificationStrategy.SERVICE_HEALTH,
                    "checkout_service_health",
                    "healthy",
                    {"service": service},
                )
            )
            if self._has_error_metric(action, service):
                checks.append(
                    self._spec(
                        VerificationStrategy.ERROR_RATE,
                        "checkout_error_rate",
                        {"threshold": 0.05},
                        {
                            "service": service,
                            "metric_names": ["checkout.error_rate", "checkout.timeout_rate"],
                            "threshold": 0.05,
                        },
                    )
                )
            checks.append(
                self._spec(
                    VerificationStrategy.LATENCY,
                    "checkout_p95_latency",
                    {"threshold_ms": 1_000},
                    {"service": service, "threshold_ms": 1_000},
                )
            )
            target = target or {"service": service, "status": "healthy"}
        elif action.action_name == "rollback_simulated_deployment":
            deployment = self._deployment(action)
            service = deployment.service
            checks.extend(
                [
                    self._spec(
                        VerificationStrategy.DEPLOYMENT_STATE,
                        "deployment_state",
                        {"deployment_id": str(deployment.id), "status": "rolled_back"},
                        {"deployment_id": str(deployment.id)},
                    ),
                    self._spec(
                        VerificationStrategy.SERVICE_HEALTH,
                        "rolled_back_service_health",
                        "healthy",
                        {"service": service},
                    ),
                ]
            )
            if self._has_error_metric(action, service):
                checks.append(
                    self._spec(
                        VerificationStrategy.ERROR_RATE,
                        "rolled_back_service_error_rate",
                        {"threshold": 0.05},
                        {"service": service, "threshold": 0.05},
                    )
                )
            target = target or {"deployment_id": str(deployment.id), "status": "rolled_back"}
        elif action.action_name == "clear_simulated_queue":
            queue_name = str(parameters["queue_name"])
            checks.append(
                self._spec(
                    VerificationStrategy.QUEUE_STATE,
                    "queue_depth",
                    {"queue_name": queue_name, "depth": 0},
                    {"queue_name": queue_name},
                )
            )
            target = target or {"queue_name": queue_name, "depth": 0}
        elif action.action_name == "disable_simulated_feature_flag":
            feature_name = str(parameters["feature_name"])
            checks.append(
                self._spec(
                    VerificationStrategy.FEATURE_FLAG_STATE,
                    "feature_flag_state",
                    {"feature_name": feature_name, "enabled": False},
                    {"feature_name": feature_name},
                )
            )
            target = target or {"feature_name": feature_name, "enabled": False}
        elif action.action_name == "restore_simulated_configuration":
            configuration = self._configuration(action)
            checks.append(
                self._spec(
                    VerificationStrategy.CONFIGURATION_STATE,
                    "configuration_state",
                    {"configuration_id": configuration.key, "value": configuration.expected_value},
                    {"configuration_id": configuration.key},
                )
            )
            target = target or {
                "configuration_id": configuration.key,
                "value": configuration.expected_value,
            }
        elif action.action_name == "scale_simulated_service":
            service_name = str(parameters["service_name"])
            desired_capacity = int(parameters["desired_capacity"])
            checks.extend(
                [
                    self._spec(
                        VerificationStrategy.CAPACITY_STATE,
                        "service_capacity",
                        {"service_name": service_name, "capacity": desired_capacity},
                        {"service_name": service_name},
                    ),
                    self._spec(
                        VerificationStrategy.SERVICE_HEALTH,
                        "scaled_service_health",
                        "healthy",
                        {"service": service_name},
                    ),
                ]
            )
            target = target or {
                "service_name": service_name,
                "desired_capacity": desired_capacity,
            }
        else:
            raise VerificationEngineError(
                f"No verification policy is registered for {definition.name!r}"
            )
        return {
            "boundary": "SIMULATED / CONTROLLED DEMONSTRATION",
            "scenario_id": action.scenario_id,
            "action_name": action.action_name,
            "parameters": parameters,
            "checks": checks,
            "verification_target": target,
            "strategy_description": definition.verification_strategy,
        }

    async def evaluate(
        self,
        action: Action,
        *,
        verification_id: UUID,
        expected_state: dict[str, Any],
        attempt: int,
    ) -> VerificationAttempt:
        collection = await self.collector.collect(action, expected_state)
        checks: list[VerificationCheck] = []
        evidence: list[VerificationEvidence] = []
        for index, item in enumerate(collection.checks):
            evidence_id = f"verification:{verification_id}:attempt:{attempt}:check:{index}"
            checks.append(
                VerificationCheck(
                    strategy=item.strategy,
                    name=item.name,
                    status=item.status,
                    required=True,
                    expected_value=item.expected_value,
                    actual_value=item.actual_value,
                    comparison=item.comparison,
                    evidence_ids=[evidence_id],
                    trust=item.trust,
                    observed_at=item.observed_at,
                    failure_reason=item.failure_reason,
                )
            )
            evidence.append(
                VerificationEvidence(
                    evidence_id=evidence_id,
                    tenant_id=action.tenant_id,
                    verification_id=verification_id,
                    incident_id=action.incident_id,
                    action_id=action.action_id,
                    source=(f"ShopFlow simulator / {item.strategy.value.lower()}"),
                    timestamp=item.observed_at or datetime.now(UTC),
                    collector=SimulatorVerificationCollector.collector_name,
                    value=item.actual_value,
                    expected_value=item.expected_value,
                    actual_value=item.actual_value,
                    comparison=item.comparison,
                    result=item.status,
                    provenance={
                        "scenario_id": action.scenario_id or "",
                        "action_id": str(action.action_id),
                        "incident_id": str(action.incident_id),
                        "attempt": str(attempt),
                        "boundary": "SIMULATED / CONTROLLED DEMONSTRATION",
                    },
                    trust=item.trust,
                    simulated=True,
                    controlled_demonstration=True,
                )
            )

        for index, raw in enumerate(collection.collector_evidence):
            evidence_id = f"verification:{verification_id}:attempt:{attempt}:collector:{index}"
            raw_result = str(raw.get("result", "UNAVAILABLE"))
            result = (
                VerificationCheckStatus.PASSED
                if raw_result == "PASSED"
                else VerificationCheckStatus.FAILED
                if raw_result == "FAILED"
                else VerificationCheckStatus.UNAVAILABLE
            )
            evidence_trust = (
                EvidenceTrust.UNAVAILABLE
                if result is VerificationCheckStatus.UNAVAILABLE
                else EvidenceTrust.SIMULATED
            )
            evidence.append(
                VerificationEvidence(
                    evidence_id=evidence_id,
                    tenant_id=action.tenant_id,
                    verification_id=verification_id,
                    incident_id=action.incident_id,
                    action_id=action.action_id,
                    source=str(raw.get("source", "read-only simulator")),
                    timestamp=(
                        raw_timestamp
                        if isinstance((raw_timestamp := raw.get("timestamp")), datetime)
                        else datetime.now(UTC)
                    ),
                    collector=SimulatorVerificationCollector.collector_name,
                    value=raw.get("value"),
                    expected_value=expected_state.get("checks", []),
                    actual_value=raw.get("value"),
                    comparison="AGGREGATE_READ_ONLY_BOUNDARY",
                    result=result,
                    provenance={
                        "scenario_id": action.scenario_id or "",
                        "action_id": str(action.action_id),
                        "incident_id": str(action.incident_id),
                        "attempt": str(attempt),
                        "boundary": "SIMULATED / CONTROLLED DEMONSTRATION",
                    },
                    trust=evidence_trust,
                    simulated=True,
                    controlled_demonstration=True,
                )
            )

        required = [item for item in checks if item.required]
        failed = [item for item in required if item.status is VerificationCheckStatus.FAILED]
        unavailable = [
            item for item in required if item.status is VerificationCheckStatus.UNAVAILABLE
        ]
        passed = [item for item in required if item.status is VerificationCheckStatus.PASSED]
        contradictory = bool(passed and (failed or unavailable))
        now = datetime.now(UTC)
        stale = any(
            item.observed_at is not None
            and (
                now
                - (
                    item.observed_at
                    if item.observed_at.tzinfo
                    else item.observed_at.replace(tzinfo=UTC)
                )
            ).total_seconds()
            > self.max_evidence_age_seconds
            for item in required
        )
        missing = not required or bool(unavailable) or stale
        if stale:
            status = VerificationStatus.INCONCLUSIVE
        elif not collection.aggregate_verified or unavailable:
            status = (
                VerificationStatus.INCONCLUSIVE
                if contradictory or unavailable
                else VerificationStatus.FAILED
            )
        elif failed:
            status = VerificationStatus.INCONCLUSIVE if contradictory else VerificationStatus.FAILED
        else:
            status = VerificationStatus.PASSED
        confidence, factors = calculate_confidence(
            checks, max_age_seconds=self.max_evidence_age_seconds
        )
        failure_reason = None
        if status is not VerificationStatus.PASSED:
            names = ", ".join(
                item.name for item in required if item.status is not VerificationCheckStatus.PASSED
            )
            reason = (
                "required evidence is stale"
                if stale
                else "failed or unavailable checks: " + (names or "none recorded")
            )
            failure_reason = f"Verification did not prove the expected state; {reason}."
        return VerificationAttempt(
            status=status,
            actual_state=collection.actual_state,
            checks=tuple(checks),
            evidence=tuple(evidence),
            confidence=confidence,
            confidence_factors=factors,
            failure_reason=failure_reason,
            failed_checks=tuple(
                item.name for item in required if item.status is not VerificationCheckStatus.PASSED
            ),
            contradictory_evidence=contradictory,
            missing_evidence=missing,
        )

    @staticmethod
    def _spec(
        strategy: VerificationStrategy,
        name: str,
        expected: Any,
        parameters: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "strategy": strategy.value,
            "name": name,
            "expected": expected,
            "parameters": parameters,
        }

    def _has_error_metric(self, action: Action, service: str) -> bool:
        """Only require an error-rate check when the bound read-only state exposes one."""
        if action.scenario_id is None:
            return False
        try:
            metrics = self.runtime.state(action.scenario_id).metrics
        except (KeyError, SimulationActionError, SimulationUnavailableError):
            return False
        return any(
            metric.service == service
            and any(token in metric.name.lower() for token in ("error", "failure", "timeout"))
            for metric in metrics
        )

    def _deployment(self, action: Action) -> Any:
        if action.scenario_id is None:
            raise VerificationEngineError("Deployment verification requires a simulator scenario")
        deployment_id = str(action.normalized_parameters["deployment_id"])
        for item in self.runtime.state(action.scenario_id).deployments:
            if str(item.id) == deployment_id:
                return item
        raise VerificationEngineError("Named simulated deployment is unavailable")

    def _configuration(self, action: Action) -> Any:
        if action.scenario_id is None:
            raise VerificationEngineError(
                "Configuration verification requires a simulator scenario"
            )
        key = str(action.normalized_parameters["configuration_id"])
        for item in self.runtime.state(action.scenario_id).configurations:
            if item.key == key:
                return item
        raise VerificationEngineError("Named simulated configuration is unavailable")


__all__ = ["VerificationAttempt", "VerificationEngine", "VerificationEngineError"]
