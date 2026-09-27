"""Allow-listed tool registry with no arbitrary execution escape hatch."""

from __future__ import annotations

from typing import Any

from backend.app.tools.contracts import ControlledTool, ToolDefinition


class ToolNotFoundError(LookupError):
    """Raised when a caller asks for a tool outside the allow-list."""


class ToolRegistry:
    """Registry for concrete ``ControlledTool`` implementations."""

    def __init__(self) -> None:
        self._tools: dict[str, ControlledTool] = {}

    def register(self, tool: ControlledTool) -> None:
        name = tool.definition.name
        if name in self._tools:
            raise ValueError(f"Tool {name!r} is already registered")
        self._tools[name] = tool

    def get(self, name: str) -> ControlledTool:
        try:
            return self._tools[name]
        except KeyError as exc:
            raise ToolNotFoundError(name) from exc

    def list_names(self) -> list[str]:
        return sorted(self._tools)

    def list_definitions(self) -> list[ToolDefinition]:
        return [self._tools[name].definition for name in sorted(self._tools)]

    async def execute(self, name: str, input_data: dict[str, Any]) -> dict[str, Any]:
        """Execute only a registered tool; shell/process access is not exposed."""

        tool = self.get(name)
        return await tool.execute(input_data)


class ToolCatalog:
    """Read-only metadata catalog for future tools before implementations exist."""

    def __init__(self, definitions: tuple[ToolDefinition, ...] = ()) -> None:
        names = [definition.name for definition in definitions]
        if len(names) != len(set(names)):
            raise ValueError("Tool catalog names must be unique")
        self._definitions = {definition.name: definition for definition in definitions}

    def get(self, name: str) -> ToolDefinition:
        try:
            return self._definitions[name]
        except KeyError as exc:
            raise ToolNotFoundError(name) from exc

    def list_definitions(self) -> list[ToolDefinition]:
        return [self._definitions[name] for name in sorted(self._definitions)]
