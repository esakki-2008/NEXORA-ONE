"""Strongly typed contracts for Phase 7 controlled actions.

The action layer is deliberately separate from arbitrary tool execution. Every
mutating operation is represented by one of the seven public action names and
is validated against a dedicated parameter model before it can be proposed.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr

from backend.app.models.enums import RiskLevel


class ActionModel(BaseModel):
    """Strict base for action API contracts."""

    model_config = ConfigDict(extra="forbid", from_attributes=True)


class ActionStatus(StrEnum):
    PROPOSED = "PROPOSED"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    EXECUTING = "EXECUTING"
    EXECUTION_COMPLETED = "EXECUTION_COMPLETED"
    VERIFICATION_RUNNING = "VERIFICATION_RUNNING"
    VERIFICATION_FAILED = "VERIFICATION_FAILED"
    RECOVERY_REQUIRED = "RECOVERY_REQUIRED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    ROLLED_BACK = "ROLLED_BACK"
    CANCELLED = "CANCELLED"
    REQUIRES_HUMAN = "REQUIRES_HUMAN"


class VerificationState(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    PASSED = "PASSED"
    FAILED = "FAILED"
    INCONCLUSIVE = "INCONCLUSIVE"
    RETRYING = "RETRYING"
    RECOVERY_REQUIRED = "RECOVERY_REQUIRED"
    REQUIRES_HUMAN = "REQUIRES_HUMAN"
    CANCELLED = "CANCELLED"


class ActionApprovalState(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"


class ActionParameters(ActionModel):
    """Base class that rejects unexpected action parameters."""


class NoParameters(ActionParameters):
    """Parameters for actions that do not accept caller-supplied values."""


class DeploymentParameters(ActionParameters):
    deployment_id: StrictStr = Field(
        min_length=2,
        max_length=120,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{1,119}$",
    )


QUEUE_NAMES = (
    "payment",
    "checkout",
    "order-processing",
    "fulfillment",
)
QueueName = Literal["payment", "checkout", "order-processing", "fulfillment"]


class QueueParameters(ActionParameters):
    queue_name: QueueName


FEATURE_NAMES = (
    "new_checkout",
    "payment_retries",
    "express_checkout",
    "fraud_screening",
)
FeatureName = Literal["new_checkout", "payment_retries", "express_checkout", "fraud_screening"]


class FeatureFlagParameters(ActionParameters):
    feature_name: FeatureName


CONFIGURATION_IDS = (
    "gateway.retry_limit",
    "gateway.endpoint",
    "checkout.timeout_ms",
    "connection.pool_size",
)
ConfigurationId = Literal[
    "gateway.retry_limit",
    "gateway.endpoint",
    "checkout.timeout_ms",
    "connection.pool_size",
]


class ConfigurationParameters(ActionParameters):
    configuration_id: ConfigurationId


SERVICE_NAMES = (
    "Payment Service",
    "Checkout Service",
    "Inventory",
    "Support System",
)
ServiceName = Literal["Payment Service", "Checkout Service", "Inventory", "Support System"]


class ScaleServiceParameters(ActionParameters):
    service_name: ServiceName
    desired_capacity: StrictInt = Field(ge=1, le=100)


PUBLIC_ACTION_NAMES = (
    "restart_payment_service",
    "rollback_simulated_deployment",
    "restart_checkout_service",
    "clear_simulated_queue",
    "disable_simulated_feature_flag",
    "restore_simulated_configuration",
    "scale_simulated_service",
)
ActionName = Literal[
    "restart_payment_service",
    "rollback_simulated_deployment",
    "restart_checkout_service",
    "clear_simulated_queue",
    "disable_simulated_feature_flag",
    "restore_simulated_configuration",
    "scale_simulated_service",
]


class ActionCreateRequest(ActionModel):
    """Untrusted proposal request; risk and approval fields are intentionally absent."""

    incident_id: UUID
    investigation_id: UUID | None = None
    scenario_id: StrictStr | None = Field(default=None, min_length=1, max_length=100)
    action_name: StrictStr | None = Field(default=None, min_length=2, max_length=120)
    recommended_action: StrictStr | None = Field(default=None, min_length=2, max_length=240)
    parameters: dict[str, Any] = Field(default_factory=dict, max_length=20)
    root_cause_candidate: StrictStr | None = Field(default=None, max_length=2_000)
    requested_by: StrictStr = Field(default="local-operator", min_length=1, max_length=200)
    idempotency_key: StrictStr | None = Field(default=None, min_length=3, max_length=200)


class ActionDecisionRequest(ActionModel):
    """Human decision/operation request. No risk or approval status is accepted."""

    requested_by: StrictStr = Field(min_length=1, max_length=200)
    reason: StrictStr | None = Field(default=None, max_length=2_000)
    auto_execute: bool = False


class ActionRejectRequest(ActionModel):
    requested_by: StrictStr = Field(min_length=1, max_length=200)
    reason: StrictStr | None = Field(default=None, max_length=2_000)


class ActionCancelRequest(ActionModel):
    requested_by: StrictStr = Field(min_length=1, max_length=200)
    reason: StrictStr | None = Field(default=None, max_length=2_000)


class ActionProposal(ActionModel):
    """Server-generated plan before it is placed behind approval."""

    action_id: UUID = Field(default_factory=uuid4)
    tenant_id: str = Field(
        default="reference-tenant",
        min_length=2,
        max_length=64,
        pattern=r"^[a-z0-9][a-z0-9._:-]{1,63}$",
    )
    incident_id: UUID
    action_name: str = Field(min_length=3, max_length=120)
    normalized_parameters: dict[str, Any] = Field(default_factory=dict, max_length=20)
    risk_level: RiskLevel
    expected_impact: str = Field(min_length=1, max_length=2_000)
    rollback_plan: str = Field(min_length=1, max_length=2_000)
    rollback_supported: bool
    rollback_action: str | None = Field(default=None, max_length=120)
    rollback_parameters: dict[str, Any] = Field(default_factory=dict, max_length=20)
    rollback_conditions: list[str] = Field(default_factory=list, max_length=20)
    verification_strategy: str = Field(min_length=1, max_length=2_000)
    action_fingerprint: str = Field(min_length=64, max_length=64)
    idempotency_key: str = Field(min_length=3, max_length=200)
    requested_by: str = Field(min_length=1, max_length=200)
    scenario_id: str | None = Field(default=None, max_length=100)
    evidence_ids: list[str] = Field(default_factory=list, max_length=100)
    planning_summary: str = Field(min_length=1, max_length=2_000)


class Action(ActionModel):
    """Full auditable action lifecycle record with immutable top-level fields."""

    model_config = ConfigDict(extra="forbid", from_attributes=True, frozen=True)

    action_id: UUID = Field(default_factory=uuid4)
    tenant_id: str = Field(
        default="reference-tenant",
        min_length=2,
        max_length=64,
        pattern=r"^[a-z0-9][a-z0-9._:-]{1,63}$",
    )
    incident_id: UUID
    action_name: str = Field(min_length=3, max_length=120)
    normalized_parameters: dict[str, Any] = Field(default_factory=dict, max_length=20)
    risk_level: RiskLevel
    expected_impact: str = Field(min_length=1, max_length=2_000)
    rollback_plan: str = Field(min_length=1, max_length=2_000)
    status: ActionStatus = ActionStatus.PROPOSED
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    requested_by: str = Field(min_length=1, max_length=200)
    approved_by: str | None = Field(default=None, max_length=200)
    approval_id: UUID | None = None
    approval_status: ActionApprovalState | None = None
    action_fingerprint: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    idempotency_key: str = Field(min_length=3, max_length=200)
    execution_attempts: int = Field(default=0, ge=0, le=3)
    verification_id: UUID | None = None
    verification_attempts: int = Field(default=0, ge=0, le=3)
    verification_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    verification_status: VerificationState = VerificationState.PENDING
    recovery_required: bool = False
    human_escalation: bool = False
    rollback_verification_status: VerificationState | None = None
    failure_reason: str | None = Field(default=None, max_length=2_000)
    audit_reference: str = Field(min_length=3, max_length=240)
    rollback_supported: bool = False
    rollback_action: str | None = Field(default=None, max_length=120)
    rollback_parameters: dict[str, Any] = Field(default_factory=dict, max_length=20)
    rollback_conditions: list[str] = Field(default_factory=list, max_length=20)
    verification_strategy: str = Field(min_length=1, max_length=2_000)
    scenario_id: str | None = Field(default=None, max_length=100)
    evidence_ids: list[str] = Field(default_factory=list, max_length=100)
    planning_summary: str = Field(min_length=1, max_length=2_000)
    execution_before_state: dict[str, Any] = Field(default_factory=dict, max_length=40)
    execution_after_state: dict[str, Any] = Field(default_factory=dict, max_length=40)
    execution_result: dict[str, Any] = Field(default_factory=dict, max_length=40)


class ActionApproval(ActionModel):
    """API-safe view of the existing Phase 4 approval primitive."""

    approval_id: UUID
    tenant_id: str = Field(
        default="reference-tenant",
        min_length=2,
        max_length=64,
        pattern=r"^[a-z0-9][a-z0-9._:-]{1,63}$",
    )
    incident_id: UUID
    action_id: UUID
    status: ActionApprovalState
    risk_level: RiskLevel
    requested_action: str
    requested_at: datetime
    expires_at: datetime
    approved_by: str | None = None
    approved_at: datetime | None = None
    decision_reason: str | None = None


class ActionExecutionOutcome(ActionModel):
    """Structured executor result, including verification and rollback evidence."""

    action_id: UUID
    status: ActionStatus
    execution_attempts: int
    result: dict[str, Any] = Field(default_factory=dict, max_length=40)
    before_state: dict[str, Any] = Field(default_factory=dict, max_length=40)
    after_state: dict[str, Any] = Field(default_factory=dict, max_length=40)
    evidence: list[dict[str, Any]] = Field(default_factory=list, max_length=100)
    verification_status: VerificationState
    verification_details: str = Field(min_length=1, max_length=2_000)
    verification_id: UUID | None = None
    verification_attempts: int = Field(default=0, ge=0, le=3)
    verification_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    recovery_required: bool = False
    human_escalation: bool = False
    rollback_attempted: bool = False
    rollback_verified: bool | None = None


class ActionVerificationRecord(ActionModel):
    action_id: UUID
    incident_id: UUID
    verification_id: UUID | None = None
    status: VerificationState
    details: str
    verification_strategy: str
    strategy: list[str] = Field(default_factory=list, max_length=12)
    attempt: int = Field(default=0, ge=0, le=3)
    max_attempts: int = Field(default=3, ge=1, le=3)
    expected_state: dict[str, Any] = Field(default_factory=dict, max_length=40)
    actual_state: dict[str, Any] = Field(default_factory=dict, max_length=40)
    checks: list[dict[str, Any]] = Field(default_factory=list, max_length=20)
    evidence_ids: list[str] = Field(default_factory=list, max_length=100)
    evidence: list[dict[str, Any]] = Field(default_factory=list, max_length=100)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    confidence_factors: dict[str, float] = Field(default_factory=dict, max_length=20)
    failure_reason: str | None = None
    recovery_recommended: bool = False
    recovery_action_id: UUID | None = None
    escalation: dict[str, Any] | None = None
    before_state: dict[str, Any] = Field(default_factory=dict, max_length=40)
    after_state: dict[str, Any] = Field(default_factory=dict, max_length=40)
    rollback_status: VerificationState | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True, slots=True)
class ActionDefinition:
    """Non-user-controlled registry metadata and explicit handler binding."""

    name: str
    description: str
    parameter_model: type[ActionParameters]
    risk_level: RiskLevel
    allowed_domains: tuple[str, ...]
    expected_impact: str
    rollback_supported: bool
    verification_strategy: str
    authorization_requirements: tuple[str, ...]
    handler_name: str
    rollback_action: str | None
    rollback_conditions: tuple[str, ...]
    verification_strategies: tuple[str, ...] = ()

    @property
    def parameter_schema(self) -> dict[str, Any]:
        return self.parameter_model.model_json_schema()

    def response_dict(self) -> dict[str, Any]:
        """Serialize safe registry metadata without exposing a callable."""

        return {
            "name": self.name,
            "description": self.description,
            "parameter_schema": self.parameter_schema,
            "risk_level": self.risk_level,
            "allowed_domains": list(self.allowed_domains),
            "expected_impact": self.expected_impact,
            "rollback_supported": self.rollback_supported,
            "verification_strategy": self.verification_strategy,
            "verification_strategies": list(self.verification_strategies),
            "authorization_requirements": list(self.authorization_requirements),
            "rollback_action": self.rollback_action,
            "rollback_conditions": list(self.rollback_conditions),
        }


__all__ = [
    "Action",
    "ActionApproval",
    "ActionApprovalState",
    "ActionCancelRequest",
    "ActionCreateRequest",
    "ActionDecisionRequest",
    "ActionDefinition",
    "ActionExecutionOutcome",
    "ActionModel",
    "ActionVerificationRecord",
    "ActionName",
    "ActionParameters",
    "ActionProposal",
    "ActionRejectRequest",
    "ActionStatus",
    "CONFIGURATION_IDS",
    "ConfigurationParameters",
    "DeploymentParameters",
    "FeatureFlagParameters",
    "FEATURE_NAMES",
    "NoParameters",
    "PUBLIC_ACTION_NAMES",
    "QUEUE_NAMES",
    "QueueParameters",
    "SERVICE_NAMES",
    "ScaleServiceParameters",
    "VerificationState",
]
