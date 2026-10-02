"""Server-owned authentication, authorization, tenant, and security-event contracts.

These contracts intentionally separate authentication from authorization.  A
valid token establishes an authenticated principal; permissions and resource
ownership are evaluated independently by the security service.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

TENANT_ID_PATTERN = r"^[a-z0-9][a-z0-9._:-]{1,63}$"
SUBJECT_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._:@-]{1,159}$"


class SecurityRole(StrEnum):
    VIEWER = "VIEWER"
    OPERATOR = "OPERATOR"
    APPROVER = "APPROVER"
    ADMIN = "ADMIN"


class AuthState(StrEnum):
    UNAUTHENTICATED = "UNAUTHENTICATED"
    AUTHENTICATED = "AUTHENTICATED"
    AUTHORIZED = "AUTHORIZED"


class Permission(StrEnum):
    VIEW_INCIDENTS = "view_incidents"
    VIEW_EVIDENCE = "view_evidence"
    VIEW_OPERATIONS = "view_operations"
    VIEW_VERIFICATION = "view_verification"
    VIEW_REPORTS = "view_reports"
    CREATE_INVESTIGATION = "create_investigation"
    COLLECT_EVIDENCE = "collect_evidence"
    PROPOSE_ACTION = "propose_action"
    REVIEW_ACTION = "review_action"
    APPROVE_ACTION = "approve_action"
    EXECUTE_ACTION = "execute_action"
    CANCEL_OPERATION = "cancel_operation"
    RETRY_VERIFICATION = "retry_verification"
    RUN_AI = "run_ai"
    VIEW_SECURITY_EVENTS = "view_security_events"
    MANAGE_SECURITY = "manage_security"


class SecurityEventType(StrEnum):
    AUTHENTICATION_FAILED = "authentication_failed"
    AUTHORIZATION_DENIED = "authorization_denied"
    CROSS_TENANT_ACCESS_DENIED = "cross_tenant_access_denied"
    INVALID_ACTION_ATTEMPT = "invalid_action_attempt"
    INVALID_TOOL_ATTEMPT = "invalid_tool_attempt"
    PROMPT_INJECTION_DETECTED = "prompt_injection_detected"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    OVERSIZED_REQUEST_REJECTED = "oversized_request_rejected"
    TAMPERED_RECORD_DETECTED = "tampered_record_detected"
    INVALID_STATE_TRANSITION = "invalid_state_transition"
    SECRET_EXPOSURE_ATTEMPT = "secret_exposure_attempt"  # nosec B105
    SECURITY_CONFIGURATION_CHANGED = "security_configuration_changed"


class Principal(BaseModel):
    """Authenticated server-issued identity and tenant scope."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    subject: str = Field(min_length=2, max_length=160, pattern=SUBJECT_PATTERN)
    tenant_id: str = Field(min_length=2, max_length=64, pattern=TENANT_ID_PATTERN)
    roles: frozenset[SecurityRole] = Field(min_length=1, max_length=4)
    issued_at: datetime
    expires_at: datetime
    token_id: UUID = Field(default_factory=uuid4)
    auth_state: AuthState = AuthState.AUTHENTICATED

    def has_role(self, role: SecurityRole) -> bool:
        return role in self.roles

    def allows(self, permission: Permission) -> bool:
        del permission
        return self.auth_state is not AuthState.UNAUTHENTICATED


class SecurityEvent(BaseModel):
    """Safe, append-only security event with a hash-chain link."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    event_id: UUID = Field(default_factory=uuid4)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    event_type: SecurityEventType
    actor: str = Field(min_length=1, max_length=160)
    tenant_id: str = Field(default="unknown", min_length=2, max_length=64)
    resource: str = Field(default="unknown", min_length=1, max_length=240)
    source: str = Field(default="api", min_length=1, max_length=120)
    result: str = Field(default="DENIED", min_length=1, max_length=40)
    safe_metadata: dict[str, str] = Field(default_factory=dict, max_length=30)
    previous_hash: str = Field(default="GENESIS", min_length=7, max_length=64)
    event_hash: str = Field(default="0" * 64, min_length=64, max_length=64)


class SecuritySession(BaseModel):
    """Safe identity response; never contains the bearer token or secret."""

    model_config = ConfigDict(extra="forbid")

    subject: str
    tenant_id: str
    roles: frozenset[SecurityRole]
    auth_state: AuthState
    expires_at: datetime


class SecurityEventList(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[SecurityEvent] = Field(default_factory=list, max_length=1_000)
    total: int = Field(ge=0)


__all__ = [
    "AuthState",
    "Permission",
    "Principal",
    "SecurityEvent",
    "SecurityEventList",
    "SecurityEventType",
    "SecurityRole",
    "SecuritySession",
    "TENANT_ID_PATTERN",
]
