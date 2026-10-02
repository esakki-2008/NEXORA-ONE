"""Deterministic remediation planning around Nemotron's structured recommendation."""

from __future__ import annotations

from backend.app.agents.context import OrchestrationContext, RemediationPlan, RemediationStep
from backend.app.ai.schemas import AIAnalysisResponse
from backend.app.models.enums import RiskLevel
from backend.app.tools.catalog import FOUNDATION_TOOL_CATALOG


class Planner:
    """Turn a model recommendation into fixed, reviewable simulator steps."""

    _safe_actions = {
        "restart_payment_service": (
            "Restart simulated payment service",
            "Restore the payment service in the ShopFlow simulator only.",
        ),
        "rollback_simulated_deployment": (
            "Rollback simulated deployment",
            "Roll back the matching ShopFlow deployment in memory only.",
        ),
    }

    def build(
        self,
        context: OrchestrationContext,
        response: AIAnalysisResponse,
    ) -> tuple[RemediationPlan | None, str]:
        if response.recommendation is None:
            return None, "Nemotron did not provide a bounded recommendation."
        if context.scenario_id is None:
            return None, "A controlled simulated action requires an explicit ShopFlow scenario."

        action_name = self._match_action(response.recommendation.action)
        if action_name is None:
            return None, "Recommendation does not match a fixed allow-listed simulator action."
        title, description = self._safe_actions[action_name]
        action_definition = FOUNDATION_TOOL_CATALOG.get("execute_safe_action")
        steps = [
            RemediationStep(
                sequence=1,
                action="collect_validation_evidence",
                description="Collect bounded logs, metrics, and deployment evidence before change.",
                tool_name="get_logs",
                parameters={"service": context.incident.service, "since": 180},
                risk_level=FOUNDATION_TOOL_CATALOG.get("get_logs").risk_level,
                is_change=False,
                requires_approval=False,
            ),
            RemediationStep(
                sequence=2,
                action=action_name,
                description=description,
                tool_name="execute_safe_action",
                parameters={"action_name": action_name, "parameters": {}},
                risk_level=action_definition.risk_level,
                is_change=True,
                requires_approval=action_definition.requires_approval,
            ),
            RemediationStep(
                sequence=3,
                action="verify_resolution",
                description="Verify simulated service health, metrics, and error logs.",
                tool_name="verify_resolution",
                parameters={
                    "checks": ["service_health", "payment_metrics", "error_logs"],
                },
                risk_level=RiskLevel.READ_ONLY,
                is_change=False,
                requires_approval=False,
            ),
        ]
        return (
            RemediationPlan(
                problem=response.summary,
                steps=steps,
            ),
            f"{title} is fixed to the ShopFlow simulator and requires server-side approval.",
        )

    @classmethod
    def _match_action(cls, recommendation: str) -> str | None:
        normalized = recommendation.strip().lower().replace("-", "_").replace(" ", "_")
        for action_name in cls._safe_actions:
            if normalized == action_name or action_name in normalized:
                return action_name
        return None


__all__ = ["Planner"]
