"""Explainable deterministic enterprise prioritization."""

from __future__ import annotations

from collections.abc import Sequence

from backend.app.models.enums import Severity
from backend.app.operations.context import (
    BusinessImpact,
    OperationalSignal,
    OperationalSignalStatus,
    PriorityItem,
    PriorityLevel,
)
from backend.app.operations.domains import DOMAIN_CRITICALITY
from backend.app.operations.signals import signal_is_active

_SEVERITY_FACTOR = {
    Severity.CRITICAL: 1.0,
    Severity.HIGH: 0.82,
    Severity.MEDIUM: 0.58,
    Severity.LOW: 0.3,
}
_IMPACT_FACTOR = {
    "CRITICAL": 1.0,
    "HIGH": 0.82,
    "MEDIUM": 0.58,
    "LOW": 0.3,
    "UNKNOWN": 0.15,
}


def _priority_for_score(score: float) -> PriorityLevel:
    if score >= 0.82:
        return PriorityLevel.CRITICAL
    if score >= 0.62:
        return PriorityLevel.HIGH
    if score >= 0.36:
        return PriorityLevel.MEDIUM
    return PriorityLevel.LOW


def prioritize_signals(
    signals: Sequence[OperationalSignal], impact: BusinessImpact
) -> list[PriorityItem]:
    """Rank signals using only server-owned factors."""

    items: list[PriorityItem] = []
    for signal in signals:
        severity = _SEVERITY_FACTOR[signal.severity]
        impact_factor = _IMPACT_FACTOR[impact.impact_level.value]
        customer_factor = min(1.0, (impact.estimated_customer_impact or 0) / 100.0)
        revenue_factor = min(1.0, (impact.estimated_revenue_impact or 0.0) / 1_000.0)
        scope_factor = min(
            1.0,
            (len(impact.affected_domains) + len(impact.affected_services)) / 8.0,
        )
        confidence_factor = 0.9 if signal.source.simulator else 0.75
        urgency_factor = (
            1.0
            if signal.status is OperationalSignalStatus.ACTIVE
            else 0.7
            if signal.status is OperationalSignalStatus.WATCH
            else 0.25
        )
        domain_factor = DOMAIN_CRITICALITY[signal.domain]
        score = round(
            min(
                1.0,
                0.25 * severity
                + 0.2 * impact_factor
                + 0.12 * customer_factor
                + 0.12 * revenue_factor
                + 0.1 * scope_factor
                + 0.08 * confidence_factor
                + 0.08 * urgency_factor
                + 0.05 * domain_factor,
            ),
            4,
        )
        priority = _priority_for_score(score)
        items.append(
            PriorityItem(
                priority_id=f"priority:{signal.signal_id}",
                signal_id=signal.signal_id,
                domain=signal.domain,
                title=signal.title,
                priority=priority,
                score=score,
                factors={
                    "severity": severity,
                    "business_impact": impact_factor,
                    "customer_impact": customer_factor,
                    "revenue_impact": revenue_factor,
                    "affected_scope": scope_factor,
                    "confidence": confidence_factor,
                    "urgency": urgency_factor,
                    "domain_criticality": domain_factor,
                },
                explanation=(
                    "Priority is server-calculated from severity, business impact, "
                    "customer/revenue exposure, scope, source confidence, and urgency; "
                    "it is not an AI-generated ranking."
                ),
                simulator=signal.simulator,
                source=signal.source,
            )
        )

    return sorted(items, key=lambda item: (-item.score, item.priority_id))


def active_signal(signal: OperationalSignal) -> bool:
    """Expose the shared active predicate for snapshot filtering."""

    return signal_is_active(signal.status)


__all__ = ["active_signal", "prioritize_signals"]
