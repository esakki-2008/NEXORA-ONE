from __future__ import annotations

from uuid import UUID

from fastapi.testclient import TestClient

from backend.app.ai.schemas import (
    AIAnalysisResponse,
    AIAnalysisStatus,
    AIAnalysisStep,
    AIHealthResponse,
    AIHealthStatus,
    HypothesisSummary,
)
from backend.app.config.settings import Settings
from backend.app.database.repository import InMemoryIncidentRepository
from backend.app.investigation.context import (
    EvidenceRecord,
    InvestigationEvidenceType,
    InvestigationHypothesis,
    InvestigationHypothesisStatus,
    InvestigationStatus,
)
from backend.app.investigation.correlation import EvidenceCorrelator
from backend.app.investigation.scoring import HypothesisScorer
from backend.app.investigation.validators import hypotheses_from_ai
from backend.app.main import create_app
from backend.app.models.enums import RiskLevel
from backend.tests.auth_helpers import authenticate


def make_client() -> tuple[TestClient, InMemoryIncidentRepository]:
    repository = InMemoryIncidentRepository()
    application = create_app(
        repository=repository,
        settings=Settings(environment="test"),
    )
    return authenticate(TestClient(application)), repository


class RecordingInvestigationAI:
    def __init__(self, *, malformed: bool = False) -> None:
        self.requests = []
        self.malformed = malformed

    def health(self) -> AIHealthResponse:
        return AIHealthResponse(
            model="nvidia/nemotron-test",
            status=AIHealthStatus.CONFIGURED,
            verified=True,
            message="test provider",
        )

    async def analyze(self, request, *, tenant_id: str | None = None):
        del tenant_id
        self.requests.append(request)
        if self.malformed:
            raise ValueError("private provider payload")
        return AIAnalysisResponse(
            status=AIAnalysisStatus.ANALYSIS_COMPLETE,
            current_step=AIAnalysisStep.HYPOTHESIS_GENERATED,
            summary="Validated structured assist.",
            confidence=0.99,
        )


