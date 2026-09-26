"""Orchestrator boundary reserved for later phases.

The class intentionally does not invent observations or execute actions. It
only owns the dependencies that Phase 3+ will connect to the structured AI,
agent, and tool contracts.
"""

from backend.app.agents.base import AgentDirectory
from backend.app.ai.contracts import AIProvider
from backend.app.tools.registry import ToolRegistry


class OrchestratorNotConfiguredError(RuntimeError):
    """Raised until the real investigation workflow is implemented."""


class AgentOrchestrator:
    """Dependency boundary for coordinating specialist agents."""

    def __init__(
        self,
        ai_provider: AIProvider,
        agents: AgentDirectory,
        tools: ToolRegistry,
    ) -> None:
        self.ai_provider = ai_provider
        self.agents = agents
        self.tools = tools

    def registered_agents(self) -> list[str]:
        return self.agents.list_names()

    def registered_tools(self) -> list[str]:
        return self.tools.list_names()

    async def investigate(self, incident_id: str) -> None:
        """Fail explicitly rather than returning a fabricated investigation."""

        raise OrchestratorNotConfiguredError(
            f"Investigation orchestration for incident {incident_id} is deferred to a future phase"
        )
