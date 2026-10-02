"""Thread-safe in-memory investigation persistence for local NEXORA operation."""

from __future__ import annotations

from threading import RLock
from uuid import UUID

from backend.app.investigation.context import InvestigationContext


class InvestigationNotFoundError(LookupError):
    """Raised when an investigation identifier is unknown."""


class InvestigationStore:
    """Reference store with request and incident idempotency indexes."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._contexts: dict[UUID, InvestigationContext] = {}
        self._by_incident: dict[UUID, UUID] = {}
        self._by_request: dict[str, UUID] = {}

    @staticmethod
    def _copy(context: InvestigationContext) -> InvestigationContext:
        return context.model_copy(deep=True)

    def save(self, context: InvestigationContext) -> InvestigationContext:
        with self._lock:
            self._contexts[context.investigation_id] = self._copy(context)
            self._by_incident[context.incident_id] = context.investigation_id
            if context.request_id:
                self._by_request[context.request_id] = context.investigation_id
            return self._copy(context)

    def get(self, investigation_id: UUID) -> InvestigationContext | None:
        with self._lock:
            context = self._contexts.get(investigation_id)
            return self._copy(context) if context else None

    def require(self, investigation_id: UUID) -> InvestigationContext:
        context = self.get(investigation_id)
        if context is None:
            raise InvestigationNotFoundError(
                f"Investigation {investigation_id} was not found"
            )
        return context

    def get_by_incident(self, incident_id: UUID) -> InvestigationContext | None:
        with self._lock:
            investigation_id = self._by_incident.get(incident_id)
            if investigation_id is None:
                return None
            context = self._contexts.get(investigation_id)
            return self._copy(context) if context else None

    def get_by_request(self, request_id: str) -> InvestigationContext | None:
        with self._lock:
            investigation_id = self._by_request.get(request_id)
            if investigation_id is None:
                return None
            context = self._contexts.get(investigation_id)
            return self._copy(context) if context else None

    def list_contexts(self) -> list[InvestigationContext]:
        with self._lock:
            values = sorted(
                self._contexts.values(), key=lambda item: item.updated_at, reverse=True
            )
            return [self._copy(item) for item in values]


__all__ = ["InvestigationNotFoundError", "InvestigationStore"]
