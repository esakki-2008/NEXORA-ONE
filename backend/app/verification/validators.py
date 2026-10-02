"""State, binding, freshness, and integrity validation for Phase 8."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
from uuid import UUID

from backend.app.verification.models import (
    EvidenceTrust,
    Verification,
    VerificationCheck,
    VerificationCheckStatus,
    VerificationStatus,
)


class VerificationValidationError(ValueError):
    """Raised when a verification request cannot be accepted safely."""


class VerificationIntegrityError(RuntimeError):
    """Raised when a stored verification or timeline has been modified."""


_TERMINAL = frozenset(
    {
        VerificationStatus.PASSED,
        VerificationStatus.REQUIRES_HUMAN,
        VerificationStatus.CANCELLED,
    }
)

_ALLOWED_TRANSITIONS: dict[VerificationStatus, frozenset[VerificationStatus]] = {
    VerificationStatus.PENDING: frozenset(
        {VerificationStatus.RUNNING, VerificationStatus.CANCELLED}
    ),
    VerificationStatus.RUNNING: frozenset(
        {
            VerificationStatus.PASSED,
            VerificationStatus.FAILED,
            VerificationStatus.INCONCLUSIVE,
            VerificationStatus.RETRYING,
            VerificationStatus.RECOVERY_REQUIRED,
            VerificationStatus.REQUIRES_HUMAN,
            VerificationStatus.CANCELLED,
        }
    ),
    VerificationStatus.FAILED: frozenset(
        {
            VerificationStatus.RETRYING,
            VerificationStatus.RECOVERY_REQUIRED,
            VerificationStatus.REQUIRES_HUMAN,
            VerificationStatus.CANCELLED,
        }
    ),
    VerificationStatus.INCONCLUSIVE: frozenset(
        {
            VerificationStatus.RETRYING,
            VerificationStatus.RECOVERY_REQUIRED,
            VerificationStatus.REQUIRES_HUMAN,
            VerificationStatus.CANCELLED,
        }
    ),
    VerificationStatus.RETRYING: frozenset(
        {
            VerificationStatus.RUNNING,
            VerificationStatus.REQUIRES_HUMAN,
            VerificationStatus.CANCELLED,
        }
    ),
    VerificationStatus.RECOVERY_REQUIRED: frozenset(
        {
            VerificationStatus.RETRYING,
            VerificationStatus.RUNNING,
            VerificationStatus.REQUIRES_HUMAN,
            VerificationStatus.CANCELLED,
        }
    ),
    VerificationStatus.PASSED: frozenset(),
    VerificationStatus.REQUIRES_HUMAN: frozenset(),
    VerificationStatus.CANCELLED: frozenset(),
}


def validate_transition(current: VerificationStatus, target: VerificationStatus) -> None:
    """Reject every transition not explicitly present in the state machine."""

    if target not in _ALLOWED_TRANSITIONS[current]:
        raise VerificationValidationError(
            f"Invalid verification state transition {current.value} -> {target.value}"
        )


def is_terminal(status: VerificationStatus) -> bool:
    return status in _TERMINAL


def validate_binding(
    verification: Verification,
    *,
    incident_id: UUID,
    action_id: UUID,
    action_fingerprint: str,
) -> None:
    if verification.incident_id != incident_id:
        raise VerificationValidationError("Verification is bound to a different incident")
    if verification.action_id != action_id:
        raise VerificationValidationError("Verification is bound to a different action")
    if verification.action_fingerprint != action_fingerprint:
        raise VerificationValidationError("Verification action fingerprint does not match")


def validate_proof(
    verification: Verification,
    *,
    max_age_seconds: int,
    now: datetime | None = None,
) -> None:
    """Ensure a record can be used as a resolution proof."""

    if verification.status is not VerificationStatus.PASSED:
        raise VerificationValidationError("Only a passed verification can prove resolution")
    if verification.failure_reason:
        raise VerificationValidationError("Verification contains a failure reason")
    if not verification.checks:
        raise VerificationValidationError("Verification has no required checks")
    if any(
        check.required and check.status is not VerificationCheckStatus.PASSED
        for check in verification.checks
    ):
        raise VerificationValidationError("Required verification checks did not pass")
    if any(
        check.trust in {EvidenceTrust.UNTRUSTED, EvidenceTrust.UNAVAILABLE}
        for check in verification.checks
    ):
        raise VerificationValidationError(
            "Untrusted or unavailable evidence cannot prove resolution"
        )
    current = now or datetime.now(UTC)
    for check in verification.checks:
        if check.required and check.observed_at is None:
            raise VerificationValidationError("Required verification evidence has no timestamp")
        if check.required and check.observed_at is not None:
            observed = check.observed_at
            if observed.tzinfo is None:
                observed = observed.replace(tzinfo=UTC)
            if (current - observed).total_seconds() > max_age_seconds:
                raise VerificationValidationError("Required verification evidence is stale")
    factors = verification.confidence_factors
    if factors.get("contradictory_evidence", 0.0) > 0.0:
        raise VerificationValidationError("Contradictory evidence cannot prove resolution")
    if factors.get("missing_evidence", 0.0) > 0.0:
        raise VerificationValidationError("Missing required evidence cannot prove resolution")


def failed_check_names(checks: Iterable[VerificationCheck]) -> list[str]:
    return [
        check.name
        for check in checks
        if check.required and check.status is not VerificationCheckStatus.PASSED
    ]


__all__ = [
    "VerificationIntegrityError",
    "VerificationValidationError",
    "failed_check_names",
    "is_terminal",
    "validate_binding",
    "validate_proof",
    "validate_transition",
]
