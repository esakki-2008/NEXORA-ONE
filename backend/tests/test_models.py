from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from backend.app.models.domain import Evidence, Hypothesis, Incident
from backend.app.models.enums import EvidenceType, Severity


def test_domain_models_validate_ranges_and_required_relationships() -> None:
    incident_id = uuid4()
    evidence = Evidence(
        incident_id=incident_id,
        type=EvidenceType.METRIC,
        source="shopflow.metrics",
        timestamp=datetime.now(UTC),
        summary="Failure rate is elevated.",
        data={"value": 0.42},
        relevance=0.9,
    )
    hypothesis = Hypothesis(
        incident_id=incident_id,
        title="Recent deployment changed payment behavior",
        description="The deployment is temporally correlated with the failure increase.",
        confidence=0.8,
        supporting_evidence=[evidence.id],
    )

    assert hypothesis.supporting_evidence == [evidence.id]


def test_incident_rejects_unknown_fields_and_invalid_severity() -> None:
    with pytest.raises(ValidationError):
        Incident(
            title="Valid title",
            description="Valid description",
            severity="urgent",
            service="Checkout Service",
            made_up_field=True,
        )


def test_incident_accepts_supported_severity() -> None:
    incident = Incident(
        title="Database unavailable",
        description="The database is not accepting connections.",
        severity=Severity.CRITICAL,
        service="Database",
    )

    assert incident.severity is Severity.CRITICAL
