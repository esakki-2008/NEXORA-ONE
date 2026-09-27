"""Domain ordering and server-owned operational constants."""

from __future__ import annotations

from backend.app.operations.context import (
    DomainHealthStatus,
    ImpactLevel,
    OperationsDomain,
)

DOMAIN_ORDER: tuple[OperationsDomain, ...] = (
    OperationsDomain.IT,
    OperationsDomain.REVENUE,
    OperationsDomain.SUPPORT,
    OperationsDomain.SUPPLY_CHAIN,
    OperationsDomain.CONTRACTS,
    OperationsDomain.CLOUD,
    OperationsDomain.DATA,
    OperationsDomain.COMPLIANCE,
)

DOMAIN_LABELS: dict[OperationsDomain, str] = {
    OperationsDomain.IT: "IT Operations",
    OperationsDomain.REVENUE: "Revenue",
    OperationsDomain.SUPPORT: "Customer Support",
    OperationsDomain.SUPPLY_CHAIN: "Supply Chain",
    OperationsDomain.CONTRACTS: "Contracts",
    OperationsDomain.CLOUD: "Cloud",
    OperationsDomain.DATA: "Data",
    OperationsDomain.COMPLIANCE: "Compliance",
}

DOMAIN_CRITICALITY: dict[OperationsDomain, float] = {
    OperationsDomain.IT: 1.0,
    OperationsDomain.REVENUE: 0.95,
    OperationsDomain.SUPPORT: 0.75,
    OperationsDomain.SUPPLY_CHAIN: 0.75,
    OperationsDomain.CONTRACTS: 0.65,
    OperationsDomain.CLOUD: 0.8,
    OperationsDomain.DATA: 0.75,
    OperationsDomain.COMPLIANCE: 0.85,
}

IMPACT_ORDER: tuple[ImpactLevel, ...] = (
    ImpactLevel.UNKNOWN,
    ImpactLevel.LOW,
    ImpactLevel.MEDIUM,
    ImpactLevel.HIGH,
    ImpactLevel.CRITICAL,
)

STATUS_ORDER: tuple[DomainHealthStatus, ...] = (
    DomainHealthStatus.NOT_CONFIGURED,
    DomainHealthStatus.UNKNOWN,
    DomainHealthStatus.HEALTHY,
    DomainHealthStatus.WARNING,
    DomainHealthStatus.DEGRADED,
    DomainHealthStatus.CRITICAL,
)


def domain_label(domain: OperationsDomain) -> str:
    return DOMAIN_LABELS[domain]


def worse_impact(left: ImpactLevel, right: ImpactLevel) -> ImpactLevel:
    return left if IMPACT_ORDER.index(left) >= IMPACT_ORDER.index(right) else right


def worse_status(left: DomainHealthStatus, right: DomainHealthStatus) -> DomainHealthStatus:
    return left if STATUS_ORDER.index(left) >= STATUS_ORDER.index(right) else right


__all__ = [
    "DOMAIN_CRITICALITY",
    "DOMAIN_LABELS",
    "DOMAIN_ORDER",
    "domain_label",
    "worse_impact",
    "worse_status",
]
