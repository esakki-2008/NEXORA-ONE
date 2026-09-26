"""Agent contracts without implementing specialist behavior in Phase 1."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from backend.app.models.enums import AgentState


class AgentContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    incident_id: UUID
    state: AgentState
    evidence_ids: list[UUID] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str = Field(min_length=1, max_length=80)
    message: str = Field(min_length=1, max_length=2_000)
    next_state: AgentState | None = None
    evidence_ids: list[UUID] = Field(default_factory=list)
    requires_human: bool = False


class SpecialistAgent(ABC):
    """Interface every future domain specialist must implement."""

    name: str
    domain: str

    @abstractmethod
    async def run(self, context: AgentContext) -> AgentResult:
        """Observe or reason within a bounded context and return a typed result."""


class AgentDirectory:
    """Explicit registry for specialist agents; no dynamic code loading."""

    def __init__(self) -> None:
        self._agents: dict[str, SpecialistAgent] = {}

    def register(self, agent: SpecialistAgent) -> None:
        if agent.name in self._agents:
            raise ValueError(f"Agent {agent.name!r} is already registered")
        self._agents[agent.name] = agent

    def get(self, name: str) -> SpecialistAgent | None:
        return self._agents.get(name)

    def list_names(self) -> list[str]:
        return sorted(self._agents)
