"""Strict input validation for the Phase 4 controlled tool surface."""

from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ToolValidationError(ValueError):
    """Raised before a tool handler receives invalid or unsafe arguments."""


class ServiceInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    service: str = Field(min_length=1, max_length=120)


class LogsInput(ServiceInput):
    since: int = Field(default=180, ge=0, le=1_440)


class MetricsInput(ServiceInput):
    metric: str = Field(min_length=1, max_length=160, pattern=r"^[a-zA-Z0-9_.*:-]+$")
    since: int = Field(default=180, ge=0, le=1_440)


class DeploymentsInput(ServiceInput):
    pass


class ConfigurationInput(ServiceInput):
    keys: list[str] = Field(min_length=1, max_length=25)


class DocumentationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=2, max_length=500)


class HealthCheckInput(ServiceInput):
    check: Literal[
        "service_health", "payment_authorization", "checkout_smoke", "database_connectivity"
    ]


class TestInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    test_id: Literal[
        "payment_authorization_smoke",
        "checkout_smoke",
        "database_connectivity",
    ]


class RemediationPlanInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    incident_id: UUID
    steps: list[str] = Field(min_length=1, max_length=20)


class SafeActionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action_name: Literal["restart_payment_service", "rollback_simulated_deployment"]
    parameters: dict[str, str | int | float | bool] = Field(default_factory=dict)


class VerifyResolutionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    service: str = Field(min_length=1, max_length=120)
    checks: list[Literal["service_health", "payment_metrics", "error_logs"]] = Field(
        min_length=1, max_length=10
    )


class ReportInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    incident_id: UUID


TOOL_INPUT_MODELS: dict[str, type[BaseModel]] = {
    "get_logs": LogsInput,
    "get_metrics": MetricsInput,
    "get_recent_deployments": DeploymentsInput,
    "inspect_configuration": ConfigurationInput,
    "search_documentation": DocumentationInput,
    "run_health_check": HealthCheckInput,
    "run_test": TestInput,
    "create_remediation_plan": RemediationPlanInput,
    "execute_safe_action": SafeActionInput,
    "verify_resolution": VerifyResolutionInput,
    "generate_incident_report": ReportInput,
}


def validate_tool_input(tool_name: str, input_data: dict[str, Any]) -> dict[str, Any]:
    """Validate against a concrete model and return only validated fields."""

    model = TOOL_INPUT_MODELS.get(tool_name)
    if model is None:
        raise ToolValidationError(f"Tool {tool_name!r} is not allow-listed")
    try:
        return model.model_validate(input_data).model_dump(mode="json")
    except Exception as exc:
        raise ToolValidationError(f"Invalid arguments for tool {tool_name!r}") from exc


__all__ = ["ToolValidationError", "validate_tool_input"]
