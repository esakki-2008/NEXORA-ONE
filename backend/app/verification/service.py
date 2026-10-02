"""Application service for reliable, append-oriented post-action verification."""

from __future__ import annotations

import asyncio
import hashlib
import json
from builtins import list as builtin_list
from collections.abc import Callable
from datetime import UTC, datetime
from threading import RLock
from typing import Any
from uuid import UUID

from backend.app.actions.models import Action, ActionStatus
from backend.app.actions.validators import ActionValidationError, validate_action_fingerprint
from backend.app.database.repository import IncidentRepository
from backend.app.verification.checks import VerificationCollectionError
from backend.app.verification.engine import (
    VerificationAttempt,
    VerificationEngine,
    VerificationEngineError,
)
from backend.app.verification.models import (
    Verification,
    VerificationCancelRequest,
    VerificationCreateRequest,
    VerificationEscalation,
    VerificationEventType,
    VerificationEvidence,
    VerificationRetryRequest,
    VerificationRunRequest,
    VerificationStatus,
    VerificationStrategy,
    VerificationSummary,
    VerificationTimelineEvent,
)
from backend.app.verification.recovery import RecoveryPolicy
from backend.app.verification.validators import (
    VerificationIntegrityError,
    VerificationValidationError,
    is_terminal,
    validate_proof,
    validate_transition,
)


class VerificationNotFoundError(LookupError):
    """Raised when a verification or bound action is unknown."""


class VerificationConflictError(ValueError):
    """Raised when a verification request violates a server-owned boundary."""


