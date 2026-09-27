import pytest

from backend.app.ai.contracts import AIRequest
from backend.app.ai.providers import AIProviderNotConfiguredError, UnconfiguredAIProvider
from backend.app.models.enums import RiskLevel
from backend.app.tools.catalog import FOUNDATION_TOOL_CATALOG
from backend.app.tools.registry import ToolNotFoundError, ToolRegistry


@pytest.mark.asyncio
async def test_ai_provider_fails_explicitly_instead_of_fabricating_output() -> None:
    provider = UnconfiguredAIProvider()
    request = AIRequest(system_instruction="observe", user_input="inspect incident")

    with pytest.raises(AIProviderNotConfiguredError):
        await provider.decide(request)


def test_tool_catalog_is_explicit_and_marks_actions_for_approval() -> None:
    execute_action = FOUNDATION_TOOL_CATALOG.get("execute_safe_action")

    assert execute_action.risk_level is RiskLevel.HIGH
    assert execute_action.requires_approval is True
    assert len(FOUNDATION_TOOL_CATALOG.list_definitions()) == 11

    registry = ToolRegistry()
    with pytest.raises(ToolNotFoundError):
        registry.get("run_arbitrary_shell")
