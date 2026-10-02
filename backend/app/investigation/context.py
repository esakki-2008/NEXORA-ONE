"""Public, secret-free contracts for Phase 5 investigation intelligence."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from backend.app.ai.schemas import AIHealthStatus
from backend.app.models.domain import Incident, utc_now


class InvestigationStatus(StrEnum):
    CREATED = "CREATED"
    COLLECTING = "COLLECTING"
    ANALYZING = "ANALYZING"
    COMPLETED = "COMPLETED"
    INCONCLUSIVE = "INCONCLUSIVE"
    REQUIRES_HUMAN = "REQUIRES_HUMAN"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class InvestigationEvidenceType(StrEnum):
    LOG = "LOG"
    METRIC = "METRIC"
    DEPLOYMENT = "DEPLOYMENT"
    CONFIGURATION = "CONFIGURATION"
    HEALTH_CHECK = "HEALTH_CHECK"
    TRANSACTION = "TRANSACTION"
    DOCUMENTATION = "DOCUMENTATION"
    TEST_RESULT = "TEST_RESULT"
    ALERT = "ALERT"
    CUSTOMER_SIGNAL = "CUSTOMER_SIGNAL"
    SYSTEM_EVENT = "SYSTEM_EVENT"


class EvidenceCollectionStatus(StrEnum):
    COLLECTED = "COLLECTED"
    FAILED = "FAILED"
    NOT_AVAILABLE = "NOT_AVAILABLE"
    REJECTED = "REJECTED"


class InvestigationHypothesisStatus(StrEnum):
    PROPOSED = "PROPOSED"
    TESTING = "TESTING"
    SUPPORTED = "SUPPORTED"
    REJECTED = "REJECTED"
    INCONCLUSIVE = "INCONCLUSIVE"


class InvestigationHandoffStatus(StrEnum):
    NOT_READY = "NOT_READY"
    READY = "READY"
    HANDED_OFF = "HANDED_OFF"
    REQUIRES_HUMAN = "REQUIRES_HUMAN"
    FAILED = "FAILED"


class EvidenceRecord(BaseModel):
    """Normalized evidence with provenance and explicit simulator labeling."""

    model_config = ConfigDict(extra="forbid")

    evidence_id: str = Field(min_length=1, max_length=240)
    incident_id: UUID
    source: str = Field(min_length=1, max_length=240)
    evidence_type: InvestigationEvidenceType
    timestamp: datetime
    summary: str = Field(min_length=1, max_length=2_000)
    raw_reference: dict[str, str] = Field(default_factory=dict)
    relevance: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    collected_by: str = Field(min_length=1, max_length=160)
    collection_status: EvidenceCollectionStatus = EvidenceCollectionStatus.COLLECTED
    metadata: dict[str, str] = Field(default_factory=dict)
    simulated: bool = False


class CorrelationRecord(BaseModel):
    """Explainable relationship between two or more evidence records."""

    model_config = ConfigDict(extra="forbid")

    correlation_id: UUID = Field(default_factory=uuid4)
    incident_id: UUID
    evidence_ids: list[str] = Field(min_length=2, max_length=20)
    relationship: str = Field(min_length=1, max_length=120)
    reason: str = Field(min_length=1, max_length=1_000)
    dimensions: list[str] = Field(min_length=1, max_length=12)
    strength: float = Field(ge=0.0, le=1.0)
    temporal_delta_seconds: int | None = Field(default=None, ge=0)
    created_at: datetime = Field(default_factory=utc_now)


class InvestigationHypothesis(BaseModel):
    """Server-owned hypothesis lifecycle; AI proposals are never authoritative."""

    model_config = ConfigDict(extra="forbid")

    hypothesis_id: UUID = Field(default_factory=uuid4)
    incident_id: UUID
    title: str = Field(min_length=3, max_length=240)
    description: str = Field(min_length=1, max_length=3_000)
    domain: str = Field(min_length=1, max_length=80)
    supporting_evidence: list[str] = Field(default_factory=list, max_length=80)
    contradicting_evidence: list[str] = Field(default_factory=list, max_length=80)
    missing_evidence: list[str] = Field(default_factory=list, max_length=40)
    confidence: float = Field(ge=0.0, le=1.0)
    confidence_factors: dict[str, float] = Field(default_factory=dict)
    status: InvestigationHypothesisStatus = InvestigationHypothesisStatus.PROPOSED
    priority: str = Field(default="MEDIUM", min_length=1, max_length=20)
    next_validation_step: str | None = Field(default=None, max_length=500)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class RootCauseCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_id: UUID = Field(default_factory=uuid4)
    hypothesis_id: UUID
    title: str = Field(min_length=3, max_length=240)
    summary: str = Field(min_length=1, max_length=2_000)
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_ids: list[str] = Field(default_factory=list, max_length=80)
    qualification: str = "Root-cause candidate"


class ConfidenceAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    confidence: float = Field(ge=0.0, le=1.0)
    factors: dict[str, float] = Field(default_factory=dict)
    explanation: list[str] = Field(default_factory=list, max_length=20)
    calculated_at: datetime = Field(default_factory=utc_now)


class InvestigationTimelineEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: UUID = Field(default_factory=uuid4)
    incident_id: UUID
    event_type: str = Field(min_length=1, max_length=100)
    timestamp: datetime = Field(default_factory=utc_now)
    actor: str = Field(min_length=1, max_length=160)
    summary: str = Field(min_length=1, max_length=500)
    related_evidence_ids: list[str] = Field(default_factory=list, max_length=80)
    status: str = Field(default="RECORDED", min_length=1, max_length=40)


class InvestigationHandoff(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: InvestigationHandoffStatus = InvestigationHandoffStatus.NOT_READY
    orchestrator_state: str | None = None
    message: str | None = Field(default=None, max_length=1_000)
    handed_off_at: datetime | None = None


class InvestigationContext(BaseModel):
    """Complete operational investigation context safe to expose to the UI."""

    model_config = ConfigDict(extra="forbid")

    investigation_id: UUID
    tenant_id: str = Field(
        default="reference-tenant",
        min_length=2,
        max_length=64,
        pattern=r"^[a-z0-9][a-z0-9._:-]{1,63}$",
    )
    incident_id: UUID
    incident: Incident
    source_type: str = Field(min_length=1, max_length=100)
    scenario_id: str | None = None
    status: InvestigationStatus
    evidence: list[EvidenceRecord] = Field(default_factory=list, max_length=1_000)
    correlations: list[CorrelationRecord] = Field(default_factory=list, max_length=500)
    hypotheses: list[InvestigationHypothesis] = Field(default_factory=list, max_length=100)
    selected_hypothesis: UUID | None = None
    evidence_gaps: list[str] = Field(default_factory=list, max_length=80)
    recommended_next_step: str | None = Field(default=None, max_length=1_000)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    confidence_factors: dict[str, float] = Field(default_factory=dict)
    confidence_explanation: list[str] = Field(default_factory=list, max_length=20)
    root_cause_candidates: list[RootCauseCandidate] = Field(default_factory=list, max_length=20)
    timeline: list[InvestigationTimelineEvent] = Field(default_factory=list, max_length=500)
    errors: list[str] = Field(default_factory=list, max_length=50)
    ai_status: AIHealthStatus | None = None
    ai_summary: str | None = Field(default=None, max_length=5_000)
    orchestrator_handoff: InvestigationHandoff = Field(default_factory=InvestigationHandoff)
    request_id: str | None = Field(default=None, max_length=160)
    operations_signal_id: str | None = Field(default=None, max_length=240)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class InvestigationSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    investigation_id: UUID
    incident_id: UUID
    status: InvestigationStatus
    source_type: str
    evidence_count: int = Field(ge=0)
    correlation_count: int = Field(ge=0)
    hypothesis_count: int = Field(ge=0)
    confidence: float = Field(ge=0.0, le=1.0)
    selected_hypothesis: UUID | None = None
    recommended_next_step: str | None = None
    orchestrator_handoff: InvestigationHandoff
    updated_at: datetime


class InvestigationStartRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scenario_id: str | None = Field(default=None, min_length=1, max_length=120)
    request_id: str | None = Field(default=None, min_length=1, max_length=160)
    auto_handoff: bool = True


class CollectionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool_names: list[str] = Field(default_factory=list, max_length=10)


class TestHypothesisRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hypothesis_id: UUID
    tool_names: list[str] = Field(default_factory=list, max_length=10)


class InvestigationCancelRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    requested_by: str = Field(min_length=1, max_length=160)
    reason: str | None = Field(default=None, max_length=1_000)


__all__ = [
    "CollectionRequest",
    "ConfidenceAssessment",
    "CorrelationRecord",
    "EvidenceCollectionStatus",
    "EvidenceRecord",
    "InvestigationCancelRequest",
    "InvestigationContext",
    "InvestigationEvidenceType",
    "InvestigationHandoff",
    "InvestigationHandoffStatus",
    "InvestigationHypothesis",
    "InvestigationHypothesisStatus",
    "InvestigationStartRequest",
    "InvestigationStatus",
    "InvestigationSummary",
    "InvestigationTimelineEvent",
    "RootCauseCandidate",
    "TestHypothesisRequest",
]
