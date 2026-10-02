"""FastAPI application factory for NEXORA ONE."""

from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.responses import Response
from starlette.types import Message

from backend.app.actions.registry import ActionRegistry
from backend.app.actions.service import ActionService
from backend.app.agents.orchestrator import AgentOrchestrator
from backend.app.agents.policies import ToolPolicy
from backend.app.agents.registry import build_specialist_directory
from backend.app.ai.services.inference import AIService
from backend.app.api.routes import (
    actions,
    ai,
    health,
    incidents,
    investigations,
    operations,
    orchestrator,
    security,
    simulator,
    verification,
)
from backend.app.config.settings import Settings, get_settings
from backend.app.database.repository import IncidentRepository, InMemoryIncidentRepository
from backend.app.investigation.engine import InvestigationEngine
from backend.app.investigation.service import InvestigationService
from backend.app.operations.service import OperationsService
from backend.app.security.authentication import AuthenticationError
from backend.app.security.models import SecurityEventType
from backend.app.security.rate_limit import RateLimitExceeded
from backend.app.security.service import SecurityService
from backend.app.security.validation import (
    RequestBodyLimitExceeded,
    SecurityValidationError,
    validate_request_size,
)
from backend.app.services.incident_service import IncidentService
from backend.app.simulator.runtime import ShopFlowSimulationRuntime
from backend.app.simulator.scenarios import ShopFlowSimulator
from backend.app.tools.runtime import ToolRuntime, build_simulation_tool_registry
from backend.app.verification.engine import VerificationEngine
from backend.app.verification.service import VerificationService


def create_app(
    repository: IncidentRepository | None = None,
    settings: Settings | None = None,
    ai_service: AIService | None = None,
) -> FastAPI:
    """Create an application with injectable storage for tests and adapters."""

    runtime_settings = settings or get_settings()
    if runtime_settings.environment == "production":
        configured_secret = runtime_settings.security_auth_secret
        if configured_secret is None or len(configured_secret.get_secret_value().strip()) < 32:
            raise ValueError("Production requires SECURITY_AUTH_SECRET with at least 32 characters")
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
    security_origins = tuple(runtime_settings.cors_origin_list)
    if "*" in security_origins:
        raise ValueError("Unrestricted CORS origins are not permitted by the security boundary")
    application.state.security_service = SecurityService(
        auth_secret=runtime_settings.security_auth_secret,
        token_ttl_seconds=runtime_settings.security_token_ttl_seconds,
    )
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
        security_service=application.state.security_service,
    )
    if hasattr(application.state.ai_service, "security_service"):
        application.state.ai_service.security_service = application.state.security_service
    application.state.simulation_runtime = ShopFlowSimulationRuntime(application.state.simulator)
    application.state.tool_registry = build_simulation_tool_registry(
        application.state.simulation_runtime
    )
    application.state.tool_runtime = ToolRuntime(
        application.state.tool_registry,
        ToolPolicy(),
        security_service=application.state.security_service,
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
    application.state.action_registry = ActionRegistry(application.state.simulation_runtime)
    application.state.verification_engine = VerificationEngine(
        application.state.action_registry,
        application.state.simulation_runtime,
        tool_runtime=application.state.tool_runtime,
        max_evidence_age_seconds=runtime_settings.verification_max_evidence_age_seconds,
    )
    application.state.verification_service = VerificationService(
        repository=application.state.repository,
        engine=application.state.verification_engine,
        max_attempts=runtime_settings.verification_max_attempts,
        retry_delay_seconds=runtime_settings.verification_retry_delay_seconds,
    )
    application.state.action_service = ActionService(
        repository=application.state.repository,
        registry=application.state.action_registry,
        orchestrator=application.state.orchestrator,
        investigation_service=application.state.investigation_service,
        verification_service=application.state.verification_service,
    )
    application.state.verification_service.set_action_lookup(application.state.action_service.get)
    application.state.verification_service.orchestrator = application.state.orchestrator
    application.state.operations_service = OperationsService(
        repository=application.state.repository,
        simulation_runtime=application.state.simulation_runtime,
        incident_service=IncidentService(application.state.repository),
        investigation_service=application.state.investigation_service,
    )

    @application.middleware("http")
    async def security_boundary(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """Authenticate and authorize every API request before route code runs."""

        if request.method == "OPTIONS" or not request.url.path.startswith("/api/"):
            response = await call_next(request)
        else:
            security_service: SecurityService = request.app.state.security_service
            try:
                validate_request_size(
                    request.headers.get("content-length"),
                    runtime_settings.security_max_request_bytes,
                )
                received_bytes = 0
                original_receive = request._receive

                async def limited_receive() -> Message:
                    nonlocal received_bytes
                    message = await original_receive()
                    if message.get("type") == "http.request":
                        received_bytes += len(message.get("body", b""))
                        if received_bytes > runtime_settings.security_max_request_bytes:
                            raise RequestBodyLimitExceeded(
                                "Request body exceeds the configured security limit"
                            )
                    return message

                request._receive = limited_receive
                principal = security_service.authenticate(
                    request.headers.get("authorization"), source="api.middleware"
                )
                request.state.principal = principal
                permission = security_service.policy.permission_for(
                    request.method, request.url.path
                )
                if permission is not None:
                    security_service.require_permission(principal, permission)
                security_service.check_rate(principal, request.method, request.url.path)
                response = await call_next(request)
            except AuthenticationError:
                response = JSONResponse(
                    status_code=401,
                    content={"detail": "Authentication is required"},
                    headers={"WWW-Authenticate": "Bearer"},
                )
            except SecurityValidationError:
                security_service.record_event(
                    SecurityEventType.OVERSIZED_REQUEST_REJECTED,
                    actor="anonymous",
                    resource=request.url.path,
                    source="api.middleware",
                )
                response = JSONResponse(
                    status_code=413,
                    content={"detail": "Request body exceeds the configured security limit"},
                )
            except PermissionError:
                response = JSONResponse(status_code=403, content={"detail": "Permission denied"})
            except RateLimitExceeded as exc:
                response = JSONResponse(
                    status_code=429,
                    content={"detail": "Request rate limit exceeded"},
                    headers={"Retry-After": str(exc.retry_after)},
                )
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
        return response

    application.add_middleware(
        CORSMiddleware,
        allow_origins=security_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Accept"],
    )

    application.include_router(health.router)
    application.include_router(actions.router)
    application.include_router(ai.router)
    application.include_router(incidents.router)
    application.include_router(investigations.router)
    application.include_router(operations.router)
    application.include_router(orchestrator.router)
    application.include_router(security.router)
    application.include_router(simulator.router)
    application.include_router(verification.router)
    return application


app = create_app()
