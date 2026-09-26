"""Application service for safe Nebius/Nemotron inference."""

from __future__ import annotations

import json
from threading import RLock
from typing import Protocol
from uuid import UUID

from backend.app.ai.contracts import AIRequest
from backend.app.ai.exceptions import AIServiceError
from backend.app.ai.providers import NebiusNemotronProvider
from backend.app.ai.schemas import (
    AIActivityEvent,
    AIAnalysisRequest,
    AIAnalysisResponse,
    AIHealthResponse,
    AITestResponse,
)
from backend.app.config.settings import Settings
from backend.app.database.repository import IncidentRepository
from backend.app.models.domain import utc_now
from backend.app.simulator.models import ScenarioFixture
from backend.app.simulator.scenarios import ShopFlowSimulator
from backend.app.tools.catalog import FOUNDATION_TOOL_CATALOG


class InferenceProvider(Protocol):
    async def decide(self, request: AIRequest) -> AIAnalysisResponse: ...

    def health(self) -> AIHealthResponse: ...


class AnalysisSourceNotFoundError(LookupError):
    """Raised when an explicitly requested incident or scenario does not exist."""


class AIService:
    """Coordinate source normalization, provider calls, validation, and activity."""

    def __init__(
        self,
        *,
        provider: InferenceProvider,
        repository: IncidentRepository,
        simulator: ShopFlowSimulator,
    ) -> None:
        self.provider = provider
        self.repository = repository
        self.simulator = simulator
        self._lock = RLock()
        self._events: list[AIActivityEvent] = []

    @classmethod
    def from_settings(
        cls,
        *,
        settings: Settings,
        repository: IncidentRepository,
        simulator: ShopFlowSimulator,
    ) -> AIService:
        return cls(
            provider=NebiusNemotronProvider.from_settings(settings),
            repository=repository,
            simulator=simulator,
        )

    def health(self) -> AIHealthResponse:
        return self.provider.health()

    def list_activity(self, incident_id: UUID | None = None) -> list[AIActivityEvent]:
        with self._lock:
            events = [
                event
                for event in self._events
                if incident_id is None or event.incident_id == incident_id
            ]
            return [event.model_copy(deep=True) for event in reversed(events)]

    def _record(
        self,
        *,
        event_type: str,
        message: str,
        incident_id: UUID | None = None,
        metadata: dict[str, str] | None = None,
    ) -> None:
        event = AIActivityEvent(
            incident_id=incident_id,
            event_type=event_type,
            message=message,
            created_at=utc_now(),
            metadata=metadata or {},
        )
        with self._lock:
            self._events.append(event)
            self._events = self._events[-250:]

    async def test_connection(self) -> AITestResponse:
        """Perform a real minimal structured request; never returns a fake success."""

        self._record(event_type="ai.test.accepted", message="AI connectivity test accepted")
        self._record(event_type="ai.inference.started", message="Nemotron inference started")
        request = self._request_for_context(
            source_label="connectivity_test",
            context={"purpose": "connectivity_test", "evidence": []},
        )
        try:
            response = await self.provider.decide(request)
        except AIServiceError as exc:
            self._record(event_type="ai.inference.failed", message=exc.public_message)
            return AITestResponse(
                success=False,
                status=self.health().status,
                message=exc.public_message,
            )

        self._record(event_type="ai.response.received", message="Structured response received")
        self._record(event_type="ai.response.validated", message="Response validation passed")
        return AITestResponse(
            success=True,
            status=self.health().status,
            message="Nebius Token Factory and NVIDIA Nemotron verification succeeded.",
            response=response,
        )

    async def analyze(self, request: AIAnalysisRequest) -> AIAnalysisResponse:
        incident_id, source_label, context = self._normalize_source(request)
        self._record(
            event_type="ai.request.accepted",
            message="AI analysis request accepted",
            incident_id=incident_id,
            metadata={"source": source_label},
        )
        self._record(
            event_type="ai.evidence.normalized",
            message="Evidence normalized for Nemotron",
            incident_id=incident_id,
            metadata={"source": source_label},
        )
        self._record(
            event_type="ai.inference.started",
            message="Nemotron inference started",
            incident_id=incident_id,
        )

        try:
            response = await self.provider.decide(
                self._request_for_context(source_label=source_label, context=context)
            )
        except AIServiceError as exc:
            self._record(
                event_type="ai.inference.failed",
                message=exc.public_message,
                incident_id=incident_id,
            )
            raise

        self._record(
            event_type="ai.response.received",
            message="Structured response received",
            incident_id=incident_id,
        )
        self._record(
            event_type="ai.response.validated",
            message="Response validation passed",
            incident_id=incident_id,
        )
        if response.recommended_action is not None:
            self._record(
                event_type="ai.recommendation.generated",
                message="Recommendation generated; approval boundary preserved",
                incident_id=incident_id,
            )
        return response

    def _normalize_source(
        self, request: AIAnalysisRequest
    ) -> tuple[UUID | None, str, dict[str, object]]:
        if request.incident_id is not None:
            incident = self.repository.get_incident(request.incident_id)
            if incident is None:
                raise AnalysisSourceNotFoundError(f"Incident {request.incident_id} was not found")
            evidence = self.repository.list_evidence(request.incident_id)
            hypotheses = self.repository.list_hypotheses(request.incident_id)
            activity = self.repository.list_activity(request.incident_id)
            evidence_records = [item.model_dump(mode="json") for item in evidence]
            return (
                incident.id,
                "live_incident",
                {
                    "data_classification": "live_incident_record",
                    "incident": incident.model_dump(mode="json"),
                    "evidence": evidence_records,
                    "evidence_index": [
                        {
                            "evidence_id": str(item.id),
                            "source": item.source,
                            "summary": item.summary,
                        }
                        for item in evidence
                    ],
                    "hypotheses": [item.model_dump(mode="json") for item in hypotheses],
                    "activity": [item.model_dump(mode="json") for item in activity],
                },
            )

        assert request.scenario_id is not None
        try:
            fixture = self.simulator.load_scenario(request.scenario_id)
        except LookupError as exc:
            raise AnalysisSourceNotFoundError(
                f"Scenario {request.scenario_id!r} was not found"
            ) from exc
        return (
            None,
            "shopflow_simulator",
            {
                "data_classification": "synthetic_demo_data",
                "scenario": fixture.model_dump(mode="json"),
                "evidence_index": self._shopflow_evidence_index(fixture),
            },
        )

    @staticmethod
    def _shopflow_evidence_index(fixture: ScenarioFixture) -> list[dict[str, str]]:
        evidence: list[dict[str, str]] = []
        for log_item in fixture.state.logs:
            evidence.append(
                {
                    "evidence_id": str(log_item.id),
                    "source": f"ShopFlow / {log_item.service}",
                    "summary": log_item.message,
                }
            )
        for metric_item in fixture.state.metrics:
            evidence.append(
                {
                    "evidence_id": f"metric:{metric_item.service}:{metric_item.name}",
                    "source": f"ShopFlow / {metric_item.service}",
                    "summary": f"{metric_item.name}: {metric_item.value} {metric_item.unit}",
                }
            )
        for deployment_item in fixture.state.deployments:
            evidence.append(
                {
                    "evidence_id": str(deployment_item.id),
                    "source": f"ShopFlow / {deployment_item.service}",
                    "summary": f"{deployment_item.version} — {deployment_item.change_summary}",
                }
            )
        for configuration_item in fixture.state.configurations:
            evidence.append(
                {
                    "evidence_id": (
                        f"configuration:{configuration_item.service}:{configuration_item.key}"
                    ),
                    "source": f"ShopFlow / {configuration_item.service}",
                    "summary": f"{configuration_item.key}: {configuration_item.value}",
                }
            )
        for transaction_item in fixture.state.transactions:
            summary: str = transaction_item.status
            if transaction_item.failure_reason:
                summary = f"{summary} — {transaction_item.failure_reason}"
            evidence.append(
                {
                    "evidence_id": str(transaction_item.id),
                    "source": f"ShopFlow / {transaction_item.service}",
                    "summary": summary,
                }
            )
        return evidence

    @staticmethod
    def _request_for_context(*, source_label: str, context: dict[str, object]) -> AIRequest:
        schema = AIAnalysisResponse.model_json_schema()
        tool_catalog = [
            definition.model_dump(mode="json")
            for definition in FOUNDATION_TOOL_CATALOG.list_definitions()
        ]
        system_instruction = (
            "You are NEXORA Enterprise Operations Intelligence. "
            "Analyze only the supplied operational evidence. The source label is "
            f"{source_label}. Do not invent evidence, metrics, logs, actions, or outcomes. "
            "Return exactly one JSON object matching the supplied schema. "
            "Use concise operational summaries only; never return chain-of-thought, "
            "private reasoning, "
            "or hidden deliberation. Future tool selections are proposals only. "
            "Any non-read-only recommendation must require human approval. "
            "Use only evidence IDs from the supplied evidence_index and copy no new evidence. "
            f"Output JSON schema: {json.dumps(schema, separators=(',', ':'), ensure_ascii=True)} "
            "Allowed future tool proposals (never execute): "
            f"{json.dumps(tool_catalog, separators=(',', ':'), ensure_ascii=True)}"
        )
        user_input = (
            "Produce a structured NEXORA analysis for the following source. "
            "Synthetic/demo data must remain clearly represented as synthetic in your summary.\n\n"
            f"{json.dumps(context, separators=(',', ':'), ensure_ascii=True)}"
        )
        return AIRequest(
            system_instruction=system_instruction,
            user_input=user_input,
            context=context,
            requested_output_schema=schema,
        )
