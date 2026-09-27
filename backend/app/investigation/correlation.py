"""Deterministic, explainable evidence correlation rules."""

from __future__ import annotations

from datetime import UTC
from itertools import combinations
from uuid import UUID

from backend.app.investigation.context import (
    CorrelationRecord,
    EvidenceRecord,
    InvestigationEvidenceType,
)


class EvidenceCorrelator:
    """Correlate evidence without claiming causation from a relationship alone."""

    _error_terms = (
        "error",
        "failed",
        "failure",
        "timeout",
        "refused",
        "unsupported",
        "invalid",
        "exhausted",
        "unavailable",
    )

    def correlate(
        self,
        evidence: list[EvidenceRecord],
        *,
        incident_id: UUID,
    ) -> list[CorrelationRecord]:
        records: list[CorrelationRecord] = []
        seen: set[tuple[str, str, str]] = set()
        for left, right in combinations(evidence, 2):
            relationship = self._relationship(left, right)
            if relationship is None:
                continue
            relation, reason, dimensions, strength = relationship
            pair = tuple(sorted((left.evidence_id, right.evidence_id)))
            key = (pair[0], pair[1], relation)
            if key in seen:
                continue
            seen.add(key)
            left_timestamp = left.timestamp.astimezone(UTC)
            right_timestamp = right.timestamp.astimezone(UTC)
            delta = int(abs((left_timestamp - right_timestamp).total_seconds()))
            records.append(
                CorrelationRecord(
                    incident_id=incident_id,
                    evidence_ids=[left.evidence_id, right.evidence_id],
                    relationship=relation,
                    reason=reason,
                    dimensions=dimensions,
                    strength=strength,
                    temporal_delta_seconds=delta,
                )
            )
        return records[:500]

    def _relationship(
        self, left: EvidenceRecord, right: EvidenceRecord
    ) -> tuple[str, str, list[str], float] | None:
        left_service = left.metadata.get("service", left.source)
        right_service = right.metadata.get("service", right.source)
        same_service = left_service == right_service
        delta = abs((left.timestamp - right.timestamp).total_seconds())
        temporal = delta <= 15 * 60
        if not temporal and not (
            same_service and self._shared_signature(left.summary, right.summary)
        ):
            return None

        types = {left.evidence_type, right.evidence_type}
        if InvestigationEvidenceType.DEPLOYMENT in types and (
            InvestigationEvidenceType.LOG in types
            or InvestigationEvidenceType.METRIC in types
        ) and temporal:
            service_note = "same affected service" if same_service else "related service records"
            return (
                "DEPLOYMENT_TEMPORAL_PROXIMITY",
                (
                    f"Temporal proximity + {service_note}; this is a correlation, "
                    "not proof of causation."
                ),
                ["temporal_proximity", "deployment_relationship"],
                0.88 if same_service else 0.72,
            )
        if InvestigationEvidenceType.CONFIGURATION in types and (
            InvestigationEvidenceType.LOG in types
            or InvestigationEvidenceType.METRIC in types
        ) and temporal:
            return (
                "CONFIGURATION_SERVICE_RELATIONSHIP",
                (
                    "Configuration record and service symptom share a service and nearby "
                    "observation window; causation remains unconfirmed."
                ),
                ["configuration_relationship", "temporal_proximity"],
                0.86 if same_service else 0.68,
            )
        if {
            InvestigationEvidenceType.LOG,
            InvestigationEvidenceType.METRIC,
        }.issubset(types) and same_service and temporal:
            return (
                "ERROR_METRIC_ALIGNMENT",
                "Error/log signal and metric anomaly align in time for the same service.",
                ["metric_anomaly", "error_signature", "temporal_proximity"],
                0.84,
            )
        if InvestigationEvidenceType.TRANSACTION in types and (
            InvestigationEvidenceType.LOG in types
            or InvestigationEvidenceType.METRIC in types
        ) and same_service:
            return (
                "TRANSACTION_CUSTOMER_IMPACT",
                (
                    "Transaction outcome aligns with a service log or metric signal "
                    "for the same service."
                ),
                ["transaction_relationship", "customer_impact"],
                0.82,
            )
        if same_service and self._shared_signature(left.summary, right.summary):
            return (
                "ERROR_SIGNATURE_MATCH",
                "Evidence summaries contain a shared error signature for the same source service.",
                ["error_signature", "service_relationship"],
                0.78,
            )
        if not same_service and self._related_services(left_service, right_service) and temporal:
            return (
                "SERVICE_RELATIONSHIP",
                (
                    "Related ShopFlow services show temporally aligned observations; "
                    "this does not establish causation."
                ),
                ["service_relationship", "temporal_proximity"],
                0.68,
            )
        return None

    @classmethod
    def _shared_signature(cls, left: str, right: str) -> bool:
        left_tokens = cls._tokens(left)
        right_tokens = cls._tokens(right)
        return bool((left_tokens & right_tokens) - {"service", "request", "error"})

    @staticmethod
    def _tokens(value: str) -> set[str]:
        return {
            token
            for token in "".join(char.lower() if char.isalnum() else " " for char in value).split()
            if len(token) >= 5
        }

    @staticmethod
    def _related_services(left: str, right: str) -> bool:
        names = {left.lower(), right.lower()}
        return (
            {"payment service", "checkout service"}.issubset(names)
            or {"checkout service", "inventory"}.issubset(names)
            or {"checkout service", "database"}.issubset(names)
        )


__all__ = ["EvidenceCorrelator"]
