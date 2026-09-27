"""Public contracts for the Phase 6 enterprise operations layer.

Operations records are intentionally informational. They carry source metadata on
 every object, use bounded numeric fields, and contain no command or execution
payloads. Simulator records are visibly classified as controlled demonstration
observations.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.app.models.enums import Severity


class OperationsModel(BaseModel):
    """Strict base contract for all operations responses."""

    model_config = ConfigDict(extra="forbid", from_attributes=True)


def operations_now() -> datetime:
    """Return a timezone-aware timestamp for server-generated records."""

    return datetime.now(UTC)


class OperationsDomain(StrEnum):
    IT = "IT"
    REVENUE = "REVENUE"
    SUPPORT = "SUPPORT"
    SUPPLY_CHAIN = "SUPPLY_CHAIN"
    CONTRACTS = "CONTRACTS"
    CLOUD = "CLOUD"
    DATA = "DATA"
    COMPLIANCE = "COMPLIANCE"


class DomainHealthStatus(StrEnum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"
    UNKNOWN = "UNKNOWN"
    NOT_CONFIGURED = "NOT_CONFIGURED"


class OperationalSignalStatus(StrEnum):
    ACTIVE = "ACTIVE"
    WATCH = "WATCH"
    INFO = "INFO"
    RESOLVED = "RESOLVED"


class PriorityLevel(StrEnum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class ImpactLevel(StrEnum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    UNKNOWN = "UNKNOWN"


class RelationshipType(StrEnum):
    TEMPORAL = "TEMPORAL"
    SERVICE_DEPENDENCY = "SERVICE_DEPENDENCY"
    BUSINESS_IMPACT = "BUSINESS_IMPACT"
    SHARED_RESOURCE = "SHARED_RESOURCE"
    SHARED_IDENTIFIER = "SHARED_IDENTIFIER"
    POSSIBLE_CAUSAL = "POSSIBLE_CAUSAL"
    UNKNOWN = "UNKNOWN"


class SourceType(StrEnum):
    SIMULATOR = "SIMULATOR"
    INCIDENT_SYSTEM = "INCIDENT_SYSTEM"
    MONITORING = "MONITORING"
    PAYMENT_SYSTEM = "PAYMENT_SYSTEM"
    SUPPORT_SYSTEM = "SUPPORT_SYSTEM"
    INVENTORY_SYSTEM = "INVENTORY_SYSTEM"
    CONTRACT_SYSTEM = "CONTRACT_SYSTEM"
    CLOUD_SYSTEM = "CLOUD_SYSTEM"
    DATA_PIPELINE = "DATA_PIPELINE"
    COMPLIANCE_SYSTEM = "COMPLIANCE_SYSTEM"
    NOT_CONFIGURED = "NOT_CONFIGURED"


class SourceAvailability(StrEnum):
    AVAILABLE = "AVAILABLE"
    PARTIAL = "PARTIAL"
    NOT_CONFIGURED = "NOT_CONFIGURED"
    FAILED = "FAILED"


class SupplyChainRiskStatus(StrEnum):
    NORMAL = "NORMAL"
    WATCH = "WATCH"
    AT_RISK = "AT_RISK"
    CRITICAL = "CRITICAL"


class ContractSignalStatus(StrEnum):
    CURRENT = "CURRENT"
    RENEWAL_DUE = "RENEWAL_DUE"
    SLA_AT_RISK = "SLA_AT_RISK"
    EXPIRED = "EXPIRED"
    MISSING_DOCUMENTATION = "MISSING_DOCUMENTATION"


class ComplianceSignalStatus(StrEnum):
    COMPLIANT = "COMPLIANT"
    WATCH = "WATCH"
    AT_RISK = "AT_RISK"
    NON_COMPLIANT = "NON_COMPLIANT"
    UNKNOWN = "UNKNOWN"


class SourceMetadata(OperationsModel):
    """Provenance attached to every public operations record."""

    source_type: SourceType
    source_name: str = Field(min_length=1, max_length=160)
    label: str = Field(min_length=1, max_length=240)
    collected_at: datetime = Field(default_factory=operations_now)
    availability: SourceAvailability = SourceAvailability.AVAILABLE
    simulator: bool = False


class OperationsSourceStatus(OperationsModel):
    """Source availability without implying health when a source is absent."""

    domain: OperationsDomain
    source_type: SourceType
    source_name: str = Field(min_length=1, max_length=160)
    status: SourceAvailability
    message: str = Field(min_length=1, max_length=500)
    last_updated: datetime | None = None
    simulator: bool = False
    source: SourceMetadata


class BusinessImpactSummary(OperationsModel):
    """Compact impact information embedded in a domain health record."""

    impact_level: ImpactLevel
    affected_customers: int | None = Field(default=None, ge=0)
    estimated_revenue_impact: float | None = None
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    explanation: str = Field(min_length=1, max_length=600)
    source: SourceMetadata
    simulator: bool = False

    @field_validator("estimated_revenue_impact")
    @classmethod
    def validate_revenue(cls, value: float | None) -> float | None:
        if value is not None and (not math.isfinite(value) or value < 0):
            raise ValueError("estimated revenue impact must be finite and non-negative")
        return value


class BusinessMetric(OperationsModel):
    """A bounded metric with explicit units and provenance."""

    metric_id: str = Field(min_length=3, max_length=200)
    domain: OperationsDomain
    name: str = Field(min_length=1, max_length=160)
    value: float
    unit: str = Field(min_length=1, max_length=80)
    baseline: float | None = None
    delta: float | None = None
    observed_at: datetime
    source: SourceMetadata
    simulator: bool = False

    @field_validator("value", "baseline", "delta")
    @classmethod
    def validate_numbers(cls, value: float | None) -> float | None:
        if value is not None and not math.isfinite(value):
            raise ValueError("metric values must be finite")
        return value


class ServiceHealth(OperationsModel):
    """Health for one IT service, separate from domain health."""

    service: str = Field(min_length=1, max_length=160)
    status: Literal["HEALTHY", "DEGRADED", "DOWN", "UNKNOWN"]
    health_score: float | None = Field(default=None, ge=0, le=100)
    latency_ms: float | None = None
    error_rate: float | None = None
    observed_at: datetime | None = None
    source: SourceMetadata
    simulator: bool = False

    @field_validator("latency_ms", "error_rate")
    @classmethod
    def validate_health_numbers(cls, value: float | None) -> float | None:
        if value is not None and (not math.isfinite(value) or value < 0):
            raise ValueError("service health values must be finite and non-negative")
        return value


class OperationalSignal(OperationsModel):
    """A server-generated signal, never an executable recommendation."""

    signal_id: str = Field(min_length=3, max_length=240)
    domain: OperationsDomain
    kind: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=3, max_length=240)
    summary: str = Field(min_length=1, max_length=1_500)
    status: OperationalSignalStatus
    severity: Severity
    priority: PriorityLevel = PriorityLevel.LOW
    observed_at: datetime
    related_service: str | None = Field(default=None, max_length=160)
    related_incident_id: UUID | None = None
    evidence_ids: list[str] = Field(default_factory=list, max_length=30)
    metrics: dict[str, float] = Field(default_factory=dict, max_length=20)
    business_impact: BusinessImpactSummary | None = None
    source: SourceMetadata
    simulator: bool = False
    impact_relevant: bool = True

    @field_validator("metrics")
    @classmethod
    def validate_metrics(cls, value: dict[str, float]) -> dict[str, float]:
        if any(not math.isfinite(item) for item in value.values()):
            raise ValueError("signal metrics must be finite")
        return value


class RevenueSignal(OperationalSignal):
    """Payment and revenue signal with explicit estimate semantics."""

    domain: Literal[OperationsDomain.REVENUE] = OperationsDomain.REVENUE
    metric_name: str = Field(min_length=1, max_length=160)
    metric_value: float
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    estimated: bool = True

    @field_validator("metric_value")
    @classmethod
    def validate_metric_value(cls, value: float) -> float:
        if not math.isfinite(value) or value < 0:
            raise ValueError("revenue signal values must be finite and non-negative")
        return value


class CustomerSignal(OperationalSignal):
    """Support and customer-experience signal."""

    domain: Literal[OperationsDomain.SUPPORT] = OperationsDomain.SUPPORT
    affected_customers: int = Field(default=0, ge=0)
    issue_category: str = Field(min_length=1, max_length=160)
    sentiment: float | None = Field(default=None, ge=-1, le=1)


class SupplyChainSignal(OperationalSignal):
    """Bounded inventory and fulfillment signal."""

    domain: Literal[OperationsDomain.SUPPLY_CHAIN] = OperationsDomain.SUPPLY_CHAIN
    risk_status: SupplyChainRiskStatus
    affected_units: int | None = Field(default=None, ge=0)


class ContractSignal(OperationalSignal):
    """Operational contract signal, not legal advice."""

    domain: Literal[OperationsDomain.CONTRACTS] = OperationsDomain.CONTRACTS
    contract_status: ContractSignalStatus
    days_remaining: int | None = None
    vendor: str = Field(min_length=1, max_length=160)

    @field_validator("days_remaining")
    @classmethod
    def validate_days(cls, value: int | None) -> int | None:
        if value is not None and value < 0:
            raise ValueError("contract days remaining cannot be negative")
        return value


class CloudSignal(OperationalSignal):
    """Simulator-backed cloud operations signal."""

    domain: Literal[OperationsDomain.CLOUD] = OperationsDomain.CLOUD
    utilization: float | None = Field(default=None, ge=0, le=1)
    estimated_cost: float | None = None
    currency: str | None = Field(default=None, min_length=3, max_length=3)

    @field_validator("estimated_cost")
    @classmethod
    def validate_cost(cls, value: float | None) -> float | None:
        if value is not None and (not math.isfinite(value) or value < 0):
            raise ValueError("estimated cost must be finite and non-negative")
        return value


class DataQualitySignal(OperationalSignal):
    """Data-quality signal with percentages represented as ratios."""

    domain: Literal[OperationsDomain.DATA] = OperationsDomain.DATA
    quality_metric: str = Field(min_length=1, max_length=160)
    quality_value: float = Field(ge=0, le=1)
    dataset: str = Field(min_length=1, max_length=160)


class ComplianceSignal(OperationalSignal):
    """Operational control signal without a legal conclusion."""

    domain: Literal[OperationsDomain.COMPLIANCE] = OperationsDomain.COMPLIANCE
    compliance_status: ComplianceSignalStatus
    control: str = Field(min_length=1, max_length=160)


class BusinessImpact(OperationsModel):
    """Deterministic cross-domain business impact estimate."""

    impact_level: ImpactLevel
    affected_domains: list[OperationsDomain]
    affected_services: list[str]
    estimated_customer_impact: int | None = Field(default=None, ge=0)
    estimated_revenue_impact: float | None = None
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    operational_scope: str = Field(min_length=1, max_length=400)
    duration_minutes: float | None = None
    explanation: list[str] = Field(min_length=1, max_length=12)
    source: SourceMetadata
    simulator: bool = False

    @field_validator("estimated_revenue_impact", "duration_minutes")
    @classmethod
    def validate_impact_numbers(cls, value: float | None, info: object) -> float | None:
        if value is not None and (not math.isfinite(value) or value < 0):
            raise ValueError("impact values must be finite and non-negative")
        return value


class DomainHealth(OperationsModel):
    """Health posture for exactly one enterprise domain."""

    domain: OperationsDomain
    status: DomainHealthStatus
    health_score: float | None = Field(default=None, ge=0, le=100)
    active_signals: list[str] = Field(default_factory=list, max_length=100)
    critical_signals: list[str] = Field(default_factory=list, max_length=100)
    business_impact: BusinessImpactSummary
    last_updated: datetime | None = None
    source: SourceMetadata
    simulator: bool = False
    service_health: list[ServiceHealth] = Field(default_factory=list, max_length=100)


class CrossDomainCorrelation(OperationsModel):
    """Relationship between signals; explicitly not proof of causation."""

    correlation_id: str = Field(min_length=3, max_length=240)
    source_domain: OperationsDomain
    target_domain: OperationsDomain
    source_signal: str = Field(min_length=3, max_length=240)
    target_signal: str = Field(min_length=3, max_length=240)
    relationship_type: RelationshipType
    temporal_relationship: str = Field(min_length=1, max_length=500)
    confidence: float = Field(ge=0, le=1)
    explanation: str = Field(min_length=1, max_length=1_000)
    evidence_ids: list[str] = Field(default_factory=list, max_length=40)
    simulator: bool = False
    source: SourceMetadata


class PriorityItem(OperationsModel):
    """Explainable priority for one operational signal."""

    priority_id: str = Field(min_length=3, max_length=240)
    signal_id: str = Field(min_length=3, max_length=240)
    domain: OperationsDomain
    title: str = Field(min_length=3, max_length=240)
    priority: PriorityLevel
    score: float = Field(ge=0, le=1)
    factors: dict[str, float] = Field(min_length=1, max_length=20)
    explanation: str = Field(min_length=1, max_length=1_000)
    simulator: bool = False
    source: SourceMetadata

    @field_validator("factors")
    @classmethod
    def validate_factors(cls, value: dict[str, float]) -> dict[str, float]:
        if any(not math.isfinite(item) or item < 0 or item > 1 for item in value.values()):
            raise ValueError("priority factors must be finite ratios")
        return value


class OperationalEvent(OperationsModel):
    """Recent observable event in the enterprise snapshot."""

    event_id: str = Field(min_length=3, max_length=240)
    event_type: str = Field(min_length=1, max_length=120)
    summary: str = Field(min_length=1, max_length=600)
    timestamp: datetime
    related_signal_ids: list[str] = Field(default_factory=list, max_length=30)
    simulator: bool = False
    source: SourceMetadata


class DomainDetail(OperationsModel):
    """Domain drill-down response assembled from the same snapshot engine."""

    health: DomainHealth
    metrics: list[BusinessMetric]
    signals: list[OperationalSignal]
    related_incidents: list[UUID]
    related_evidence_ids: list[str]
    correlations: list[CrossDomainCorrelation]
    business_impact: BusinessImpact
    recommended_investigation: str | None = None
    source_status: OperationsSourceStatus
    simulator: bool = False


class OperationalSnapshot(OperationsModel):
    """Unified server-generated enterprise operations snapshot."""

    timestamp: datetime
    overall_status: DomainHealthStatus
    domains: list[DomainHealth] = Field(min_length=8, max_length=8)
    critical_signals: list[OperationalSignal] = Field(default_factory=list, max_length=100)
    business_impact: BusinessImpact
    cross_domain_correlations: list[CrossDomainCorrelation] = Field(
        default_factory=list, max_length=100
    )
    priority_items: list[PriorityItem] = Field(default_factory=list, max_length=100)
    recent_events: list[OperationalEvent] = Field(default_factory=list, max_length=100)
    source_status: list[OperationsSourceStatus] = Field(min_length=8, max_length=20)
    scenario_id: str | None = Field(default=None, max_length=100)
    incident_id: UUID | None = None
    simulator: bool = False
    source: SourceMetadata
    refresh_id: str = Field(min_length=3, max_length=120)


class OperationsHealth(OperationsModel):
    """Health endpoint for the operations data boundary."""

    status: SourceAvailability
    timestamp: datetime
    configured_domains: list[OperationsDomain]
    not_configured_domains: list[OperationsDomain]
    source_status: list[OperationsSourceStatus]
    simulator: bool = False
    source: SourceMetadata


class InvestigateSignalRequest(OperationsModel):
    """Request to open Phase 5 investigation for a signal."""

    scenario_id: str | None = Field(default=None, max_length=100)
    request_id: str | None = Field(default=None, min_length=3, max_length=160)
    auto_handoff: bool = False


class InvestigationLaunch(OperationsModel):
    """Result of a safe Operations → Phase 5 investigation transition."""

    signal_id: str
    incident_id: UUID
    investigation_id: UUID
    investigation_status: str
    message: str
    scenario_id: str | None
    simulator: bool
    source: SourceMetadata


__all__ = [
    "BusinessImpact",
    "BusinessImpactSummary",
    "BusinessMetric",
    "ComplianceSignal",
    "ComplianceSignalStatus",
    "ContractSignal",
    "ContractSignalStatus",
    "CrossDomainCorrelation",
    "CustomerSignal",
    "DataQualitySignal",
    "DomainDetail",
    "DomainHealth",
    "DomainHealthStatus",
    "ImpactLevel",
    "InvestigationLaunch",
    "InvestigateSignalRequest",
    "OperationalEvent",
    "OperationalSignal",
    "OperationalSignalStatus",
    "OperationalSnapshot",
    "OperationsDomain",
    "OperationsHealth",
    "OperationsSourceStatus",
    "PriorityItem",
    "PriorityLevel",
    "RelationshipType",
    "RevenueSignal",
    "ServiceHealth",
    "SourceAvailability",
    "SourceMetadata",
    "SourceType",
    "SupplyChainRiskStatus",
    "SupplyChainSignal",
]
