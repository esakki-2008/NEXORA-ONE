"""Phase 5 deterministic investigation engine with an optional Nemotron assist."""

from __future__ import annotations

import asyncio
import json
from typing import Any, Protocol
from uuid import UUID, uuid4

from backend.app.ai.exceptions import AIServiceError
from backend.app.ai.schemas import (
    AIAnalysisRequest,
    AIAnalysisResponse,
    AIHealthResponse,
    AIHealthStatus,
)
from backend.app.ai.services.inference import AnalysisSourceNotFoundError
from backend.app.database.repository import IncidentRepository
from backend.app.investigation.context import (
    EvidenceRecord,
    InvestigationContext,
    InvestigationEvidenceType,
    InvestigationHandoffStatus,
    InvestigationHypothesis,
    InvestigationHypothesisStatus,
    InvestigationStatus,
    InvestigationTimelineEvent,
    RootCauseCandidate,
)
from backend.app.investigation.correlation import EvidenceCorrelator
from backend.app.investigation.evidence import EvidenceNormalizer, domain_evidence_type
from backend.app.investigation.hypotheses import HypothesisEngine
from backend.app.investigation.scoring import HypothesisScorer
from backend.app.investigation.store import InvestigationStore
from backend.app.investigation.timeline import InvestigationTimeline
from backend.app.investigation.validators import (
    InvestigationValidationError,
    hypotheses_from_ai,
    validate_hypothesis,
    validate_read_only_tool,
)
from backend.app.models.domain import Evidence, Hypothesis, utc_now
from backend.app.models.enums import HypothesisValidationStatus
from backend.app.schemas.incidents import ActivityEvent
from backend.app.simulator.runtime import ShopFlowSimulationRuntime, SimulationUnavailableError
from backend.app.tools.contracts import ToolExecutionResult, ToolExecutionStatus
from backend.app.tools.runtime import ToolRuntime


class InvestigationAIService(Protocol):
    async def analyze(
        self,
        request: AIAnalysisRequest,
        *,
        tenant_id: str | None = None,
    ) -> AIAnalysisResponse: ...

    def health(self) -> AIHealthResponse: ...


