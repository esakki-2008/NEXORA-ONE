"""API request and response schemas for incident resources."""

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from backend.app.models.domain import (
    Evidence,
    Hypothesis,
    Incident,
    IncidentReport,
    utc_now,
)
from backend.app.models.enums import EvidenceType, IncidentStatus, Severity


class IncidentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=3, max_length=200)
    description: str = Field(min_length=1, max_length=10_000)
    severity: Severity
    service: str = Field(min_length=1, max_length=120)


class ActivityEvent(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: UUID = Field(default_factory=uuid4)
    incident_id: UUID
    event_type: str = Field(min_length=1, max_length=80)
    message: str = Field(min_length=1, max_length=2_000)
    created_at: datetime = Field(default_factory=utc_now)
    metadata: dict[str, Any] = Field(default_factory=dict)


class HealthResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    service: str
    environment: str
    timestamp: datetime = Field(default_factory=utc_now)


class ScenarioSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scenario_id: str
    name: str
    description: str
    incident_title: str
    severity: Severity


class IncidentListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[Incident]
    total: int = Field(ge=0)


class ErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    detail: str


# Explicit aliases keep route annotations readable while retaining one canonical model.
IncidentResponse = Incident
EvidenceResponse = Evidence
HypothesisResponse = Hypothesis
IncidentReportResponse = IncidentReport

__all__ = [
    "ActivityEvent",
    "ErrorResponse",
    "EvidenceResponse",
    "HealthResponse",
    "HypothesisResponse",
    "IncidentCreate",
    "IncidentListResponse",
    "IncidentReportResponse",
    "IncidentResponse",
    "ScenarioSummary",
    "EvidenceType",
    "IncidentStatus",
]
