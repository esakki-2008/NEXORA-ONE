"""Validated contracts exchanged between NEXORA and an AI provider."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, model_validator

from backend.app.models.enums import RiskLevel
from backend.app.tools.catalog import FOUNDATION_TOOL_CATALOG


class AIAnalysisStatus(StrEnum):
    ANALYSIS_COMPLETE = "analysis_complete"
    ANALYSIS_IN_PROGRESS = "analysis_in_progress"
    REQUIRES_HUMAN = "requires_human"


class AIAnalysisStep(StrEnum):
    OBSERVING = "observing"
    INVESTIGATING = "investigating"
    HYPOTHESIS_GENERATED = "hypothesis_generated"
    VALIDATING = "validating"
    REMEDIATION_PROPOSED = "remediation_proposed"
    WAITING_FOR_APPROVAL = "waiting_for_approval"
    VERIFYING = "verifying"
    RESOLVED = "resolved"
    REQUIRES_HUMAN = "requires_human"


class ToolCall(BaseModel):
    """A future bounded tool proposal; it is data, not an execution request."""

    model_config = ConfigDict(extra="forbid")

    tool_name: str = Field(pattern=r"^[a-z][a-z0-9_]{1,79}$")
    arguments: dict[str, Any] = Field(default_factory=dict)
    risk_level: RiskLevel = RiskLevel.READ_ONLY
    reason: str = Field(min_length=1, max_length=1_000)


class EvidenceReference(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence_id: str = Field(min_length=1, max_length=200)
    source: str = Field(min_length=1, max_length=200)
    summary: str = Field(min_length=1, max_length=2_000)


class HypothesisSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=3, max_length=200)
    description: str = Field(min_length=1, max_length=3_000)
    confidence: float = Field(ge=0.0, le=1.0)
    supporting_evidence: list[str] = Field(default_factory=list, max_length=50)
    contradicting_evidence: list[str] = Field(default_factory=list, max_length=50)
    validation_status: Literal["unvalidated", "supported", "contradicted", "inconclusive"] = (
        "unvalidated"
    )


class RecommendedAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: str = Field(min_length=1, max_length=2_000)
    rationale: str = Field(min_length=1, max_length=2_000)
    risk_level: RiskLevel = RiskLevel.READ_ONLY
    requires_approval: bool = True


class VerificationPlanItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    check: str = Field(min_length=1, max_length=500)
    expected_state: dict[str, Any] = Field(default_factory=dict)


class AIAnalysisResponse(BaseModel):
    """The only model output envelope consumed by the rest of NEXORA."""

    model_config = ConfigDict(extra="forbid")

    status: AIAnalysisStatus
    current_step: AIAnalysisStep
    summary: str = Field(min_length=1, max_length=5_000)
    selected_tools: list[ToolCall] = Field(default_factory=list, max_length=25)
    evidence: list[EvidenceReference] = Field(default_factory=list, max_length=100)
    hypotheses: list[HypothesisSummary] = Field(default_factory=list, max_length=25)
    validated_hypothesis: str | None = Field(default=None, max_length=1_000)
    recommendation: RecommendedAction | None = Field(
        default=None,
        validation_alias=AliasChoices("recommendation", "recommended_action"),
    )
    risk_level: RiskLevel = RiskLevel.READ_ONLY
    requires_approval: bool = True
    verification_plan: list[VerificationPlanItem] = Field(default_factory=list, max_length=25)
    confidence: float = Field(ge=0.0, le=1.0)

    @property
    def recommended_action(self) -> RecommendedAction | None:
        """Compatibility accessor for callers using the older envelope name."""

        return self.recommendation

    @model_validator(mode="after")
    def enforce_safe_action_boundaries(self) -> AIAnalysisResponse:
        risk_order = {
            RiskLevel.READ_ONLY: 0,
            RiskLevel.LOW: 1,
            RiskLevel.MEDIUM: 2,
            RiskLevel.HIGH: 3,
        }
        required_risk = RiskLevel.READ_ONLY
        if self.recommendation is not None:
            required_risk = self.recommendation.risk_level
            if self.recommendation.risk_level != RiskLevel.READ_ONLY and (
                not self.requires_approval or not self.recommendation.requires_approval
            ):
                raise ValueError("Risky recommendations must require human approval")

        for tool_call in self.selected_tools:
            try:
                definition = FOUNDATION_TOOL_CATALOG.get(tool_call.tool_name)
            except LookupError as exc:
                raise ValueError("Selected tool is not in the NEXORA allow-list") from exc
            if definition.risk_level != tool_call.risk_level:
                raise ValueError("Selected tool risk does not match its NEXORA definition")
            if definition.requires_approval and not self.requires_approval:
                raise ValueError("Selected tool requires human approval")
            if risk_order[tool_call.risk_level] > risk_order[required_risk]:
                required_risk = tool_call.risk_level

        if risk_order[self.risk_level] < risk_order[required_risk]:
            raise ValueError("Response risk must cover proposed tool or action risk")
        return self


class AIHealthStatus(StrEnum):
    CONFIGURED = "configured"
    NOT_CONFIGURED = "not_configured"
    AUTHENTICATION_FAILED = "authentication_failed"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    MODEL_UNAVAILABLE = "model_unavailable"
    TIMEOUT = "timeout"
    ERROR = "error"


class AIHealthResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: Literal["nebius"] = "nebius"
    model: str
    status: AIHealthStatus
    verified: bool = False
    message: str
    last_verified_at: datetime | None = None


class AIAnalysisRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    incident_id: UUID | None = None
    scenario_id: str | None = Field(default=None, min_length=1, max_length=120)

    @model_validator(mode="after")
    def require_one_source(self) -> AIAnalysisRequest:
        if (self.incident_id is None) == (self.scenario_id is None):
            raise ValueError("Provide exactly one of incident_id or scenario_id")
        return self


class AITestResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    success: bool
    status: AIHealthStatus
    message: str
    response: AIAnalysisResponse | None = None


class AIActivityEvent(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: UUID = Field(default_factory=uuid4)
    tenant_id: str = Field(
        default="reference-tenant",
        min_length=2,
        max_length=64,
        pattern=r"^[a-z0-9][a-z0-9._:-]{1,63}$",
    )
    incident_id: UUID | None = None
    event_type: str = Field(min_length=1, max_length=100)
    message: str = Field(min_length=1, max_length=500)
    created_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)
