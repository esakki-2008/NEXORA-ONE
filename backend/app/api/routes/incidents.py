"""Incident resource routes."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from backend.app.api.dependencies import get_incident_service
from backend.app.models.domain import Evidence, Hypothesis, Incident, IncidentReport
from backend.app.schemas.incidents import ActivityEvent, IncidentCreate
from backend.app.services.incident_service import (
    IncidentNotFoundError,
    IncidentService,
    ReportNotFoundError,
)

router = APIRouter(prefix="/api/incidents", tags=["incidents"])
IncidentServiceDependency = Annotated[IncidentService, Depends(get_incident_service)]


def _not_found(incident_id: UUID) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND, detail=f"Incident {incident_id} was not found"
    )


@router.post(
    "", response_model=Incident, status_code=status.HTTP_201_CREATED, summary="Create an incident"
)
def create_incident(request: IncidentCreate, service: IncidentServiceDependency) -> Incident:
    return service.create_incident(request)


@router.get("", response_model=list[Incident], summary="List incidents")
def list_incidents(service: IncidentServiceDependency) -> list[Incident]:
    return service.list_incidents()


@router.get("/{incident_id}", response_model=Incident, summary="Get an incident")
def get_incident(incident_id: UUID, service: IncidentServiceDependency) -> Incident:
    try:
        return service.get_incident(incident_id)
    except IncidentNotFoundError as exc:
        raise _not_found(incident_id) from exc


@router.get(
    "/{incident_id}/activity", response_model=list[ActivityEvent], summary="List incident activity"
)
def list_activity(incident_id: UUID, service: IncidentServiceDependency) -> list[ActivityEvent]:
    try:
        return service.list_activity(incident_id)
    except IncidentNotFoundError as exc:
        raise _not_found(incident_id) from exc


@router.get(
    "/{incident_id}/evidence", response_model=list[Evidence], summary="List incident evidence"
)
def list_evidence(incident_id: UUID, service: IncidentServiceDependency) -> list[Evidence]:
    try:
        return service.list_evidence(incident_id)
    except IncidentNotFoundError as exc:
        raise _not_found(incident_id) from exc


@router.get(
    "/{incident_id}/hypotheses", response_model=list[Hypothesis], summary="List incident hypotheses"
)
def list_hypotheses(incident_id: UUID, service: IncidentServiceDependency) -> list[Hypothesis]:
    try:
        return service.list_hypotheses(incident_id)
    except IncidentNotFoundError as exc:
        raise _not_found(incident_id) from exc


@router.get(
    "/{incident_id}/report", response_model=IncidentReport, summary="Get an incident report"
)
def get_report(incident_id: UUID, service: IncidentServiceDependency) -> IncidentReport:
    try:
        return service.get_report(incident_id)
    except IncidentNotFoundError as exc:
        raise _not_found(incident_id) from exc
    except ReportNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No report is available for incident {incident_id}",
        ) from exc
