"""FastAPI application factory for NEXORA ONE."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.ai.services.inference import AIService
from backend.app.api.routes import ai, health, incidents, simulator
from backend.app.config.settings import Settings, get_settings
from backend.app.database.repository import IncidentRepository, InMemoryIncidentRepository
from backend.app.simulator.scenarios import ShopFlowSimulator


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
            "Nebius/Nemotron AI analysis boundary. "
            "Investigation orchestration and execution workflows are intentionally not enabled."
        ),
        version="0.1.0",
        debug=runtime_settings.debug,
    )
    application.state.settings = runtime_settings
    application.state.repository = (
        repository if repository is not None else InMemoryIncidentRepository()
    )
    application.state.simulator = ShopFlowSimulator()
    application.state.ai_service = ai_service or AIService.from_settings(
        settings=runtime_settings,
        repository=application.state.repository,
        simulator=application.state.simulator,
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
    application.include_router(simulator.router)
    return application


app = create_app()
