"""Provider-neutral contracts for structured enterprise reasoning."""

from __future__ import annotations

from typing import Any, Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from backend.app.ai.schemas import AIAnalysisResponse


class AIRequest(BaseModel):
    """Structured input sent to a provider adapter."""

    model_config = ConfigDict(extra="forbid")

    system_instruction: str = Field(min_length=1, max_length=20_000)
    user_input: str = Field(min_length=1, max_length=30_000)
    context: dict[str, Any] = Field(default_factory=dict)
    requested_output_schema: dict[str, Any] = Field(default_factory=dict)


class StructuredAgentDecision(BaseModel):
    """Legacy Phase 1 envelope retained for compatibility with agent contracts."""

    model_config = ConfigDict(extra="forbid")

    decision: str = Field(min_length=1, max_length=120)
    rationale: str = Field(min_length=1, max_length=10_000)
    confidence: float = Field(ge=0.0, le=1.0)
    supporting_evidence: list[UUID] = Field(default_factory=list)
    proposed_action: dict[str, Any] | None = None
    requires_approval: bool = True


class AIProvider(Protocol):
    """Provider port implemented by Nebius Token Factory in Phase 3."""

    async def decide(self, request: AIRequest) -> AIAnalysisResponse:
        ...
