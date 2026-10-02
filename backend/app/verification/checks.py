"""Read-only verification collectors for the deterministic ShopFlow simulator."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from backend.app.actions.models import Action
from backend.app.simulator.models import ShopFlowState
from backend.app.simulator.runtime import ShopFlowSimulationRuntime
from backend.app.verification.models import (
    EvidenceTrust,
    VerificationCheckStatus,
    VerificationStrategy,
)


class VerificationCollectionError(RuntimeError):
    """Raised when a bounded read-only verification source is unavailable."""


@dataclass(frozen=True, slots=True)
class CollectedCheck:
    strategy: VerificationStrategy
    name: str
    expected_value: Any
    actual_value: Any
    status: VerificationCheckStatus
    comparison: str
    observed_at: datetime | None
    trust: EvidenceTrust
    failure_reason: str | None = None


@dataclass(frozen=True, slots=True)
class CollectionResult:
    actual_state: dict[str, Any]
    checks: tuple[CollectedCheck, ...]
    aggregate_verified: bool
    collector_evidence: tuple[dict[str, Any], ...]


class SimulatorVerificationCollector:
    """Collect only fixed, read-only values from an existing simulator boundary."""

    collector_name = "phase8.verification.read_only_simulator_boundary"

    def __init__(self, runtime: ShopFlowSimulationRuntime, tool_runtime: Any = None) -> None:
        self.runtime = runtime
        self.tool_runtime = tool_runtime

    async def collect(self, action: Action, expected_state: dict[str, Any]) -> CollectionResult:
        if action.scenario_id is None:
            raise VerificationCollectionError("Verification requires an explicit ShopFlow scenario")
        state = self.runtime.state(action.scenario_id)
        check_specs = expected_state.get("checks", [])
        if not isinstance(check_specs, list) or not check_specs:
            raise VerificationCollectionError(
                "Server-generated verification checks are unavailable"
            )

        aggregate_verified = True
        collector_evidence: list[dict[str, Any]] = []
        try:
            aggregate = self.runtime.verify_phase7_action(
                scenario_id=action.scenario_id,
                action_name=action.action_name,
                parameters=dict(action.normalized_parameters),
                verification_target=dict(expected_state.get("verification_target", {})),
            )
            aggregate_verified = bool(aggregate.get("verified"))
            collector_evidence.append(
                {
                    "source": "ShopFlow simulator / existing read-only verification boundary",
                    "value": aggregate.get("checks", {}),
                    "result": "PASSED" if aggregate_verified else "FAILED",
                    "timestamp": datetime.now(UTC),
                }
            )
        except Exception as exc:
            aggregate_verified = False
            collector_evidence.append(
                {
                    "source": "ShopFlow simulator / existing read-only verification boundary",
                    "value": {},
                    "result": "UNAVAILABLE",
                    "timestamp": datetime.now(UTC),
                    "failure_reason": str(exc)[:300],
                }
            )

        # The existing allow-listed read-only tool layer remains part of the
        # collection path where a service target exists.  Its output is
        # supplementary; it can never override the server-owned comparisons.
        service = self._service_target(expected_state)
        if self.tool_runtime is not None and service:
            tool_result = await self.tool_runtime.execute(
                "verify_resolution",
                {"service": service, "checks": ["service_health"]},
                scenario_id=action.scenario_id,
                idempotency_key=f"verification:read:{action.action_id}",
                tenant_id=action.tenant_id,
            )
            if getattr(tool_result.status, "value", "") == "SUCCESS":
                collector_evidence.append(
                    {
                        "source": "NEXORA allow-listed read-only tool layer",
                        "value": tool_result.result,
                        "result": "PASSED",
                        "timestamp": tool_result.timestamp,
                    }
                )

        checks = [self._collect_one(state, spec, action) for spec in check_specs]
        if not aggregate_verified:
            # Preserve the existing Phase 7 verification boundary as a safety
            # guard.  A patched, contradictory, or unavailable aggregate check
            # must not be hidden by a locally optimistic field comparison.
            for index, item in enumerate(checks):
                if item.status is VerificationCheckStatus.PASSED:
                    checks[index] = CollectedCheck(
                        strategy=item.strategy,
                        name=item.name,
                        expected_value=item.expected_value,
                        actual_value=item.actual_value,
                        status=VerificationCheckStatus.FAILED,
                        comparison=item.comparison,
                        observed_at=item.observed_at,
                        trust=item.trust,
                        failure_reason=(
                            "Existing read-only simulator verification did not prove the "
                            "aggregate expected state."
                        ),
                    )
                    break
        actual_state = {
            "observed_at": datetime.now(UTC).isoformat(),
            "scenario_id": action.scenario_id,
            "action_name": action.action_name,
            "checks": {
                item.name: {
                    "expected": item.expected_value,
                    "actual": item.actual_value,
                    "status": item.status.value,
                }
                for item in checks
            },
        }
        return CollectionResult(
            actual_state=actual_state,
            checks=tuple(checks),
            aggregate_verified=aggregate_verified,
            collector_evidence=tuple(collector_evidence),
        )

    def _collect_one(self, state: ShopFlowState, spec: Any, action: Action) -> CollectedCheck:
        if not isinstance(spec, dict):
            return CollectedCheck(
                strategy=VerificationStrategy.SERVICE_HEALTH,
                name="invalid_check_specification",
                expected_value=None,
                actual_value=None,
                status=VerificationCheckStatus.UNAVAILABLE,
                comparison="SERVER_SPECIFICATION_REQUIRED",
                observed_at=None,
                trust=EvidenceTrust.UNAVAILABLE,
                failure_reason="Server verification specification is malformed.",
            )
        try:
            strategy = VerificationStrategy(str(spec["strategy"]))
        except (KeyError, ValueError):
            return CollectedCheck(
                strategy=VerificationStrategy.SERVICE_HEALTH,
                name=str(spec.get("name", "unknown_check")),
                expected_value=spec.get("expected"),
                actual_value=None,
                status=VerificationCheckStatus.UNAVAILABLE,
                comparison="UNKNOWN_STRATEGY",
                observed_at=None,
                trust=EvidenceTrust.UNAVAILABLE,
                failure_reason="Verification strategy is not registered.",
            )
        name = str(spec.get("name", strategy.value))
        expected = spec.get("expected")
        observed_at = datetime.now(UTC)
        try:
            actual, comparison, passed = self._read_value(
                state, action, strategy, dict(spec.get("parameters", {})), expected
            )
        except (KeyError, TypeError, ValueError, VerificationCollectionError) as exc:
            return CollectedCheck(
                strategy=strategy,
                name=name,
                expected_value=expected,
                actual_value=None,
                status=VerificationCheckStatus.UNAVAILABLE,
                comparison="READ_UNAVAILABLE",
                observed_at=None,
                trust=EvidenceTrust.UNAVAILABLE,
                failure_reason=str(exc)[:500],
            )
        return CollectedCheck(
            strategy=strategy,
            name=name,
            expected_value=expected,
            actual_value=actual,
            status=(VerificationCheckStatus.PASSED if passed else VerificationCheckStatus.FAILED),
            comparison=comparison,
            observed_at=observed_at,
            trust=EvidenceTrust.SIMULATED,
            failure_reason=None if passed else f"Expected {expected!r}; observed {actual!r}.",
        )

    @staticmethod
    def _service_target(expected_state: dict[str, Any]) -> str | None:
        for spec in expected_state.get("checks", []):
            if isinstance(spec, dict):
                parameters = spec.get("parameters", {})
                if isinstance(parameters, dict) and isinstance(parameters.get("service"), str):
                    return str(parameters["service"])
        return None

    @staticmethod
    def _read_value(
        state: ShopFlowState,
        action: Action,
        strategy: VerificationStrategy,
        parameters: dict[str, Any],
        expected: Any,
    ) -> tuple[Any, str, bool]:
        actual: Any
        if strategy is VerificationStrategy.SERVICE_HEALTH:
            service = str(parameters["service"])
            current = next((item for item in state.services if item.name == service), None)
            if current is None:
                raise VerificationCollectionError(f"Service {service!r} is unavailable")
            actual = current.status
            return actual, "EQUALS", actual == expected
        if strategy is VerificationStrategy.ERROR_RATE:
            service = str(parameters["service"])
            metric_names = parameters.get("metric_names", [])
            metrics = [
                item
                for item in state.metrics
                if item.service == service
                and (not metric_names or item.name in set(metric_names))
                and any(token in item.name for token in ("error", "failure", "timeout"))
            ]
            if not metrics:
                raise VerificationCollectionError(
                    f"No error-rate metric is available for {service!r}"
                )
            actual = {item.name: item.value for item in metrics}
            threshold = float(parameters.get("threshold", 0.05))
            return (
                actual,
                f"ALL_LESS_THAN {threshold:g}",
                all(item.value < threshold for item in metrics),
            )
        if strategy is VerificationStrategy.LATENCY:
            service = str(parameters["service"])
            metrics = [
                item
                for item in state.metrics
                if item.service == service and ("p95" in item.name or "latency" in item.name)
            ]
            if not metrics:
                raise VerificationCollectionError(f"No latency metric is available for {service!r}")
            actual = {item.name: item.value for item in metrics}
            threshold = float(parameters.get("threshold_ms", 1_000))
            return (
                actual,
                f"ALL_LESS_THAN {threshold:g}ms",
                all(item.value < threshold for item in metrics),
            )
        if strategy is VerificationStrategy.DEPLOYMENT_STATE:
            deployment_id = str(parameters["deployment_id"])
            deployment = next(
                (item for item in state.deployments if str(item.id) == deployment_id), None
            )
            if deployment is None:
                raise VerificationCollectionError("Named simulated deployment is unavailable")
            actual = {
                "id": str(deployment.id),
                "version": deployment.version,
                "status": deployment.status,
            }
            return actual, "FIELD_EQUALS", actual.get("status") == expected.get("status")
        if strategy is VerificationStrategy.CONFIGURATION_STATE:
            key = str(parameters["configuration_id"])
            configuration = next((item for item in state.configurations if item.key == key), None)
            if configuration is None:
                raise VerificationCollectionError("Named simulated configuration is unavailable")
            actual = {"key": configuration.key, "value": configuration.value}
            return actual, "FIELD_EQUALS_KNOWN_GOOD", configuration.value == expected.get("value")
        if strategy is VerificationStrategy.QUEUE_STATE:
            queue_name = str(parameters["queue_name"])
            if queue_name not in state.queues:
                raise VerificationCollectionError("Named simulated queue is unavailable")
            actual = {"queue_name": queue_name, "depth": state.queues[queue_name]}
            return actual, "FIELD_EQUALS", state.queues[queue_name] == expected.get("depth")
        if strategy is VerificationStrategy.FEATURE_FLAG_STATE:
            feature_name = str(parameters["feature_name"])
            if feature_name not in state.feature_flags:
                raise VerificationCollectionError("Named simulated feature flag is unavailable")
            actual = {"feature_name": feature_name, "enabled": state.feature_flags[feature_name]}
            return (
                actual,
                "FIELD_EQUALS",
                state.feature_flags[feature_name] == expected.get("enabled"),
            )
        if strategy is VerificationStrategy.CAPACITY_STATE:
            service_name = str(parameters["service_name"])
            if service_name not in state.service_capacities:
                raise VerificationCollectionError("Named simulated service capacity is unavailable")
            actual = {
                "service_name": service_name,
                "capacity": state.service_capacities[service_name],
            }
            return (
                actual,
                "FIELD_EQUALS",
                state.service_capacities[service_name] == expected.get("capacity"),
            )
        if strategy is VerificationStrategy.TRANSACTION_SUCCESS:
            service = str(parameters["service"])
            successful = [
                item
                for item in state.transactions
                if item.service == service and item.status == "succeeded"
            ]
            actual = {"service": service, "successful_transactions": len(successful)}
            minimum = int(expected.get("minimum", 1))
            return actual, "COUNT_AT_LEAST", len(successful) >= minimum
        raise VerificationCollectionError(f"Unsupported verification strategy {strategy.value}")


__all__ = [
    "CollectedCheck",
    "CollectionResult",
    "SimulatorVerificationCollector",
    "VerificationCollectionError",
]
