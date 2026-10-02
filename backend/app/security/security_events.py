"""Append-only, secret-safe security event stream."""

from __future__ import annotations

from threading import RLock
from uuid import UUID

from backend.app.security.integrity import canonical_hash
from backend.app.security.models import SecurityEvent, SecurityEventType
from backend.app.security.sanitization import safe_metadata


class SecurityEventIntegrityError(RuntimeError):
    """Raised when a security event chain has been modified."""


class SecurityEventStore:
    def __init__(self) -> None:
        self._lock = RLock()
        self._events: list[SecurityEvent] = []

    @staticmethod
    def _hash(event: SecurityEvent) -> str:
        payload = event.model_dump(mode="json", exclude={"event_hash"})
        return canonical_hash(payload)

    def append(
        self,
        *,
        event_type: SecurityEventType,
        actor: str,
        tenant_id: str = "unknown",
        resource: str = "unknown",
        source: str = "api",
        result: str = "DENIED",
        metadata: dict[str, object] | None = None,
    ) -> SecurityEvent:
        with self._lock:
            previous = self._events[-1].event_hash if self._events else "GENESIS"
            candidate = SecurityEvent(
                event_type=event_type,
                actor=actor[:160],
                tenant_id=tenant_id[:64],
                resource=resource[:240],
                source=source[:120],
                result=result[:40],
                safe_metadata=safe_metadata(metadata),
                previous_hash=previous,
            )
            event = candidate.model_copy(update={"event_hash": self._hash(candidate)})
            self._events.append(event)
            return event.model_copy(deep=True)

    def list(self, *, tenant_id: str | None = None) -> list[SecurityEvent]:
        with self._lock:
            events = [
                event for event in self._events if tenant_id is None or event.tenant_id == tenant_id
            ]
            return [event.model_copy(deep=True) for event in events]

    def verify(self) -> bool:
        with self._lock:
            previous = "GENESIS"
            for event in self._events:
                if event.previous_hash != previous or self._hash(event) != event.event_hash:
                    return False
                previous = event.event_hash
            return True

    def require_integrity(self) -> None:
        if not self.verify():
            raise SecurityEventIntegrityError("Security event history failed integrity validation")

    def tamper_for_test(self, event_id: UUID, **updates: object) -> None:
        """Test-only mutation hook; production callers have no update API."""

        with self._lock:
            for index, event in enumerate(self._events):
                if event.event_id == event_id:
                    self._events[index] = event.model_copy(update=updates)
                    return
            raise KeyError(str(event_id))


__all__ = ["SecurityEventIntegrityError", "SecurityEventStore"]
