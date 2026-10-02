"""Deterministic hypothesis generation and server-owned lifecycle helpers."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from backend.app.investigation.context import (
    CorrelationRecord,
    EvidenceRecord,
    InvestigationHypothesis,
    InvestigationHypothesisStatus,
)
from backend.app.models.domain import Incident


class HypothesisEngine:
    """Generate bounded candidates from observed evidence, never from empty context."""

    def generate(
        self,
        incident: Incident,
        evidence: list[EvidenceRecord],
        correlations: list[CorrelationRecord],
        scenario_id: str | None = None,
    ) -> list[InvestigationHypothesis]:
        if not evidence:
            return []
        by_type = self._by_type(evidence)
        text = " ".join([incident.title, incident.description, incident.service]).lower()
        builders: list[Callable[[], InvestigationHypothesis | None]] = []
        scenario_builders: dict[str, Callable[[], InvestigationHypothesis]] = {
            "payment-failure": lambda: self._payment_candidate(incident, by_type),
            "database-failure": lambda: self._database_candidate(incident, by_type),
            "latency-spike": lambda: self._latency_candidate(incident, by_type),
            "bad-deployment": lambda: self._deployment_candidate(incident, by_type),
            "configuration-mismatch": lambda: self._configuration_candidate(incident, by_type),
        }
        if scenario_id in scenario_builders:
            builders.append(scenario_builders[scenario_id])
        elif "database" in text or incident.service.lower() == "database":
            builders.append(lambda: self._database_candidate(incident, by_type))
        elif "latency" in text or "latency" in self._summaries(evidence):
            builders.append(lambda: self._latency_candidate(incident, by_type))
        elif "configuration" in text or any(
            item.evidence_type.value == "CONFIGURATION" for item in evidence
        ):
            builders.append(lambda: self._configuration_candidate(incident, by_type))
        elif "deployment" in text or by_type["deployment"]:
            builders.append(lambda: self._deployment_candidate(incident, by_type))
        elif "payment" in text or "checkout" in text:
            builders.append(lambda: self._payment_candidate(incident, by_type))
        else:
            builders.append(lambda: self._generic_candidate(incident, by_type))

        candidates = [candidate for builder in builders if (candidate := builder()) is not None]
        # A second candidate is useful where both a deployment and a configuration
        # signal exist, but it never changes the server-owned status by itself.
        if (
            scenario_id is None
            and by_type["deployment"]
            and by_type["configuration"]
            and candidates
        ):
            secondary = self._configuration_candidate(incident, by_type)
            if all(item.title != secondary.title for item in candidates):
                candidates.append(secondary)
        return candidates

    @staticmethod
    def _by_type(evidence: list[EvidenceRecord]) -> dict[str, list[EvidenceRecord]]:
        result: dict[str, list[EvidenceRecord]] = {
            "log": [],
            "metric": [],
            "deployment": [],
            "configuration": [],
            "health": [],
            "transaction": [],
            "test": [],
            "other": [],
        }
        for item in evidence:
            key = {
                "LOG": "log",
                "METRIC": "metric",
                "DEPLOYMENT": "deployment",
                "CONFIGURATION": "configuration",
                "HEALTH_CHECK": "health",
                "TRANSACTION": "transaction",
                "TEST_RESULT": "test",
            }.get(item.evidence_type.value, "other")
            result[key].append(item)
        return result

    @staticmethod
    def _summaries(evidence: list[EvidenceRecord]) -> str:
        return " ".join(item.summary.lower() for item in evidence)

    @staticmethod
    def _candidate(
        incident: Incident,
        *,
        title: str,
        description: str,
        domain: str,
        supporting: list[EvidenceRecord],
        contradicting: list[EvidenceRecord],
        missing: list[str],
        priority: str = "HIGH",
        next_step: str | None = None,
    ) -> InvestigationHypothesis:
        return InvestigationHypothesis(
            incident_id=incident.id,
            title=title,
            description=description,
            domain=domain,
            supporting_evidence=[item.evidence_id for item in supporting],
            contradicting_evidence=[item.evidence_id for item in contradicting],
            missing_evidence=missing,
            confidence=0.0,
            status=InvestigationHypothesisStatus.PROPOSED,
            priority=priority,
            next_validation_step=next_step,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

    def _payment_candidate(
        self, incident: Incident, grouped: dict[str, list[EvidenceRecord]]
    ) -> InvestigationHypothesis:
        support = (
            grouped["log"] + grouped["metric"] + grouped["transaction"] + grouped["configuration"]
        )
        return self._candidate(
            incident,
            title="Payment service failure is supported by aligned operational signals",
            description=(
                "Payment failures align with observed payment-service logs, metrics, "
                "or transactions."
            ),
            domain="REVENUE",
            supporting=support[:8],
            # A healthy database is an exclusion signal for a database cause,
            # not a contradiction of a payment-service cause.
            contradicting=[],
            missing=["deployment-specific error signature"] if not grouped["deployment"] else [],
            next_step=(
                "Validate the payment error signature against recent deployment or "
                "configuration evidence."
            ),
        )

    def _database_candidate(
        self, incident: Incident, grouped: dict[str, list[EvidenceRecord]]
    ) -> InvestigationHypothesis:
        return self._candidate(
            incident,
            title="Primary database connectivity failure is driving application impact",
            description=(
                "Database health, connection error logs, and dependent service metrics "
                "indicate a connectivity candidate."
            ),
            domain="DATA",
            supporting=grouped["log"] + grouped["metric"] + grouped["health"],
            contradicting=[],
            missing=["database connectivity recovery evidence"],
            priority="CRITICAL",
            next_step=(
                "Run the database connectivity test and confirm whether dependent services recover."
            ),
        )

    def _latency_candidate(
        self, incident: Incident, grouped: dict[str, list[EvidenceRecord]]
    ) -> InvestigationHypothesis:
        return self._candidate(
            incident,
            title="Downstream dependency latency is causing checkout degradation",
            description=(
                "Checkout latency and dependency observations align within the same "
                "incident window."
            ),
            domain="IT",
            supporting=grouped["metric"] + grouped["log"],
            contradicting=[],
            missing=["dependency saturation metric"],
            priority="HIGH",
            next_step=(
                "Collect a read-only dependency health check before recommending remediation."
            ),
        )

    def _deployment_candidate(
        self, incident: Incident, grouped: dict[str, list[EvidenceRecord]]
    ) -> InvestigationHypothesis:
        return self._candidate(
            incident,
            title="A recent deployment is a root-cause candidate for the service errors",
            description="A deployment occurred near the observed service errors or metric anomaly.",
            domain="IT",
            supporting=grouped["deployment"] + grouped["log"] + grouped["metric"],
            contradicting=[],
            missing=["deployment-specific regression test result"],
            next_step="Run the allow-listed smoke test and inspect the deployment error signature.",
        )

    def _configuration_candidate(
        self, incident: Incident, grouped: dict[str, list[EvidenceRecord]]
    ) -> InvestigationHypothesis:
        return self._candidate(
            incident,
            title="A configuration mismatch is a root-cause candidate",
            description=(
                "The observed configuration differs from its expected value and aligns "
                "with service symptoms."
            ),
            domain="IT",
            supporting=grouped["configuration"] + grouped["log"] + grouped["metric"],
            contradicting=[],
            missing=["configuration rollback validation"],
            next_step="Validate the configuration-specific error signature with a read-only test.",
        )

    def _generic_candidate(
        self, incident: Incident, grouped: dict[str, list[EvidenceRecord]]
    ) -> InvestigationHypothesis:
        return self._candidate(
            incident,
            title="Observed service signals share a common incident window",
            description=(
                "The available evidence suggests a service-level incident, but the "
                "causal mechanism remains unresolved."
            ),
            domain="IT",
            supporting=grouped["log"] + grouped["metric"] + grouped["health"],
            contradicting=[],
            missing=["independent causal signal"],
            priority="MEDIUM",
            next_step="Collect an additional independent read-only signal before escalation.",
        )


__all__ = ["HypothesisEngine"]
