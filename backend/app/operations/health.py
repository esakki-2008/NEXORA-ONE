"""Deterministic domain-health calculation."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from backend.app.models.enums import Severity
from backend.app.operations.context import (
    BusinessImpactSummary,
    BusinessMetric,
    DomainHealth,
    DomainHealthStatus,
    OperationalSignal,
    OperationalSignalStatus,
    OperationsDomain,
    OperationsSourceStatus,
    ServiceHealth,
)
from backend.app.operations.signals import signal_is_active

_SEVERITY_PENALTY = {
    Severity.CRITICAL: 60.0,
    Severity.HIGH: 32.0,
    Severity.MEDIUM: 16.0,
    Severity.LOW: 5.0,
}


def build_domain_health(
    domain: OperationsDomain,
    signals: Sequence[OperationalSignal],
    metrics: Sequence[BusinessMetric],
    service_health: Sequence[ServiceHealth],
    source_status: OperationsSourceStatus,
    impact: BusinessImpactSummary,
    last_updated: datetime | None,
) -> DomainHealth:
    """Build one domain posture without treating missing data as healthy."""

    active_ids = [item.signal_id for item in signals if signal_is_active(item.status)]
    critical_ids = [
        item.signal_id for item in signals if item.severity is Severity.CRITICAL
    ]

    if source_status.status.value == "NOT_CONFIGURED":
        status = DomainHealthStatus.NOT_CONFIGURED
        score = None
    elif source_status.status.value == "FAILED":
        status = DomainHealthStatus.UNKNOWN
        score = None
    elif not signals and not service_health and not metrics:
        status = DomainHealthStatus.UNKNOWN
        score = None
    else:
        penalty = sum(
            _SEVERITY_PENALTY[item.severity]
            + (8.0 if item.status is OperationalSignalStatus.WATCH else 0.0)
            for item in signals
            if signal_is_active(item.status)
        )
        score = round(max(0.0, min(100.0, 100.0 - penalty)), 1)
        if critical_ids:
            status = DomainHealthStatus.CRITICAL
        elif any(
            item.severity is Severity.HIGH and signal_is_active(item.status) for item in signals
        ):
            status = DomainHealthStatus.DEGRADED
        elif any(signal_is_active(item.status) for item in signals):
            status = DomainHealthStatus.WARNING
        else:
            status = DomainHealthStatus.HEALTHY

    return DomainHealth(
        domain=domain,
        status=status,
        health_score=score,
        active_signals=active_ids,
        critical_signals=critical_ids,
        business_impact=impact,
        last_updated=last_updated,
        source=source_status.source,
        simulator=source_status.simulator,
        service_health=list(service_health),
    )


__all__ = ["build_domain_health"]
