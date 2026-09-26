"""Deterministic scenario catalog for the fictional ShopFlow company."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Literal

from backend.app.models.enums import Severity
from backend.app.schemas.incidents import ScenarioSummary
from backend.app.simulator.models import (
    ConfigurationSnapshot,
    DeploymentSnapshot,
    LogSnapshot,
    MetricSnapshot,
    ScenarioFixture,
    ServiceSnapshot,
    ShopFlowState,
    SimulatedIncident,
    TransactionSnapshot,
)


def _now() -> datetime:
    return datetime.now(UTC)


def _at(now: datetime, minutes_ago: int) -> datetime:
    return now - timedelta(minutes=minutes_ago)


ServiceStatus = Literal["healthy", "degraded", "down"]


def _services(*overrides: tuple[str, ServiceStatus]) -> list[ServiceSnapshot]:
    status_by_service: dict[str, ServiceStatus] = dict(overrides)
    names = [
        "Checkout Service",
        "Payment Service",
        "User Service",
        "Database",
        "Inventory",
        "Support System",
    ]
    return [
        ServiceSnapshot(
            name=name,
            status=status_by_service.get(name, "healthy"),
            version="2026.09.1",
        )
        for name in names
    ]


def _fixture(
    *,
    scenario_id: str,
    name: str,
    description: str,
    title: str,
    incident_description: str,
    severity: Severity,
    service: str,
    state: ShopFlowState,
    now: datetime,
) -> ScenarioFixture:
    return ScenarioFixture(
        scenario_id=scenario_id,
        name=name,
        description=description,
        incident=SimulatedIncident(
            scenario_id=scenario_id,
            title=title,
            description=incident_description,
            severity=severity,
            service=service,
            created_at=now,
        ),
        state=state,
    )


def _payment_failure() -> ScenarioFixture:
    now = _now()
    return _fixture(
        scenario_id="payment-failure",
        name="Payment Failure",
        description="Payment failures increase shortly after a payment deployment.",
        title="Payment authorization failures increased",
        incident_description="Checkout payment authorization failures rose after a recent release.",
        severity=Severity.HIGH,
        service="Payment Service",
        now=now,
        state=ShopFlowState(
            services=_services(("Payment Service", "degraded")),
            deployments=[
                DeploymentSnapshot(
                    service="Payment Service",
                    version="2026.09.2",
                    status="successful",
                    deployed_at=_at(now, 18),
                    change_summary="Updated gateway retry policy",
                )
            ],
            configurations=[
                ConfigurationSnapshot(
                    service="Payment Service",
                    key="gateway.retry_limit",
                    value=1,
                    expected_value=3,
                    updated_at=_at(now, 20),
                    updated_by="release-pipeline",
                )
            ],
            metrics=[
                MetricSnapshot(
                    service="Payment Service",
                    name="payment.failure_rate",
                    value=0.31,
                    unit="ratio",
                    observed_at=_at(now, 1),
                ),
                MetricSnapshot(
                    service="Checkout Service",
                    name="checkout.error_rate",
                    value=0.18,
                    unit="ratio",
                    observed_at=_at(now, 1),
                ),
            ],
            logs=[
                LogSnapshot(
                    service="Payment Service",
                    level="ERROR",
                    message="Gateway authorization failed after retry budget was exhausted",
                    timestamp=_at(now, 2),
                    metadata={"gateway": "shopflow-gateway", "error_code": "AUTH_RETRY_EXHAUSTED"},
                )
            ],
            transactions=[
                TransactionSnapshot(
                    service="Payment Service",
                    status="failed",
                    amount=149.99,
                    currency="USD",
                    timestamp=_at(now, 1),
                    failure_reason="AUTH_RETRY_EXHAUSTED",
                ),
                TransactionSnapshot(
                    service="Payment Service",
                    status="succeeded",
                    amount=42.50,
                    currency="USD",
                    timestamp=_at(now, 1),
                ),
            ],
        ),
    )


def _database_failure() -> ScenarioFixture:
    now = _now()
    return _fixture(
        scenario_id="database-failure",
        name="Database Failure",
        description="Application services cannot reliably establish database connections.",
        title="ShopFlow database connections are failing",
        incident_description=(
            "Multiple application requests fail while connecting to the primary database."
        ),
        severity=Severity.CRITICAL,
        service="Database",
        now=now,
        state=ShopFlowState(
            services=_services(("Database", "down"), ("Checkout Service", "degraded")),
            deployments=[],
            configurations=[
                ConfigurationSnapshot(
                    service="Database",
                    key="connection.pool_size",
                    value=30,
                    expected_value=30,
                    updated_at=_at(now, 180),
                    updated_by="platform-admin",
                )
            ],
            metrics=[
                MetricSnapshot(
                    service="Database",
                    name="database.connection_errors",
                    value=87,
                    unit="count_per_minute",
                    observed_at=_at(now, 1),
                ),
                MetricSnapshot(
                    service="Checkout Service",
                    name="checkout.timeout_rate",
                    value=0.44,
                    unit="ratio",
                    observed_at=_at(now, 1),
                ),
            ],
            logs=[
                LogSnapshot(
                    service="Database",
                    level="ERROR",
                    message="connection refused by primary database endpoint",
                    timestamp=_at(now, 2),
                    metadata={"host": "shopflow-db-primary", "port": 5432},
                ),
                LogSnapshot(
                    service="Checkout Service",
                    level="ERROR",
                    message="request aborted while waiting for database connection",
                    timestamp=_at(now, 1),
                    metadata={"timeout_ms": 3000},
                ),
            ],
            transactions=[],
        ),
    )


def _latency_spike() -> ScenarioFixture:
    now = _now()
    return _fixture(
        scenario_id="latency-spike",
        name="Latency Spike",
        description="API response times suddenly increase without a new deployment.",
        title="Checkout API latency exceeds threshold",
        incident_description="Checkout response latency is elevated across the production API.",
        severity=Severity.HIGH,
        service="Checkout Service",
        now=now,
        state=ShopFlowState(
            services=_services(("Checkout Service", "degraded")),
            deployments=[],
            configurations=[],
            metrics=[
                MetricSnapshot(
                    service="Checkout Service",
                    name="http.request.p95",
                    value=3200,
                    unit="milliseconds",
                    observed_at=_at(now, 1),
                ),
                MetricSnapshot(
                    service="Checkout Service",
                    name="http.request.rate",
                    value=980,
                    unit="requests_per_minute",
                    observed_at=_at(now, 1),
                ),
            ],
            logs=[
                LogSnapshot(
                    service="Checkout Service",
                    level="WARN",
                    message="downstream inventory request exceeded latency budget",
                    timestamp=_at(now, 2),
                    metadata={"dependency": "Inventory", "elapsed_ms": 2800},
                )
            ],
            transactions=[],
        ),
    )


def _bad_deployment() -> ScenarioFixture:
    now = _now()
    return _fixture(
        scenario_id="bad-deployment",
        name="Bad Deployment",
        description="A recent release introduces application errors.",
        title="User Service errors followed the latest release",
        incident_description=(
            "User Service error rate increased immediately after a production deployment."
        ),
        severity=Severity.HIGH,
        service="User Service",
        now=now,
        state=ShopFlowState(
            services=_services(("User Service", "degraded")),
            deployments=[
                DeploymentSnapshot(
                    service="User Service",
                    version="2026.09.3",
                    status="active",
                    deployed_at=_at(now, 8),
                    change_summary="Introduced profile cache migration",
                )
            ],
            configurations=[],
            metrics=[
                MetricSnapshot(
                    service="User Service",
                    name="http.5xx_rate",
                    value=0.22,
                    unit="ratio",
                    observed_at=_at(now, 1),
                )
            ],
            logs=[
                LogSnapshot(
                    service="User Service",
                    level="ERROR",
                    message="profile cache schema version is not supported",
                    timestamp=_at(now, 3),
                    metadata={"expected_schema": 4, "actual_schema": 3},
                )
            ],
            transactions=[],
        ),
    )


def _configuration_mismatch() -> ScenarioFixture:
    now = _now()
    return _fixture(
        scenario_id="configuration-mismatch",
        name="Configuration Mismatch",
        description="A configuration change causes application failures.",
        title="Payment Service has an invalid gateway configuration",
        incident_description=(
            "Payment requests fail because the active gateway endpoint differs from "
            "the approved value."
        ),
        severity=Severity.CRITICAL,
        service="Payment Service",
        now=now,
        state=ShopFlowState(
            services=_services(("Payment Service", "degraded")),
            deployments=[],
            configurations=[
                ConfigurationSnapshot(
                    service="Payment Service",
                    key="gateway.endpoint",
                    value="https://invalid-gateway.shopflow.internal",
                    expected_value="https://gateway.shopflow.internal",
                    updated_at=_at(now, 5),
                    updated_by="config-sync",
                )
            ],
            metrics=[
                MetricSnapshot(
                    service="Payment Service",
                    name="payment.failure_rate",
                    value=0.67,
                    unit="ratio",
                    observed_at=_at(now, 1),
                )
            ],
            logs=[
                LogSnapshot(
                    service="Payment Service",
                    level="ERROR",
                    message="unable to resolve configured payment gateway endpoint",
                    timestamp=_at(now, 2),
                    metadata={"configuration_key": "gateway.endpoint"},
                )
            ],
            transactions=[],
        ),
    )


_BUILDERS: dict[str, Callable[[], ScenarioFixture]] = {
    "payment-failure": _payment_failure,
    "database-failure": _database_failure,
    "latency-spike": _latency_spike,
    "bad-deployment": _bad_deployment,
    "configuration-mismatch": _configuration_mismatch,
}


def list_scenario_summaries() -> list[ScenarioSummary]:
    """Return metadata without pretending any scenario is an active incident."""

    fixtures = [builder() for builder in _BUILDERS.values()]
    return [
        ScenarioSummary(
            scenario_id=fixture.scenario_id,
            name=fixture.name,
            description=fixture.description,
            incident_title=fixture.incident.title,
            severity=fixture.incident.severity,
        )
        for fixture in fixtures
    ]


class ScenarioNotFoundError(LookupError):
    """Raised for a scenario outside the explicit catalog."""


class ShopFlowSimulator:
    """Read-only scenario simulator for structured ShopFlow observations."""

    company = "ShopFlow"

    def list_scenarios(self) -> list[ScenarioSummary]:
        return list_scenario_summaries()

    def load_scenario(self, scenario_id: str) -> ScenarioFixture:
        try:
            return _BUILDERS[scenario_id]()
        except KeyError as exc:
            raise ScenarioNotFoundError(scenario_id) from exc
