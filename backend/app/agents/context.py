"""Structured, secret-free state carried by the central orchestrator."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from backend.app.ai.schemas import AIHealthStatus
from backend.app.models.domain import Incident, utc_now
from backend.app.models.enums import AgentState, ApprovalStatus, RiskLevel


class OrchestrationDomain(StrEnum):
    IT = "IT"
    REVENUE = "REVENUE"
    SUPPORT = "SUPPORT"
    SUPPLY_CHAIN = "SUPPLY_CHAIN"
    CONTRACTS = "CONTRACTS"
    CLOUD = "CLOUD"
    DATA = "DATA"
    COMPLIANCE = "COMPLIANCE"


class OrchestratorRuntimeStatus(StrEnum):
    IDLE = "IDLE"
    RUNNING = "RUNNING"
    WAITING = "WAITING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class HypothesisStatus(StrEnum):
    PROPOSED = "PROPOSED"
    TESTING = "TESTING"
    SUPPORTED = "SUPPORTED"
    REJECTED = "REJECTED"
    INCONCLUSIVE = "INCONCLUSIVE"


class ToolRequestStatus(StrEnum):
    REQUESTED = "REQUESTED"
    EXECUTED = "EXECUTED"
    REJECTED = "REJECTED"
    FAILED = "FAILED"


class ToolExecutionStatus(StrEnum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    REJECTED = "REJECTED"
    TIMEOUT = "TIMEOUT"
    NOT_AVAILABLE = "NOT_AVAILABLE"


class Priority(StrEnum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class VerificationOutcome(StrEnum):
    VERIFIED = "VERIFIED"
    NOT_VERIFIED = "NOT_VERIFIED"
    PARTIALLY_VERIFIED = "PARTIALLY_VERIFIED"


class EvidenceItem(BaseModel):
    """A normalized evidence reference; raw source payloads are not copied here."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=200)
    source: str = Field(min_length=1, max_length=200)
    timestamp: datetime
    type: str = Field(min_length=1, max_length=60)
    summary: str = Field(min_length=1, max_length=2_000)
    raw_reference: dict[str, str] = Field(default_factory=dict)
    relevance: float = Field(default=0.0, ge=0.0, le=1.0)


class ToolCallRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID = Field(default_factory=uuid4)
    tool_name: str = Field(min_length=1, max_length=120)
    arguments: dict[str, Any] = Field(default_factory=dict)
    risk_level: RiskLevel
    reason: str = Field(min_length=1, max_length=1_000)
    status: ToolRequestStatus = ToolRequestStatus.REQUESTED
    requested_at: datetime = Field(default_factory=utc_now)


class ToolResultRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    execution_id: UUID
    tool_name: str = Field(min_length=1, max_length=120)
    status: ToolExecutionStatus
    result: dict[str, Any] = Field(default_factory=dict)
    evidence: list[EvidenceItem] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=utc_now)
    risk_level: RiskLevel


class HypothesisRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID = Field(default_factory=uuid4)
    title: str = Field(min_length=3, max_length=200)
    description: str = Field(min_length=1, max_length=3_000)
    supporting_evidence: list[str] = Field(default_factory=list, max_length=50)
    contradicting_evidence: list[str] = Field(default_factory=list, max_length=50)
    missing_evidence: list[str] = Field(default_factory=list, max_length=50)
    confidence: float = Field(ge=0.0, le=1.0)
    status: HypothesisStatus = HypothesisStatus.PROPOSED


