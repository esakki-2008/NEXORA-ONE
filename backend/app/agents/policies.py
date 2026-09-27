"""Deterministic routing, prioritization, and server-side tool policy."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from backend.app.agents.context import (
    EvidenceItem,
    HypothesisRecord,
    HypothesisStatus,
    OrchestrationDomain,
    Priority,
)
from backend.app.models.domain import Incident
from backend.app.models.enums import ApprovalStatus, RiskLevel, Severity
from backend.app.tools.contracts import ToolDefinition

RISK_ORDER: dict[RiskLevel, int] = {
    RiskLevel.READ_ONLY: 0,
    RiskLevel.LOW: 1,
    RiskLevel.MEDIUM: 2,
    RiskLevel.HIGH: 3,
}


@dataclass(frozen=True, slots=True)
class DomainSelection:
    primary: OrchestrationDomain | None
    domains: tuple[OrchestrationDomain, ...]
    confidence: float
    signals: tuple[str, ...]


class DomainRouter:
    """Keyword/service routing only; it never invents domain observations."""

    _rules: dict[OrchestrationDomain, tuple[str, ...]] = {
        OrchestrationDomain.REVENUE: ("payment", "billing", "checkout", "revenue", "charge"),
        OrchestrationDomain.IT: ("api", "service", "database", "incident", "deployment", "latency"),
        OrchestrationDomain.SUPPORT: ("support", "ticket", "customer", "case", "escalation"),
        OrchestrationDomain.SUPPLY_CHAIN: (
            "supplier",
            "inventory",
            "shipment",
            "warehouse",
            "order",
        ),
        OrchestrationDomain.CONTRACTS: (
            "contract",
            "renewal",
            "obligation",
            "penalty",
            "expiration",
        ),
        OrchestrationDomain.CLOUD: ("cloud", "compute", "resource", "usage", "cost", "capacity"),
        OrchestrationDomain.DATA: (
            "data",
            "pipeline",
            "quality",
            "warehouse",
            "database",
            "schema",
        ),
        OrchestrationDomain.COMPLIANCE: ("compliance", "control", "audit", "policy", "regulatory"),
    }

    def select(self, incident: Incident, evidence: list[EvidenceItem]) -> DomainSelection:
        text = " ".join(
            [incident.title, incident.description, incident.service]
            + [item.summary for item in evidence[:100]]
        ).lower()
        scored: list[tuple[OrchestrationDomain, int, list[str]]] = []
        for domain, signals in self._rules.items():
            matched = [signal for signal in signals if signal in text]
            if matched:
                scored.append((domain, len(matched), matched))
        scored.sort(key=lambda item: (-item[1], item[0].value))
        if not scored:
            return DomainSelection(None, (), 0.0, ())
        top_score = scored[0][1]
        selected = tuple(item[0] for item in scored if item[1] >= max(1, top_score - 1))[:3]
        confidence = min(0.98, 0.55 + (top_score * 0.12) + (0.05 if incident.service else 0))
        signals = tuple(signal for _, _, matches in scored[:3] for signal in matches)
        return DomainSelection(selected[0], selected, confidence, signals)


@dataclass(frozen=True, slots=True)
class PolicyDecision:
    allowed: bool
    requires_approval: bool
    reason: str


class ToolPolicy:
    """Central policy; model-provided risk metadata is never trusted."""

    explicitly_permitted_low_risk = frozenset(
        {"run_test", "create_remediation_plan", "generate_incident_report"}
    )

    def evaluate(self, definition: ToolDefinition, approval: Any = None) -> PolicyDecision:
        if not definition.enabled:
            return PolicyDecision(False, False, "Tool is disabled by server policy")
        actual_risk = definition.risk_level
        if actual_risk is RiskLevel.READ_ONLY:
            return PolicyDecision(True, False, "Read-only tool permitted by policy")
        if actual_risk is RiskLevel.LOW and definition.name in self.explicitly_permitted_low_risk:
            return PolicyDecision(True, False, "Low-risk tool explicitly permitted by policy")
        if approval is None:
            return PolicyDecision(
                False, True, f"{actual_risk.value} action requires human approval"
            )
        if approval.status is not ApprovalStatus.APPROVED:
            return PolicyDecision(False, True, "Approval is not approved")
        if RISK_ORDER[approval.risk_level] < RISK_ORDER[actual_risk]:
            return PolicyDecision(False, True, "Approval does not cover server-defined tool risk")
        return PolicyDecision(True, True, "Approved by server-side policy")


class PriorityPolicy:
    """Explainable priority calculation independent of model claims."""

    def calculate(
        self,
        incident: Incident,
        *,
        evidence_count: int,
        confidence: float,
        risk: RiskLevel,
    ) -> tuple[Priority, dict[str, float]]:
        severity_score = {
            Severity.LOW: 0.2,
            Severity.MEDIUM: 0.45,
            Severity.HIGH: 0.75,
            Severity.CRITICAL: 1.0,
        }[incident.severity]
        scope = min(1.0, evidence_count / 10)
        risk_score = RISK_ORDER[risk] / 3
        score = (severity_score * 0.45) + (scope * 0.15) + (confidence * 0.25) + (risk_score * 0.15)
        if score >= 0.8:
            priority = Priority.CRITICAL
        elif score >= 0.6:
            priority = Priority.HIGH
        elif score >= 0.35:
            priority = Priority.MEDIUM
        else:
            priority = Priority.LOW
        return priority, {
            "severity": round(severity_score, 3),
            "scope": round(scope, 3),
            "confidence": round(confidence, 3),
            "risk": round(risk_score, 3),
            "score": round(score, 3),
        }


class HypothesisEvaluator:
    """Server-controlled lifecycle evaluator based only on cited available evidence."""

    def evaluate(
        self, hypotheses: list[HypothesisRecord], evidence: list[EvidenceItem]
    ) -> list[HypothesisRecord]:
        available = {item.id for item in evidence}
        evaluated: list[HypothesisRecord] = []
        for hypothesis in hypotheses:
            supporting = [item for item in hypothesis.supporting_evidence if item in available]
            contradicting = [
                item for item in hypothesis.contradicting_evidence if item in available
            ]
            missing = [item for item in hypothesis.supporting_evidence if item not in available]
            if contradicting:
                lifecycle = HypothesisStatus.REJECTED
            elif supporting:
                lifecycle = HypothesisStatus.SUPPORTED
            else:
                lifecycle = HypothesisStatus.INCONCLUSIVE
            evaluated.append(
                hypothesis.model_copy(
                    update={
                        "supporting_evidence": supporting,
                        "contradicting_evidence": contradicting,
                        "missing_evidence": missing,
                        "status": lifecycle,
                    }
                )
            )
        return evaluated


__all__ = [
    "DomainRouter",
    "DomainSelection",
    "HypothesisEvaluator",
    "PolicyDecision",
    "PriorityPolicy",
    "RISK_ORDER",
    "ToolPolicy",
]
