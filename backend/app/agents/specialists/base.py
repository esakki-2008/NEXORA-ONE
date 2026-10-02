"""Controlled specialist modules; intelligence remains in the shared AI service."""

from __future__ import annotations

from typing import Any

from backend.app.agents.base import AgentContext, AgentResult, SpecialistAgent
from backend.app.agents.context import OrchestrationContext, OrchestrationDomain


class DomainSpecialist(SpecialistAgent):
    """A bounded domain module, not an independent unrestricted model."""

    domain_enum: OrchestrationDomain
    capabilities: tuple[str, ...] = ()
    tool_names: tuple[str, ...] = ()
    keywords: tuple[str, ...] = ()

    async def run(self, context: AgentContext) -> AgentResult:
        return AgentResult(
            status="available",
            message=f"{self.name} is registered for bounded {self.domain} work.",
            next_state=None,
        )

    def get_available_tools(self) -> list[str]:
        return list(self.tool_names)

    def build_context(self, context: OrchestrationContext) -> dict[str, Any]:
        return {
            "incident_id": str(context.incident_id),
            "domain": self.domain,
            "service": context.incident.service,
            "evidence_count": len(context.evidence),
            "source_type": context.source_type,
        }

    def analyze(self, context: OrchestrationContext) -> dict[str, Any]:
        """Return deterministic routing metadata; shared AIService does reasoning."""

        text = " ".join(
            [context.incident.title, context.incident.description, context.incident.service]
        ).lower()
        matched = [keyword for keyword in self.keywords if keyword in text]
        return {
            "domain": self.domain,
            "matched_signals": matched,
            "relevant": bool(matched),
            "evidence_count": len(context.evidence),
        }

    def recommend_next_step(self, context: OrchestrationContext) -> str:
        if not context.evidence:
            return "collect_read_only_evidence"
        return "validate_supported_hypothesis"


__all__ = ["DomainSpecialist"]