class RemediationStep(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID = Field(default_factory=uuid4)
    sequence: int = Field(ge=1, le=50)
    action: str = Field(min_length=1, max_length=160)
    description: str = Field(min_length=1, max_length=2_000)
    tool_name: str = Field(min_length=1, max_length=120)
    parameters: dict[str, Any] = Field(default_factory=dict)
    risk_level: RiskLevel
    is_change: bool = False
    requires_approval: bool = False
    status: ToolRequestStatus = ToolRequestStatus.REQUESTED


class RemediationPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID = Field(default_factory=uuid4)
    problem: str = Field(min_length=1, max_length=2_000)
    steps: list[RemediationStep] = Field(default_factory=list, max_length=50)
    created_at: datetime = Field(default_factory=utc_now)

    @property
    def change_step(self) -> RemediationStep | None:
        return next((step for step in self.steps if step.is_change), None)


class ApprovalRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    approval_id: UUID = Field(default_factory=uuid4)
    incident_id: UUID
    action_id: UUID
    requested_action: str = Field(min_length=1, max_length=500)
    risk_level: RiskLevel
    reason: str = Field(min_length=1, max_length=2_000)
    expected_impact: str = Field(min_length=1, max_length=2_000)
    rollback_plan: str = Field(min_length=1, max_length=2_000)
    requested_at: datetime = Field(default_factory=utc_now)
    expires_at: datetime
    status: ApprovalStatus = ApprovalStatus.PENDING
    approved_by: str | None = Field(default=None, max_length=200)
    approved_at: datetime | None = None
    rejected_by: str | None = Field(default=None, max_length=200)
    rejected_at: datetime | None = None
    decision_reason: str | None = Field(default=None, max_length=2_000)


class VerificationRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID = Field(default_factory=uuid4)
    incident_id: UUID
    check: str = Field(min_length=1, max_length=500)
    expected_result: dict[str, Any] = Field(default_factory=dict)
    actual_result: dict[str, Any] = Field(default_factory=dict)
    status: VerificationOutcome
    timestamp: datetime = Field(default_factory=utc_now)


class OrchestrationActivity(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID = Field(default_factory=uuid4)
    incident_id: UUID
    event_type: str = Field(min_length=1, max_length=100)
    message: str = Field(min_length=1, max_length=500)
    created_at: datetime = Field(default_factory=utc_now)
    metadata: dict[str, str] = Field(default_factory=dict)


class TransitionRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    from_state: AgentState
    to_state: AgentState
    occurred_at: datetime = Field(default_factory=utc_now)
    reason: str | None = Field(default=None, max_length=500)


class ActionRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    execution_id: UUID | None = None
    action_id: UUID
    incident_id: UUID
    action: str
    risk_level: RiskLevel
    approval_status: ApprovalStatus | None = None
    status: ToolExecutionStatus | ToolRequestStatus
    timestamp: datetime
    requested_by: str = "orchestrator"
    approved_by: str | None = None
    result: dict[str, Any] = Field(default_factory=dict)


class SpecialistRuntime(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    domain: OrchestrationDomain
    status: str = "IDLE"
    current_task: str | None = None
    last_activity: datetime | None = None
    capabilities: list[str] = Field(default_factory=list)


class OrchestratorOverview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = "NEXORA CENTRAL ORCHESTRATOR"
    status: OrchestratorRuntimeStatus
    active_incidents: int = Field(ge=0)
    specialists: list[SpecialistRuntime] = Field(default_factory=list)
    last_activity: datetime | None = None


class OrchestrationStartRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scenario_id: str | None = Field(default=None, min_length=1, max_length=120)
    request_id: str | None = Field(default=None, min_length=1, max_length=120)


class ApprovalDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decided_by: str = Field(min_length=1, max_length=200)
    reason: str | None = Field(default=None, max_length=2_000)


class CancellationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    requested_by: str = Field(min_length=1, max_length=200)
    reason: str | None = Field(default=None, max_length=2_000)


class OrchestrationContext(BaseModel):
    """Full public operational context; it intentionally has no prompt or secret fields."""

    model_config = ConfigDict(extra="forbid")

    incident_id: UUID
    incident: Incident
    source_type: str = Field(min_length=1, max_length=80)
    scenario_id: str | None = None
    current_state: AgentState
    runtime_status: OrchestratorRuntimeStatus
    evidence: list[EvidenceItem] = Field(default_factory=list, max_length=500)
    hypotheses: list[HypothesisRecord] = Field(default_factory=list, max_length=50)
    selected_domain: OrchestrationDomain | None = None
    selected_domains: list[OrchestrationDomain] = Field(default_factory=list, max_length=8)
    selected_agent: str | None = None
    tool_calls: list[ToolCallRecord] = Field(default_factory=list, max_length=100)
    tool_results: list[ToolResultRecord] = Field(default_factory=list, max_length=200)
    risk_level: RiskLevel = RiskLevel.READ_ONLY
    priority: Priority | None = None
    priority_factors: dict[str, float] = Field(default_factory=dict)
    remediation_plan: RemediationPlan | None = None
    approval: ApprovalRecord | None = None
    verification_plan: list[str] = Field(default_factory=list, max_length=25)
    verification_results: list[VerificationRecord] = Field(default_factory=list, max_length=50)
    verification_outcome: VerificationOutcome | None = None
    activity: list[OrchestrationActivity] = Field(default_factory=list, max_length=500)
    transition_history: list[TransitionRecord] = Field(default_factory=list, max_length=100)
    errors: list[str] = Field(default_factory=list, max_length=50)
    analysis_summary: str | None = Field(default=None, max_length=5_000)
    analysis_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    ai_status: AIHealthStatus | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


__all__ = [
    "ActionRecord",
    "ApprovalDecisionRequest",
    "ApprovalRecord",
    "CancellationRequest",
    "EvidenceItem",
    "HypothesisRecord",
    "HypothesisStatus",
    "OrchestrationActivity",
    "OrchestrationContext",
    "OrchestrationDomain",
    "OrchestrationStartRequest",
    "OrchestratorOverview",
    "OrchestratorRuntimeStatus",
    "Priority",
    "RemediationPlan",
    "RemediationStep",
    "SpecialistRuntime",
    "ToolCallRecord",
    "ToolExecutionStatus",
    "ToolRequestStatus",
    "ToolResultRecord",
    "TransitionRecord",
    "VerificationOutcome",
    "VerificationRecord",
]
