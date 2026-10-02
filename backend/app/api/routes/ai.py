"""Safe NEXORA AI health, verification, analysis, and activity routes."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from backend.app.ai.exceptions import (
    AIAuthenticationError,
    AIConfigurationError,
    AIModelUnavailableError,
    AIProviderError,
    AIProviderUnavailableError,
    AIRequestError,
    AIResponseValidationError,
    AIServiceError,
    AITimeoutError,
)
from backend.app.ai.schemas import (
    AIActivityEvent,
    AIAnalysisRequest,
    AIAnalysisResponse,
    AIHealthResponse,
    AITestResponse,
)
from backend.app.ai.services.inference import AIService, AnalysisSourceNotFoundError
from backend.app.api.dependencies import get_ai_service, get_principal
from backend.app.security.models import Principal

router = APIRouter(prefix="/api/ai", tags=["ai"])
AIServiceDependency = Annotated[AIService, Depends(get_ai_service)]


def _provider_error(error: AIServiceError) -> HTTPException:
    if isinstance(error, AITimeoutError):
        code = status.HTTP_504_GATEWAY_TIMEOUT
    elif isinstance(
        error, (AIConfigurationError, AIModelUnavailableError, AIProviderUnavailableError)
    ):
        code = status.HTTP_503_SERVICE_UNAVAILABLE
    elif isinstance(
        error,
        (AIAuthenticationError, AIProviderError, AIRequestError, AIResponseValidationError),
    ):
        code = status.HTTP_502_BAD_GATEWAY
    else:
        code = status.HTTP_503_SERVICE_UNAVAILABLE
    return HTTPException(status_code=code, detail=error.public_message)


@router.get("/health", response_model=AIHealthResponse, summary="Inspect Nebius AI readiness")
def ai_health(service: AIServiceDependency) -> AIHealthResponse:
    """Return provider configuration and last verification state without probing."""

    return service.health()


@router.post("/test", response_model=AITestResponse, summary="Verify Nebius Nemotron")
async def ai_test(
    service: AIServiceDependency,
    principal: Annotated[Principal, Depends(get_principal)],
) -> AITestResponse:
    """Make a real bounded structured request; successful status means verified."""

    return await service.test_connection(tenant_id=principal.tenant_id)


@router.post(
    "/analyze",
    response_model=AIAnalysisResponse,
    summary="Analyze supplied incident evidence",
)
async def ai_analyze(
    request: AIAnalysisRequest,
    service: AIServiceDependency,
    principal: Annotated[Principal, Depends(get_principal)],
) -> AIAnalysisResponse:
    """Analyze one live incident or one read-only synthetic ShopFlow fixture."""

    try:
        if request.incident_id is not None:
            incident = service.repository.get_incident(request.incident_id)
            if incident is None or incident.tenant_id != principal.tenant_id:
                raise AnalysisSourceNotFoundError(f"Incident {request.incident_id} was not found")
        return await service.analyze(request, tenant_id=principal.tenant_id)
    except AnalysisSourceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except AIServiceError as exc:
        raise _provider_error(exc) from exc


@router.get(
    "/activity",
    response_model=list[AIActivityEvent],
    summary="List observable AI lifecycle events",
)
def ai_activity(
    service: AIServiceDependency,
    principal: Annotated[Principal, Depends(get_principal)],
    incident_id: UUID | None = Query(default=None),
) -> list[AIActivityEvent]:
    """Return concise lifecycle events only; private model reasoning is excluded."""

    if incident_id is not None:
        incident = service.repository.get_incident(incident_id)
        if incident is None or incident.tenant_id != principal.tenant_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Incident {incident_id} was not found",
            )
    return service.list_activity(incident_id=incident_id, tenant_id=principal.tenant_id)
