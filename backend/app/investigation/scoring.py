"""Explainable, server-controlled hypothesis confidence scoring."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime

from backend.app.investigation.context import (
    ConfidenceAssessment,
    CorrelationRecord,
    EvidenceRecord,
    InvestigationHypothesis,
    InvestigationHypothesisStatus,
)


class HypothesisScorer:
    """Calculate confidence from evidence quality, independence, and contradictions."""

    def score(
        self,
        hypothesis: InvestigationHypothesis,
        evidence: list[EvidenceRecord],
        correlations: list[CorrelationRecord],
    ) -> tuple[InvestigationHypothesis, ConfidenceAssessment]:
        by_id = {item.evidence_id: item for item in evidence}
        supporting = [by_id[item] for item in hypothesis.supporting_evidence if item in by_id]
        contradicting = [by_id[item] for item in hypothesis.contradicting_evidence if item in by_id]
        types = {item.evidence_type.value for item in supporting}
        related = [
            item
            for item in correlations
            if set(item.evidence_ids) & set(hypothesis.supporting_evidence)
        ]
        support_signal = min(1.0, len(supporting) / 4)
        independent_signal = min(1.0, len(types) / 4)
        relationship_signal = min(1.0, len(related) / 3)
        quality_signal = (
            sum(item.confidence * item.relevance for item in supporting) / len(supporting)
            if supporting
            else 0.0
        )
        temporal_signal = sum(item.strength for item in related) / len(related) if related else 0.0
        contradiction_penalty = min(0.45, len(contradicting) * 0.18)
        missing_penalty = min(0.25, len(hypothesis.missing_evidence) * 0.05)
        raw_score = (
            0.10
            + (support_signal * 0.24)
            + (independent_signal * 0.18)
            + (relationship_signal * 0.18)
            + (quality_signal * 0.18)
            + (temporal_signal * 0.12)
            - contradiction_penalty
            - missing_penalty
        )
        confidence = max(0.0, min(1.0, raw_score))
        factors = {
            "supporting_signals": round(support_signal, 3),
            "independent_signal_types": round(independent_signal, 3),
            "correlation_strength": round(relationship_signal, 3),
            "evidence_quality": round(quality_signal, 3),
            "temporal_alignment": round(temporal_signal, 3),
            "contradiction_penalty": round(contradiction_penalty, 3),
            "missing_evidence_penalty": round(missing_penalty, 3),
        }
        if contradicting:
            status = (
                InvestigationHypothesisStatus.REJECTED
                if confidence < 0.55
                else InvestigationHypothesisStatus.INCONCLUSIVE
            )
        elif confidence >= 0.62 and len(supporting) >= 2:
            status = InvestigationHypothesisStatus.SUPPORTED
        else:
            status = InvestigationHypothesisStatus.INCONCLUSIVE
        explanation = self.explain(factors, status, supporting, contradicting)
        updated = hypothesis.model_copy(
            update={
                "confidence": round(confidence, 3),
                "confidence_factors": factors,
                "status": status,
                "updated_at": datetime.now(UTC),
            }
        )
        return updated, ConfidenceAssessment(
            confidence=round(confidence, 3),
            factors=factors,
            explanation=explanation,
        )

    @staticmethod
    def explain(
        factors: dict[str, float],
        status: InvestigationHypothesisStatus,
        supporting: Iterable[EvidenceRecord],
        contradicting: Iterable[EvidenceRecord],
    ) -> list[str]:
        support_count = len(list(supporting))
        contradiction_count = len(list(contradicting))
        explanation = [
            (
                f"{support_count} cited supporting signal(s) from "
                f"{factors['independent_signal_types']:.0%} independent "
                "evidence-type coverage."
            ),
            (
                "Correlation and temporal alignment contributed "
                f"{factors['correlation_strength']:.0%} and "
                f"{factors['temporal_alignment']:.0%} respectively."
            ),
        ]
        if contradiction_count:
            explanation.append(f"{contradiction_count} contradictory signal(s) reduced confidence.")
        if factors["missing_evidence_penalty"] > 0:
            explanation.append(
                "Missing evidence reduced confidence; this remains a candidate, "
                "not a confirmed root cause."
            )
        if status is InvestigationHypothesisStatus.SUPPORTED:
            explanation.append(
                "Server-side validation supports this hypothesis as a root-cause candidate."
            )
        else:
            explanation.append("Evidence is not sufficient to call this a confirmed root cause.")
        return explanation


__all__ = ["HypothesisScorer"]
