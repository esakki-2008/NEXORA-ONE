"""Controlled tool contracts and permission metadata."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from backend.app.models.enums import RiskLevel


class ToolDefinition(BaseModel):
    """Serializable tool metadata used for allow-listing and audit review."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(pattern=r"^[a-z][a-z0-9_]{1,79}$")
    description: str = Field(min_length=1, max_length=1_000)
    input_schema: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any] = Field(default_factory=dict)
    risk_level: RiskLevel
    requires_approval: bool


class ControlledTool(ABC):
    """Base class for explicit, bounded tools.

    Implementations must validate their own typed inputs and must not invoke
    arbitrary shell commands, dynamic code, or model-supplied executables.
    """

    definition: ToolDefinition

    @abstractmethod
    async def execute(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Run one bounded operation and return structured output."""
