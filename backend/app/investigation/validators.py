"""Validation gates for untrusted evidence and structured AI suggestions."""

from __future__ import annotations

from collections.abc import Iterable
from uuid import UUID

from backend.app.ai.schemas import AIAnalysisResponse
from backend.app.investigation.context import (
    EvidenceRecord,
    InvestigationHypothesis,
    InvestigationHypothesisStatus,
)
from backend.app.models.enums import RiskLevel
from backend.app.tools.catalog import FOUNDATION_TOOL_CATALOG
from backend.app.tools.contracts import ToolDefinition

READ_ONLY_INVESTIGATION_TOOLS = frozenset(
    {
        "get_logs",
        "get_metrics",
        "get_recent_deployments",
        "inspect_configuration",
        "search_documentation",
        "run_health_check",
        "run_test",
    }
)


class InvestigationValidationError(ValueError):
    """Raised when an investigation input cannot be safely accepted."""


def validate_read_only_tool(tool_name: str) -> ToolDefinition:
    """Return server metadata only for the Phase 5 read-only allow-list."""

    if tool_name not in READ_ONLY_INVESTIGATION_TOOLS:
        raise InvestigationValidationError(
            f"Investigation tool {tool_name!r} is not read-only allow-listed"
        )
    try:
        definition = FOUNDATION_TOOL_CATALOG.get(tool_name)
    except LookupError as exc:
        raise InvestigationValidationError("Investigation tool is not registered") from exc
    # run_test is a bounded, explicitly permitted low-risk Phase 4 tool. It
    # cannot mutate state and is admitted here as a read-only investigation probe.
    if not definition.enabled or definition.risk_level is RiskLevel.HIGH:
        raise InvestigationValidationError("Investigation tool is disabled or carries change risk")
    return definition


def validate_evidence_citations(
    citations: Iterable[str], evidence: list[EvidenceRecord]
) -> list[str]:
    """Keep only citations that exist in the server-collected evidence ledger."""

    available = {item.evidence_id for item in evidence}
    result: list[str] = []
    for citation in citations:
        if citation in available and citation not in result:
            result.append(citation)
    return result


def validate_hypothesis(
    hypothesis: InvestigationHypothesis, evidence: list[EvidenceRecord]
) -> InvestigationHypothesis:
    """Ground a candidate in server evidence and reset untrusted lifecycle claims."""

    supporting = validate_evidence_citations(hypothesis.supporting_evidence, evidence)
    contradicting = validate_evidence_citations(hypothesis.contradicting_evidence, evidence)
    return hypothesis.model_copy(
        update={
            "supporting_evidence": supporting,
            "contradicting_evidence": contradicting,
            "status": InvestigationHypothesisStatus.PROPOSED,
        }
    )


def hypotheses_from_ai(
    response: AIAnalysisResponse,
    *,
    incident_id: UUID,
    evidence: list[EvidenceRecord],
) -> list[InvestigationHypothesis]:
    """Convert Nemotron suggestions into proposed, server-scored candidates."""

    known = {item.evidence_id for item in evidence}
    candidates: list[InvestigationHypothesis] = []
    for item in response.hypotheses:
        supporting = [value for value in item.supporting_evidence if value in known]
        contradicting = [value for value in item.contradicting_evidence if value in known]
        # The model's confidence and status are deliberately not authoritative.
        candidates.append(
            InvestigationHypothesis(
                incident_id=incident_id,
                title=item.title,
                description=item.description,
                domain="AI_SUGGESTED",
                supporting_evidence=supporting,
                contradicting_evidence=contradicting,
                missing_evidence=[],
                confidence=0.0,
                status=InvestigationHypothesisStatus.PROPOSED,
                priority="MEDIUM",
                next_validation_step="Server-side evidence validation required.",
            )
        )
    return candidates


__all__ = [
    "InvestigationValidationError",
    "READ_ONLY_INVESTIGATION_TOOLS",
    "hypotheses_from_ai",
    "validate_evidence_citations",
    "validate_hypothesis",
    "validate_read_only_tool",
]
