"""Controlled tool contracts and permission metadata."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

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
    domain: str = Field(default="shared", min_length=1, max_length=80)
    enabled: bool = True

    @property
    def tool_name(self) -> str:
        return self.name


class ToolExecutionStatus(StrEnum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    REJECTED = "REJECTED"
    TIMEOUT = "TIMEOUT"
    NOT_AVAILABLE = "NOT_AVAILABLE"


class ToolExecutionResult(BaseModel):
    """Uniform, auditable result returned by every controlled tool."""

    model_config = ConfigDict(extra="forbid")

    tool_name: str
    status: ToolExecutionStatus
    result: dict[str, Any] = Field(default_factory=dict)
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    timestamp: datetime
    risk_level: RiskLevel
    execution_id: UUID = Field(default_factory=uuid4)


class ControlledTool(ABC):
    """Base class for explicit, bounded tools.

    Implementations must validate their own typed inputs and must not invoke
    arbitrary shell commands, dynamic code, or model-supplied executables.
    """

    definition: ToolDefinition

    @abstractmethod
    async def execute(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Run one bounded operation and return structured output."""
