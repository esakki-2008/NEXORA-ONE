"""Deterministic confidence calculation for verification evidence."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime

from backend.app.verification.models import (
    EvidenceTrust,
    VerificationCheck,
    VerificationCheckStatus,
    VerificationConfidenceFactors,
)

_DEFAULT_MAX_AGE_SECONDS = 300


def _score(checks: Iterable[VerificationCheck], strategy: str) -> float:
    matching = [item for item in checks if item.strategy.value == strategy]
    if not matching:
        return 0.0
    return 1.0 if all(item.status is VerificationCheckStatus.PASSED for item in matching) else 0.0


def calculate_confidence(
    checks: list[VerificationCheck],
    *,
    now: datetime | None = None,
    max_age_seconds: int = _DEFAULT_MAX_AGE_SECONDS,
) -> tuple[float, VerificationConfidenceFactors]:
    """Calculate a bounded score from explicit check and provenance factors.

    The formula is intentionally simple and reviewable.  It never consumes
    model-generated text, hidden reasoning, or a client-provided confidence.
    """

    current = now or datetime.now(UTC)
    required = [item for item in checks if item.required]
    passed = [item for item in required if item.status is VerificationCheckStatus.PASSED]
    failures = [
        item
        for item in required
        if item.status in {VerificationCheckStatus.FAILED, VerificationCheckStatus.UNAVAILABLE}
    ]
    unavailable = any(item.status is VerificationCheckStatus.UNAVAILABLE for item in required)
    trusts = {item.trust for item in required}
    contradictory = bool(passed and failures)
    missing = not required or unavailable or any(item.observed_at is None for item in required)
    fresh_values: list[float] = []
    for item in required:
        if item.observed_at is None:
            fresh_values.append(0.0)
            continue
        observed = item.observed_at
        if observed.tzinfo is None:
            observed = observed.replace(tzinfo=UTC)
        age = max(0.0, (current - observed).total_seconds())
        fresh_values.append(max(0.0, min(1.0, 1.0 - age / max_age_seconds)))
    freshness = sum(fresh_values) / len(fresh_values) if fresh_values else 0.0
    factors = VerificationConfidenceFactors(
        health_check_passed=_score(checks, "SERVICE_HEALTH"),
        error_rate_recovered=_score(checks, "ERROR_RATE"),
        latency_recovered=_score(checks, "LATENCY"),
        expected_state_match=(len(passed) / len(required)) if required else 0.0,
        multiple_independent_checks=(1.0 if len(required) >= 2 else 0.0),
        evidence_freshness=freshness,
        contradictory_evidence=1.0 if contradictory else 0.0,
        missing_evidence=1.0 if missing else 0.0,
        required_checks_passed=(len(passed) / len(required)) if required else 0.0,
    )

    # Trust is represented explicitly.  Simulated evidence can prove the
    # simulator state for a controlled demonstration, but it is not production
    # telemetry and is never silently relabelled as trusted evidence.
    trust_factor = 0.0 if EvidenceTrust.UNTRUSTED in trusts else 1.0
    positive = (
        0.22 * factors.health_check_passed
        + 0.18 * factors.error_rate_recovered
        + 0.12 * factors.latency_recovered
        + 0.20 * factors.expected_state_match
        + 0.08 * factors.multiple_independent_checks
        + 0.10 * factors.evidence_freshness
        + 0.10 * factors.required_checks_passed
    )
    penalty = (
        0.30 * factors.contradictory_evidence
        + 0.25 * factors.missing_evidence
        + 0.35 * (1.0 - trust_factor)
    )
    confidence = round(max(0.0, min(1.0, positive - penalty)), 4)
    return confidence, factors


__all__ = ["calculate_confidence"]