class InvestigationEngine:
    """Collect, normalize, correlate, test, score, and summarize evidence."""

    _related_services = {
        "Payment Service": ("Checkout Service", "Database"),
        "Checkout Service": ("Payment Service", "Inventory", "Database"),
        "Database": ("Checkout Service",),
    }
    _config_keys = (
        "gateway.retry_limit",
        "gateway.endpoint",
        "connection.pool_size",
        "cache.schema_version",
    )

    def __init__(
        self,
        *,
        repository: IncidentRepository,
        tool_runtime: ToolRuntime,
        simulation_runtime: ShopFlowSimulationRuntime,
        ai_service: InvestigationAIService | None = None,
        store: InvestigationStore | None = None,
    ) -> None:
        self.repository = repository
        self.tool_runtime = tool_runtime
        self.simulation_runtime = simulation_runtime
        self.ai_service = ai_service
        self.store = store or InvestigationStore()
        self.normalizer = EvidenceNormalizer()
        self.correlator = EvidenceCorrelator()
        self.hypothesis_engine = HypothesisEngine()
        self.scorer = HypothesisScorer()
        self.timeline = InvestigationTimeline()
        self._locks: dict[UUID, asyncio.Lock] = {}

    def _lock(self, incident_id: UUID) -> asyncio.Lock:
        if incident_id not in self._locks:
            self._locks[incident_id] = asyncio.Lock()
        return self._locks[incident_id]

    async def start(
        self,
        incident_id: UUID,
        *,
        scenario_id: str | None = None,
        request_id: str | None = None,
        operations_signal_id: str | None = None,
    ) -> InvestigationContext:
        incident = self.repository.get_incident(incident_id)
        if incident is None:
            raise LookupError(f"Incident {incident_id} was not found")
        if request_id:
            existing_request = self.store.get_by_request(request_id)
            if existing_request is not None:
                if existing_request.incident_id != incident_id:
                    raise InvestigationValidationError(
                        "Investigation request_id is already bound to another incident"
                    )
                return existing_request
        existing = self.store.get_by_incident(incident_id)
        if existing is not None:
            return existing
        async with self._lock(incident_id):
            existing = self.store.get_by_incident(incident_id)
            if existing is not None:
                return existing
            context = InvestigationContext(
                investigation_id=uuid4(),
                tenant_id=incident.tenant_id,
                incident_id=incident_id,
                incident=incident,
                source_type=(
                    "SIMULATED / CONTROLLED DEMONSTRATION"
                    if scenario_id
                    else "LIVE INCIDENT RECORD"
                ),
                scenario_id=scenario_id,
                status=InvestigationStatus.CREATED,
                request_id=request_id,
                operations_signal_id=operations_signal_id,
            )
            self.store.save(context)
            self._record(context, "investigation.created", "Investigation context created")
            try:
                self._set_status(context, InvestigationStatus.COLLECTING)
                await self._collect_default(context)
                self._set_status(context, InvestigationStatus.ANALYZING)
                await self._analyze(context)
            except (SimulationUnavailableError, InvestigationValidationError) as exc:
                self._safe_error(context, str(exc), requires_human=True)
            except (AIServiceError, AnalysisSourceNotFoundError) as exc:
                # AI is an assistive source; deterministic evidence remains usable.
                self._record(context, "investigation.ai.unavailable", "Nemotron assist unavailable")
                context.errors.append(self._public_ai_error(exc))
                await self._analyze_deterministically(context)
            except Exception:
                self._safe_error(
                    context,
                    "Investigation failed safely before a conclusion could be recorded",
                    requires_human=True,
                )
            self.store.save(context)
            return context

    async def collect(
        self, investigation_id: UUID, tool_names: list[str] | None = None
    ) -> InvestigationContext:
        context = self.store.require(investigation_id)
        if context.status is InvestigationStatus.CANCELLED:
            return context
        async with self._lock(context.incident_id):
            context = self.store.require(investigation_id)
            self._set_status(context, InvestigationStatus.COLLECTING)
            try:
                await self._collect_tools(context, tool_names or self._default_tool_names(context))
                self._set_status(context, InvestigationStatus.ANALYZING)
                await self._analyze_deterministically(context)
            except (SimulationUnavailableError, InvestigationValidationError) as exc:
                self._safe_error(context, str(exc), requires_human=True)
            self.store.save(context)
            return context

    async def test_hypothesis(
        self,
        investigation_id: UUID,
        hypothesis_id: UUID,
        tool_names: list[str] | None = None,
    ) -> InvestigationContext:
        context = self.store.require(investigation_id)
        async with self._lock(context.incident_id):
            context = self.store.require(investigation_id)
            hypothesis = next(
                (item for item in context.hypotheses if item.hypothesis_id == hypothesis_id), None
            )
            if hypothesis is None:
                raise LookupError(f"Hypothesis {hypothesis_id} was not found")
            hypothesis.status = InvestigationHypothesisStatus.TESTING
            hypothesis.updated_at = utc_now()
            self._record(
                context,
                "hypothesis.testing.started",
                "Hypothesis testing started",
                evidence_ids=hypothesis.supporting_evidence,
            )
            selected_tools = tool_names or ["run_test", "run_health_check"]
            try:
                await self._collect_tools(context, selected_tools)
                self._rescore(context)
                self._finish_analysis(context)
            except (SimulationUnavailableError, InvestigationValidationError) as exc:
                self._safe_error(context, str(exc), requires_human=True)
            self._record(
                context,
                "hypothesis.testing.completed",
                "Hypothesis testing completed",
                evidence_ids=hypothesis.supporting_evidence,
            )
            self.store.save(context)
            return context

    async def cancel(self, investigation_id: UUID, reason: str) -> InvestigationContext:
        context = self.store.require(investigation_id)
        async with self._lock(context.incident_id):
            context = self.store.require(investigation_id)
            if context.status not in {
                InvestigationStatus.COMPLETED,
                InvestigationStatus.CANCELLED,
            }:
                self._set_status(context, InvestigationStatus.CANCELLED)
                context.errors.append(reason)
                self._record(context, "investigation.cancelled", reason, status="CANCELLED")
                self.store.save(context)
            return context

    async def _collect_default(self, context: InvestigationContext) -> None:
        if context.scenario_id is None:
            self._load_existing_evidence(context)
            if not context.evidence:
                message = "No recorded evidence is attached to the live incident"
                if message not in context.errors:
                    context.errors.append(message)
                self._record(
                    context,
                    "evidence.unavailable",
                    message,
                    status="NOT_AVAILABLE",
                )
            return
        await self._collect_tools(context, self._default_tool_names(context))

    async def _collect_tools(self, context: InvestigationContext, tool_names: list[str]) -> None:
        if context.scenario_id is None:
            self._load_existing_evidence(context)
            return
        fixture = self.simulation_runtime.fixture(context.scenario_id)
        services = [context.incident.service]
        services.extend(
            service
            for service in self._related_services.get(context.incident.service, ())
            if service in {item.name for item in fixture.state.services}
        )
        config_keys = [
            item.key
            for item in fixture.state.configurations
            if item.service == context.incident.service
        ] or list(self._config_keys)
        for tool_name in dict.fromkeys(tool_names):
            validate_read_only_tool(tool_name)
            if tool_name == "inspect_configuration":
                await self._execute_read_only(
                    context,
                    tool_name,
                    {"service": context.incident.service, "keys": config_keys},
                )
                continue
            if tool_name == "run_test":
                test_id = self._test_id(context, fixture)
                if test_id:
                    await self._execute_read_only(context, tool_name, {"test_id": test_id})
                continue
            if tool_name in {
                "get_logs",
                "get_metrics",
                "get_recent_deployments",
                "run_health_check",
            }:
                for service in services:
                    arguments = self._arguments_for(tool_name, service)
                    if arguments is not None:
                        await self._execute_read_only(context, tool_name, arguments)
                continue
            # Documentation remains bounded and may report NOT_AVAILABLE without
            # turning a missing source into fabricated evidence.
            await self._execute_read_only(
                context,
                tool_name,
                {"query": context.incident.title},
            )

    async def _execute_read_only(
        self,
        context: InvestigationContext,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> ToolExecutionResult:
        validate_read_only_tool(tool_name)
        self._record(
            context,
            "evidence.requested",
            f"Evidence requested from {tool_name}",
        )
        key = json.dumps(
            [str(context.investigation_id), tool_name, arguments],
            sort_keys=True,
            separators=(",", ":"),
        )
        result = await self.tool_runtime.execute(
            tool_name,
            arguments,
            scenario_id=context.scenario_id,
            idempotency_key=f"investigation:{key}",
            tenant_id=context.tenant_id,
        )
        if result.status is ToolExecutionStatus.SUCCESS:
            normalized = self.normalizer.normalize_result(
                result,
                incident_id=context.incident_id,
                collected_by=f"investigation_tool:{tool_name}",
                simulated=context.scenario_id is not None,
            )
            new_ids: list[str] = []
            known = {item.evidence_id for item in context.evidence}
            for item in normalized:
                if item.evidence_id in known:
                    continue
                context.evidence.append(item)
                new_ids.append(item.evidence_id)
                self._persist_domain_evidence(context, item)
            self._record(
                context,
                "evidence.collected",
                f"Evidence collected from {tool_name}",
                evidence_ids=new_ids,
            )
        else:
            self._record(
                context,
                "evidence.collection.failed",
                f"Evidence collection from {tool_name} returned {result.status.value}",
                status=result.status.value,
            )
            if result.result.get("reason"):
                message = str(result.result["reason"])
                if message not in context.errors:
                    context.errors.append(message)
        self.store.save(context)
        return result

    async def _analyze(self, context: InvestigationContext) -> None:
        await self._analyze_deterministically(context)
        if self.ai_service is None:
            return
        try:
            health = self.ai_service.health()
            context.ai_status = health.status
            if health.status is AIHealthStatus.NOT_CONFIGURED:
                self._record(
                    context,
                    "investigation.ai.not_configured",
                    "Nemotron assist is not configured; deterministic analysis retained",
                )
                return
            response = await self.ai_service.analyze(
                AIAnalysisRequest(
                    incident_id=context.incident_id if context.scenario_id is None else None,
                    scenario_id=context.scenario_id,
                ),
                tenant_id=context.tenant_id,
            )
            context.ai_summary = response.summary
            ai_candidates = hypotheses_from_ai(
                response,
                incident_id=context.incident_id,
                evidence=context.evidence,
            )
            existing_titles = {item.title for item in context.hypotheses}
            for candidate in ai_candidates:
                if candidate.title not in existing_titles:
                    context.hypotheses.append(candidate)
                    existing_titles.add(candidate.title)
            self._record(
                context,
                "investigation.ai.summary_received",
                "Nemotron returned a validated investigation summary",
            )
            self._rescore(context)
            self._finish_analysis(context)
        except (AIServiceError, AnalysisSourceNotFoundError) as exc:
            context.ai_status = self._health_status()
            message = self._public_ai_error(exc)
            if message not in context.errors:
                context.errors.append(message)
            context.orchestrator_handoff.status = InvestigationHandoffStatus.REQUIRES_HUMAN
            self._record(
                context,
                "investigation.ai.unavailable",
                "Nemotron assist unavailable; deterministic evidence retained",
                status="REQUIRES_HUMAN",
            )
        except Exception:
            message = "Nemotron response could not be safely incorporated"
            if message not in context.errors:
                context.errors.append(message)
            context.orchestrator_handoff.status = InvestigationHandoffStatus.REQUIRES_HUMAN
            self._record(
                context,
                "investigation.ai.invalid",
                message,
                status="REQUIRES_HUMAN",
            )
        self.store.save(context)

    async def _analyze_deterministically(self, context: InvestigationContext) -> None:
        context.correlations = self.correlator.correlate(
            context.evidence,
            incident_id=context.incident_id,
        )
        self._record(
            context,
            "evidence.correlated",
            f"{len(context.correlations)} explainable evidence correlation(s) recorded",
            evidence_ids=[item.evidence_id for item in context.evidence[:20]],
        )
        generated = self.hypothesis_engine.generate(
            context.incident,
            context.evidence,
            context.correlations,
            scenario_id=context.scenario_id,
        )
        existing_titles = {item.title for item in context.hypotheses}
        for hypothesis in generated:
            if hypothesis.title not in existing_titles:
                context.hypotheses.append(hypothesis)
                existing_titles.add(hypothesis.title)
        self._record(
            context,
            "hypothesis.generated",
            f"{len(generated)} deterministic hypothesis candidate(s) generated",
        )
        if context.scenario_id is not None:
            test_id = self._test_id_for_incident(context)
            if test_id:
                await self._collect_tools(context, ["run_test"])
                self._record(
                    context,
                    "hypothesis.tested",
                    f"Read-only test probe executed: {test_id}",
                )
        self._rescore(context)
        self._finish_analysis(context)
        self.store.save(context)

    def _rescore(self, context: InvestigationContext) -> None:
        updated: list[InvestigationHypothesis] = []
        for hypothesis in context.hypotheses:
            grounded = validate_hypothesis(hypothesis, context.evidence)
            scored, _ = self.scorer.score(grounded, context.evidence, context.correlations)
            updated.append(scored)
        context.hypotheses = updated
        self._persist_hypotheses(context)

    def _finish_analysis(self, context: InvestigationContext) -> None:
        supported = [
            item
            for item in context.hypotheses
            if item.status is InvestigationHypothesisStatus.SUPPORTED
        ]
        ranked = sorted(context.hypotheses, key=lambda item: item.confidence, reverse=True)
        selected = supported[0] if supported else (ranked[0] if ranked else None)
        if selected is not None:
            context.selected_hypothesis = selected.hypothesis_id
            context.confidence = selected.confidence
            context.confidence_factors = selected.confidence_factors
            context.confidence_explanation = self.scorer.explain(
                selected.confidence_factors,
                selected.status,
                [
                    item
                    for item in context.evidence
                    if item.evidence_id in selected.supporting_evidence
                ],
                [
                    item
                    for item in context.evidence
                    if item.evidence_id in selected.contradicting_evidence
                ],
            )
            context.evidence_gaps = selected.missing_evidence
            context.root_cause_candidates = [
                RootCauseCandidate(
                    hypothesis_id=item.hypothesis_id,
                    title=item.title,
                    summary=item.description,
                    confidence=item.confidence,
                    evidence_ids=item.supporting_evidence,
                )
                for item in ranked[:3]
            ]
        else:
            context.selected_hypothesis = None
            context.confidence = 0.0
            context.confidence_factors = {}
            context.confidence_explanation = ["No evidence-grounded hypothesis is available."]
            context.evidence_gaps = ["At least one independent evidence signal"]
            context.root_cause_candidates = []
        if selected is not None and selected.status is InvestigationHypothesisStatus.SUPPORTED:
            context.status = InvestigationStatus.COMPLETED
            context.recommended_next_step = (
                "Hand off this root-cause candidate to the Phase 4 orchestrator "
                "for approval-gated planning."
            )
            context.orchestrator_handoff.status = InvestigationHandoffStatus.READY
        elif context.evidence:
            context.status = InvestigationStatus.INCONCLUSIVE
            context.recommended_next_step = (
                selected.next_validation_step
                if selected is not None and selected.next_validation_step
                else (
                    "Collect an additional independent read-only signal before making "
                    "a remediation recommendation."
                )
            )
            context.orchestrator_handoff.status = InvestigationHandoffStatus.REQUIRES_HUMAN
        else:
            context.status = InvestigationStatus.REQUIRES_HUMAN
            context.recommended_next_step = (
                "Attach or collect permitted evidence before continuing investigation."
            )
            context.orchestrator_handoff.status = InvestigationHandoffStatus.REQUIRES_HUMAN
        self._record(
            context,
            "investigation.analysis.completed",
            f"Investigation analysis is {context.status.value}",
            status=context.status.value,
        )

    def _load_existing_evidence(self, context: InvestigationContext) -> None:
        known = {item.evidence_id for item in context.evidence}
        for item in self.repository.list_evidence(context.incident_id):
            evidence_id = str(item.id)
            if evidence_id in known:
                continue
            context.evidence.append(
                EvidenceRecord(
                    evidence_id=evidence_id,
                    incident_id=context.incident_id,
                    source=item.source,
                    evidence_type=self._legacy_type(item.type.value),
                    timestamp=item.timestamp,
                    summary=item.summary,
                    raw_reference={"record_id": evidence_id},
                    relevance=item.relevance,
                    confidence=0.75,
                    collected_by="incident_repository",
                    metadata={"service": item.source, "simulated": "false"},
                    simulated=False,
                )
            )

    def _persist_domain_evidence(self, context: InvestigationContext, item: EvidenceRecord) -> None:
        try:
            self.repository.add_evidence(
                Evidence(
                    id=self._stable_uuid(item.evidence_id),
                    tenant_id=context.tenant_id,
                    evidence_id=item.evidence_id,
                    incident_id=item.incident_id,
                    type=domain_evidence_type(item.evidence_type),
                    source=item.source,
                    timestamp=item.timestamp,
                    summary=item.summary,
                    raw_reference=item.raw_reference,
                    confidence=item.confidence,
                    collected_by=item.collected_by,
                    collection_status=item.collection_status.value,
                    metadata=item.metadata,
                    simulated=item.simulated,
                    data={
                        "evidence_id": item.evidence_id,
                        "raw_reference": item.raw_reference,
                        "metadata": item.metadata,
                        "confidence": item.confidence,
                        "collected_by": item.collected_by,
                        "collection_status": item.collection_status.value,
                        "simulated": item.simulated,
                    },
                    relevance=item.relevance,
                )
            )
        except ValueError:
            # A repeated collection is idempotent at the investigation context
            # boundary; the public ledger remains the first recorded observation.
            pass

    def _persist_hypotheses(self, context: InvestigationContext) -> None:
        existing = {item.title for item in self.repository.list_hypotheses(context.incident_id)}
        mapping = {
            InvestigationHypothesisStatus.SUPPORTED: HypothesisValidationStatus.SUPPORTED,
            InvestigationHypothesisStatus.REJECTED: HypothesisValidationStatus.CONTRADICTED,
            InvestigationHypothesisStatus.INCONCLUSIVE: HypothesisValidationStatus.INCONCLUSIVE,
            InvestigationHypothesisStatus.TESTING: HypothesisValidationStatus.UNVALIDATED,
            InvestigationHypothesisStatus.PROPOSED: HypothesisValidationStatus.UNVALIDATED,
        }
        for item in context.hypotheses:
            if item.title in existing:
                continue
            self.repository.add_hypothesis(
                Hypothesis(
                    id=item.hypothesis_id,
                    tenant_id=context.tenant_id,
                    incident_id=context.incident_id,
                    title=item.title,
                    description=item.description,
                    confidence=item.confidence,
                    supporting_evidence=[
                        self._stable_uuid(value) for value in item.supporting_evidence
                    ],
                    contradicting_evidence=[
                        self._stable_uuid(value) for value in item.contradicting_evidence
                    ],
                    validation_status=mapping[item.status],
                )
            )

    def _record(
        self,
        context: InvestigationContext,
        event_type: str,
        summary: str,
        *,
        evidence_ids: list[str] | None = None,
        status: str = "RECORDED",
    ) -> InvestigationTimelineEvent:
        event = self.timeline.record(
            context,
            event_type,
            summary,
            evidence_ids=evidence_ids or (),
            status=status,
        )
        context.updated_at = event.timestamp
        self.repository.add_activity(
            ActivityEvent(
                tenant_id=context.tenant_id,
                incident_id=context.incident_id,
                event_type=event_type,
                message=summary,
                metadata={"actor": event.actor, "status": status},
                created_at=event.timestamp,
            )
        )
        self.store.save(context)
        return event

    def _set_status(self, context: InvestigationContext, status: InvestigationStatus) -> None:
        context.status = status
        context.updated_at = utc_now()
        self._record(
            context,
            "investigation.status.changed",
            f"Investigation status: {status.value}",
            status=status.value,
        )

    def _safe_error(
        self, context: InvestigationContext, message: str, *, requires_human: bool
    ) -> None:
        if message not in context.errors:
            context.errors.append(message)
        context.status = (
            InvestigationStatus.REQUIRES_HUMAN if requires_human else InvestigationStatus.FAILED
        )
        context.orchestrator_handoff.status = InvestigationHandoffStatus.REQUIRES_HUMAN
        self._record(context, "investigation.stopped", message, status=context.status.value)
        self.store.save(context)

    def _health_status(self) -> AIHealthStatus | None:
        if self.ai_service is None:
            return None
        try:
            return self.ai_service.health().status
        except Exception:
            return AIHealthStatus.ERROR

    @staticmethod
    def _public_ai_error(error: Exception) -> str:
        return getattr(
            error,
            "public_message",
            "Nemotron assist was unavailable; deterministic analysis retained",
        )

    def _default_tool_names(self, context: InvestigationContext) -> list[str]:
        tools = [
            "get_logs",
            "get_metrics",
            "get_recent_deployments",
            "inspect_configuration",
            "run_health_check",
            "run_test",
        ]
        if context.scenario_id is None:
            return []
        return tools

    @staticmethod
    def _arguments_for(tool_name: str, service: str) -> dict[str, Any] | None:
        if tool_name == "get_logs":
            return {"service": service, "since": 180}
        if tool_name == "get_metrics":
            return {"service": service, "metric": "*", "since": 180}
        if tool_name == "get_recent_deployments":
            return {"service": service}
        if tool_name == "run_health_check":
            return {"service": service, "check": "service_health"}
        return None

    @staticmethod
    def _test_id(context: InvestigationContext, fixture: Any) -> str | None:
        available = {item.name for item in fixture.state.services}
        if context.scenario_id == "database-failure" and "Database" in available:
            return "database_connectivity"
        if "Payment Service" in available and (
            "payment" in context.incident.service.lower()
            or "payment" in context.incident.title.lower()
        ):
            return "payment_authorization_smoke"
        if "Checkout Service" in available:
            return "checkout_smoke"
        return None

    def _test_id_for_incident(self, context: InvestigationContext) -> str | None:
        try:
            fixture = self.simulation_runtime.fixture(context.scenario_id or "")
        except SimulationUnavailableError:
            return None
        return self._test_id(context, fixture)

    @staticmethod
    def _legacy_type(value: str) -> InvestigationEvidenceType:
        mapping = {
            "log": InvestigationEvidenceType.LOG,
            "metric": InvestigationEvidenceType.METRIC,
            "deployment": InvestigationEvidenceType.DEPLOYMENT,
            "configuration": InvestigationEvidenceType.CONFIGURATION,
            "health_check": InvestigationEvidenceType.HEALTH_CHECK,
            "transaction": InvestigationEvidenceType.TRANSACTION,
            "documentation": InvestigationEvidenceType.DOCUMENTATION,
            "document": InvestigationEvidenceType.DOCUMENTATION,
            "test_result": InvestigationEvidenceType.TEST_RESULT,
            "alert": InvestigationEvidenceType.ALERT,
            "customer_signal": InvestigationEvidenceType.CUSTOMER_SIGNAL,
            "system_event": InvestigationEvidenceType.SYSTEM_EVENT,
        }
        return mapping.get(value.lower(), InvestigationEvidenceType.SYSTEM_EVENT)

    @staticmethod
    def _stable_uuid(value: str) -> UUID:
        try:
            return UUID(value)
        except ValueError:
            return UUID(bytes=value.encode("utf-8")[:16].ljust(16, b"0"))


__all__ = ["InvestigationEngine"]
