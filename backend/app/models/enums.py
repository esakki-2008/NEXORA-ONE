"""Shared domain enumerations used across API and service boundaries."""

from enum import StrEnum


class Severity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class IncidentStatus(StrEnum):
    OPEN = "open"
    INVESTIGATING = "investigating"
    REMEDIATION_PROPOSED = "remediation_proposed"
    RESOLVED = "resolved"
    CLOSED = "closed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    REQUIRES_HUMAN = "requires_human"


class AgentState(StrEnum):
    IDLE = "IDLE"
    INCIDENT_RECEIVED = "INCIDENT_RECEIVED"
    OBSERVING = "OBSERVING"
    INVESTIGATING = "INVESTIGATING"
    HYPOTHESIS_GENERATED = "HYPOTHESIS_GENERATED"
    VALIDATING = "VALIDATING"
    REMEDIATION_PROPOSED = "REMEDIATION_PROPOSED"
    WAITING_FOR_APPROVAL = "WAITING_FOR_APPROVAL"
    EXECUTING = "EXECUTING"
    VERIFYING = "VERIFYING"
    RESOLVED = "RESOLVED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    REQUIRES_HUMAN = "REQUIRES_HUMAN"


class RiskLevel(StrEnum):
    READ_ONLY = "READ_ONLY"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class EvidenceType(StrEnum):
    LOG = "log"
    METRIC = "metric"
    DEPLOYMENT = "deployment"
    CONFIGURATION = "configuration"
    TRANSACTION = "transaction"
    DOCUMENT = "document"
    MANUAL = "manual"


class HypothesisValidationStatus(StrEnum):
    UNVALIDATED = "unvalidated"
    SUPPORTED = "supported"
    CONTRADICTED = "contradicted"
    INCONCLUSIVE = "inconclusive"


class ActionStatus(StrEnum):
    PROPOSED = "proposed"
    APPROVED = "approved"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ApprovalStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


class VerificationStatus(StrEnum):
    PENDING = "pending"
    PASSED = "passed"
    FAILED = "failed"
    INCONCLUSIVE = "inconclusive"
