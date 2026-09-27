"""Deterministic cross-domain signal relationships."""

from __future__ import annotations

from collections.abc import Sequence

from backend.app.operations.context import (
    CrossDomainCorrelation,
    OperationalSignal,
    OperationsDomain,
    RelationshipType,
)


def _pair(
    source: OperationalSignal,
    target: OperationalSignal,
    relationship: RelationshipType,
    explanation: str,
    confidence: float,
) -> CrossDomainCorrelation:
    source_ids = list(dict.fromkeys([*source.evidence_ids, *target.evidence_ids]))
    return CrossDomainCorrelation(
        correlation_id=f"correlation:{source.signal_id}:{target.signal_id}",
        source_domain=source.domain,
        target_domain=target.domain,
        source_signal=source.signal_id,
        target_signal=target.signal_id,
        relationship_type=relationship,
        temporal_relationship="Signals were observed within the same bounded observation window.",
        confidence=confidence,
        explanation=(
            f"{explanation} This is a related-signal relationship, not proof of causation."
        ),
        evidence_ids=source_ids[:40],
        simulator=source.simulator or target.simulator,
        source=source.source if source.simulator else target.source,
    )


def build_correlations(signals: Sequence[OperationalSignal]) -> list[CrossDomainCorrelation]:
    """Correlate known payment/checkout relationships without causal claims."""

    by_domain: dict[OperationsDomain, list[OperationalSignal]] = {}
    for signal in signals:
        by_domain.setdefault(signal.domain, []).append(signal)

    correlations: list[CrossDomainCorrelation] = []
    it_signals = by_domain.get(OperationsDomain.IT, [])
    revenue_signals = by_domain.get(OperationsDomain.REVENUE, [])
    support_signals = by_domain.get(OperationsDomain.SUPPORT, [])

    payment_it = next(
        (
            item
            for item in it_signals
            if "payment" in f"{item.title} {item.summary}".lower()
            or item.related_service == "Payment Service"
        ),
        None,
    )
    revenue = next(iter(revenue_signals), None)
    support = next(iter(support_signals), None)

    if payment_it is not None and revenue is not None:
        correlations.append(
            _pair(
                payment_it,
                revenue,
                RelationshipType.BUSINESS_IMPACT,
                "Payment-service errors and transaction-failure metrics are related to "
                "the observed revenue signal.",
                0.88,
            )
        )
    if revenue is not None and support is not None:
        correlations.append(
            _pair(
                revenue,
                support,
                RelationshipType.TEMPORAL,
                "Transaction failures and checkout-related support activity share the "
                "observation window.",
                0.81,
            )
        )
    if payment_it is not None and support is not None:
        correlations.append(
            _pair(
                payment_it,
                support,
                RelationshipType.SERVICE_DEPENDENCY,
                "Payment and checkout support signals reference the same simulated customer path.",
                0.77,
            )
        )

    deployment = next((item for item in it_signals if item.kind == "deployment"), None)
    if deployment is not None and revenue is not None:
        correlations.append(
            _pair(
                deployment,
                revenue,
                RelationshipType.TEMPORAL,
                "A deployment observation and the revenue signal are temporally proximate.",
                0.74,
            )
        )

    return correlations


__all__ = ["build_correlations"]