def create_incident(client: TestClient, *, service: str = "Payment Service") -> str:
    response = client.post(
        "/api/incidents",
        json={
            "title": "ShopFlow payment investigation",
            "description": "Payment authorization failures increased after a release.",
            "severity": "high",
            "service": service,
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_payment_investigation_collects_provenance_and_scores_a_candidate() -> None:
    client, repository = make_client()
    with client:
        incident_id = create_incident(client)
        response = client.post(
            f"/api/investigations/incidents/{incident_id}/start",
            json={
                "scenario_id": "payment-failure",
                "request_id": "investigation-payment-1",
                "auto_handoff": False,
            },
        )
        assert response.status_code == 202
        payload = response.json()
        investigation_id = payload["investigation_id"]

        assert payload["status"] == InvestigationStatus.COMPLETED
        assert payload["source_type"] == "SIMULATED / CONTROLLED DEMONSTRATION"
        assert len(payload["evidence"]) >= 8
        assert len(payload["correlations"]) >= 1
        assert len(payload["hypotheses"]) == 1
        assert len({item["title"] for item in payload["hypotheses"]}) == len(payload["hypotheses"])
        assert any(
            item["status"] == InvestigationHypothesisStatus.SUPPORTED
            for item in payload["hypotheses"]
        )
        assert payload["confidence"] >= 0.62
        assert payload["confidence_factors"]
        assert payload["root_cause_candidates"][0]["qualification"] == "Root-cause candidate"
        assert payload["recommended_next_step"]
        assert payload["orchestrator_handoff"]["status"] == "READY"
        assert all(
            item["source"].startswith("SIMULATED / CONTROLLED DEMONSTRATION")
            for item in payload["evidence"]
        )
        assert all(item["raw_reference"] for item in payload["evidence"])
        assert any(item["event_type"] == "evidence.collected" for item in payload["timeline"])
        assert any(item["event_type"] == "evidence.correlated" for item in payload["timeline"])
        assert any(item["event_type"] == "hypothesis.tested" for item in payload["timeline"])

        assert client.get(f"/api/investigations/{investigation_id}").status_code == 200
        assert client.get(f"/api/investigations/{investigation_id}/evidence").status_code == 200
        assert client.get(f"/api/investigations/{investigation_id}/correlations").status_code == 200
        assert client.get(f"/api/investigations/{investigation_id}/hypotheses").status_code == 200
        assert client.get(f"/api/investigations/{investigation_id}/timeline").status_code == 200
        summary = client.get(f"/api/investigations/{investigation_id}/summary")
        assert summary.status_code == 200
        assert summary.json()["evidence_count"] == len(payload["evidence"])
        assert repository.list_evidence(UUID(incident_id))
        assert repository.list_hypotheses(UUID(incident_id))


def test_simulator_ai_request_uses_scenario_boundary_and_invalid_ai_stops_handoff() -> None:
    ai = RecordingInvestigationAI()
    repository = InMemoryIncidentRepository()
    client = TestClient(
        create_app(
            repository=repository,
            settings=Settings(environment="test"),
            ai_service=ai,
        )
    )
    authenticate(client)
    with client:
        incident_id = create_incident(client)
        response = client.post(
            f"/api/investigations/incidents/{incident_id}/start",
            json={"scenario_id": "payment-failure", "auto_handoff": False},
        )
        assert response.status_code == 202
        assert ai.requests[0].scenario_id == "payment-failure"
        assert ai.requests[0].incident_id is None
        assert response.json()["ai_summary"] == "Validated structured assist."

    malformed_ai = RecordingInvestigationAI(malformed=True)
    malformed_client = TestClient(
        create_app(
            repository=InMemoryIncidentRepository(),
            settings=Settings(environment="test"),
            ai_service=malformed_ai,
        )
    )
    authenticate(malformed_client)
    with malformed_client:
        incident_id = create_incident(malformed_client)
        payload = malformed_client.post(
            f"/api/investigations/incidents/{incident_id}/start",
            json={"scenario_id": "payment-failure", "auto_handoff": False},
        ).json()
        assert payload["status"] == "COMPLETED"
        assert payload["orchestrator_handoff"]["status"] == "REQUIRES_HUMAN"
        assert "private provider payload" not in " ".join(payload["errors"])
        assert "Nemotron response could not be safely incorporated" in payload["errors"]


def test_investigation_request_id_and_incident_id_are_idempotent() -> None:
    client, _ = make_client()
    with client:
        incident_id = create_incident(client)
        body = {
            "scenario_id": "database-failure",
            "request_id": "same-request",
            "auto_handoff": False,
        }
        first = client.post(f"/api/investigations/incidents/{incident_id}/start", json=body)
        second = client.post(f"/api/investigations/incidents/{incident_id}/start", json=body)
        assert first.status_code == second.status_code == 202
        assert first.json()["investigation_id"] == second.json()["investigation_id"]
        by_incident = client.get(f"/api/investigations/incidents/{incident_id}")
        assert by_incident.status_code == 200
        assert by_incident.json()["investigation_id"] == first.json()["investigation_id"]

        other_incident_id = create_incident(client, service="Checkout Service")
        conflict = client.post(
            f"/api/investigations/incidents/{other_incident_id}/start",
            json=body,
        )
        assert conflict.status_code == 409
        assert "another incident" in conflict.json()["detail"]


def test_read_only_boundary_rejects_change_tool_and_does_not_execute_action() -> None:
    client, _ = make_client()
    with client:
        incident_id = create_incident(client)
        started = client.post(
            f"/api/investigations/incidents/{incident_id}/start",
            json={"scenario_id": "payment-failure", "auto_handoff": False},
        )
        investigation_id = started.json()["investigation_id"]
        response = client.post(
            f"/api/investigations/{investigation_id}/collect",
            json={"tool_names": ["execute_safe_action"]},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "REQUIRES_HUMAN"
        assert not any(
            item["evidence_type"] == "SYSTEM_EVENT" and "action" in item["summary"].lower()
            for item in payload["evidence"]
        )
        assert client.get("/api/orchestrator/actions").json() == []


def test_test_hypothesis_operation_reuses_only_allow_listed_read_only_probes() -> None:
    client, _ = make_client()
    with client:
        incident_id = create_incident(client)
        started = client.post(
            f"/api/investigations/incidents/{incident_id}/start",
            json={"scenario_id": "payment-failure", "auto_handoff": False},
        ).json()
        investigation_id = started["investigation_id"]
        hypothesis_id = started["hypotheses"][0]["hypothesis_id"]
        response = client.post(
            f"/api/investigations/{investigation_id}/test-hypothesis",
            json={"hypothesis_id": hypothesis_id, "tool_names": ["run_health_check"]},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["hypotheses"][0]["status"] in {"SUPPORTED", "INCONCLUSIVE"}
        assert any(
            item["event_type"] == "hypothesis.testing.completed" for item in payload["timeline"]
        )
        assert client.get("/api/orchestrator/actions").json() == []


def test_ai_hypotheses_are_citation_filtered_and_server_owned() -> None:
    evidence = [
        EvidenceRecord(
            evidence_id="known-evidence",
            incident_id=UUID("00000000-0000-0000-0000-000000000001"),
            source="SIMULATED / CONTROLLED DEMONSTRATION · ShopFlow",
            evidence_type=InvestigationEvidenceType.LOG,
            timestamp="2026-09-27T00:00:00Z",
            summary="Gateway authorization failed",
            relevance=0.9,
            confidence=0.9,
            collected_by="test",
            simulated=True,
        )
    ]
    response = AIAnalysisResponse(
        status=AIAnalysisStatus.ANALYSIS_COMPLETE,
        current_step=AIAnalysisStep.HYPOTHESIS_GENERATED,
        summary="A model suggestion that still requires server validation.",
        hypotheses=[
            HypothesisSummary(
                title="Untrusted model candidate",
                description="The model supplied this as a possible explanation.",
                confidence=0.99,
                supporting_evidence=["known-evidence", "invented-evidence"],
                contradicting_evidence=["invented-evidence"],
            )
        ],
        confidence=0.99,
    )
    candidates = hypotheses_from_ai(
        response,
        incident_id=evidence[0].incident_id,
        evidence=evidence,
    )
    assert len(candidates) == 1
    assert candidates[0].confidence == 0.0
    assert candidates[0].status == InvestigationHypothesisStatus.PROPOSED
    assert candidates[0].supporting_evidence == ["known-evidence"]
    assert candidates[0].contradicting_evidence == []


def test_contradicting_evidence_remains_visible_and_reduces_confidence() -> None:
    incident_id = UUID("00000000-0000-0000-0000-000000000002")
    evidence = [
        EvidenceRecord(
            evidence_id="supporting-log",
            incident_id=incident_id,
            source="Payment Service",
            evidence_type=InvestigationEvidenceType.LOG,
            timestamp="2026-09-27T00:00:00Z",
            summary="Payment gateway authorization failed",
            relevance=0.9,
            confidence=0.9,
            collected_by="test",
        ),
        EvidenceRecord(
            evidence_id="contradicting-health",
            incident_id=incident_id,
            source="Payment Service",
            evidence_type=InvestigationEvidenceType.HEALTH_CHECK,
            timestamp="2026-09-27T00:01:00Z",
            summary="Payment Service health: HEALTHY",
            relevance=0.9,
            confidence=0.9,
            collected_by="test",
        ),
    ]
    hypothesis = {
        "incident_id": incident_id,
        "title": "Payment service failure candidate",
        "description": "A test candidate with an explicit contradictory health signal.",
        "domain": "REVENUE",
        "supporting_evidence": ["supporting-log"],
        "contradicting_evidence": ["contradicting-health"],
        "confidence": 0.0,
    }
    scored, assessment = HypothesisScorer().score(
        InvestigationHypothesis(**hypothesis), evidence, []
    )
    assert scored.contradicting_evidence == ["contradicting-health"]
    assert scored.status == InvestigationHypothesisStatus.REJECTED
    assert assessment.factors["contradiction_penalty"] > 0
    assert any("contradictory" in item for item in assessment.explanation)


def test_all_controlled_scenarios_produce_distinct_evidence_conclusions() -> None:
    scenarios = [
        ("payment-failure", "Payment Service"),
        ("database-failure", "Database"),
        ("latency-spike", "Checkout Service"),
        ("bad-deployment", "User Service"),
        ("configuration-mismatch", "Payment Service"),
    ]
    client, _ = make_client()
    statuses: dict[str, str] = {}
    with client:
        for scenario_id, service in scenarios:
            incident_id = create_incident(client, service=service)
            response = client.post(
                f"/api/investigations/incidents/{incident_id}/start",
                json={"scenario_id": scenario_id, "auto_handoff": False},
            )
            assert response.status_code == 202
            payload = response.json()
            statuses[scenario_id] = payload["hypotheses"][0]["title"]
            assert payload["evidence"]
            assert payload["status"] in {"COMPLETED", "INCONCLUSIVE", "REQUIRES_HUMAN"}
    assert len(set(statuses.values())) == len(statuses)


def test_live_incident_without_evidence_is_not_fabricated() -> None:
    client, _ = make_client()
    with client:
        incident_id = create_incident(client)
        response = client.post(
            f"/api/investigations/incidents/{incident_id}/start",
            json={"auto_handoff": False},
        )
        assert response.status_code == 202
        payload = response.json()
        assert payload["status"] == "REQUIRES_HUMAN"
        assert payload["evidence"] == []
        assert payload["hypotheses"] == []
        assert payload["errors"]


def test_cancellation_is_safe_and_handoff_stays_at_the_boundary() -> None:
    client, _ = make_client()
    with client:
        incident_id = create_incident(client)
        started = client.post(
            f"/api/investigations/incidents/{incident_id}/start",
            json={"scenario_id": "latency-spike", "auto_handoff": False},
        ).json()
        investigation_id = started["investigation_id"]
        response = client.post(
            f"/api/investigations/{investigation_id}/cancel",
            json={"requested_by": "test-operator", "reason": "Stop investigation"},
        )
        assert response.status_code == 200
        # A completed investigation is immutable by cancellation; the request
        # cannot downgrade an evidence-grounded result.
        assert response.json()["status"] == "COMPLETED"
        handoff = client.post(f"/api/investigations/{investigation_id}/handoff")
        assert handoff.status_code == 200
        assert handoff.json()["orchestrator_handoff"]["status"] == "REQUIRES_HUMAN"


def test_correlator_and_scorer_are_explainable_without_model_reasoning() -> None:
    client, _ = make_client()
    with client:
        incident_id = UUID(create_incident(client))
        started = client.post(
            f"/api/investigations/incidents/{incident_id}/start",
            json={"scenario_id": "bad-deployment", "auto_handoff": False},
        ).json()
        assert started["correlations"]
        correlation = started["correlations"][0]
        assert correlation["reason"]
        assert correlation["dimensions"]
        assert "causation" not in correlation["reason"].lower()
        assert started["confidence_factors"]
        assert all(isinstance(value, float) for value in started["confidence_factors"].values())

    # The public imports also enforce that the dedicated layer is independently usable.
    assert EvidenceRecord.model_fields["raw_reference"].is_required() is False
    assert InvestigationEvidenceType.LOG.value == "LOG"
    assert HypothesisScorer
    assert EvidenceCorrelator
    assert RiskLevel.READ_ONLY.value == "READ_ONLY"
