"""Policy-gated execution adapter for the fixed ShopFlow simulator tools."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from backend.app.agents.policies import ToolPolicy
from backend.app.models.enums import RiskLevel
from backend.app.simulator.runtime import (
    DuplicateSimulationActionError,
    ShopFlowSimulationRuntime,
    SimulationActionError,
    SimulationUnavailableError,
)
from backend.app.tools.catalog import FOUNDATION_TOOL_DEFINITIONS
from backend.app.tools.contracts import (
    ControlledTool,
    ToolDefinition,
    ToolExecutionResult,
    ToolExecutionStatus,
)
from backend.app.tools.registry import ToolNotFoundError, ToolRegistry
from backend.app.tools.validation import ToolValidationError, validate_tool_input


class SimulationTool(ControlledTool):
    def __init__(self, definition: ToolDefinition, runtime: ShopFlowSimulationRuntime) -> None:
        self.definition = definition
        self._runtime = runtime

    async def execute(self, input_data: dict[str, Any]) -> dict[str, Any]:
        scenario_id = input_data.pop("_scenario_id", None)
        if not scenario_id:
            raise SimulationUnavailableError(
                "No ShopFlow scenario is attached to this tool request"
            )
        if self.definition.name == "execute_safe_action":
            return_value, evidence = self._runtime.execute_safe_action(
                scenario_id=scenario_id,
                action_name=input_data["action_name"],
                parameters=input_data.get("parameters", {}),
                idempotency_key=input_data["_idempotency_key"],
            )
        else:
            return_value, evidence = self._runtime.read(
                self.definition.name,
                input_data,
                scenario_id,
            )
        return {"result": return_value, "evidence": evidence}


def build_simulation_tool_registry(runtime: ShopFlowSimulationRuntime) -> ToolRegistry:
    registry = ToolRegistry()
    for definition in FOUNDATION_TOOL_DEFINITIONS:
        registry.register(SimulationTool(definition, runtime))
    return registry


class ToolRuntime:
    """One entry point that validates, authorizes, executes, and structures results."""

    def __init__(self, registry: ToolRegistry, policy: ToolPolicy) -> None:
        self.registry = registry
        self.policy = policy

    async def execute(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        *,
        scenario_id: str | None,
        approval: Any = None,
        idempotency_key: str | None = None,
    ) -> ToolExecutionResult:
        try:
            tool = self.registry.get(tool_name)
        except ToolNotFoundError:
            return self._result(
                tool_name=tool_name,
                status=ToolExecutionStatus.REJECTED,
                risk_level=RiskLevel.READ_ONLY,
                result={"reason": "Tool request rejected: tool not allow-listed."},
            )

        decision = self.policy.evaluate(tool.definition, approval)
        if not decision.allowed:
            return self._result(
                tool_name=tool_name,
                status=ToolExecutionStatus.REJECTED,
                risk_level=tool.definition.risk_level,
                result={"reason": decision.reason, "requires_approval": decision.requires_approval},
            )
        try:
            validated = validate_tool_input(tool_name, arguments)
        except ToolValidationError as exc:
            return self._result(
                tool_name=tool_name,
                status=ToolExecutionStatus.REJECTED,
                risk_level=tool.definition.risk_level,
                result={"reason": str(exc)},
            )
        if scenario_id is None:
            return self._result(
                tool_name=tool_name,
                status=ToolExecutionStatus.NOT_AVAILABLE,
                risk_level=tool.definition.risk_level,
                result={"reason": "Tool requires a connected ShopFlow simulator source"},
            )
        validated["_scenario_id"] = scenario_id
        if idempotency_key is None:
            idempotency_key = f"tool:{tool_name}:{scenario_id}"
        validated["_idempotency_key"] = idempotency_key
        try:
            payload = await tool.execute(validated)
            return self._result(
                tool_name=tool_name,
                status=ToolExecutionStatus.SUCCESS,
                risk_level=tool.definition.risk_level,
                result=payload.get("result", {}),
                evidence=payload.get("evidence", []),
            )
        except DuplicateSimulationActionError as exc:
            return self._result(
                tool_name=tool_name,
                status=ToolExecutionStatus.REJECTED,
                risk_level=tool.definition.risk_level,
                result={"reason": str(exc)},
            )
        except SimulationUnavailableError as exc:
            return self._result(
                tool_name=tool_name,
                status=ToolExecutionStatus.NOT_AVAILABLE,
                risk_level=tool.definition.risk_level,
                result={"reason": str(exc)},
            )
        except SimulationActionError as exc:
            return self._result(
                tool_name=tool_name,
                status=ToolExecutionStatus.FAILED,
                risk_level=tool.definition.risk_level,
                result={"reason": str(exc)},
            )
        except Exception:
            return self._result(
                tool_name=tool_name,
                status=ToolExecutionStatus.FAILED,
                risk_level=tool.definition.risk_level,
                result={"reason": "Controlled tool execution failed safely"},
            )

    @staticmethod
    def _result(
        *,
        tool_name: str,
        status: ToolExecutionStatus,
        risk_level: RiskLevel,
        result: dict[str, Any],
        evidence: list[dict[str, Any]] | None = None,
    ) -> ToolExecutionResult:
        return ToolExecutionResult(
            tool_name=tool_name,
            status=status,
            risk_level=risk_level,
            result=result,
            evidence=evidence or [],
            timestamp=datetime.now(UTC),
        )


__all__ = ["ToolRuntime", "build_simulation_tool_registry"]
