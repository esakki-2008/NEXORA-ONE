"""Canonical, transport-friendly domain models for NEXORA ONE."""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from backend.app.models.enums import (
    ActionStatus,
    AgentState,
    ApprovalStatus,
    EvidenceType,
    HypothesisValidationStatus,
    IncidentStatus,
    RiskLevel,
    Severity,
    VerificationStatus,
)


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp for all generated records."""

    return datetime.now(UTC)


class DomainModel(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)


class Incident(DomainModel):
    id: UUID = Field(default_factory=uuid4)
    tenant_id: str = Field(
        default="reference-tenant",
        min_length=2,
        max_length=64,
        pattern=r"^[a-z0-9][a-z0-9._:-]{1,63}$",
    )
    title: str = Field(min_length=3, max_length=200)
    description: str = Field(min_length=1, max_length=10_000)
    severity: Severity
    status: IncidentStatus = IncidentStatus.OPEN
    service: str = Field(min_length=1, max_length=120)
    agent_state: AgentState = AgentState.INCIDENT_RECEIVED
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class Evidence(DomainModel):
    id: UUID = Field(default_factory=uuid4)
    tenant_id: str = Field(
        default="reference-tenant",
        min_length=2,
        max_length=64,
        pattern=r"^[a-z0-9][a-z0-9._:-]{1,63}$",
    )
    evidence_id: str | None = Field(default=None, min_length=1, max_length=240)
    incident_id: UUID
    type: EvidenceType
    source: str = Field(min_length=1, max_length=240)
    timestamp: datetime
    summary: str = Field(min_length=1, max_length=2_000)
    raw_reference: dict[str, str] = Field(default_factory=dict)
    relevance: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(default=0.75, ge=0.0, le=1.0)
    collected_by: str = Field(default="incident_service", min_length=1, max_length=160)
    collection_status: str = Field(default="COLLECTED", min_length=1, max_length=40)
    metadata: dict[str, str] = Field(default_factory=dict)
    simulated: bool = False
    # ``data`` remains for the Phase 1/2 contract and contains only bounded,
    # structured metadata; raw secret-bearing payloads are never stored here.
    data: dict[str, Any] = Field(default_factory=dict)


class Hypothesis(DomainModel):
    id: UUID = Field(default_factory=uuid4)
    tenant_id: str = Field(
        default="reference-tenant",
        min_length=2,
        max_length=64,
        pattern=r"^[a-z0-9][a-z0-9._:-]{1,63}$",
    )
    incident_id: UUID
    title: str = Field(min_length=3, max_length=200)
    description: str = Field(min_length=1, max_length=5_000)
    confidence: float = Field(ge=0.0, le=1.0)
    supporting_evidence: list[UUID] = Field(default_factory=list)
    contradicting_evidence: list[UUID] = Field(default_factory=list)
    validation_status: HypothesisValidationStatus = HypothesisValidationStatus.UNVALIDATED


class AgentAction(DomainModel):
    id: UUID = Field(default_factory=uuid4)
    tenant_id: str = Field(
        default="reference-tenant",
        min_length=2,
        max_length=64,
        pattern=r"^[a-z0-9][a-z0-9._:-]{1,63}$",
    )
    incident_id: UUID
    agent: str = Field(min_length=1, max_length=120)
    tool: str = Field(min_length=1, max_length=120)
    action: str = Field(min_length=1, max_length=2_000)
    risk_level: RiskLevel
    status: ActionStatus = ActionStatus.PROPOSED
    timestamp: datetime = Field(default_factory=utc_now)
    result: dict[str, Any] | None = None


class Approval(DomainModel):
    id: UUID = Field(default_factory=uuid4)
    tenant_id: str = Field(
        default="reference-tenant",
        min_length=2,
        max_length=64,
        pattern=r"^[a-z0-9][a-z0-9._:-]{1,63}$",
    )
    incident_id: UUID
    action_id: UUID
    requested_at: datetime = Field(default_factory=utc_now)
    approved_at: datetime | None = None
    approved_by: str | None = Field(default=None, max_length=200)
    status: ApprovalStatus = ApprovalStatus.PENDING


class Verification(DomainModel):
    id: UUID = Field(default_factory=uuid4)
    tenant_id: str = Field(
        default="reference-tenant",
        min_length=2,
        max_length=64,
        pattern=r"^[a-z0-9][a-z0-9._:-]{1,63}$",
    )
    incident_id: UUID
    check: str = Field(min_length=1, max_length=500)
    before_state: dict[str, Any] = Field(default_factory=dict)
    after_state: dict[str, Any] = Field(default_factory=dict)
    status: VerificationStatus = VerificationStatus.PENDING
    timestamp: datetime = Field(default_factory=utc_now)


class IncidentReport(DomainModel):
    id: UUID = Field(default_factory=uuid4)
    tenant_id: str = Field(
        default="reference-tenant",
        min_length=2,
        max_length=64,
        pattern=r"^[a-z0-9][a-z0-9._:-]{1,63}$",
    )
    incident_id: UUID
    summary: str = Field(min_length=1, max_length=10_000)
    root_cause: str = Field(min_length=1, max_length=5_000)
    impact: str = Field(min_length=1, max_length=5_000)
    timeline: list[dict[str, Any]] = Field(default_factory=list)
    actions: list[dict[str, Any]] = Field(default_factory=list)
    verification: list[dict[str, Any]] = Field(default_factory=list)
    final_status: IncidentStatus
    created_at: datetime = Field(default_factory=utc_now)


class Service(DomainModel):
    id: UUID = Field(default_factory=uuid4)
    tenant_id: str = Field(
        default="reference-tenant",
        min_length=2,
        max_length=64,
        pattern=r"^[a-z0-9][a-z0-9._:-]{1,63}$",
    )
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=500)
    owner: str = Field(min_length=1, max_length=120)
    status: str = Field(min_length=1, max_length=40)
    environment: str = Field(default="production", min_length=1, max_length=40)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class Deployment(DomainModel):
    id: UUID = Field(default_factory=uuid4)
    tenant_id: str = Field(
        default="reference-tenant",
        min_length=2,
        max_length=64,
        pattern=r"^[a-z0-9][a-z0-9._:-]{1,63}$",
    )
    service_id: UUID
    version: str = Field(min_length=1, max_length=120)
    status: str = Field(min_length=1, max_length=40)
    deployed_at: datetime
    commit_sha: str | None = Field(default=None, max_length=80)


class ConfigurationChange(DomainModel):
    id: UUID = Field(default_factory=uuid4)
    tenant_id: str = Field(
        default="reference-tenant",
        min_length=2,
        max_length=64,
        pattern=r"^[a-z0-9][a-z0-9._:-]{1,63}$",
    )
    service_id: UUID
    key: str = Field(min_length=1, max_length=200)
    previous_value: Any = None
    new_value: Any = None
    changed_at: datetime = Field(default_factory=utc_now)
    changed_by: str = Field(min_length=1, max_length=200)
