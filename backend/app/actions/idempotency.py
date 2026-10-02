"""Thread-safe action proposal and execution idempotency indexes."""

from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
from typing import Any
from uuid import UUID


class IdempotencyConflictError(ValueError):
    """The same key was reused for a materially different action."""


@dataclass(frozen=True, slots=True)
class IdempotencyRecord:
    key: str
    fingerprint: str
    action_id: UUID
    execution_result: dict[str, Any] | None = None


class ActionIdempotencyStore:
    """Reference store preventing duplicate action creation and execution."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._records: dict[str, IdempotencyRecord] = {}

    def bind(self, key: str, fingerprint: str, action_id: UUID) -> IdempotencyRecord:
        with self._lock:
            existing = self._records.get(key)
            if existing is not None:
                if existing.fingerprint != fingerprint:
                    raise IdempotencyConflictError(
                        "Idempotency key is already bound to a different action fingerprint"
                    )
                return existing
            record = IdempotencyRecord(key, fingerprint, action_id)
            self._records[key] = record
            return record

    def get(self, key: str) -> IdempotencyRecord | None:
        with self._lock:
            return self._records.get(key)

    def save_execution(self, key: str, result: dict[str, Any]) -> IdempotencyRecord:
        with self._lock:
            existing = self._records.get(key)
            if existing is None:
                raise KeyError(f"No idempotency key is bound: {key}")
            updated = IdempotencyRecord(
                key=existing.key,
                fingerprint=existing.fingerprint,
                action_id=existing.action_id,
                execution_result=dict(result),
            )
            self._records[key] = updated
            return updated

    def execution(self, key: str) -> dict[str, Any] | None:
        with self._lock:
            record = self._records.get(key)
            return dict(record.execution_result) if record and record.execution_result else None


__all__ = ["ActionIdempotencyStore", "IdempotencyConflictError", "IdempotencyRecord"]