class VerificationStore:
    """Thread-safe in-memory store with record and timeline integrity checks."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._records: dict[UUID, Verification] = {}
        self._by_action: dict[UUID, UUID] = {}
        self._evidence: dict[UUID, list[VerificationEvidence]] = {}
        self._timeline: dict[UUID, list[VerificationTimelineEvent]] = {}

    @staticmethod
    def _record_hash(record: Verification) -> str:
        payload = record.model_dump(mode="json", exclude={"integrity_hash"})
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
        ).hexdigest()

    @staticmethod
    def _event_hash(event: VerificationTimelineEvent) -> str:
        payload = event.model_dump(mode="json", exclude={"event_hash"})
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
        ).hexdigest()

    def save(self, record: Verification, *, allow_update: bool = False) -> Verification:
        """Create a record or perform one service-authorized lifecycle update.

        Callers cannot overwrite an existing record through the public store
        method.  Lifecycle updates retain the previous hash as a compare-and-
        swap token and are only issued by ``VerificationService._update``.
        """
        with self._lock:
            existing = self._records.get(record.verification_id)
            if existing is not None:
                current_hash = self._record_hash(existing)
                if current_hash != existing.integrity_hash:
                    raise VerificationIntegrityError(
                        f"Verification record {record.verification_id} failed integrity validation"
                    )
                if not allow_update:
                    if record == existing:
                        return existing.model_copy(deep=True)
                    raise VerificationIntegrityError(
                        "Historical verification records are append-only and cannot be overwritten"
                    )
                if record.integrity_hash != existing.integrity_hash:
                    raise VerificationIntegrityError(
                        "Verification update lost its compare-and-swap integrity token"
                    )
                if (
                    record.tenant_id != existing.tenant_id
                    or record.incident_id != existing.incident_id
                    or record.action_id != existing.action_id
                    or record.action_fingerprint != existing.action_fingerprint
                ):
                    raise VerificationIntegrityError("Verification binding cannot change")
            bound_id = self._by_action.get(record.action_id)
            if bound_id is not None and bound_id != record.verification_id:
                raise VerificationIntegrityError("An action can have only one verification record")
            stored = record.model_copy(
                update={"integrity_hash": self._record_hash(record)}, deep=True
            )
            self._records[stored.verification_id] = stored
            self._by_action[stored.action_id] = stored.verification_id
            self._evidence.setdefault(stored.verification_id, [])
            self._timeline.setdefault(stored.verification_id, [])
            return stored.model_copy(deep=True)

    def get(self, verification_id: UUID) -> Verification | None:
        with self._lock:
            record = self._records.get(verification_id)
            if record is None:
                return None
            if self._record_hash(record) != record.integrity_hash:
                raise VerificationIntegrityError(
                    f"Verification record {verification_id} failed integrity validation"
                )
            return record.model_copy(deep=True)

    def get_by_action(self, action_id: UUID) -> Verification | None:
        with self._lock:
            verification_id = self._by_action.get(action_id)
        return self.get(verification_id) if verification_id is not None else None

    def list(
        self,
        status: VerificationStatus | None = None,
        *,
        tenant_id: str | None = None,
    ) -> list[Verification]:
        with self._lock:
            ids = list(self._records)
        records = [self.get(item) for item in ids]
        values = [item for item in records if item is not None]
        if tenant_id is not None:
            values = [item for item in values if item.tenant_id == tenant_id]
        if status is not None:
            values = [item for item in values if item.status is status]
        return sorted(values, key=lambda item: item.updated_at, reverse=True)

    def add_evidence(self, evidence: VerificationEvidence) -> VerificationEvidence:
        with self._lock:
            record = self._records.get(evidence.verification_id)
            if record is None:
                raise VerificationIntegrityError("Evidence references an unknown verification")
            if (
                record.tenant_id != evidence.tenant_id
                or record.incident_id != evidence.incident_id
                or record.action_id != evidence.action_id
            ):
                raise VerificationIntegrityError(
                    "Evidence tenant, incident, and action bindings do not match the verification"
                )
            records = self._evidence.setdefault(evidence.verification_id, [])
            existing = next(
                (item for item in records if item.evidence_id == evidence.evidence_id), None
            )
            if existing is not None:
                if existing != evidence:
                    raise VerificationIntegrityError(
                        "Historical verification evidence was modified"
                    )
                return existing.model_copy(deep=True)
            records.append(evidence.model_copy(deep=True))
            return evidence.model_copy(deep=True)

    def evidence(self, verification_id: UUID) -> builtin_list[VerificationEvidence]:
        with self._lock:
            return [item.model_copy(deep=True) for item in self._evidence.get(verification_id, [])]

    def append_event(
        self,
        *,
        record: Verification,
        event_type: VerificationEventType,
        actor: str,
        summary: str,
        metadata: dict[str, Any] | None = None,
    ) -> VerificationTimelineEvent:
        with self._lock:
            stored_record = self._records.get(record.verification_id)
            if stored_record is None:
                raise VerificationIntegrityError("Timeline references an unknown verification")
            if (
                stored_record.tenant_id != record.tenant_id
                or stored_record.incident_id != record.incident_id
                or stored_record.action_id != record.action_id
            ):
                raise VerificationIntegrityError(
                    "Timeline tenant and resource binding does not match the verification"
                )
            if self._record_hash(stored_record) != stored_record.integrity_hash:
                raise VerificationIntegrityError("Verification record failed integrity validation")
            events = self._timeline.setdefault(record.verification_id, [])
            previous = events[-1].event_hash if events else "GENESIS"
            candidate = VerificationTimelineEvent(
                verification_id=record.verification_id,
                tenant_id=record.tenant_id,
                incident_id=record.incident_id,
                action_id=record.action_id,
                event_type=event_type,
                actor=actor,
                summary=summary,
                metadata=dict(metadata or {}),
                previous_hash=previous,
            )
            event = candidate.model_copy(update={"event_hash": self._event_hash(candidate)})
            events.append(event)
            return event.model_copy(deep=True)

    def tamper_for_test(
        self,
        verification_id: UUID,
        event_index: int = 0,
        **updates: Any,
    ) -> None:
        """Test-only mutation hook; production lifecycle code is append-only."""

        with self._lock:
            events = self._timeline.get(verification_id)
            if events is None or not 0 <= event_index < len(events):
                raise KeyError(f"Verification event {verification_id}:{event_index} was not found")
            events[event_index] = events[event_index].model_copy(update=updates)

    def timeline(self, verification_id: UUID) -> builtin_list[VerificationTimelineEvent]:
        with self._lock:
            events = [
                item.model_copy(deep=True) for item in self._timeline.get(verification_id, [])
            ]
        previous = "GENESIS"
        for event in events:
            if event.previous_hash != previous or self._event_hash(event) != event.event_hash:
                raise VerificationIntegrityError(
                    f"Verification timeline {verification_id} failed integrity validation"
                )
            previous = event.event_hash
        return events


class VerificationService:
    """Own verification state transitions and the incident resolution gate."""

    SYSTEM_ACTORS = frozenset({"phase8.system", "phase8.engine", "phase7.executor"})
    HUMAN_ACTORS = frozenset(
        {
            "local-operator",
            "Local operator",
            "test-operator",
            "operator",
            "human-operator",
            "system-admin",
            "phase8.operator",
        }
    )

    def __init__(
        self,
        repository: IncidentRepository,
        engine: VerificationEngine,
        *,
        store: VerificationStore | None = None,
        recovery_policy: RecoveryPolicy | None = None,
        action_lookup: Callable[[UUID], Action] | None = None,
        max_attempts: int = 3,
        retry_delay_seconds: float = 0.01,
    ) -> None:
        if max_attempts < 1 or max_attempts > 3:
            raise ValueError("Verification attempts must be bounded between 1 and 3")
        if retry_delay_seconds < 0 or retry_delay_seconds > 1:
            raise ValueError("Verification retry delay must be bounded between 0 and 1 second")
        self.repository = repository
        self.engine = engine
        self.store = store or VerificationStore()
        self.recovery_policy = recovery_policy or RecoveryPolicy()
        self.action_lookup = action_lookup
        self.max_attempts = max_attempts
        self.retry_delay_seconds = retry_delay_seconds
        self.orchestrator: Any | None = None
        self._lock = RLock()

    def set_action_lookup(self, action_lookup: Callable[[UUID], Action]) -> None:
        self.action_lookup = action_lookup

    def create_for_action(
        self,
        action: Action,
        *,
        execution_result: dict[str, Any] | None = None,
    ) -> Verification:
        existing = self.store.get_by_action(action.action_id)
        if existing is not None:
            if execution_result and not existing.execution_result:
                existing = self._update(
                    existing,
                    execution_result=dict(execution_result),
                    updated_at=datetime.now(UTC),
                )
            return existing
        if action.scenario_id is None:
            raise VerificationConflictError("Verification requires a ShopFlow scenario binding")
        try:
            expected = self.engine.expected_state(action)
        except (VerificationEngineError, KeyError, ValueError) as exc:
            raise VerificationConflictError(str(exc)) from exc
        strategies = [VerificationStrategy(item["strategy"]) for item in expected["checks"]]
        now = datetime.now(UTC)
        record = Verification(
            tenant_id=action.tenant_id,
            incident_id=action.incident_id,
            action_id=action.action_id,
            status=VerificationStatus.PENDING,
            strategy=strategies,
            max_attempts=self.max_attempts,
            expected_state=expected,
            action_fingerprint=action.action_fingerprint,
            execution_result=dict(execution_result or action.execution_result),
            created_at=now,
            updated_at=now,
        )
        with self._lock:
            saved = self.store.save(record)
            self.store.append_event(
                record=saved,
                event_type=VerificationEventType.VERIFICATION_CREATED,
                actor="phase8.system",
                summary="Verification record created from the server-owned action plan.",
                metadata={"boundary": "SIMULATED / CONTROLLED DEMONSTRATION"},
            )
            return saved

    def create(
        self, request: VerificationCreateRequest, *, tenant_id: str | None = None
    ) -> Verification:
        if request.requested_by is None:
            raise VerificationConflictError("Verification creator identity is required")
        self._authorize_control(request.requested_by)
        action = self._require_action(request.action_id)
        if tenant_id is not None and action.tenant_id != tenant_id:
            raise VerificationNotFoundError(f"Action {request.action_id} was not found")
        if action.status is ActionStatus.CANCELLED:
            raise VerificationConflictError("Verification cannot be created for a cancelled action")
        return self.create_for_action(action)

    def list(
        self,
        *,
        status: VerificationStatus | None = None,
        incident_id: UUID | None = None,
        action_id: UUID | None = None,
        tenant_id: str | None = None,
    ) -> list[Verification]:
        records = self.store.list(status, tenant_id=tenant_id)
        if incident_id is not None:
            records = [item for item in records if item.incident_id == incident_id]
        if action_id is not None:
            records = [item for item in records if item.action_id == action_id]
        return records

    def get(self, verification_id: UUID, *, tenant_id: str | None = None) -> Verification:
        try:
            record = self.store.get(verification_id)
        except VerificationIntegrityError as exc:
            raise VerificationConflictError(str(exc)) from exc
        if record is None or (tenant_id is not None and record.tenant_id != tenant_id):
            raise VerificationNotFoundError(f"Verification {verification_id} was not found")
        return record

    def get_for_action(self, action_id: UUID) -> Verification:
        record = self.store.get_by_action(action_id)
        if record is None:
            raise VerificationNotFoundError(f"No verification exists for action {action_id}")
        return self.get(record.verification_id)

    async def run(
        self,
        verification_id: UUID,
        request: VerificationRunRequest | None = None,
    ) -> Verification:
        actor = request.requested_by if request else "phase8.system"
        self._authorize_control(actor)
        try:
            return await self._run_once(verification_id, actor=actor)
        except VerificationValidationError as exc:
            raise VerificationConflictError(str(exc)) from exc

    async def run_for_action(
        self,
        action: Action,
        *,
        execution_result: dict[str, Any],
        attempts: int = 1,
    ) -> Verification:
        record = self.create_for_action(action, execution_result=execution_result)
        execution_bound_action = action.model_copy(
            update={"execution_result": dict(execution_result)}, deep=True
        )
        # The post-action hook is bounded by the configured maximum. The
        # production executor requests one attempt and exposes later retries
        # explicitly; callers that request more still cannot exceed the cap.
        requested_attempts = max(1, min(attempts, self.max_attempts))
        result = await self._run_once(
            record.verification_id,
            actor="phase8.system",
            action_override=execution_bound_action,
        )
        for _ in range(1, requested_attempts):
            if result.status in {
                VerificationStatus.PASSED,
                VerificationStatus.REQUIRES_HUMAN,
                VerificationStatus.CANCELLED,
            }:
                break
            result = await self.retry(record.verification_id)
        return result

    async def retry(
        self,
        verification_id: UUID,
        request: VerificationRetryRequest | None = None,
    ) -> Verification:
        actor = request.requested_by if request else "phase8.system"
        self._authorize_control(actor)
        record = self.get(verification_id)
        if record.status is VerificationStatus.PASSED:
            return record
        if record.status is VerificationStatus.REQUIRES_HUMAN:
            raise VerificationConflictError("Verification requires human review and cannot retry")
        if record.status is VerificationStatus.CANCELLED:
            raise VerificationConflictError("Cancelled verification cannot retry")
        if record.attempt >= record.max_attempts:
            return self._escalate(record, actor, "Maximum verification attempts have been reached")
        if record.status is not VerificationStatus.RETRYING:
            validate_transition(record.status, VerificationStatus.RETRYING)
            record = self._update(
                record, status=VerificationStatus.RETRYING, updated_at=datetime.now(UTC)
            )
        self.store.append_event(
            record=record,
            event_type=VerificationEventType.VERIFICATION_RETRY,
            actor=actor,
            summary="Bounded verification retry requested.",
            metadata={"attempt": str(record.attempt + 1), "max_attempts": str(record.max_attempts)},
        )
        # Backoff is deterministic, bounded, and intentionally small for the
        # simulator boundary; the service never schedules an unbounded loop.
        await asyncio.sleep(self.retry_delay_seconds * (2 ** max(0, record.attempt - 1)))
        return await self._run_once(verification_id, actor=actor)

    def cancel(self, verification_id: UUID, request: VerificationCancelRequest) -> Verification:
        self._authorize_human(request.requested_by)
        record = self.get(verification_id)
        if is_terminal(record.status):
            if record.status is VerificationStatus.CANCELLED:
                return record
            raise VerificationConflictError("Terminal verification cannot be cancelled")
        if record.status is VerificationStatus.RUNNING:
            raise VerificationConflictError("Running verification cannot be cancelled safely")
        validate_transition(record.status, VerificationStatus.CANCELLED)
        updated = self._update(
            record,
            status=VerificationStatus.CANCELLED,
            failure_reason=request.reason or "Verification cancelled by operator",
            completed_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        self.store.append_event(
            record=updated,
            event_type=VerificationEventType.VERIFICATION_CANCELLED,
            actor=request.requested_by,
            summary=updated.failure_reason or "Verification cancelled.",
        )
        return updated

    def evidence(
        self, verification_id: UUID, *, tenant_id: str | None = None
    ) -> builtin_list[VerificationEvidence]:
        self.get(verification_id, tenant_id=tenant_id)
        return self.store.evidence(verification_id)

    def timeline(
        self, verification_id: UUID, *, tenant_id: str | None = None
    ) -> builtin_list[VerificationTimelineEvent]:
        self.get(verification_id, tenant_id=tenant_id)
        try:
            return self.store.timeline(verification_id)
        except VerificationIntegrityError as exc:
            raise VerificationConflictError(str(exc)) from exc

    def summary(self, *, tenant_id: str | None = None) -> VerificationSummary:
        records = self.store.list(tenant_id=tenant_id)
        counts = {
            status: sum(item.status is status for item in records) for status in VerificationStatus
        }
        terminal = counts[VerificationStatus.PASSED] + counts[VerificationStatus.REQUIRES_HUMAN]
        success_rate = counts[VerificationStatus.PASSED] / terminal if terminal else None
        return VerificationSummary(
            active=(
                counts[VerificationStatus.PENDING]
                + counts[VerificationStatus.RUNNING]
                + counts[VerificationStatus.RETRYING]
                + counts[VerificationStatus.RECOVERY_REQUIRED]
                + counts[VerificationStatus.FAILED]
                + counts[VerificationStatus.INCONCLUSIVE]
            ),
            passed=counts[VerificationStatus.PASSED],
            failed=counts[VerificationStatus.FAILED] + counts[VerificationStatus.INCONCLUSIVE],
            retrying=counts[VerificationStatus.RETRYING],
            recovery_required=counts[VerificationStatus.RECOVERY_REQUIRED],
            requires_human=counts[VerificationStatus.REQUIRES_HUMAN],
            cancelled=counts[VerificationStatus.CANCELLED],
            total=len(records),
            success_rate=success_rate,
            message="Recorded verification history" if records else "No verification history yet",
        )

    def can_resolve(self, action: Action, verification: Verification) -> bool:
        if (
            action.incident_id != verification.incident_id
            or action.action_id != verification.action_id
        ):
            return False
        if verification.action_fingerprint != action.action_fingerprint:
            return False
        try:
            validate_proof(
                verification,
                max_age_seconds=self.engine.max_evidence_age_seconds,
            )
        except VerificationValidationError:
            return False
        return True

    def mark_incident_resolved(
        self, verification: Verification, actor: str = "phase8.gate"
    ) -> None:
        self.store.append_event(
            record=verification,
            event_type=VerificationEventType.INCIDENT_RESOLVED,
            actor=actor,
            summary="Incident resolution gate opened after verification proof passed.",
            metadata={"boundary": "SIMULATED / CONTROLLED DEMONSTRATION"},
        )

    async def _run_once(
        self,
        verification_id: UUID,
        *,
        actor: str,
        action_override: Action | None = None,
    ) -> Verification:
        with self._lock:
            record = self.get(verification_id)
            if record.status is VerificationStatus.PASSED:
                return record
            if record.status is VerificationStatus.CANCELLED:
                raise VerificationConflictError("Cancelled verification cannot run")
            if record.status is VerificationStatus.REQUIRES_HUMAN:
                raise VerificationConflictError("Verification requires human review")
            if record.status is VerificationStatus.RUNNING:
                raise VerificationConflictError("Verification is already running")
            if record.attempt >= record.max_attempts:
                return self._escalate(
                    record, actor, "Maximum verification attempts have been reached"
                )
            action = action_override or self._require_action(record.action_id)
            self._validate_action_for_verification(action, record)
            target_status = VerificationStatus.RUNNING
            validate_transition(record.status, target_status)
            started = datetime.now(UTC)
            running = self._update(
                record,
                status=target_status,
                attempt=record.attempt + 1,
                started_at=started,
                completed_at=None,
                updated_at=started,
            )
            self.store.append_event(
                record=running,
                event_type=VerificationEventType.VERIFICATION_STARTED,
                actor=actor,
                summary="Verification started against current simulator state.",
                metadata={"attempt": str(running.attempt)},
            )

        try:
            attempt = await self.engine.evaluate(
                action,
                verification_id=running.verification_id,
                expected_state=running.expected_state,
                attempt=running.attempt,
            )
        except (VerificationEngineError, VerificationCollectionError) as exc:
            return self._handle_engine_failure(running, actor, str(exc)[:1_000])
        except Exception as exc:
            # Unexpected collector failures are safer as an explicit human
            # escalation than as a partial or optimistic proof.
            return self._handle_engine_failure(running, actor, str(exc)[:1_000])
        return self._complete_attempt(running, attempt, actor)

    def _complete_attempt(
        self,
        running: Verification,
        attempt: VerificationAttempt,
        actor: str,
    ) -> Verification:
        for evidence in attempt.evidence:
            self.store.add_evidence(evidence)
        for check in attempt.checks:
            event_type = (
                VerificationEventType.CHECK_PASSED
                if check.status.value == "PASSED"
                else VerificationEventType.CHECK_FAILED
            )
            self.store.append_event(
                record=running,
                event_type=event_type,
                actor="phase8.engine",
                summary=f"{check.name}: {check.status.value}",
                metadata={"strategy": check.strategy.value, "comparison": check.comparison},
            )
        evidence_ids = list(
            dict.fromkeys(running.evidence_ids + [item.evidence_id for item in attempt.evidence])
        )
        if attempt.status is VerificationStatus.PASSED:
            validate_transition(running.status, VerificationStatus.PASSED)
            updated = self._update(
                running,
                status=VerificationStatus.PASSED,
                completed_at=datetime.now(UTC),
                actual_state=attempt.actual_state,
                checks=list(attempt.checks),
                evidence_ids=evidence_ids,
                confidence=attempt.confidence,
                confidence_factors=attempt.confidence_factors.as_dict(),
                failure_reason=None,
                recovery_recommended=False,
                escalation=None,
                updated_at=datetime.now(UTC),
            )
            self.store.append_event(
                record=updated,
                event_type=VerificationEventType.VERIFICATION_PASSED,
                actor="phase8.engine",
                summary="All required verification checks passed.",
                metadata={"confidence": f"{updated.confidence:.4f}"},
            )
            self._notify_orchestrator(updated)
            return updated

        decision = self.recovery_policy.select(
            self._require_action(running.action_id), attempt.status, attempt.failed_checks
        )
        final_status = (
            VerificationStatus.RECOVERY_REQUIRED
            if running.attempt < running.max_attempts
            else VerificationStatus.REQUIRES_HUMAN
        )
        validate_transition(running.status, final_status)
        escalation = None
        if final_status is VerificationStatus.REQUIRES_HUMAN:
            escalation = VerificationEscalation(
                incident_id=running.incident_id,
                action_id=running.action_id,
                verification_id=running.verification_id,
                execution_result=running.execution_result,
                attempts=running.attempt,
                failed_checks=list(attempt.failed_checks),
                evidence_ids=evidence_ids,
                recommended_next_step=decision.next_step,
                reason=attempt.failure_reason or decision.reason,
            )
        updated = self._update(
            running,
            status=final_status,
            completed_at=datetime.now(UTC)
            if final_status is VerificationStatus.REQUIRES_HUMAN
            else None,
            actual_state=attempt.actual_state,
            checks=list(attempt.checks),
            evidence_ids=evidence_ids,
            confidence=attempt.confidence,
            confidence_factors=attempt.confidence_factors.as_dict(),
            failure_reason=attempt.failure_reason or decision.reason,
            recovery_recommended=decision.recommended,
            escalation=escalation,
            updated_at=datetime.now(UTC),
        )
        self.store.append_event(
            record=updated,
            event_type=VerificationEventType.VERIFICATION_FAILED,
            actor="phase8.engine",
            summary=updated.failure_reason or "Verification failed.",
            metadata={"status": updated.status.value},
        )
        if decision.recommended:
            self.store.append_event(
                record=updated,
                event_type=VerificationEventType.RECOVERY_REQUIRED,
                actor="phase8.recovery",
                summary=decision.next_step,
                metadata={
                    "action_name": decision.action_name or "none",
                    "requires_approval": str(decision.requires_approval).lower(),
                },
            )
        if final_status is VerificationStatus.REQUIRES_HUMAN:
            self.store.append_event(
                record=updated,
                event_type=VerificationEventType.HUMAN_ESCALATION,
                actor="phase8.policy",
                summary=decision.next_step,
                metadata={"attempts": str(updated.attempt)},
            )
        self._notify_orchestrator(updated)
        return updated

    def _handle_engine_failure(
        self, running: Verification, actor: str, reason: str
    ) -> Verification:
        final_status = (
            VerificationStatus.RECOVERY_REQUIRED
            if running.attempt < running.max_attempts
            else VerificationStatus.REQUIRES_HUMAN
        )
        validate_transition(running.status, final_status)
        updated = self._update(
            running,
            status=final_status,
            completed_at=datetime.now(UTC)
            if final_status is VerificationStatus.REQUIRES_HUMAN
            else None,
            failure_reason=f"Verification integrity or collection failure: {reason}",
            recovery_recommended=True,
            updated_at=datetime.now(UTC),
        )
        self.store.append_event(
            record=updated,
            event_type=VerificationEventType.VERIFICATION_FAILED,
            actor=actor,
            summary=updated.failure_reason or "Verification failed safely.",
        )
        if final_status is VerificationStatus.REQUIRES_HUMAN:
            self.store.append_event(
                record=updated,
                event_type=VerificationEventType.HUMAN_ESCALATION,
                actor="phase8.policy",
                summary="Verification could not establish a reliable current state.",
                metadata={"attempts": str(updated.attempt)},
            )
        self._notify_orchestrator(updated)
        return updated

    def _escalate(self, record: Verification, actor: str, reason: str) -> Verification:
        if record.status is VerificationStatus.REQUIRES_HUMAN:
            return record
        if record.status is not VerificationStatus.RUNNING:
            validate_transition(record.status, VerificationStatus.REQUIRES_HUMAN)
        updated = self._update(
            record,
            status=VerificationStatus.REQUIRES_HUMAN,
            completed_at=datetime.now(UTC),
            failure_reason=reason,
            recovery_recommended=True,
            updated_at=datetime.now(UTC),
        )
        self.store.append_event(
            record=updated,
            event_type=VerificationEventType.HUMAN_ESCALATION,
            actor=actor,
            summary=reason,
        )
        return updated

    def _update(self, record: Verification, **updates: Any) -> Verification:
        updated = record.model_copy(update=updates, deep=True)
        return self.store.save(updated, allow_update=True)

    def _require_action(self, action_id: UUID) -> Action:
        if self.action_lookup is None:
            raise VerificationConflictError("Action lookup is not configured")
        try:
            return self.action_lookup(action_id)
        except Exception as exc:
            raise VerificationNotFoundError(f"Action {action_id} was not found") from exc

    @staticmethod
    def _validate_action_for_verification(action: Action, record: Verification) -> None:
        if action.status is ActionStatus.CANCELLED:
            raise VerificationConflictError(
                "Verification after a cancelled action is not permitted"
            )
        try:
            validate_action_fingerprint(action)
        except ActionValidationError as exc:
            raise VerificationConflictError(str(exc)) from exc
        if action.incident_id != record.incident_id:
            raise VerificationConflictError("Verification action is bound to a different incident")
        if not action.execution_result and action.status not in {
            ActionStatus.COMPLETED,
            ActionStatus.ROLLED_BACK,
            ActionStatus.FAILED,
            ActionStatus.REQUIRES_HUMAN,
        }:
            raise VerificationConflictError("Verification requires a completed action result")

    def _authorize_control(self, actor: str) -> None:
        if actor in self.SYSTEM_ACTORS or actor in self.HUMAN_ACTORS:
            return
        raise VerificationConflictError("Actor is not authorized for verification control")

    def _authorize_human(self, actor: str) -> None:
        self._authorize_control(actor)

    def _notify_orchestrator(self, record: Verification) -> None:
        # Bound lazily by the application factory to avoid a dependency cycle.
        callback = getattr(self, "orchestrator", None)
        if callback is not None:
            callback.record_verification_result(record)


__all__ = [
    "VerificationConflictError",
    "VerificationNotFoundError",
    "VerificationService",
    "VerificationStore",
]
