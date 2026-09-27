"""Application service and orchestration handoff for Phase 5 investigations."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from backend.app.agents.orchestrator import (
    AgentOrchestrator,
    OrchestratorNotConfiguredError,
    OrchestratorOperationError,
)
from backend.app.investigation.context import (
    CollectionRequest,
    CorrelationRecord,
    EvidenceRecord,
    InvestigationCancelRequest,
    InvestigationContext,
    InvestigationHandoffStatus,
    InvestigationHypothesis,
    InvestigationStatus,
    InvestigationSummary,
    InvestigationTimelineEvent,
    TestHypothesisRequest,
)
from backend.app.investigation.engine import InvestigationEngine
from backend.app.investigation.store import InvestigationNotFoundError, InvestigationStore


class InvestigationService:
    """Expose validated investigation operations without bypassing Phase 4 policy."""

    def __init__(
        self,
        engine: InvestigationEngine,
        orchestrator: AgentOrchestrator,
    ) -> None:
        self.engine = engine
        self.orchestrator = orchestrator
        self.store: InvestigationStore = engine.store

    async def start(
        self,
        incident_id: UUID,
        *,
        scenario_id: str | None = None,
        request_id: str | None = None,
        auto_handoff: bool = True,
        operations_signal_id: str | None = None,
    ) -> InvestigationContext:
        context = await self.engine.start(
            incident_id,
            scenario_id=scenario_id,
            request_id=request_id,
            operations_signal_id=operations_signal_id,
        )
        if auto_handoff and context.orchestrator_handoff.status is InvestigationHandoffStatus.READY:
            return await self.handoff(context.investigation_id)
        return context

    def get(self, investigation_id: UUID) -> InvestigationContext:
        return self.store.require(investigation_id)

    def get_by_request(self, request_id: str) -> InvestigationContext | None:
        """Return an existing request-bound context for idempotent callers."""

        return self.store.get_by_request(request_id)

    def get_for_incident(self, incident_id: UUID) -> InvestigationContext:
        context = self.store.get_by_incident(incident_id)
        if context is None:
            raise InvestigationNotFoundError(
                f"No investigation exists for incident {incident_id}"
            )
        return context

    def list_contexts(self) -> list[InvestigationSummary]:
        return [self._summary(item) for item in self.store.list_contexts()]

    def evidence(self, investigation_id: UUID) -> list[EvidenceRecord]:
        return self.get(investigation_id).evidence

    def correlations(self, investigation_id: UUID) -> list[CorrelationRecord]:
        return self.get(investigation_id).correlations

    def hypotheses(self, investigation_id: UUID) -> list[InvestigationHypothesis]:
        return self.get(investigation_id).hypotheses

    def timeline(self, investigation_id: UUID) -> list[InvestigationTimelineEvent]:
        return list(reversed(self.get(investigation_id).timeline))

    def summary(self, investigation_id: UUID) -> InvestigationSummary:
        return self._summary(self.get(investigation_id))

    async def collect(
        self, investigation_id: UUID, request: CollectionRequest
    ) -> InvestigationContext:
        return await self.engine.collect(investigation_id, request.tool_names or None)

    async def test_hypothesis(
        self, investigation_id: UUID, request: TestHypothesisRequest
    ) -> InvestigationContext:
        return await self.engine.test_hypothesis(
            investigation_id,
            request.hypothesis_id,
            request.tool_names or None,
        )

    async def cancel(
        self, investigation_id: UUID, request: InvestigationCancelRequest
    ) -> InvestigationContext:
        return await self.engine.cancel(
            investigation_id,
            request.reason or f"Investigation cancelled by {request.requested_by}",
        )

    async def handoff(self, investigation_id: UUID) -> InvestigationContext:
        context = self.get(investigation_id)
        if context.orchestrator_handoff.status is InvestigationHandoffStatus.HANDED_OFF:
            return context
        if context.status is not InvestigationStatus.COMPLETED:
            context.orchestrator_handoff = context.orchestrator_handoff.model_copy(
                update={
                    "status": InvestigationHandoffStatus.REQUIRES_HUMAN,
                    "message": (
                        "Investigation is not sufficiently supported for orchestrator "
                        "handoff."
                    ),
                }
            )
            self._record_handoff(context, "Investigation requires human review before handoff")
            return context
        try:
            orchestration = await self.orchestrator.start(
                context.incident_id,
                scenario_id=context.scenario_id,
                request_id=f"investigation-handoff:{context.investigation_id}",
            )
        except (OrchestratorNotConfiguredError, OrchestratorOperationError) as exc:
            context.orchestrator_handoff = context.orchestrator_handoff.model_copy(
                update={
                    "status": InvestigationHandoffStatus.REQUIRES_HUMAN,
                    "message": str(exc),
                }
            )
            self._record_handoff(context, "Orchestrator handoff requires human review")
            return context
        except Exception:
            context.orchestrator_handoff = context.orchestrator_handoff.model_copy(
                update={
                    "status": InvestigationHandoffStatus.FAILED,
                    "message": "Orchestrator handoff failed safely",
                }
            )
            self._record_handoff(context, "Orchestrator handoff failed safely")
            return context
        context.orchestrator_handoff = context.orchestrator_handoff.model_copy(
            update={
                "status": (
                    InvestigationHandoffStatus.REQUIRES_HUMAN
                    if orchestration.current_state.value == "REQUIRES_HUMAN"
                    else InvestigationHandoffStatus.HANDED_OFF
                ),
                "orchestrator_state": orchestration.current_state.value,
                "message": "Evidence-grounded context handed to the Phase 4 orchestrator.",
                "handed_off_at": datetime.now(UTC),
            }
        )
        self._record_handoff(context, "Investigation handed off to Phase 4 orchestrator")
        return context

    def _record_handoff(self, context: InvestigationContext, message: str) -> None:
        self.engine._record(  # noqa: SLF001 - service shares the engine's audit boundary
            context,
            "investigation.orchestrator.handoff",
            message,
            status=context.orchestrator_handoff.status.value,
        )
        self.store.save(context)

    @staticmethod
    def _summary(context: InvestigationContext) -> InvestigationSummary:
        return InvestigationSummary(
            investigation_id=context.investigation_id,
            incident_id=context.incident_id,
            status=context.status,
            source_type=context.source_type,
            evidence_count=len(context.evidence),
            correlation_count=len(context.correlations),
            hypothesis_count=len(context.hypotheses),
            confidence=context.confidence,
            selected_hypothesis=context.selected_hypothesis,
            recommended_next_step=context.recommended_next_step,
            orchestrator_handoff=context.orchestrator_handoff,
            updated_at=context.updated_at,
        )


__all__ = ["InvestigationNotFoundError", "InvestigationService"]
