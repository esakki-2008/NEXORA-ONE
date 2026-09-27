"""Persistence ports and the deterministic Phase 1 reference repository.

The service layer depends on ``IncidentRepository`` rather than a concrete
storage engine. This keeps API behavior independent of the eventual
PostgreSQL adapter while making the foundation easy to run locally and in
unit tests. The in-memory implementation is intentionally explicit and is not
presented as durable production storage.
"""

from __future__ import annotations

from threading import RLock
from typing import Protocol, TypeVar
from uuid import UUID

from pydantic import BaseModel

from backend.app.models.domain import Evidence, Hypothesis, Incident, IncidentReport
from backend.app.schemas.incidents import ActivityEvent

ModelT = TypeVar("ModelT", bound=BaseModel)


class IncidentRepository(Protocol):
    """Storage contract consumed by the incident service."""

    def create_incident(self, incident: Incident) -> Incident: ...

    def list_incidents(self) -> list[Incident]: ...

    def get_incident(self, incident_id: UUID) -> Incident | None: ...

    def update_incident(self, incident: Incident) -> Incident: ...

    def add_activity(self, event: ActivityEvent) -> ActivityEvent: ...

    def list_activity(self, incident_id: UUID) -> list[ActivityEvent]: ...

    def list_evidence(self, incident_id: UUID) -> list[Evidence]: ...

    def add_evidence(self, evidence: Evidence) -> Evidence: ...

    def list_hypotheses(self, incident_id: UUID) -> list[Hypothesis]: ...

    def add_hypothesis(self, hypothesis: Hypothesis) -> Hypothesis: ...

    def add_report(self, report: IncidentReport) -> IncidentReport: ...

    def get_report(self, incident_id: UUID) -> IncidentReport | None: ...


class InMemoryIncidentRepository:
    """Thread-safe reference repository for the Phase 1 application shell."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._incidents: dict[UUID, Incident] = {}
        self._activity: dict[UUID, list[ActivityEvent]] = {}
        self._evidence: dict[UUID, list[Evidence]] = {}
        self._hypotheses: dict[UUID, list[Hypothesis]] = {}
        self._reports: dict[UUID, IncidentReport] = {}

    @staticmethod
    def _copy(value: ModelT) -> ModelT:
        """Deep-copy Pydantic values at the repository boundary."""

        # Pydantic models expose model_copy; typing stays local to avoid a
        # storage layer dependency on a particular serialization format.
        return value.model_copy(deep=True)

    def create_incident(self, incident: Incident) -> Incident:
        with self._lock:
            if incident.id in self._incidents:
                raise ValueError(f"Incident {incident.id} already exists")
            self._incidents[incident.id] = self._copy(incident)
            self._activity.setdefault(incident.id, [])
            self._evidence.setdefault(incident.id, [])
            self._hypotheses.setdefault(incident.id, [])
            return self._copy(incident)

    def list_incidents(self) -> list[Incident]:
        with self._lock:
            incidents = sorted(
                self._incidents.values(), key=lambda item: item.created_at, reverse=True
            )
            return [self._copy(incident) for incident in incidents]

    def get_incident(self, incident_id: UUID) -> Incident | None:
        with self._lock:
            incident = self._incidents.get(incident_id)
            return self._copy(incident) if incident is not None else None

    def update_incident(self, incident: Incident) -> Incident:
        with self._lock:
            if incident.id not in self._incidents:
                raise KeyError(f"Incident {incident.id} does not exist")
            self._incidents[incident.id] = self._copy(incident)
            return self._copy(incident)

    def add_activity(self, event: ActivityEvent) -> ActivityEvent:
        with self._lock:
            if event.incident_id not in self._incidents:
                raise KeyError(f"Incident {event.incident_id} does not exist")
            self._activity.setdefault(event.incident_id, []).append(self._copy(event))
            return self._copy(event)

    def list_activity(self, incident_id: UUID) -> list[ActivityEvent]:
        with self._lock:
            return [self._copy(event) for event in self._activity.get(incident_id, [])]

    def list_evidence(self, incident_id: UUID) -> list[Evidence]:
        with self._lock:
            return [self._copy(item) for item in self._evidence.get(incident_id, [])]

    def list_hypotheses(self, incident_id: UUID) -> list[Hypothesis]:
        with self._lock:
            return [self._copy(item) for item in self._hypotheses.get(incident_id, [])]

    def get_report(self, incident_id: UUID) -> IncidentReport | None:
        with self._lock:
            report = self._reports.get(incident_id)
            return self._copy(report) if report is not None else None

    def add_evidence(self, evidence: Evidence) -> Evidence:
        """Store one evidence record while preserving collection idempotency."""

        with self._lock:
            if evidence.incident_id not in self._incidents:
                raise KeyError(f"Incident {evidence.incident_id} does not exist")
            records = self._evidence.setdefault(evidence.incident_id, [])
            existing = next(
                (
                    item
                    for item in records
                    if item.id == evidence.id
                    or (
                        evidence.evidence_id is not None
                        and item.evidence_id == evidence.evidence_id
                    )
                ),
                None,
            )
            if existing is not None:
                return self._copy(existing)
            records.append(self._copy(evidence))
            return self._copy(evidence)

    def add_hypothesis(self, hypothesis: Hypothesis) -> Hypothesis:
        """Provide a controlled fixture hook for later investigation services."""

        with self._lock:
            if hypothesis.incident_id not in self._incidents:
                raise KeyError(f"Incident {hypothesis.incident_id} does not exist")
            self._hypotheses.setdefault(hypothesis.incident_id, []).append(self._copy(hypothesis))
            return self._copy(hypothesis)

    def add_report(self, report: IncidentReport) -> IncidentReport:
        """Store a report generated by a future report service."""

        with self._lock:
            if report.incident_id not in self._incidents:
                raise KeyError(f"Incident {report.incident_id} does not exist")
            self._reports[report.incident_id] = self._copy(report)
            return self._copy(report)

    def clear(self) -> None:
        """Clear local state; useful for isolated tests and local restarts."""

        with self._lock:
            self._incidents.clear()
            self._activity.clear()
            self._evidence.clear()
            self._hypotheses.clear()
            self._reports.clear()
