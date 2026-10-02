"""Use cases for the incident API."""

from uuid import UUID

from backend.app.database.repository import IncidentRepository
from backend.app.models.domain import Evidence, Hypothesis, Incident, IncidentReport
from backend.app.schemas.incidents import ActivityEvent, IncidentCreate


class IncidentNotFoundError(LookupError):
    """Raised when a requested incident does not exist."""


class ReportNotFoundError(LookupError):
    """Raised when an incident has no generated report yet."""


class IncidentService:
    """Coordinate incident use cases without coupling them to storage."""

    def __init__(self, repository: IncidentRepository) -> None:
        self._repository = repository

    def create_incident(
        self, request: IncidentCreate, *, tenant_id: str = "reference-tenant"
    ) -> Incident:
        incident = Incident(
            tenant_id=tenant_id,
            title=request.title,
            description=request.description,
            severity=request.severity,
            service=request.service,
        )
        created = self._repository.create_incident(incident)
        self._repository.add_activity(
            ActivityEvent(
                tenant_id=created.tenant_id,
                incident_id=created.id,
                event_type="incident.created",
                message="Incident received by NEXORA ONE.",
                metadata={"source": "api"},
            )
        )
        return created

    def list_incidents(self, *, tenant_id: str | None = None) -> list[Incident]:
        incidents = self._repository.list_incidents()
        return [item for item in incidents if tenant_id is None or item.tenant_id == tenant_id]

    def get_incident(self, incident_id: UUID, *, tenant_id: str | None = None) -> Incident:
        incident = self._repository.get_incident(incident_id)
        if incident is None or (tenant_id is not None and incident.tenant_id != tenant_id):
            raise IncidentNotFoundError(str(incident_id))
        return incident

    def list_activity(
        self, incident_id: UUID, *, tenant_id: str | None = None
    ) -> list[ActivityEvent]:
        self.get_incident(incident_id, tenant_id=tenant_id)
        return self._repository.list_activity(incident_id)

    def list_evidence(self, incident_id: UUID, *, tenant_id: str | None = None) -> list[Evidence]:
        self.get_incident(incident_id, tenant_id=tenant_id)
        return self._repository.list_evidence(incident_id)

    def list_hypotheses(
        self, incident_id: UUID, *, tenant_id: str | None = None
    ) -> list[Hypothesis]:
        self.get_incident(incident_id, tenant_id=tenant_id)
        return self._repository.list_hypotheses(incident_id)

    def get_report(self, incident_id: UUID, *, tenant_id: str | None = None) -> IncidentReport:
        self.get_incident(incident_id, tenant_id=tenant_id)
        report = self._repository.get_report(incident_id)
        if report is None:
            raise ReportNotFoundError(str(incident_id))
        return report
