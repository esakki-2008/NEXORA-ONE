"""Append-only, hash-chained action audit records."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from enum import StrEnum
from threading import RLock
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class AuditEventType(StrEnum):
    ACTION_CREATED = "action.created"
    APPROVAL_REQUESTED = "action.approval.requested"
    ACTION_APPROVED = "action.approved"
    ACTION_REJECTED = "action.rejected"
    ACTION_EXPIRED = "action.expired"
    ACTION_CANCELLED = "action.cancelled"
    EXECUTION_STARTED = "action.execution.started"
    EXECUTION_COMPLETED = "action.execution.completed"
    EXECUTION_FAILED = "action.execution.failed"
    ROLLBACK_STARTED = "action.rollback.started"
    ROLLBACK_COMPLETED = "action.rollback.completed"
    VERIFICATION_STARTED = "action.verification.started"
    VERIFICATION_COMPLETED = "action.verification.completed"
    HUMAN_ESCALATION = "action.human.escalation"
    INCIDENT_RESOLVED = "action.incident.resolved"


class AuditEvent(BaseModel):
    """One immutable event in the action audit chain."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    event_id: UUID = Field(default_factory=uuid4)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    event_type: AuditEventType
    action_id: UUID
    tenant_id: str = Field(
        default="reference-tenant",
        min_length=2,
        max_length=64,
        pattern=r"^[a-z0-9][a-z0-9._:-]{1,63}$",
    )
    incident_id: UUID
    actor: str = Field(min_length=1, max_length=200)
    source: str = Field(min_length=1, max_length=160)
    metadata: dict[str, Any] = Field(default_factory=dict, max_length=40)
    previous_hash: str = Field(default="GENESIS", min_length=7, max_length=64)
    event_hash: str = Field(default="0" * 64, min_length=64, max_length=64)


class AuditIntegrityError(RuntimeError):
    """Raised when an append-only chain cannot be verified."""


class AuditTrail:
    """Append-only local audit boundary with tamper-evident hash chaining."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._events: dict[UUID, list[AuditEvent]] = {}

    def append(
        self,
        *,
        event_type: AuditEventType,
        action_id: UUID,
        incident_id: UUID,
        actor: str,
        tenant_id: str = "reference-tenant",
        source: str = "phase7.actions",
        metadata: dict[str, Any] | None = None,
    ) -> AuditEvent:
        with self._lock:
            events = self._events.setdefault(action_id, [])
            previous_hash = events[-1].event_hash if events else "GENESIS"
            candidate = AuditEvent(
                event_type=event_type,
                action_id=action_id,
                tenant_id=tenant_id,
                incident_id=incident_id,
                actor=actor,
                source=source,
                metadata=dict(metadata or {}),
                previous_hash=previous_hash,
            )
            event_hash = self._hash_event(candidate)
            event = candidate.model_copy(update={"event_hash": event_hash})
            events.append(event)
            return event.model_copy(deep=True)

    def list(self, action_id: UUID) -> list[AuditEvent]:
        with self._lock:
            return [event.model_copy(deep=True) for event in self._events.get(action_id, [])]

    def verify(self, action_id: UUID) -> bool:
        with self._lock:
            events = self._events.get(action_id, [])
            previous = "GENESIS"
            for event in events:
                if event.previous_hash != previous:
                    return False
                if self._hash_event(event) != event.event_hash:
                    return False
                previous = event.event_hash
            return True

    def require_integrity(self, action_id: UUID) -> None:
        if not self.verify(action_id):
            raise AuditIntegrityError(
                f"Audit chain for action {action_id} failed integrity validation"
            )

    def tamper_for_test(self, action_id: UUID, event_index: int = 0, **updates: Any) -> None:
        """Test-only mutation hook; production code has no update operation."""

        with self._lock:
            events = self._events.get(action_id)
            if events is None or not 0 <= event_index < len(events):
                raise KeyError(f"Audit event {action_id}:{event_index} was not found")
            events[event_index] = events[event_index].model_copy(update=updates)

    @staticmethod
    def _hash_event(event: AuditEvent) -> str:
        payload = {
            "event_id": str(event.event_id),
            "timestamp": event.timestamp.isoformat(),
            "event_type": event.event_type.value,
            "action_id": str(event.action_id),
            "incident_id": str(event.incident_id),
            "tenant_id": event.tenant_id,
            "actor": event.actor,
            "source": event.source,
            "metadata": event.metadata,
            "previous_hash": event.previous_hash,
        }
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
        ).hexdigest()


__all__ = ["AuditEvent", "AuditEventType", "AuditIntegrityError", "AuditTrail"]
