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
    """Read-only fixture access plus fixed, non-production Phase 4/7 state changes."""

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

    PHASE7_ACTIONS = frozenset(
        {
            "restart_payment_service",
            "rollback_simulated_deployment",
            "restart_checkout_service",
            "clear_simulated_queue",
            "disable_simulated_feature_flag",
            "restore_simulated_configuration",
            "scale_simulated_service",
        }
    )

    def execute_phase7_action(
        self,
        *,
        scenario_id: str,
        action_name: str,
        parameters: dict[str, Any],
        idempotency_key: str,
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        """Execute one explicit Phase 7 handler against in-memory simulator state."""

        if action_name not in self.PHASE7_ACTIONS:
            raise SimulationActionError("Phase 7 simulator action is not allow-listed")
        with self._lock:
            if idempotency_key in self._action_keys:
                raise DuplicateSimulationActionError("Duplicate simulator action prevented")
            self.fixture(scenario_id)
            fixture = self._fixtures[scenario_id]
            before = self._phase7_snapshot(fixture.state, action_name, parameters)
            verification_target: dict[str, Any]
            if action_name == "restart_payment_service":
                self._recover_service_state(fixture, "Payment Service")
                verification_target = {"service": "Payment Service", "status": "healthy"}
            elif action_name == "restart_checkout_service":
                self._recover_service_state(fixture, "Checkout Service")
                verification_target = {"service": "Checkout Service", "status": "healthy"}
            elif action_name == "rollback_simulated_deployment":
                deployment = self._deployment(fixture, parameters["deployment_id"])
                deployment.status = "rolled_back"
                self._recover_service_state(fixture, deployment.service)
                verification_target = {
                    "deployment_id": str(deployment.id),
                    "status": "rolled_back",
                }
            elif action_name == "clear_simulated_queue":
                queue_name = parameters["queue_name"]
                if queue_name not in fixture.state.queues:
                    raise SimulationActionError("Simulated queue is not available")
                fixture.state.queues[queue_name] = 0
                verification_target = {"queue_name": queue_name, "depth": 0}
            elif action_name == "disable_simulated_feature_flag":
                feature_name = parameters["feature_name"]
                if feature_name not in fixture.state.feature_flags:
                    raise SimulationActionError("Simulated feature flag is not available")
                fixture.state.feature_flags[feature_name] = False
                verification_target = {"feature_name": feature_name, "enabled": False}
            elif action_name == "restore_simulated_configuration":
                configuration = self._configuration(fixture, parameters["configuration_id"])
                if configuration.expected_value is None:
                    raise SimulationActionError("Configuration has no known-good value")
                configuration.value = configuration.expected_value
                verification_target = {
                    "configuration_id": configuration.key,
                    "value": configuration.expected_value,
                }
            else:
                service_name = parameters["service_name"]
                if service_name not in fixture.state.service_capacities:
                    raise SimulationActionError("Simulated service capacity is not available")
                fixture.state.service_capacities[service_name] = parameters["desired_capacity"]
                verification_target = {
                    "service_name": service_name,
                    "desired_capacity": parameters["desired_capacity"],
                }
            after = self._phase7_snapshot(fixture.state, action_name, parameters)
            self._action_keys.add(idempotency_key)
            result = {
                "simulated": True,
                "controlled_demonstration": True,
                "scenario_id": scenario_id,
                "action": action_name,
                "production_change": False,
                "before_state": before,
                "after_state": after,
                "verification_target": verification_target,
            }
            return result, [
                {
                    "id": f"phase7-action:{idempotency_key}",
                    "source": "ShopFlow simulator",
                    "timestamp": datetime.now(UTC),
                    "type": "controlled_simulated_action",
                    "summary": f"Controlled simulator action completed: {action_name}",
                    "raw_reference": {"scenario_id": scenario_id, "action": action_name},
                    "relevance": 1.0,
                }
            ]

    def restore_phase7_action(
        self,
        *,
        scenario_id: str,
        action_name: str,
        parameters: dict[str, Any],
        before_state: dict[str, Any],
        idempotency_key: str,
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        """Restore only the before-state captured by a registered action."""

        if action_name not in self.PHASE7_ACTIONS:
            raise SimulationActionError("Rollback target is not allow-listed")
        with self._lock:
            if idempotency_key in self._action_keys:
                raise DuplicateSimulationActionError("Duplicate rollback prevented")
            self.fixture(scenario_id)
            fixture = self._fixtures[scenario_id]
            current = self._phase7_snapshot(fixture.state, action_name, parameters)
            if action_name in {"restart_payment_service", "restart_checkout_service"}:
                service_snapshot = before_state.get("service")
                if not isinstance(service_snapshot, dict):
                    raise SimulationActionError("Rollback state for service action is unavailable")
                for service in fixture.state.services:
                    if service.name == service_snapshot.get("name"):
                        service.status = service_snapshot.get("status", service.status)
                        service.version = service_snapshot.get("version")
                for metric_snapshot in before_state.get("metrics", []):
                    if not isinstance(metric_snapshot, dict):
                        continue
                    for metric in fixture.state.metrics:
                        if metric.service == metric_snapshot.get(
                            "service"
                        ) and metric.name == metric_snapshot.get("name"):
                            metric.value = metric_snapshot.get("value", metric.value)
            elif action_name == "rollback_simulated_deployment":
                deployment_snapshot = before_state.get("deployment")
                if not isinstance(deployment_snapshot, dict):
                    raise SimulationActionError("Rollback state for deployment is unavailable")
                for deployment in fixture.state.deployments:
                    if str(deployment.id) == str(deployment_snapshot.get("id")):
                        deployment.status = deployment_snapshot.get("status", deployment.status)
                        deployment.version = deployment_snapshot.get("version", deployment.version)
                service_snapshot = before_state.get("service")
                if isinstance(service_snapshot, dict):
                    for service in fixture.state.services:
                        if service.name == service_snapshot.get("name"):
                            service.status = service_snapshot.get("status", service.status)
            elif action_name == "clear_simulated_queue":
                queue_name = before_state.get("queue_name")
                if not isinstance(queue_name, str):
                    raise SimulationActionError("Rollback queue state is unavailable")
                fixture.state.queues[queue_name] = int(before_state.get("depth", 0))
            elif action_name == "disable_simulated_feature_flag":
                feature_name = before_state.get("feature_name")
                if not isinstance(feature_name, str):
                    raise SimulationActionError("Rollback feature state is unavailable")
                fixture.state.feature_flags[feature_name] = bool(before_state.get("enabled", True))
            elif action_name == "restore_simulated_configuration":
                configuration_snapshot = before_state.get("configuration")
                if not isinstance(configuration_snapshot, dict):
                    raise SimulationActionError("Rollback configuration state is unavailable")
                key = str(configuration_snapshot.get("key"))
                configuration = self._configuration(fixture, key)
                configuration.value = configuration_snapshot.get("value")
            else:
                service_name = before_state.get("service_name")
                if not isinstance(service_name, str):
                    raise SimulationActionError("Rollback capacity state is unavailable")
                fixture.state.service_capacities[service_name] = int(
                    before_state.get("desired_capacity", 1)
                )
            after = self._phase7_snapshot(fixture.state, action_name, parameters)
            self._action_keys.add(idempotency_key)
            return (
                {
                    "simulated": True,
                    "controlled_demonstration": True,
                    "scenario_id": scenario_id,
                    "action": "restore_simulated_action_state",
                    "production_change": False,
                    "before_state": current,
                    "after_state": after,
                },
                [],
            )

    def verify_phase7_action(
        self,
        *,
        scenario_id: str,
        action_name: str,
        parameters: dict[str, Any],
        verification_target: dict[str, Any],
    ) -> dict[str, Any]:
        """Return a structured, deterministic verification result."""

        state = self.state(scenario_id)
        checks: dict[str, Any] = {}
        if action_name in {"restart_payment_service", "restart_checkout_service"}:
            service = str(verification_target["service"])
            checks["service_health"] = self._health_check(state, service)
            metric_names = (
                {
                    "payment.failure_rate",
                    "checkout.error_rate",
                    "checkout.timeout_rate",
                    "http.request.p95",
                }
                if service == "Payment Service"
                else {"checkout.error_rate", "checkout.timeout_rate", "http.request.p95"}
            )
            metrics = [
                item
                for item in state.metrics
                if item.service == service and item.name in metric_names
            ]
            checks["service_metrics"] = {
                "healthy": bool(metrics)
                and all(
                    item.value < 1_000 if "p95" in item.name else item.value < 0.05
                    for item in metrics
                ),
                "metrics": [item.model_dump(mode="json") for item in metrics],
            }
            verified = bool(checks["service_health"].get("healthy")) and bool(
                checks["service_metrics"].get("healthy")
            )
        elif action_name == "rollback_simulated_deployment":
            deployment = next(
                (
                    item
                    for item in state.deployments
                    if str(item.id) == str(verification_target["deployment_id"])
                ),
                None,
            )
            checks["deployment"] = {
                "found": deployment is not None,
                "status": deployment.status if deployment else "NOT_FOUND",
            }
            verified = deployment is not None and deployment.status == "rolled_back"
        elif action_name == "clear_simulated_queue":
            queue_name = str(verification_target["queue_name"])
            depth = state.queues.get(queue_name)
            checks["queue"] = {"queue_name": queue_name, "depth": depth}
            verified = depth == 0
        elif action_name == "disable_simulated_feature_flag":
            feature_name = str(verification_target["feature_name"])
            enabled = state.feature_flags.get(feature_name)
            checks["feature_flag"] = {"feature_name": feature_name, "enabled": enabled}
            verified = enabled is False
        elif action_name == "restore_simulated_configuration":
            configuration = self._configuration(
                self.fixture(scenario_id), str(parameters["configuration_id"])
            )
            checks["configuration"] = {
                "key": configuration.key,
                "value": configuration.value,
                "expected_value": configuration.expected_value,
            }
            verified = configuration.value == configuration.expected_value
        else:
            service_name = str(verification_target["service_name"])
            capacity = state.service_capacities.get(service_name)
            checks["capacity"] = {"service_name": service_name, "capacity": capacity}
            verified = capacity == verification_target["desired_capacity"]
        return {
            "verified": verified,
            "checks": checks,
            "action": action_name,
            "parameters": parameters,
        }

    def verify_phase7_rollback(
        self,
        *,
        scenario_id: str,
        action_name: str,
        parameters: dict[str, Any],
        before_state: dict[str, Any],
    ) -> bool:
        """Verify that a registered rollback restored the captured before-state."""

        current = self._phase7_snapshot(self.fixture(scenario_id).state, action_name, parameters)
        return current == before_state

    @staticmethod
    def _phase7_snapshot(
        state: ShopFlowState, action_name: str, parameters: dict[str, Any]
    ) -> dict[str, Any]:
        if action_name in {"restart_payment_service", "restart_checkout_service"}:
            service_name = (
                "Payment Service"
                if action_name == "restart_payment_service"
                else "Checkout Service"
            )
            service = next((item for item in state.services if item.name == service_name), None)
            if service is None:
                raise SimulationActionError(f"Simulated service {service_name!r} is not available")
            metrics = [
                item.model_dump(mode="json")
                for item in state.metrics
                if item.service == service_name
                and any(token in item.name for token in ("failure", "error", "timeout"))
            ]
            return {"service": service.model_dump(mode="json"), "metrics": metrics}
        if action_name == "rollback_simulated_deployment":
            deployment = next(
                (
                    item
                    for item in state.deployments
                    if str(item.id) == str(parameters["deployment_id"])
                ),
                None,
            )
            if deployment is None:
                raise SimulationActionError("Simulated deployment is not available")
            service = next(
                (item for item in state.services if item.name == deployment.service), None
            )
            return {
                "deployment": deployment.model_dump(mode="json"),
                "service": service.model_dump(mode="json") if service else {},
            }
        if action_name == "clear_simulated_queue":
            queue_name = str(parameters["queue_name"])
            if queue_name not in state.queues:
                raise SimulationActionError("Simulated queue is not available")
            return {"queue_name": queue_name, "depth": state.queues[queue_name]}
        if action_name == "disable_simulated_feature_flag":
            feature_name = str(parameters["feature_name"])
            if feature_name not in state.feature_flags:
                raise SimulationActionError("Simulated feature flag is not available")
            return {"feature_name": feature_name, "enabled": state.feature_flags[feature_name]}
        if action_name == "restore_simulated_configuration":
            configuration = next(
                (
                    item
                    for item in state.configurations
                    if item.key == str(parameters["configuration_id"])
                    or str(item.id) == str(parameters["configuration_id"])
                ),
                None,
            )
            if configuration is None:
                raise SimulationActionError("Simulated configuration is not available")
            return {"configuration": configuration.model_dump(mode="json")}
        service_name = str(parameters["service_name"])
        if service_name not in state.service_capacities:
            raise SimulationActionError("Simulated service capacity is not available")
        return {
            "service_name": service_name,
            "desired_capacity": state.service_capacities[service_name],
        }

    @staticmethod
    def _deployment(fixture: ScenarioFixture, deployment_id: str) -> Any:
        for deployment in fixture.state.deployments:
            if str(deployment.id) == str(deployment_id):
                return deployment
        raise SimulationActionError("Simulated deployment is not available")

    @staticmethod
    def _configuration(fixture: ScenarioFixture, configuration_id: str) -> Any:
        for configuration in fixture.state.configurations:
            if configuration.key == configuration_id or str(configuration.id) == str(
                configuration_id
            ):
                return configuration
        raise SimulationActionError("Simulated configuration is not available")

    @staticmethod
    def _recover_service_state(fixture: ScenarioFixture, service_name: str) -> None:
        matching = [item for item in fixture.state.services if item.name == service_name]
        if not matching:
            raise SimulationActionError(f"Simulated service {service_name!r} is not available")
        matching[0].status = "healthy"
        for metric in fixture.state.metrics:
            if metric.service == service_name and any(
                token in metric.name for token in ("failure", "error", "timeout")
            ):
                metric.value = 0.01
            elif metric.service == service_name and "p95" in metric.name:
                metric.value = 250.0
        for log in fixture.state.logs:
            if log.service == service_name and log.level == "ERROR":
                log.level = "INFO"
                log.message = f"Resolved simulated prior error: {log.message}"

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
