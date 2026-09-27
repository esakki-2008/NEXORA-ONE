"""FastAPI application factory for NEXORA ONE."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.agents.orchestrator import AgentOrchestrator
from backend.app.agents.policies import ToolPolicy
from backend.app.agents.registry import build_specialist_directory
from backend.app.ai.services.inference import AIService
from backend.app.api.routes import ai, health, incidents, investigations, orchestrator, simulator
from backend.app.config.settings import Settings, get_settings
from backend.app.database.repository import IncidentRepository, InMemoryIncidentRepository
from backend.app.investigation.engine import InvestigationEngine
from backend.app.investigation.service import InvestigationService
from backend.app.simulator.runtime import ShopFlowSimulationRuntime
from backend.app.simulator.scenarios import ShopFlowSimulator
from backend.app.tools.runtime import ToolRuntime, build_simulation_tool_registry


def create_app(
    repository: IncidentRepository | None = None,
    settings: Settings | None = None,
    ai_service: AIService | None = None,
) -> FastAPI:
    """Create an application with injectable storage for tests and adapters."""

    runtime_settings = settings or get_settings()
    application = FastAPI(
        title="NEXORA ONE",
        summary="One AI operations brain for the entire business.",
        description=(
            "Controlled enterprise incident operations with a bounded "
            "Nebius/Nemotron AI analysis boundary, explicit orchestration state machine, "
            "approval gate, simulator actions, and verification."
        ),
        version="0.1.0",
        debug=runtime_settings.debug,
    )
    application.state.settings = runtime_settings
    application.state.repository = (
        repository if repository is not None else InMemoryIncidentRepository()
    )
    application.state.simulator = (
        ai_service.simulator
        if ai_service is not None and hasattr(ai_service, "simulator")
        else ShopFlowSimulator()
    )
    application.state.ai_service = ai_service or AIService.from_settings(
        settings=runtime_settings,
        repository=application.state.repository,
        simulator=application.state.simulator,
    )
    application.state.simulation_runtime = ShopFlowSimulationRuntime(application.state.simulator)
    application.state.tool_registry = build_simulation_tool_registry(
        application.state.simulation_runtime
    )
    application.state.tool_runtime = ToolRuntime(
        application.state.tool_registry,
        ToolPolicy(),
    )
    application.state.orchestrator = AgentOrchestrator(
        application.state.ai_service,
        build_specialist_directory(),
        application.state.tool_registry,
        repository=application.state.repository,
        simulation_runtime=application.state.simulation_runtime,
        tool_runtime=application.state.tool_runtime,
    )
    application.state.investigation_engine = InvestigationEngine(
        repository=application.state.repository,
        tool_runtime=application.state.tool_runtime,
        simulation_runtime=application.state.simulation_runtime,
        ai_service=application.state.ai_service,
    )
    application.state.investigation_service = InvestigationService(
        application.state.investigation_engine,
        application.state.orchestrator,
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=runtime_settings.cors_origin_list,
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )

    application.include_router(health.router)
    application.include_router(ai.router)
    application.include_router(incidents.router)
    application.include_router(investigations.router)
    application.include_router(orchestrator.router)
    application.include_router(simulator.router)
    return application


app = create_app()
