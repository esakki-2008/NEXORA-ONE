"""Application service for the unified Phase 6 operations intelligence layer."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from threading import RLock
from typing import Literal, cast
from uuid import UUID

from backend.app.database.repository import IncidentRepository
from backend.app.investigation.service import InvestigationService
from backend.app.models.domain import Incident
from backend.app.models.enums import IncidentStatus, Severity
from backend.app.operations.context import (
    BusinessImpact,
    BusinessImpactSummary,
    BusinessMetric,
    CloudSignal,
    ComplianceSignal,
    ComplianceSignalStatus,
    ContractSignal,
    ContractSignalStatus,
    CrossDomainCorrelation,
    CustomerSignal,
    DataQualitySignal,
    DomainDetail,
    DomainHealth,
    ImpactLevel,
    InvestigateSignalRequest,
    InvestigationLaunch,
    OperationalEvent,
    OperationalSignal,
    OperationalSignalStatus,
    OperationalSnapshot,
    OperationsDomain,
    OperationsHealth,
    OperationsSourceStatus,
    PriorityItem,
    PriorityLevel,
    RevenueSignal,
    ServiceHealth,
    SourceAvailability,
    SourceMetadata,
    SourceType,
    SupplyChainRiskStatus,
    SupplyChainSignal,
)
from backend.app.operations.correlations import build_correlations
from backend.app.operations.domains import DOMAIN_ORDER
from backend.app.operations.health import build_domain_health
from backend.app.operations.metrics import safe_ratio, transaction_totals
from backend.app.operations.priorities import prioritize_signals
from backend.app.operations.signals import evidence_ref, signal_is_active, slug, source_metadata
from backend.app.operations.snapshots import (
    not_configured_source,
    overall_status,
    refresh_id,
)
from backend.app.schemas.incidents import ActivityEvent, IncidentCreate
from backend.app.services.incident_service import IncidentService
from backend.app.simulator.models import ScenarioFixture
from backend.app.simulator.runtime import ShopFlowSimulationRuntime


class OperationsNotFoundError(LookupError):
    """Raised when an operations resource does not exist."""


class OperationsValidationError(ValueError):
    """Raised when an operations request cannot be completed safely."""


@dataclass
class _OperationsBuild:
    timestamp: datetime
    scenario_id: str | None
    incident_id: UUID | None
    fixture: ScenarioFixture | None
    incident: Incident | None
    signals: list[OperationalSignal] = field(default_factory=list)
    metrics: list[BusinessMetric] = field(default_factory=list)
    service_health: dict[OperationsDomain, list[ServiceHealth]] = field(default_factory=dict)
    source_status: dict[OperationsDomain, OperationsSourceStatus] = field(default_factory=dict)
    events: list[OperationalEvent] = field(default_factory=list)


class OperationsService:
    """Build snapshots once and expose all operations endpoints from that model."""

    def __init__(
        self,
        repository: IncidentRepository,
        simulation_runtime: ShopFlowSimulationRuntime,
        *,
        incident_service: IncidentService | None = None,
        investigation_service: InvestigationService | None = None,
    ) -> None:
        self.repository = repository
        self.simulation_runtime = simulation_runtime
        self.incident_service = incident_service
        self.investigation_service = investigation_service
        self._signal_incidents: dict[tuple[str, str], UUID] = {}
        self._signal_incidents_lock = RLock()

    def snapshot(
        self,
        *,
        scenario_id: str | None = None,
        incident_id: UUID | None = None,
    ) -> OperationalSnapshot:
        build = self._build(scenario_id=scenario_id, incident_id=incident_id)
        impact = self._business_impact(build)
        priorities = prioritize_signals(build.signals, impact)
        priority_by_signal = {item.signal_id: item.priority for item in priorities}
        signals = [
            signal.model_copy(update={"priority": priority_by_signal[signal.signal_id]})
            for signal in build.signals
        ]
        build.signals = signals
        correlations = build_correlations(signals)
        domains = self._domain_health(build, impact)
        source_status = [build.source_status[domain] for domain in DOMAIN_ORDER]
        source = self._snapshot_source(build, source_status)
        critical_signals = [
            signal
            for signal in signals
            if signal_is_active(signal.status)
            and (signal.severity is Severity.CRITICAL or signal.priority is PriorityLevel.CRITICAL)
        ]
        events = self._events(signals)
        return OperationalSnapshot(
            timestamp=build.timestamp,
            overall_status=overall_status(domains),
            domains=domains,
            critical_signals=critical_signals,
            business_impact=impact,
            cross_domain_correlations=correlations,
            priority_items=priorities,
            recent_events=events,
            source_status=source_status,
            scenario_id=build.scenario_id,
            incident_id=build.incident_id,
            simulator=any(item.simulator for item in source_status),
            source=source,
            refresh_id=refresh_id(
                build.timestamp,
                build.scenario_id,
                str(build.incident_id) if build.incident_id else None,
            ),
        )

    def domains(
        self,
        *,
        scenario_id: str | None = None,
        incident_id: UUID | None = None,
    ) -> list[DomainHealth]:
        return self.snapshot(scenario_id=scenario_id, incident_id=incident_id).domains

    def domain(
        self,
        domain: OperationsDomain,
        *,
        scenario_id: str | None = None,
        incident_id: UUID | None = None,
    ) -> DomainDetail:
        build = self._build(scenario_id=scenario_id, incident_id=incident_id)
        impact = self._business_impact(build)
        priorities = prioritize_signals(build.signals, impact)
        priority_by_signal = {item.signal_id: item.priority for item in priorities}
        build.signals = [
            signal.model_copy(update={"priority": priority_by_signal[signal.signal_id]})
            for signal in build.signals
        ]
        correlations = build_correlations(build.signals)
        domain_signals = [item for item in build.signals if item.domain is domain]
        domain_metrics = [item for item in build.metrics if item.domain is domain]
        domain_health = next(
            item for item in self._domain_health(build, impact) if item.domain is domain
        )
        related_incidents = list(
            dict.fromkeys(
                item.related_incident_id
                for item in domain_signals
                if item.related_incident_id is not None
            )
        )
        related_evidence = list(
            dict.fromkeys(
                evidence_id for item in domain_signals for evidence_id in item.evidence_ids
            )
        )
        active = next((item for item in domain_signals if signal_is_active(item.status)), None)
        recommendation = (
            f"Open a Phase 5 investigation for {active.title}." if active is not None else None
        )
        return DomainDetail(
            health=domain_health,
            metrics=domain_metrics,
            signals=domain_signals,
            related_incidents=related_incidents,
            related_evidence_ids=related_evidence,
            correlations=[
                item
                for item in correlations
                if item.source_domain is domain or item.target_domain is domain
            ],
            business_impact=impact,
            recommended_investigation=recommendation,
            source_status=build.source_status[domain],
            simulator=build.source_status[domain].simulator,
        )

    def signals(
        self,
        *,
        scenario_id: str | None = None,
        incident_id: UUID | None = None,
        domain: OperationsDomain | None = None,
    ) -> list[OperationalSignal]:
        build = self._build(scenario_id=scenario_id, incident_id=incident_id)
        impact = self._business_impact(build)
        priorities = prioritize_signals(build.signals, impact)
        priority_by_signal = {item.signal_id: item.priority for item in priorities}
        result = [
            signal.model_copy(update={"priority": priority_by_signal[signal.signal_id]})
            for signal in build.signals
        ]
        if domain is not None:
            result = [item for item in result if item.domain is domain]
        return sorted(result, key=lambda item: (item.domain.value, item.signal_id))

    def signal(
        self,
        signal_id: str,
        *,
        scenario_id: str | None = None,
        incident_id: UUID | None = None,
    ) -> OperationalSignal:
        for item in self.signals(scenario_id=scenario_id, incident_id=incident_id):
            if item.signal_id == signal_id:
                return item
        raise OperationsNotFoundError(f"Operational signal {signal_id!r} was not found")

    def correlations(
        self,
        *,
        scenario_id: str | None = None,
        incident_id: UUID | None = None,
    ) -> list[CrossDomainCorrelation]:
        return self.snapshot(
            scenario_id=scenario_id, incident_id=incident_id
        ).cross_domain_correlations

    def priorities(
        self,
        *,
        scenario_id: str | None = None,
        incident_id: UUID | None = None,
    ) -> list[PriorityItem]:
        return self.snapshot(scenario_id=scenario_id, incident_id=incident_id).priority_items

    def business_impact(
        self,
        *,
        scenario_id: str | None = None,
        incident_id: UUID | None = None,
    ) -> BusinessImpact:
        return self.snapshot(scenario_id=scenario_id, incident_id=incident_id).business_impact

    def health(
        self,
        *,
        scenario_id: str | None = None,
        incident_id: UUID | None = None,
    ) -> OperationsHealth:
        snapshot = self.snapshot(scenario_id=scenario_id, incident_id=incident_id)
        configured = [
            item.domain
            for item in snapshot.source_status
            if item.status is not SourceAvailability.NOT_CONFIGURED
        ]
        not_configured = [
            item.domain
            for item in snapshot.source_status
            if item.status is SourceAvailability.NOT_CONFIGURED
        ]
        availability = (
            SourceAvailability.NOT_CONFIGURED
            if not configured
            else SourceAvailability.PARTIAL
            if not_configured
            else SourceAvailability.AVAILABLE
        )
        return OperationsHealth(
            status=availability,
            timestamp=snapshot.timestamp,
            configured_domains=configured,
            not_configured_domains=not_configured,
            source_status=snapshot.source_status,
            simulator=snapshot.simulator,
            source=snapshot.source,
        )

    async def investigate_signal(
        self,
        signal_id: str,
        request: InvestigateSignalRequest,
    ) -> InvestigationLaunch:
        if self.incident_service is None or self.investigation_service is None:
            raise OperationsValidationError("Investigation integration is not configured")
        signal = self.signal(signal_id, scenario_id=request.scenario_id)
        scenario_id = request.scenario_id
        if scenario_id is None and signal.signal_id.startswith("simulator:"):
            scenario_id = signal.signal_id.split(":", maxsplit=2)[1]
        if signal.simulator and scenario_id is None:
            raise OperationsValidationError(
                "A simulator scenario_id is required to open a controlled investigation"
            )

        existing_request = (
            self.investigation_service.get_by_request(request.request_id)
            if request.request_id is not None
            else None
        )
        incident_id: UUID | None = None
        if existing_request is not None:
            if existing_request.operations_signal_id != signal.signal_id:
                raise OperationsValidationError(
                    "Investigation request_id is already bound to another operations signal"
                )
            incident_id = existing_request.incident_id
        else:
            key = (scenario_id or "", signal.signal_id)
            with self._signal_incidents_lock:
                incident_id = self._signal_incidents.get(key) or signal.related_incident_id
                if incident_id is None:
                    created = self.incident_service.create_incident(
                        IncidentCreate(
                            title=signal.title,
                            description=(
                                f"{signal.summary} Source: SIMULATED / CONTROLLED DEMONSTRATION."
                                if signal.simulator
                                else signal.summary
                            ),
                            severity=signal.severity,
                            service=signal.related_service or signal.title,
                        )
                    )
                    incident_id = created.id
                    self.repository.add_activity(
                        ActivityEvent(
                            incident_id=incident_id,
                            event_type="operations.investigation.requested",
                            message="Operational signal opened a Phase 5 investigation.",
                            metadata={
                                "signal_id": signal.signal_id,
                                "source": signal.source.source_type.value,
                                "simulator": str(signal.simulator).lower(),
                            },
                        )
                    )
                self._signal_incidents[key] = incident_id
        if incident_id is None:
            raise OperationsValidationError("Could not resolve an incident for the signal")
        context = await self.investigation_service.start(
            incident_id,
            scenario_id=scenario_id,
            request_id=request.request_id,
            auto_handoff=request.auto_handoff,
            operations_signal_id=signal.signal_id,
        )
        return InvestigationLaunch(
            signal_id=signal.signal_id,
            incident_id=incident_id,
            investigation_id=context.investigation_id,
            investigation_status=context.status.value,
            message=(
                "Operational signal opened a Phase 5 investigation; remediation remains "
                "behind the Phase 4 orchestrator approval and verification boundary."
            ),
            scenario_id=scenario_id,
            simulator=signal.simulator,
            source=signal.source,
        )

    def _build(
        self,
        *,
        scenario_id: str | None,
        incident_id: UUID | None,
    ) -> _OperationsBuild:
        timestamp = datetime.now(UTC)
        fixture = self.simulation_runtime.fixture(scenario_id) if scenario_id else None
        incident = self.repository.get_incident(incident_id) if incident_id else None
        if incident_id is not None and incident is None:
            raise OperationsNotFoundError(f"Incident {incident_id} was not found")
        build = _OperationsBuild(
            timestamp=timestamp,
            scenario_id=scenario_id,
            incident_id=incident_id,
            fixture=fixture,
            incident=incident,
            source_status={
                domain: not_configured_source(domain, timestamp) for domain in DOMAIN_ORDER
            },
        )
        if fixture is not None:
            self._append_it_fixture(build, fixture)
            self._append_revenue_fixture(build, fixture)
            self._append_support_fixture(build, fixture)
            self._append_enterprise_simulator(build, fixture)
        if incident is not None:
            self._append_incident(build, incident)
        elif fixture is None:
            for item in self.repository.list_incidents():
                if item.status not in {
                    IncidentStatus.RESOLVED,
                    IncidentStatus.CLOSED,
                    IncidentStatus.CANCELLED,
                }:
                    self._append_incident(build, item)
        return build

    @staticmethod
    def _register_source(
        build: _OperationsBuild,
        domain: OperationsDomain,
        *,
        source_type: SourceType,
        source_name: str,
        message: str,
        simulator: bool,
    ) -> SourceMetadata:
        source = source_metadata(
            source_type=source_type,
            source_name=source_name,
            collected_at=build.timestamp,
            simulator=simulator,
        )
        build.source_status[domain] = OperationsSourceStatus(
            domain=domain,
            source_type=source_type,
            source_name=source_name,
            status=SourceAvailability.AVAILABLE,
            message=message,
            last_updated=build.timestamp,
            simulator=simulator,
            source=source,
        )
        return source

    @staticmethod
    def _add_metric(build: _OperationsBuild, metric: BusinessMetric) -> None:
        if not any(item.metric_id == metric.metric_id for item in build.metrics):
            build.metrics.append(metric)

    @staticmethod
    def _add_signal(build: _OperationsBuild, signal: OperationalSignal) -> None:
        if not any(item.signal_id == signal.signal_id for item in build.signals):
            build.signals.append(signal)

    def _append_incident(self, build: _OperationsBuild, incident: Incident) -> None:
        source = self._register_source(
            build,
            OperationsDomain.IT,
            source_type=SourceType.INCIDENT_SYSTEM,
            source_name="NEXORA incident repository",
            message=(
                "Recorded incident intake is connected; telemetry is limited to stored records."
            ),
            simulator=False,
        )
        evidence_ids = [
            item.evidence_id or str(item.id) for item in self.repository.list_evidence(incident.id)
        ]
        status = (
            OperationalSignalStatus.RESOLVED
            if incident.status in {IncidentStatus.RESOLVED, IncidentStatus.CLOSED}
            else OperationalSignalStatus.ACTIVE
        )
        self._add_signal(
            build,
            OperationalSignal(
                signal_id=f"incident:{incident.id}",
                domain=OperationsDomain.IT,
                kind="incident",
                title=incident.title,
                summary=incident.description,
                status=status,
                severity=incident.severity,
                observed_at=incident.updated_at,
                related_service=incident.service,
                related_incident_id=incident.id,
                evidence_ids=evidence_ids,
                source=source,
                simulator=False,
            ),
        )

    def _append_it_fixture(self, build: _OperationsBuild, fixture: ScenarioFixture) -> None:
        source = self._register_source(
            build,
            OperationsDomain.IT,
            source_type=SourceType.SIMULATOR,
            source_name="ShopFlow simulator / IT operations",
            message="SIMULATED / CONTROLLED DEMONSTRATION; ShopFlow service observations only.",
            simulator=True,
        )
        state = fixture.state
        health_rows: list[ServiceHealth] = []
        for service in state.services:
            service_status = cast(
                Literal["HEALTHY", "DEGRADED", "DOWN", "UNKNOWN"],
                {
                    "healthy": "HEALTHY",
                    "degraded": "DEGRADED",
                    "down": "DOWN",
                }[service.status],
            )
            latency = next(
                (
                    metric.value
                    for metric in state.metrics
                    if metric.service == service.name
                    and ("p95" in metric.name or "latency" in metric.name)
                ),
                None,
            )
            error_rate = next(
                (
                    metric.value
                    for metric in state.metrics
                    if metric.service == service.name
                    and any(
                        token in metric.name
                        for token in ("error_rate", "failure_rate", "timeout_rate")
                    )
                ),
                None,
            )
            health_rows.append(
                ServiceHealth(
                    service=service.name,
                    status=service_status,
                    health_score={
                        "HEALTHY": 100.0,
                        "DEGRADED": 60.0,
                        "DOWN": 0.0,
                    }[service_status],
                    latency_ms=latency,
                    error_rate=error_rate,
                    observed_at=build.timestamp,
                    source=source,
                    simulator=True,
                )
            )
            if service.status != "healthy":
                self._add_signal(
                    build,
                    OperationalSignal(
                        signal_id=f"simulator:{slug(fixture.scenario_id)}:service:{slug(service.name)}",
                        domain=OperationsDomain.IT,
                        kind="service_health",
                        title=f"{service.name} is {service.status}",
                        summary=(
                            f"ShopFlow simulator reports {service.name} as {service.status}. "
                            "This is synthetic service-health data."
                        ),
                        status=OperationalSignalStatus.ACTIVE,
                        severity=Severity.CRITICAL if service.status == "down" else Severity.HIGH,
                        observed_at=build.timestamp,
                        related_service=service.name,
                        evidence_ids=[evidence_ref(fixture.scenario_id, "service", service.name)],
                        source=source,
                        simulator=True,
                    ),
                )
        build.service_health[OperationsDomain.IT] = health_rows

        for metric in state.metrics:
            metric_source = evidence_ref(fixture.scenario_id, "metric", metric.name)
            self._add_metric(
                build,
                BusinessMetric(
                    metric_id=metric_source,
                    domain=OperationsDomain.IT,
                    name=metric.name,
                    value=metric.value,
                    unit=metric.unit,
                    observed_at=metric.observed_at,
                    source=source,
                    simulator=True,
                ),
            )
            name = metric.name.lower()
            is_error = any(token in name for token in ("error", "failure", "timeout", "connection"))
            is_latency = "latency" in name or "p95" in name
            bad_metric = (
                is_error and (metric.value > 0.05 or ("connection" in name and metric.value > 0))
            ) or (is_latency and metric.value > 1_000)
            if bad_metric:
                critical_metric = (
                    (metric.unit == "ratio" and metric.value >= 0.5)
                    or ("connection" in name and metric.value >= 50)
                )
                severity = Severity.CRITICAL if critical_metric else Severity.HIGH
                self._add_signal(
                    build,
                    OperationalSignal(
                        signal_id=f"simulator:{slug(fixture.scenario_id)}:metric:{slug(metric.name)}",
                        domain=OperationsDomain.IT,
                        kind="metric",
                        title=f"{metric.name} is outside the simulated operating range",
                        summary=(
                            f"{metric.name} measured {metric.value:g} {metric.unit}. "
                            "SIMULATED / CONTROLLED DEMONSTRATION only."
                        ),
                        status=OperationalSignalStatus.ACTIVE,
                        severity=severity,
                        observed_at=metric.observed_at,
                        related_service=metric.service,
                        evidence_ids=[metric_source],
                        metrics={metric.name: metric.value},
                        source=source,
                        simulator=True,
                    ),
                )

        for log in state.logs:
            if log.level not in {"ERROR", "WARN"}:
                continue
            severity = Severity.HIGH if log.level == "ERROR" else Severity.MEDIUM
            self._add_signal(
                build,
                OperationalSignal(
                    signal_id=f"simulator:{slug(fixture.scenario_id)}:log:{slug(str(log.id))}",
                    domain=OperationsDomain.IT,
                    kind="log",
                    title=f"{log.service} emitted a {log.level.lower()} signal",
                    summary=(f"{log.message[:500]} SIMULATED / CONTROLLED DEMONSTRATION only."),
                    status=OperationalSignalStatus.ACTIVE,
                    severity=severity,
                    observed_at=log.timestamp,
                    related_service=log.service,
                    evidence_ids=[evidence_ref(fixture.scenario_id, "log", str(log.id))],
                    source=source,
                    simulator=True,
                ),
            )

        for deployment in state.deployments:
            deployment_signal = evidence_ref(fixture.scenario_id, "deployment", str(deployment.id))
            signal_status = (
                OperationalSignalStatus.ACTIVE
                if deployment.status == "failed"
                else OperationalSignalStatus.WATCH
            )
            self._add_signal(
                build,
                OperationalSignal(
                    signal_id=f"simulator:{slug(fixture.scenario_id)}:deployment:{slug(str(deployment.id))}",
                    domain=OperationsDomain.IT,
                    kind="deployment",
                    title=f"Recent {deployment.service} deployment observed",
                    summary=(
                        f"Version {deployment.version} is {deployment.status}: "
                        f"{deployment.change_summary}. "
                        "Relationship to other signals is not causation."
                    ),
                    status=signal_status,
                    severity=Severity.HIGH if deployment.status == "failed" else Severity.MEDIUM,
                    observed_at=deployment.deployed_at,
                    related_service=deployment.service,
                    evidence_ids=[deployment_signal],
                    source=source,
                    simulator=True,
                ),
            )

        for configuration in state.configurations:
            if (
                configuration.expected_value is None
                or configuration.value == configuration.expected_value
            ):
                continue
            configuration_signal = evidence_ref(
                fixture.scenario_id, "configuration", configuration.key
            )
            self._add_signal(
                build,
                OperationalSignal(
                    signal_id=f"simulator:{slug(fixture.scenario_id)}:configuration:{slug(configuration.key)}",
                    domain=OperationsDomain.IT,
                    kind="configuration",
                    title=f"Configuration mismatch: {configuration.key}",
                    summary=(
                        f"The simulator reports {configuration.key} differs from its "
                        "expected value. "
                        "Values are intentionally not exposed in this operations surface."
                    ),
                    status=OperationalSignalStatus.ACTIVE,
                    severity=Severity.HIGH,
                    observed_at=configuration.updated_at,
                    related_service=configuration.service,
                    evidence_ids=[configuration_signal],
                    source=source,
                    simulator=True,
                ),
            )

    def _append_revenue_fixture(self, build: _OperationsBuild, fixture: ScenarioFixture) -> None:
        transactions = fixture.state.transactions
        if not transactions:
            return
        source = self._register_source(
            build,
            OperationsDomain.REVENUE,
            source_type=SourceType.PAYMENT_SYSTEM,
            source_name="ShopFlow simulator / payment system",
            message="SIMULATED / CONTROLLED DEMONSTRATION; no production financial data.",
            simulator=True,
        )
        total, succeeded, failed, failed_amount, currency = transaction_totals(transactions)
        success_rate = safe_ratio(succeeded, total)
        failure_rate = safe_ratio(failed, total)
        observed_at = max(item.timestamp for item in transactions)
        metric_rows = [
            ("transaction_volume", float(total), "transactions"),
            ("successful_transactions", float(succeeded), "transactions"),
            ("failed_transactions", float(failed), "transactions"),
        ]
        if success_rate is not None:
            metric_rows.append(("payment_success_rate", success_rate, "ratio"))
        if failure_rate is not None:
            metric_rows.append(("payment_failure_rate", failure_rate, "ratio"))
        metric_rows.append(("estimated_revenue_exposure", failed_amount, currency or "mixed"))
        for name, value, unit in metric_rows:
            self._add_metric(
                build,
                BusinessMetric(
                    metric_id=f"simulator:{slug(fixture.scenario_id)}:revenue:{slug(name)}",
                    domain=OperationsDomain.REVENUE,
                    name=name,
                    value=value,
                    unit=unit,
                    observed_at=observed_at,
                    source=source,
                    simulator=True,
                ),
            )
        if failed <= 0:
            return
        severity = (
            Severity.CRITICAL if failure_rate is not None and failure_rate >= 0.5 else Severity.HIGH
        )
        self._add_signal(
            build,
            RevenueSignal(
                signal_id=f"simulator:{slug(fixture.scenario_id)}:revenue:payment-failure",
                kind="revenue_anomaly",
                title="Payment transaction failure rate increased",
                summary=(
                    f"{failed} of {total} simulated transactions failed. Estimated exposure is "
                    f"{failed_amount:.2f} {currency or 'mixed currency'}; "
                    "this is not financial reporting."
                ),
                status=OperationalSignalStatus.ACTIVE,
                severity=severity,
                observed_at=observed_at,
                related_service="Payment Service",
                evidence_ids=[
                    evidence_ref(fixture.scenario_id, "transaction", str(item.id))
                    for item in transactions
                ],
                metrics={
                    "transaction_volume": float(total),
                    "failed_transactions": float(failed),
                    "payment_failure_rate": failure_rate or 0.0,
                    "estimated_revenue_exposure": failed_amount,
                },
                source=source,
                simulator=True,
                metric_name="payment_failure_rate",
                metric_value=failure_rate or 0.0,
                currency=currency,
                estimated=True,
            ),
        )

    def _append_support_fixture(self, build: _OperationsBuild, fixture: ScenarioFixture) -> None:
        support = fixture.state.support
        if support is None:
            return
        source = self._register_source(
            build,
            OperationsDomain.SUPPORT,
            source_type=SourceType.SUPPORT_SYSTEM,
            source_name="ShopFlow simulator / support system",
            message="SIMULATED / CONTROLLED DEMONSTRATION; customer-support observations only.",
            simulator=True,
        )
        rows = [
            ("support_tickets", float(support.ticket_volume), "tickets"),
            ("unresolved_tickets", float(support.unresolved_tickets), "tickets"),
            ("escalation_rate", support.escalation_rate, "ratio"),
            ("response_time_minutes", support.response_time_minutes, "minutes"),
            ("resolution_time_minutes", support.resolution_time_minutes, "minutes"),
            ("sentiment_signal", support.sentiment_signal, "ratio"),
            ("affected_customers", float(support.affected_customers), "customers"),
        ]
        for name, value, unit in rows:
            self._add_metric(
                build,
                BusinessMetric(
                    metric_id=f"simulator:{slug(fixture.scenario_id)}:support:{slug(name)}",
                    domain=OperationsDomain.SUPPORT,
                    name=name,
                    value=value,
                    unit=unit,
                    observed_at=support.observed_at,
                    source=source,
                    simulator=True,
                ),
            )
        signal_status = (
            OperationalSignalStatus.ACTIVE
            if support.unresolved_tickets > 0 or support.escalation_rate >= 0.1
            else OperationalSignalStatus.INFO
        )
        self._add_signal(
            build,
            CustomerSignal(
                signal_id=f"simulator:{slug(fixture.scenario_id)}:support:checkout-tickets",
                kind="customer_support",
                title="Checkout-related support activity is elevated",
                summary=(
                    f"{support.ticket_volume} simulated tickets and "
                    f"{support.unresolved_tickets} unresolved "
                    "tickets were observed. This is a related signal, not proof of causation."
                ),
                status=signal_status,
                severity=Severity.HIGH if support.unresolved_tickets >= 20 else Severity.MEDIUM,
                observed_at=support.observed_at,
                related_service="Checkout Service",
                evidence_ids=[evidence_ref(fixture.scenario_id, "support", support.source_id)],
                metrics={
                    "ticket_volume": float(support.ticket_volume),
                    "unresolved_tickets": float(support.unresolved_tickets),
                    "escalation_rate": support.escalation_rate,
                },
                source=source,
                simulator=True,
                affected_customers=support.affected_customers,
                issue_category=support.top_issue_categories[0],
                sentiment=support.sentiment_signal,
            ),
        )

    def _append_enterprise_simulator(
        self, build: _OperationsBuild, fixture: ScenarioFixture
    ) -> None:
        """Add bounded non-IT simulator sources without implying production telemetry."""

        observed_at = build.timestamp
        scenario = fixture.scenario_id
        supply_source = self._register_source(
            build,
            OperationsDomain.SUPPLY_CHAIN,
            source_type=SourceType.INVENTORY_SYSTEM,
            source_name="ShopFlow enterprise operations simulator / inventory",
            message="SIMULATED / CONTROLLED DEMONSTRATION; inventory data is synthetic.",
            simulator=True,
        )
        supply_rows = [
            ("inventory_level", 640.0, "units"),
            ("delayed_shipments", 3.0, "shipments"),
            ("order_backlog", 18.0, "orders"),
            ("fulfillment_delay_hours", 6.0, "hours"),
            ("stockout_risk", 0.12, "ratio"),
        ]
        for name, value, unit in supply_rows:
            self._add_metric(
                build,
                BusinessMetric(
                    metric_id=f"simulator:{slug(scenario)}:supply:{slug(name)}",
                    domain=OperationsDomain.SUPPLY_CHAIN,
                    name=name,
                    value=value,
                    unit=unit,
                    observed_at=observed_at,
                    source=supply_source,
                    simulator=True,
                ),
            )
        self._add_signal(
            build,
            SupplyChainSignal(
                signal_id=f"simulator:{slug(scenario)}:supply:inventory-watch",
                kind="inventory_risk",
                title="Inventory buffer is on watch",
                summary=(
                    "Synthetic inventory observations show delayed shipments and a bounded "
                    "stockout risk."
                ),
                status=OperationalSignalStatus.WATCH,
                severity=Severity.MEDIUM,
                observed_at=observed_at,
                related_service="Inventory",
                evidence_ids=[evidence_ref(scenario, "inventory", "buffer")],
                metrics={"stockout_risk": 0.12, "delayed_shipments": 3.0},
                source=supply_source,
                simulator=True,
                risk_status=SupplyChainRiskStatus.WATCH,
                affected_units=96,
                impact_relevant=False,
            ),
        )

        contract_source = self._register_source(
            build,
            OperationsDomain.CONTRACTS,
            source_type=SourceType.CONTRACT_SYSTEM,
            source_name="ShopFlow enterprise operations simulator / contracts",
            message=(
                "SIMULATED / CONTROLLED DEMONSTRATION; contract signals are operational "
                "reminders only."
            ),
            simulator=True,
        )
        self._add_metric(
            build,
            BusinessMetric(
                metric_id=f"simulator:{slug(scenario)}:contracts:renewal-days",
                domain=OperationsDomain.CONTRACTS,
                name="renewal_days_remaining",
                value=23.0,
                unit="days",
                observed_at=observed_at,
                source=contract_source,
                simulator=True,
            ),
        )
        self._add_signal(
            build,
            ContractSignal(
                signal_id=f"simulator:{slug(scenario)}:contracts:vendor-renewal",
                kind="contract_renewal",
                title="Vendor contract renewal is approaching",
                summary=(
                    "A synthetic vendor renewal has 23 days remaining; this is operational "
                    "tracking, not legal advice."
                ),
                status=OperationalSignalStatus.WATCH,
                severity=Severity.MEDIUM,
                observed_at=observed_at,
                related_service="Payment gateway vendor",
                evidence_ids=[evidence_ref(scenario, "contract", "payment-gateway-renewal")],
                source=contract_source,
                simulator=True,
                contract_status=ContractSignalStatus.RENEWAL_DUE,
                days_remaining=23,
                vendor="ShopFlow payment gateway vendor",
                impact_relevant=False,
            ),
        )

        cloud_source = self._register_source(
            build,
            OperationsDomain.CLOUD,
            source_type=SourceType.CLOUD_SYSTEM,
            source_name="ShopFlow enterprise operations simulator / cloud",
            message=(
                "SIMULATED / CONTROLLED DEMONSTRATION; cost values are estimates, not billing data."
            ),
            simulator=True,
        )
        for name, value, unit in (
            ("compute_utilization", 0.68, "ratio"),
            ("service_availability", 0.997, "ratio"),
            ("estimated_cost", 428.75, "USD"),
            ("unused_resources", 2.0, "resources"),
        ):
            self._add_metric(
                build,
                BusinessMetric(
                    metric_id=f"simulator:{slug(scenario)}:cloud:{slug(name)}",
                    domain=OperationsDomain.CLOUD,
                    name=name,
                    value=value,
                    unit=unit,
                    observed_at=observed_at,
                    source=cloud_source,
                    simulator=True,
                ),
            )
        self._add_signal(
            build,
            CloudSignal(
                signal_id=f"simulator:{slug(scenario)}:cloud:capacity",
                kind="cloud_capacity",
                title="Cloud capacity is within simulated operating range",
                summary=(
                    "Synthetic compute utilization and availability are recorded for "
                    "observation only."
                ),
                status=OperationalSignalStatus.INFO,
                severity=Severity.LOW,
                observed_at=observed_at,
                related_service="ShopFlow cloud",
                evidence_ids=[evidence_ref(scenario, "cloud", "capacity")],
                metrics={"compute_utilization": 0.68, "service_availability": 0.997},
                source=cloud_source,
                simulator=True,
                utilization=0.68,
                estimated_cost=428.75,
                currency="USD",
                impact_relevant=False,
            ),
        )

        data_source = self._register_source(
            build,
            OperationsDomain.DATA,
            source_type=SourceType.DATA_PIPELINE,
            source_name="ShopFlow enterprise operations simulator / data quality",
            message="SIMULATED / CONTROLLED DEMONSTRATION; dataset quality values are synthetic.",
            simulator=True,
        )
        for name, value, unit in (
            ("customer_freshness", 0.94, "ratio"),
            ("customer_completeness", 0.87, "ratio"),
            ("customer_duplicate_rate", 0.032, "ratio"),
            ("schema_violations", 1.0, "violations"),
            ("pipeline_failures", 0.0, "failures"),
        ):
            self._add_metric(
                build,
                BusinessMetric(
                    metric_id=f"simulator:{slug(scenario)}:data:{slug(name)}",
                    domain=OperationsDomain.DATA,
                    name=name,
                    value=value,
                    unit=unit,
                    observed_at=observed_at,
                    source=data_source,
                    simulator=True,
                ),
            )
        self._add_signal(
            build,
            DataQualitySignal(
                signal_id=f"simulator:{slug(scenario)}:data:completeness",
                kind="data_quality",
                title="Customer dataset completeness is below target",
                summary=(
                    "Synthetic customer dataset completeness is 87%; no production dataset "
                    "is being inspected."
                ),
                status=OperationalSignalStatus.WATCH,
                severity=Severity.MEDIUM,
                observed_at=observed_at,
                related_service="Customer dataset",
                evidence_ids=[evidence_ref(scenario, "dataset", "customer-quality")],
                metrics={"completeness": 0.87, "duplicate_rate": 0.032},
                source=data_source,
                simulator=True,
                quality_metric="completeness",
                quality_value=0.87,
                dataset="Customer dataset",
                impact_relevant=False,
            ),
        )

        compliance_source = self._register_source(
            build,
            OperationsDomain.COMPLIANCE,
            source_type=SourceType.COMPLIANCE_SYSTEM,
            source_name="ShopFlow enterprise operations simulator / controls",
            message="SIMULATED / CONTROLLED DEMONSTRATION; findings are not legal conclusions.",
            simulator=True,
        )
        for name, value, unit in (
            ("policy_violations", 1.0, "findings"),
            ("overdue_reviews", 2.0, "reviews"),
            ("missing_control_documents", 1.0, "documents"),
        ):
            self._add_metric(
                build,
                BusinessMetric(
                    metric_id=f"simulator:{slug(scenario)}:compliance:{slug(name)}",
                    domain=OperationsDomain.COMPLIANCE,
                    name=name,
                    value=value,
                    unit=unit,
                    observed_at=observed_at,
                    source=compliance_source,
                    simulator=True,
                ),
            )
        self._add_signal(
            build,
            ComplianceSignal(
                signal_id=f"simulator:{slug(scenario)}:compliance:documentation",
                kind="control_gap",
                title="Synthetic audit evidence documentation gap",
                summary=(
                    "One synthetic control document is missing; this is an operational "
                    "tracking signal, not a legal conclusion."
                ),
                status=OperationalSignalStatus.WATCH,
                severity=Severity.MEDIUM,
                observed_at=observed_at,
                related_service="Audit evidence register",
                evidence_ids=[evidence_ref(scenario, "compliance", "documentation-gap")],
                metrics={"missing_control_documents": 1.0, "overdue_reviews": 2.0},
                source=compliance_source,
                simulator=True,
                compliance_status=ComplianceSignalStatus.AT_RISK,
                control="Audit evidence documentation",
                impact_relevant=False,
            ),
        )

    def _business_impact(self, build: _OperationsBuild) -> BusinessImpact:
        active = [
            item for item in build.signals if signal_is_active(item.status) and item.impact_relevant
        ]
        source = self._snapshot_source(build, list(build.source_status.values()))
        if not active:
            return BusinessImpact(
                impact_level=ImpactLevel.UNKNOWN,
                affected_domains=[],
                affected_services=[],
                operational_scope="No active operational signals are available.",
                explanation=[
                    "No connected source supplied an active signal.",
                    "Missing data is not converted into a business-impact estimate.",
                ],
                source=source,
                simulator=source.simulator,
            )
        domains = [
            domain for domain in DOMAIN_ORDER if any(item.domain is domain for item in active)
        ]
        services = list(
            dict.fromkeys(
                item.related_service for item in active if item.related_service is not None
            )
        )
        customers = [
            item.affected_customers
            for item in active
            if isinstance(item, CustomerSignal) and item.affected_customers > 0
        ]
        revenue_signals = [item for item in active if isinstance(item, RevenueSignal)]
        exposure_values = [
            item.metrics.get("estimated_revenue_exposure", 0.0) for item in revenue_signals
        ]
        estimated_revenue = sum(exposure_values) if exposure_values else None
        currencies = {item.currency for item in revenue_signals if item.currency is not None}
        currency = currencies.pop() if len(currencies) == 1 else None
        highest_severity = max(
            (item.severity for item in active),
            key=lambda value: {
                Severity.LOW: 1,
                Severity.MEDIUM: 2,
                Severity.HIGH: 3,
                Severity.CRITICAL: 4,
            }[value],
        )
        if build.incident is not None:
            highest_severity = max(
                (highest_severity, build.incident.severity),
                key=lambda value: {
                    Severity.LOW: 1,
                    Severity.MEDIUM: 2,
                    Severity.HIGH: 3,
                    Severity.CRITICAL: 4,
                }[value],
            )
        impact_level = {
            Severity.CRITICAL: ImpactLevel.CRITICAL,
            Severity.HIGH: ImpactLevel.HIGH,
            Severity.MEDIUM: ImpactLevel.MEDIUM,
            Severity.LOW: ImpactLevel.LOW,
        }[highest_severity]
        observed = [item.observed_at for item in active]
        duration = max(0.0, min(10_080.0, (build.timestamp - min(observed)).total_seconds() / 60.0))
        explanation = [
            f"{len(active)} active related signal(s) span {len(domains)} domain(s).",
            "Cross-domain relationships are related signals and are not proof of causation.",
        ]
        if estimated_revenue is not None:
            explanation.append(
                "Revenue exposure is a simulator estimate from failed transaction amounts; "
                "it is not financial reporting."
            )
        if customers:
            explanation.append("Customer impact is a bounded simulator support estimate.")
        return BusinessImpact(
            impact_level=impact_level,
            affected_domains=domains,
            affected_services=services,
            estimated_customer_impact=max(customers) if customers else None,
            estimated_revenue_impact=estimated_revenue,
            currency=currency,
            operational_scope=f"{len(domains)} affected domain(s), {len(services)} service(s)",
            duration_minutes=round(duration, 1),
            explanation=explanation,
            source=source,
            simulator=source.simulator,
        )

    def _domain_health(self, build: _OperationsBuild, impact: BusinessImpact) -> list[DomainHealth]:
        result: list[DomainHealth] = []
        for domain in DOMAIN_ORDER:
            signals = [item for item in build.signals if item.domain is domain]
            metrics = [item for item in build.metrics if item.domain is domain]
            source_status = build.source_status[domain]
            domain_impact = self._domain_impact(domain, signals, source_status, impact)
            result.append(
                build_domain_health(
                    domain,
                    signals,
                    metrics,
                    build.service_health.get(domain, []),
                    source_status,
                    domain_impact,
                    source_status.last_updated,
                )
            )
        return result

    @staticmethod
    def _domain_impact(
        domain: OperationsDomain,
        signals: Sequence[OperationalSignal],
        source_status: OperationsSourceStatus,
        impact: BusinessImpact,
    ) -> BusinessImpactSummary:
        if source_status.status is SourceAvailability.NOT_CONFIGURED:
            return BusinessImpactSummary(
                impact_level=ImpactLevel.UNKNOWN,
                explanation="No connected source; no domain impact is inferred.",
                source=source_status.source,
                simulator=source_status.simulator,
            )
        active = [
            item for item in signals if signal_is_active(item.status) and item.impact_relevant
        ]
        if not active:
            return BusinessImpactSummary(
                impact_level=ImpactLevel.LOW,
                explanation="Connected source has no active domain signal.",
                source=source_status.source,
                simulator=source_status.simulator,
            )
        severity = max(
            (item.severity for item in active),
            key=lambda value: [
                Severity.LOW,
                Severity.MEDIUM,
                Severity.HIGH,
                Severity.CRITICAL,
            ].index(value),
        )
        level = {
            Severity.LOW: ImpactLevel.LOW,
            Severity.MEDIUM: ImpactLevel.MEDIUM,
            Severity.HIGH: ImpactLevel.HIGH,
            Severity.CRITICAL: ImpactLevel.CRITICAL,
        }[severity]
        customers = max(
            (item.affected_customers for item in active if isinstance(item, CustomerSignal)),
            default=None,
        )
        revenue = sum(
            item.metrics.get("estimated_revenue_exposure", 0.0)
            for item in active
            if isinstance(item, RevenueSignal)
        )
        has_revenue = any(isinstance(item, RevenueSignal) for item in active)
        currencies = {
            item.currency for item in active if isinstance(item, RevenueSignal) and item.currency
        }
        return BusinessImpactSummary(
            impact_level=level,
            affected_customers=customers,
            estimated_revenue_impact=revenue if has_revenue else None,
            currency=currencies.pop() if len(currencies) == 1 else None,
            explanation=(
                f"{domain.value} has {len(active)} active signal(s); global impact is "
                f"{impact.impact_level.value}."
            ),
            source=active[0].source,
            simulator=active[0].simulator,
        )

    @staticmethod
    def _events(signals: Sequence[OperationalSignal]) -> list[OperationalEvent]:
        events = [
            OperationalEvent(
                event_id=f"event:{signal.signal_id}",
                event_type=f"signal.{signal.kind}",
                summary=signal.summary,
                timestamp=signal.observed_at,
                related_signal_ids=[signal.signal_id],
                simulator=signal.simulator,
                source=signal.source,
            )
            for signal in signals
            if signal_is_active(signal.status)
        ]
        return sorted(events, key=lambda item: item.timestamp, reverse=True)[:100]

    @staticmethod
    def _snapshot_source(
        build: _OperationsBuild, statuses: Sequence[OperationsSourceStatus]
    ) -> SourceMetadata:
        if build.scenario_id is not None:
            return source_metadata(
                source_type=SourceType.SIMULATOR,
                source_name="ShopFlow enterprise operations simulator",
                collected_at=build.timestamp,
                simulator=True,
            )
        available = [
            item.source for item in statuses if item.status is not SourceAvailability.NOT_CONFIGURED
        ]
        if available:
            return available[0]
        return source_metadata(
            source_type=SourceType.NOT_CONFIGURED,
            source_name="No connected operations source",
            collected_at=build.timestamp,
            simulator=False,
            availability=SourceAvailability.NOT_CONFIGURED,
        )


__all__ = [
    "OperationsNotFoundError",
    "OperationsService",
    "OperationsValidationError",
]
