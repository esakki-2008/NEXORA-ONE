"""Strongly typed Phase 8 verification and reliability contracts.

The models in this module are server-owned records.  Request models deliberately
contain identifiers and operator context only; expected state, actual state,
confidence, evidence trust, and lifecycle status are calculated by the
verification boundary.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr


class VerificationModel(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)


class VerificationStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    PASSED = "PASSED"
    FAILED = "FAILED"
    INCONCLUSIVE = "INCONCLUSIVE"
    RETRYING = "RETRYING"
    RECOVERY_REQUIRED = "RECOVERY_REQUIRED"
    REQUIRES_HUMAN = "REQUIRES_HUMAN"
    CANCELLED = "CANCELLED"


class VerificationStrategy(StrEnum):
    SERVICE_HEALTH = "SERVICE_HEALTH"
    ERROR_RATE = "ERROR_RATE"
    LATENCY = "LATENCY"
    DEPLOYMENT_STATE = "DEPLOYMENT_STATE"
    CONFIGURATION_STATE = "CONFIGURATION_STATE"
    QUEUE_STATE = "QUEUE_STATE"
    FEATURE_FLAG_STATE = "FEATURE_FLAG_STATE"
    CAPACITY_STATE = "CAPACITY_STATE"
    TRANSACTION_SUCCESS = "TRANSACTION_SUCCESS"


class VerificationCheckStatus(StrEnum):
    PASSED = "PASSED"
    FAILED = "FAILED"
    INCONCLUSIVE = "INCONCLUSIVE"
    UNAVAILABLE = "UNAVAILABLE"


class EvidenceTrust(StrEnum):
    TRUSTED = "TRUSTED"
    SIMULATED = "SIMULATED"
    UNTRUSTED = "UNTRUSTED"
    UNAVAILABLE = "UNAVAILABLE"


class VerificationEventType(StrEnum):
    VERIFICATION_CREATED = "verification_created"
    VERIFICATION_STARTED = "verification_started"
    CHECK_STARTED = "check_started"
    CHECK_PASSED = "check_passed"
    CHECK_FAILED = "check_failed"
    VERIFICATION_PASSED = "verification_passed"
    VERIFICATION_FAILED = "verification_failed"
    VERIFICATION_RETRY = "verification_retry"
    RECOVERY_REQUIRED = "recovery_required"
    RECOVERY_STARTED = "recovery_started"
    RECOVERY_COMPLETED = "recovery_completed"
    HUMAN_ESCALATION = "human_escalation"
    INCIDENT_RESOLVED = "incident_resolved"
    VERIFICATION_CANCELLED = "verification_cancelled"


class VerificationCheck(VerificationModel):
    """One deterministic expected-versus-actual comparison."""

    check_id: str = Field(default_factory=lambda: f"check:{uuid4()}", min_length=8, max_length=180)
    strategy: VerificationStrategy
    name: str = Field(min_length=1, max_length=160)
    status: VerificationCheckStatus
    required: bool = True
    expected_value: Any = None
    actual_value: Any = None
    comparison: str = Field(min_length=1, max_length=240)
    evidence_ids: list[str] = Field(default_factory=list, max_length=20)
    trust: EvidenceTrust
    observed_at: datetime | None = None
    failure_reason: str | None = Field(default=None, max_length=1_000)


class VerificationEvidence(VerificationModel):
    """Provenance-aware evidence produced for exactly one verification attempt."""

    model_config = ConfigDict(extra="forbid", from_attributes=True, frozen=True)

    evidence_id: str = Field(min_length=8, max_length=240)
    tenant_id: str = Field(
        default="reference-tenant",
        min_length=2,
        max_length=64,
        pattern=r"^[a-z0-9][a-z0-9._:-]{1,63}$",
    )
    verification_id: UUID
    incident_id: UUID
    action_id: UUID
    source: str = Field(min_length=1, max_length=240)
    timestamp: datetime
    collector: str = Field(min_length=1, max_length=180)
    value: Any = None
    expected_value: Any = None
    actual_value: Any = None
    comparison: str = Field(min_length=1, max_length=240)
    result: VerificationCheckStatus
    provenance: dict[str, str] = Field(default_factory=dict, max_length=20)
    trust: EvidenceTrust
    simulated: bool = False
    controlled_demonstration: bool = True


class VerificationConfidenceFactors(VerificationModel):
    """Structured, deterministic confidence factors; not an AI opinion."""

    health_check_passed: float = Field(ge=0.0, le=1.0)
    error_rate_recovered: float = Field(ge=0.0, le=1.0)
    latency_recovered: float = Field(ge=0.0, le=1.0)
    expected_state_match: float = Field(ge=0.0, le=1.0)
    multiple_independent_checks: float = Field(ge=0.0, le=1.0)
    evidence_freshness: float = Field(ge=0.0, le=1.0)
    contradictory_evidence: float = Field(ge=0.0, le=1.0)
    missing_evidence: float = Field(ge=0.0, le=1.0)
    required_checks_passed: float = Field(ge=0.0, le=1.0)

    def as_dict(self) -> dict[str, float]:
        return {key: float(value) for key, value in self.model_dump().items()}


class VerificationEscalation(VerificationModel):
    """Safe escalation payload containing structured facts only."""

    tenant_id: str = Field(
        default="reference-tenant",
        min_length=2,
        max_length=64,
        pattern=r"^[a-z0-9][a-z0-9._:-]{1,63}$",
    )
    incident_id: UUID
    action_id: UUID
    verification_id: UUID
    execution_result: dict[str, Any] = Field(default_factory=dict, max_length=40)
    attempts: int = Field(ge=0)
    failed_checks: list[str] = Field(default_factory=list, max_length=20)
    evidence_ids: list[str] = Field(default_factory=list, max_length=100)
    recommended_next_step: str = Field(min_length=1, max_length=1_000)
    reason: str = Field(min_length=1, max_length=1_000)


class Verification(VerificationModel):
    """Complete append-oriented verification lifecycle record."""

    model_config = ConfigDict(extra="forbid", from_attributes=True, frozen=True)

    verification_id: UUID = Field(default_factory=uuid4)
    tenant_id: str = Field(
        default="reference-tenant",
        min_length=2,
        max_length=64,
        pattern=r"^[a-z0-9][a-z0-9._:-]{1,63}$",
    )
    incident_id: UUID
    action_id: UUID
    status: VerificationStatus = VerificationStatus.PENDING
    strategy: list[VerificationStrategy] = Field(default_factory=list, max_length=12)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    attempt: StrictInt = Field(default=0, ge=0, le=3)
    max_attempts: StrictInt = Field(default=3, ge=1, le=3)
    expected_state: dict[str, Any] = Field(default_factory=dict, max_length=40)
    actual_state: dict[str, Any] = Field(default_factory=dict, max_length=40)
    checks: list[VerificationCheck] = Field(default_factory=list, max_length=20)
    evidence_ids: list[str] = Field(default_factory=list, max_length=100)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    confidence_factors: dict[str, float] = Field(default_factory=dict, max_length=20)
    failure_reason: str | None = Field(default=None, max_length=2_000)
    recovery_recommended: bool = False
    recovery_action_id: UUID | None = None
    escalation: VerificationEscalation | None = None
    execution_result: dict[str, Any] = Field(default_factory=dict, max_length=40)
    action_fingerprint: str = Field(default="", max_length=64)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    integrity_hash: str = Field(default="", max_length=64)


class VerificationCreateRequest(VerificationModel):
    """Create a verification for a server-known action; state fields are forbidden."""

    action_id: UUID
    requested_by: StrictStr | None = Field(default=None, min_length=1, max_length=200)


class VerificationRunRequest(VerificationModel):
    requested_by: StrictStr = Field(default="phase8.system", min_length=1, max_length=200)


class VerificationRetryRequest(VerificationModel):
    requested_by: StrictStr = Field(default="phase8.system", min_length=1, max_length=200)
    reason: StrictStr | None = Field(default=None, max_length=1_000)


class VerificationCancelRequest(VerificationModel):
    requested_by: StrictStr = Field(min_length=1, max_length=200)
    reason: StrictStr | None = Field(default=None, max_length=1_000)


class VerificationTimelineEvent(VerificationModel):
    """Immutable verification timeline event with a tamper-evident chain link."""

    model_config = ConfigDict(extra="forbid", from_attributes=True, frozen=True)

    event_id: UUID = Field(default_factory=uuid4)
    tenant_id: str = Field(
        default="reference-tenant",
        min_length=2,
        max_length=64,
        pattern=r"^[a-z0-9][a-z0-9._:-]{1,63}$",
    )
    verification_id: UUID
    incident_id: UUID
    action_id: UUID
    event_type: VerificationEventType
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    actor: str = Field(min_length=1, max_length=200)
    summary: str = Field(min_length=1, max_length=1_000)
    metadata: dict[str, Any] = Field(default_factory=dict, max_length=30)
    previous_hash: str = Field(default="GENESIS", min_length=7, max_length=64)
    event_hash: str = Field(default="0" * 64, min_length=64, max_length=64)


class VerificationSummary(VerificationModel):
    active: int = Field(ge=0)
    passed: int = Field(ge=0)
    failed: int = Field(ge=0)
    retrying: int = Field(ge=0)
    recovery_required: int = Field(ge=0)
    requires_human: int = Field(ge=0)
    cancelled: int = Field(ge=0)
    total: int = Field(ge=0)
    success_rate: float | None = Field(default=None, ge=0.0, le=1.0)
    message: str = Field(min_length=1, max_length=240)


__all__ = [
    "EvidenceTrust",
    "Verification",
    "VerificationCancelRequest",
    "VerificationCheck",
    "VerificationCheckStatus",
    "VerificationConfidenceFactors",
    "VerificationCreateRequest",
    "VerificationEscalation",
    "VerificationEvidence",
    "VerificationEventType",
    "VerificationModel",
    "VerificationRetryRequest",
    "VerificationRunRequest",
    "VerificationStatus",
    "VerificationStrategy",
    "VerificationSummary",
    "VerificationTimelineEvent",
]
