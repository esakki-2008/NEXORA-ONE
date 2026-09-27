"""Controlled, in-memory ShopFlow actions for demonstrations only."""

from __future__ import annotations

from datetime import UTC, datetime
from threading import RLock
from typing import Any

from backend.app.simulator.models import ScenarioFixture, ShopFlowState
from backend.app.simulator.scenarios import ScenarioNotFoundError, ShopFlowSimulator


class SimulationUnavailableError(LookupError):
    """Raised when a requested simulator source is not available."""


class SimulationActionError(RuntimeError):
    """Raised when a fixed simulator action cannot be applied."""


class DuplicateSimulationActionError(SimulationActionError):
    """Raised when the same idempotency key is submitted twice."""


class ShopFlowSimulationRuntime:
    """Read-only fixture access plus two fixed, non-production state changes."""

    SAFE_ACTIONS = frozenset({"restart_payment_service", "rollback_simulated_deployment"})

    def __init__(self, simulator: ShopFlowSimulator | None = None) -> None:
        self.simulator = simulator or ShopFlowSimulator()
        self._lock = RLock()
        self._fixtures: dict[str, ScenarioFixture] = {}
        self._action_keys: set[str] = set()

    def fixture(self, scenario_id: str) -> ScenarioFixture:
        with self._lock:
            if scenario_id not in self._fixtures:
                try:
                    self._fixtures[scenario_id] = self.simulator.load_scenario(scenario_id)
                except ScenarioNotFoundError as exc:
                    raise SimulationUnavailableError(
                        f"ShopFlow scenario {scenario_id!r} is not available"
                    ) from exc
            return self._fixtures[scenario_id].model_copy(deep=True)

    def state(self, scenario_id: str) -> ShopFlowState:
        return self.fixture(scenario_id).state

    def read(
        self, tool_name: str, arguments: dict[str, Any], scenario_id: str
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        fixture = self.fixture(scenario_id)
        state = fixture.state
        service = arguments.get("service")
        if service:
            service = str(service)
        if tool_name == "get_logs":
            log_rows = [item for item in state.logs if not service or item.service == service]
            return self._rows(log_rows), [self._log_evidence(fixture, item) for item in log_rows]
        if tool_name == "get_metrics":
            metric = str(arguments["metric"])
            metric_rows = [
                item
                for item in state.metrics
                if (not service or item.service == service)
                and (metric == "*" or item.name == metric)
            ]
            return self._rows(metric_rows), [
                self._metric_evidence(fixture, item) for item in metric_rows
            ]
        if tool_name == "get_recent_deployments":
            deployment_rows = [
                item for item in state.deployments if not service or item.service == service
            ]
            return self._rows(deployment_rows), [
                self._deployment_evidence(fixture, item) for item in deployment_rows
            ]
        if tool_name == "inspect_configuration":
            keys = set(arguments["keys"])
            configuration_rows = [
                item
                for item in state.configurations
                if (not service or item.service == service) and item.key in keys
            ]
            return self._rows(configuration_rows), [
                self._configuration_evidence(fixture, item) for item in configuration_rows
            ]
        if tool_name == "run_health_check":
            result = self._health_check(state, service or "")
            return result, [self._health_evidence(fixture, service or "", result)]
        if tool_name == "run_test":
            result = self._test(state, str(arguments["test_id"]))
            return result, [self._test_evidence(fixture, str(arguments["test_id"]), result)]
        if tool_name == "verify_resolution":
            return self._verify(state, arguments["checks"], service or ""), []
        if tool_name == "search_documentation":
            raise SimulationUnavailableError("ShopFlow documentation is not connected in Phase 4")
        if tool_name == "create_remediation_plan":
            return {"created": True, "simulated": True, "steps": arguments["steps"]}, []
        if tool_name == "generate_incident_report":
            return {"available": True, "assembled_by": "NEXORA orchestrator"}, []
        raise SimulationUnavailableError(f"Tool {tool_name!r} is not available in ShopFlow runtime")

    def execute_safe_action(
        self,
        *,
        scenario_id: str,
        action_name: str,
        parameters: dict[str, Any],
        idempotency_key: str,
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        del parameters
        if action_name not in self.SAFE_ACTIONS:
            raise SimulationActionError("Simulator action is not allow-listed")
        with self._lock:
            if idempotency_key in self._action_keys:
                raise DuplicateSimulationActionError("Duplicate simulator action prevented")
            self.fixture(scenario_id)
            fixture = self._fixtures[scenario_id]
            if action_name == "restart_payment_service":
                self._recover_payment_state(fixture)
            elif action_name == "rollback_simulated_deployment":
                self._recover_payment_state(fixture)
                for deployment in fixture.state.deployments:
                    if deployment.service == "Payment Service":
                        deployment.status = "rolled_back"
            self._action_keys.add(idempotency_key)
            result = {
                "simulated": True,
                "scenario_id": scenario_id,
                "action": action_name,
                "affected_services": ["Payment Service"],
                "production_change": False,
            }
            return result, [
                {
                    "id": f"simulation-action:{idempotency_key}",
                    "source": "ShopFlow simulator",
                    "timestamp": datetime.now(UTC),
                    "type": "simulated_action",
                    "summary": f"Simulated action completed: {action_name}",
                    "raw_reference": {"scenario_id": scenario_id, "action": action_name},
                    "relevance": 1.0,
                }
            ]

    @staticmethod
    def _recover_payment_state(fixture: ScenarioFixture) -> None:
        for service in fixture.state.services:
            if service.name == "Payment Service":
                service.status = "healthy"
        for metric in fixture.state.metrics:
            if metric.name in {
                "payment.failure_rate",
                "checkout.error_rate",
                "checkout.timeout_rate",
            }:
                metric.value = 0.01
        for log in fixture.state.logs:
            if log.level == "ERROR":
                log.level = "INFO"
                log.message = f"Resolved simulated prior error: {log.message}"
        for transaction in fixture.state.transactions:
            if transaction.status == "failed":
                transaction.status = "pending"
                transaction.failure_reason = None

    @staticmethod
    def _health_check(state: ShopFlowState, service: str) -> dict[str, Any]:
        matching = [item for item in state.services if item.name == service]
        if not matching:
            return {"service": service, "status": "NOT_AVAILABLE", "healthy": False}
        item = matching[0]
        return {
            "service": service,
            "status": item.status.upper(),
            "healthy": item.status == "healthy",
        }

    @staticmethod
    def _test(state: ShopFlowState, test_id: str) -> dict[str, Any]:
        service_by_test = {
            "payment_authorization_smoke": "Payment Service",
            "checkout_smoke": "Checkout Service",
            "database_connectivity": "Database",
        }
        service_name = service_by_test.get(test_id)
        healthy = bool(service_name) and any(
            item.name == service_name and item.status == "healthy" for item in state.services
        )
        return {
            "test_id": test_id,
            "service": service_name or "NOT_AVAILABLE",
            "status": "PASS" if healthy else "FAIL",
            "passed": healthy,
        }

    @staticmethod
    def _verify(
        state: ShopFlowState,
        checks: list[str],
        service: str,
    ) -> dict[str, Any]:
        results: dict[str, Any] = {}
        for check in checks:
            if check == "service_health":
                results[check] = ShopFlowSimulationRuntime._health_check(state, service)
            elif check == "payment_metrics":
                metrics = [
                    item
                    for item in state.metrics
                    if item.name in {"payment.failure_rate", "checkout.error_rate"}
                ]
                results[check] = {
                    "healthy": bool(metrics) and all(item.value < 0.05 for item in metrics),
                    "metrics": [item.model_dump(mode="json") for item in metrics],
                }
            elif check == "error_logs":
                errors = [item for item in state.logs if item.level == "ERROR"]
                results[check] = {"healthy": len(errors) == 0, "error_count": len(errors)}
        return {
            "checks": results,
            "verified": bool(results) and all(_check_passed(item) for item in results.values()),
        }

    @staticmethod
    def _rows(rows: list[Any]) -> dict[str, Any]:
        return {"count": len(rows), "items": [row.model_dump(mode="json") for row in rows]}

    @staticmethod
    def _log_evidence(fixture: ScenarioFixture, item: Any) -> dict[str, Any]:
        return _evidence(
            str(item.id), f"ShopFlow / {item.service}", item.timestamp, "log", item.message
        )

    @staticmethod
    def _metric_evidence(fixture: ScenarioFixture, item: Any) -> dict[str, Any]:
        return _evidence(
            f"metric:{item.service}:{item.name}",
            f"ShopFlow / {item.service}",
            item.observed_at,
            "metric",
            f"{item.name}: {item.value} {item.unit}",
        )

    @staticmethod
    def _deployment_evidence(fixture: ScenarioFixture, item: Any) -> dict[str, Any]:
        return _evidence(
            str(item.id),
            f"ShopFlow / {item.service}",
            item.deployed_at,
            "deployment",
            f"{item.version} — {item.change_summary}",
        )

    @staticmethod
    def _configuration_evidence(fixture: ScenarioFixture, item: Any) -> dict[str, Any]:
        return _evidence(
            f"configuration:{item.service}:{item.key}",
            f"ShopFlow / {item.service}",
            item.updated_at,
            "configuration",
            f"{item.key}: {item.value}",
        )

    @staticmethod
    def _health_evidence(
        fixture: ScenarioFixture, service: str, result: dict[str, Any]
    ) -> dict[str, Any]:
        return _evidence(
            f"health:{fixture.scenario_id}:{service}",
            "ShopFlow simulator",
            datetime.now(UTC),
            "health_check",
            f"{service} health: {result['status']}",
        )

    @staticmethod
    def _test_evidence(
        fixture: ScenarioFixture, test_id: str, result: dict[str, Any]
    ) -> dict[str, Any]:
        return _evidence(
            f"test:{fixture.scenario_id}:{test_id}",
            "ShopFlow simulator",
            datetime.now(UTC),
            "test",
            f"{test_id}: {result['status']}",
        )


def _evidence(
    evidence_id: str,
    source: str,
    timestamp: datetime,
    evidence_type: str,
    summary: str,
) -> dict[str, Any]:
    return {
        "id": evidence_id,
        "source": source,
        "timestamp": timestamp,
        "type": evidence_type,
        "summary": summary,
        "raw_reference": {"source": source, "id": evidence_id},
        "relevance": 0.7,
    }


def _check_passed(value: Any) -> bool:
    if isinstance(value, dict):
        if "healthy" in value:
            return bool(value["healthy"])
        if "verified" in value:
            return bool(value["verified"])
    return False


__all__ = [
    "DuplicateSimulationActionError",
    "ShopFlowSimulationRuntime",
    "SimulationActionError",
    "SimulationUnavailableError",
]
