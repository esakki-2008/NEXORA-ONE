"""Central NEXORA ONE agent orchestrator.

The orchestrator is a policy-controlled workflow coordinator. It delegates
structured intelligence to the Phase 3 AI service, keeps specialists bounded,
executes only allow-listed simulator tools, and stops at approval or human
escalation boundaries.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol, cast
from uuid import UUID

from backend.app.agents.base import AgentDirectory
from backend.app.agents.context import (
    ActionRecord,
    ApprovalDecisionRequest,
    ApprovalRecord,
    CancellationRequest,
    EvidenceItem,
    HypothesisRecord,
    HypothesisStatus,
    OrchestrationActivity,
    OrchestrationContext,
    OrchestrationDomain,
    OrchestratorOverview,
    OrchestratorRuntimeStatus,
    RemediationPlan,
    SpecialistRuntime,
    ToolCallRecord,
    ToolExecutionStatus,
    ToolRequestStatus,
    ToolResultRecord,
    TransitionRecord,
    VerificationOutcome,
    VerificationRecord,
)
from backend.app.agents.planner import Planner
from backend.app.agents.policies import (
    DomainRouter,
    HypothesisEvaluator,
    PriorityPolicy,
    ToolPolicy,
)
from backend.app.agents.state_machine import AgentStateMachine, InvalidTransitionError
from backend.app.agents.store import OrchestrationNotFoundError, OrchestrationStore
from backend.app.ai.exceptions import AIServiceError
from backend.app.ai.schemas import AIAnalysisRequest, AIAnalysisResponse, AIHealthResponse
from backend.app.ai.services.inference import AnalysisSourceNotFoundError
from backend.app.database.repository import IncidentRepository
from backend.app.models.domain import Hypothesis, Incident, IncidentReport, utc_now
from backend.app.models.enums import (
    AgentState,
    ApprovalStatus,
    HypothesisValidationStatus,
    IncidentStatus,
    RiskLevel,
)
from backend.app.schemas.incidents import ActivityEvent
from backend.app.simulator.runtime import ShopFlowSimulationRuntime, SimulationUnavailableError
from backend.app.tools.contracts import ToolDefinition, ToolExecutionResult
from backend.app.tools.registry import ToolRegistry
from backend.app.tools.runtime import ToolRuntime


class OrchestrationAIService(Protocol):
    async def analyze(self, request: AIAnalysisRequest) -> AIAnalysisResponse: ...

    def health(self) -> AIHealthResponse: ...


class OrchestratorNotConfiguredError(RuntimeError):
    """Retained for callers that used the Phase 1 dependency boundary."""


class OrchestratorOperationError(RuntimeError):
    """Raised when a server-side orchestration operation cannot proceed safely."""


class AgentOrchestrator:
    """Coordinate one explicit state machine per incident."""

    def __init__(
        self,
        ai_provider: Any,
        agents: AgentDirectory,
        tools: ToolRegistry,
        *,
        repository: IncidentRepository | None = None,
        store: OrchestrationStore | None = None,
        simulation_runtime: ShopFlowSimulationRuntime | None = None,
        tool_runtime: ToolRuntime | None = None,
        policy: ToolPolicy | None = None,
    ) -> None:
        self.ai_provider = ai_provider
        self.ai_service: OrchestrationAIService | None = (
            cast(OrchestrationAIService, ai_provider) if hasattr(ai_provider, "analyze") else None
        )
        self.agents = agents
        self.tools = tools
        self.repository = repository
        self.store = store or OrchestrationStore()
        self.simulation_runtime = simulation_runtime or ShopFlowSimulationRuntime()
        self.policy = policy or ToolPolicy()
        self.tool_runtime = tool_runtime
        self.domain_router = DomainRouter()
        self.hypothesis_evaluator = HypothesisEvaluator()
        self.priority_policy = PriorityPolicy()
        self.planner = Planner()
        self._locks: dict[UUID, asyncio.Lock] = {}

    def registered_agents(self) -> list[str]:
        return self.agents.list_names()

    def registered_tools(self) -> list[str]:
        return self.tools.list_names()

    def tool_definitions(self) -> list[ToolDefinition]:
        return self.tools.list_definitions()

    def _incident_lock(self, incident_id: UUID) -> asyncio.Lock:
        if incident_id not in self._locks:
            self._locks[incident_id] = asyncio.Lock()
        return self._locks[incident_id]

    async def investigate(self, incident_id: str) -> OrchestrationContext:
        """Backward-compatible entry point for a live incident investigation."""

        try:
            parsed_id = UUID(incident_id)
        except ValueError as exc:
            raise OrchestratorOperationError("Incident identifier is invalid") from exc
        return await self.start(parsed_id)

    async def start(
        self,
        incident_id: UUID,
        *,
        scenario_id: str | None = None,
        request_id: str | None = None,
    ) -> OrchestrationContext:
        if self.repository is None or self.ai_service is None or self.tool_runtime is None:
            raise OrchestratorNotConfiguredError(
                "Central orchestrator dependencies are not configured"
            )
        incident = self.repository.get_incident(incident_id)
        if incident is None:
            raise OrchestrationNotFoundError(f"Incident {incident_id} was not found")

        async with self._incident_lock(incident_id):
            existing = self.store.get_context(incident_id)
            if existing is not None and existing.current_state is not AgentState.IDLE:
                if (
                    existing.approval is not None
                    and existing.approval.status is ApprovalStatus.PENDING
                    and existing.approval.expires_at <= datetime.now(UTC)
                ):
                    return self.context(incident_id)
                return existing
            context = OrchestrationContext(
                incident_id=incident_id,
                incident=incident,
                source_type="synthetic_demo_data" if scenario_id else "live_incident_record",
                scenario_id=scenario_id,
                current_state=AgentState.IDLE,
                runtime_status=OrchestratorRuntimeStatus.RUNNING,
            )
            self.store.save_context(context)
            try:
                self._transition(context, AgentState.INCIDENT_RECEIVED, "Incident received")
                self._record(context, "orchestrator.started", "Orchestrator started")
                self._transition(context, AgentState.OBSERVING, "Observation stage started")
                self._record(
                    context,
                    "orchestrator.evidence.collecting",
                    "Initial evidence collection started",
                )
                self._collect_initial_evidence(context)
                self._record(
                    context, "orchestrator.evidence.collected", "Initial evidence collected"
                )
                self._record(context, "orchestrator.evidence.normalized", "Evidence normalized")
                self._transition(context, AgentState.INVESTIGATING, "Evidence normalized")
                self._route_domain(context)
                if context.selected_domain is None:
                    return self._escalate(
                        context, "Domain confidence is insufficient for safe routing"
                    )
                self._record(
                    context,
                    "orchestrator.specialist.selected",
                    f"Specialist selected: {context.selected_agent or 'none'}",
                    {"domain": context.selected_domain.value},
                )
                response = await self._investigate(context)
                if response is None:
                    return context
                self._record(
                    context, "orchestrator.hypothesis.generated", "Hypothesis generation completed"
                )
                self._transition(
                    context, AgentState.HYPOTHESIS_GENERATED, "Structured hypotheses received"
                )
                self._transition(context, AgentState.VALIDATING, "Validation stage started")
                await self._validate(context, response)
                if not any(
                    item.status is HypothesisStatus.SUPPORTED for item in context.hypotheses
                ):
                    return self._escalate(
                        context, "Evidence is insufficient to support a hypothesis"
                    )
                plan, plan_message = self.planner.build(context, response)
                if plan is None:
                    return self._escalate(context, plan_message)
                self._set_plan(context, plan)
                self._record(context, "orchestrator.remediation.proposed", plan_message)
                self._transition(
                    context, AgentState.REMEDIATION_PROPOSED, "Bounded remediation plan proposed"
                )
                change_step = plan.change_step
                if change_step is None or not change_step.requires_approval:
                    return self._escalate(context, "No approval-gated change step was produced")
                approval = ApprovalRecord(
                    incident_id=context.incident_id,
                    action_id=change_step.id,
                    requested_action=change_step.action,
                    risk_level=change_step.risk_level,
                    reason=plan_message,
                    expected_impact="Restore the affected ShopFlow service in the simulator.",
                    rollback_plan=(
                        "No production rollback is possible; simulator state remains isolated."
                    ),
                    expires_at=datetime.now(UTC) + timedelta(minutes=30),
                )
                context.approval = approval
                context.risk_level = change_step.risk_level
                context.runtime_status = OrchestratorRuntimeStatus.WAITING
                context.updated_at = utc_now()
                self.store.save_context(context)
                self._record(
                    context,
                    "orchestrator.approval.requested",
                    "Action requires approval",
                    {
                        "approval_id": str(approval.approval_id),
                        "risk_level": approval.risk_level.value,
                    },
                )
                self._transition(
                    context,
                    AgentState.WAITING_FOR_APPROVAL,
                    "Approval required before simulated action",
                )
                return context
            except (AIServiceError, AnalysisSourceNotFoundError) as exc:
                return self._escalate(context, self._safe_error(exc))
            except SimulationUnavailableError:
                return self._escalate(
                    context, "Evidence source is unavailable to the controlled simulator"
                )
            except (InvalidTransitionError, OrchestratorOperationError):
                raise
            except Exception:
                return self._fail(context, "Orchestrator failed safely after an unexpected error")

    async def approve(
        self,
        approval_id: UUID,
        request: ApprovalDecisionRequest,
    ) -> OrchestrationContext:
        approval = self.store.get_approval(approval_id)
        if approval is None:
            raise OrchestrationNotFoundError(f"Approval {approval_id} was not found")
        async with self._incident_lock(approval.incident_id):
            context = self.store.require_context(approval.incident_id)
            if approval.status is ApprovalStatus.EXPIRED:
                return self._escalate(context, "Approval expired before execution")
            if approval.status is not ApprovalStatus.PENDING:
                raise OrchestratorOperationError("Approval is no longer pending")
            if context.current_state is not AgentState.WAITING_FOR_APPROVAL:
                raise OrchestratorOperationError("Incident is not waiting for this approval")
            approval = approval.model_copy(
                update={
                    "status": ApprovalStatus.APPROVED,
                    "approved_by": request.decided_by,
                    "approved_at": utc_now(),
                    "decision_reason": request.reason,
                }
            )
            self.store.save_approval(approval)
            context.approval = approval
            self._record(context, "orchestrator.approval.granted", "Approval granted by operator")
            self._transition(context, AgentState.EXECUTING, "Server-side approval accepted")
            change_step = context.remediation_plan.change_step if context.remediation_plan else None
            if change_step is None:
                return self._fail(context, "Approved plan has no controlled change step")
            result = await self._execute_tool(
                context,
                "execute_safe_action",
                change_step.parameters,
                approval=approval,
                idempotency_key=f"approval:{approval.approval_id}",
                reason="Approved simulated action",
            )
            if result.status.value != ToolExecutionStatus.SUCCESS.value:
                if result.status.value in {
                    ToolExecutionStatus.REJECTED.value,
                    ToolExecutionStatus.NOT_AVAILABLE.value,
                }:
                    return self._escalate(
                        context,
                        "Approved action was not available to the policy-controlled simulator",
                    )
                return self._fail(context, "Controlled simulated action failed")
            self._set_step_status(context, change_step.id, ToolRequestStatus.EXECUTED)
            self._record(
                context, "orchestrator.action.executed", "Controlled simulated action executed"
            )
            self._transition(
                context, AgentState.VERIFYING, "Execution completed; verification started"
            )
            verified = await self._verify(context)
            if not verified:
                return self._escalate(context, "Verification did not prove the expected state")
            report = self._build_report(context)
            if self.repository is None:
                return self._fail(context, "Orchestrator repository is unavailable")
            try:
                self.repository.add_report(report)
            except Exception:
                return self._fail(context, "Incident report could not be recorded")
            self._record(context, "orchestrator.report.generated", "Incident report generated")
            self._transition(context, AgentState.RESOLVED, "Verification succeeded")
            context.runtime_status = OrchestratorRuntimeStatus.COMPLETED
            context.updated_at = utc_now()
            self.store.save_context(context)
            return context

    async def cancel(
        self,
        incident_id: UUID,
        request: CancellationRequest,
    ) -> OrchestrationContext:
        async with self._incident_lock(incident_id):
            context = self.store.require_context(incident_id)
            machine = AgentStateMachine(context.current_state)
            if not machine.can_transition(AgentState.CANCELLED):
                raise OrchestratorOperationError(
                    "Incident cannot be cancelled in its current state"
                )
            if context.approval is not None and context.approval.status is ApprovalStatus.PENDING:
                context.approval = context.approval.model_copy(
                    update={
                        "status": ApprovalStatus.CANCELLED,
                        "rejected_by": request.requested_by,
                        "rejected_at": utc_now(),
                        "decision_reason": request.reason or "Orchestration cancelled",
                    }
                )
                self.store.save_approval(context.approval)
            self._transition(
                context,
                AgentState.CANCELLED,
                request.reason or f"Cancelled by {request.requested_by}",
            )
            context.runtime_status = OrchestratorRuntimeStatus.CANCELLED
            self._record(context, "orchestrator.cancelled", "Orchestration cancelled by operator")
            self.store.save_context(context)
            return context

    async def reject(
        self,
        approval_id: UUID,
        request: ApprovalDecisionRequest,
    ) -> OrchestrationContext:
        approval = self.store.get_approval(approval_id)
        if approval is None:
            raise OrchestrationNotFoundError(f"Approval {approval_id} was not found")
        async with self._incident_lock(approval.incident_id):
            context = self.store.require_context(approval.incident_id)
            if approval.status is not ApprovalStatus.PENDING:
                raise OrchestratorOperationError("Approval is no longer pending")
            approval = approval.model_copy(
                update={
                    "status": ApprovalStatus.REJECTED,
                    "rejected_by": request.decided_by,
                    "rejected_at": utc_now(),
                    "decision_reason": request.reason,
                }
            )
            self.store.save_approval(approval)
            context.approval = approval
            self._record(
                context, "orchestrator.approval.rejected", "Approval rejected; no action executed"
            )
            return self._escalate(context, "Human approval was rejected")

    def context(self, incident_id: UUID) -> OrchestrationContext:
        context = self.store.require_context(incident_id)
        if (
            context.approval is not None
            and context.approval.status is ApprovalStatus.PENDING
            and context.approval.expires_at <= datetime.now(UTC)
        ):
            context.approval = self.store.get_approval(context.approval.approval_id)
            if context.approval is not None:
                return self._escalate(context, "Approval expired before execution")
        return context

    def activity(self, incident_id: UUID) -> list[OrchestrationActivity]:
        return list(reversed(self.context(incident_id).activity))

    def hypotheses(self, incident_id: UUID) -> list[HypothesisRecord]:
        return self.context(incident_id).hypotheses

    def actions(self) -> list[ActionRecord]:
        return self.store.list_actions()

    def verifications(self) -> list[VerificationRecord]:
        return self.store.list_verifications()

    def approvals(self, status: ApprovalStatus | None = None) -> list[ApprovalRecord]:
        return self.store.list_approvals(status)

    def overview(self) -> OrchestratorOverview:
        contexts = self.store.list_contexts()
        if any(item.runtime_status is OrchestratorRuntimeStatus.RUNNING for item in contexts):
            status = OrchestratorRuntimeStatus.RUNNING
        elif any(item.runtime_status is OrchestratorRuntimeStatus.WAITING for item in contexts):
            status = OrchestratorRuntimeStatus.WAITING
        elif any(item.runtime_status is OrchestratorRuntimeStatus.FAILED for item in contexts):
            status = OrchestratorRuntimeStatus.FAILED
        elif any(item.runtime_status is OrchestratorRuntimeStatus.COMPLETED for item in contexts):
            status = OrchestratorRuntimeStatus.COMPLETED
        else:
            status = OrchestratorRuntimeStatus.IDLE
        specialists: list[SpecialistRuntime] = []
        for agent in self.agents.list_agents():
            selected = next((item for item in contexts if item.selected_agent == agent.name), None)
            specialist_status = "IDLE"
            if selected is not None:
                specialist_status = (
                    "WAITING"
                    if selected.runtime_status is OrchestratorRuntimeStatus.WAITING
                    else selected.runtime_status.value
                )
            specialists.append(
                SpecialistRuntime(
                    name=agent.name,
                    domain=getattr(agent, "domain_enum", OrchestrationDomain.IT),
                    status=specialist_status,
                    current_task=(selected.current_state.value if selected else None),
                    last_activity=selected.updated_at if selected else None,
                    capabilities=list(getattr(agent, "capabilities", ())),
                )
            )
        last_activity = contexts[0].updated_at if contexts else None
        return OrchestratorOverview(
            status=status,
            active_incidents=sum(
                item.runtime_status
                in {OrchestratorRuntimeStatus.RUNNING, OrchestratorRuntimeStatus.WAITING}
                for item in contexts
            ),
            specialists=specialists,
            last_activity=last_activity,
        )

    def _collect_initial_evidence(self, context: OrchestrationContext) -> None:
        if context.scenario_id:
            fixture = self.simulation_runtime.fixture(context.scenario_id)
            context.evidence.extend(self._fixture_evidence(fixture))
            return
        if self.repository is None:
            raise OrchestratorOperationError("Orchestrator repository is not configured")
        for item in self.repository.list_evidence(context.incident_id):
            context.evidence.append(
                EvidenceItem(
                    id=str(item.id),
                    source=item.source,
                    timestamp=item.timestamp,
                    type=item.type.value,
                    summary=item.summary,
                    raw_reference={"record_id": str(item.id), "source": item.source},
                    relevance=item.relevance,
                )
            )
        context.updated_at = utc_now()

    def _route_domain(self, context: OrchestrationContext) -> None:
        selection = self.domain_router.select(context.incident, context.evidence)
        if selection.primary is None or selection.confidence < 0.6:
            return
        context.selected_domain = selection.primary
        context.selected_domains = list(selection.domains)
        agent_by_domain = {
            OrchestrationDomain.IT: "it_operations",
            OrchestrationDomain.REVENUE: "revenue",
            OrchestrationDomain.SUPPORT: "support",
            OrchestrationDomain.SUPPLY_CHAIN: "supply_chain",
            OrchestrationDomain.CONTRACTS: "contracts",
            OrchestrationDomain.CLOUD: "cloud",
            OrchestrationDomain.DATA: "data",
            OrchestrationDomain.COMPLIANCE: "compliance",
        }
        context.selected_agent = agent_by_domain.get(selection.primary)

    async def _investigate(self, context: OrchestrationContext) -> AIAnalysisResponse | None:
        if self.ai_service is None:
            raise OrchestratorOperationError("Orchestrator AI service is not configured")
        self._record(context, "orchestrator.ai.requested", "Nemotron investigation requested")
        request = AIAnalysisRequest(
            scenario_id=context.scenario_id if context.scenario_id is not None else None,
            incident_id=None if context.scenario_id is not None else context.incident_id,
        )
        response = await self.ai_service.analyze(request)
        context.analysis_summary = response.summary
        context.analysis_confidence = response.confidence
        context.ai_status = self.ai_service.health().status
        context.hypotheses = [
            HypothesisRecord(
                title=item.title,
                description=item.description,
                supporting_evidence=item.supporting_evidence,
                contradicting_evidence=item.contradicting_evidence,
                confidence=item.confidence,
                status=HypothesisStatus.PROPOSED,
            )
            for item in response.hypotheses
        ]
        if not context.hypotheses:
            self._escalate(context, "Nemotron returned no hypothesis to validate")
            return None
        for tool_call in response.selected_tools:
            try:
                definition = self.tools.get(tool_call.tool_name).definition
            except Exception:
                self._record(
                    context,
                    "orchestrator.tool.rejected",
                    "Tool request rejected: tool not allow-listed.",
                    {"tool_name": tool_call.tool_name},
                )
                continue
            context.tool_calls.append(
                ToolCallRecord(
                    tool_name=tool_call.tool_name,
                    arguments=tool_call.arguments,
                    risk_level=definition.risk_level,
                    reason=tool_call.reason,
                )
            )
        self.store.save_context(context)
        return response

    async def _validate(self, context: OrchestrationContext, response: AIAnalysisResponse) -> None:
        if context.scenario_id is None:
            context.hypotheses = self.hypothesis_evaluator.evaluate(
                context.hypotheses, context.evidence
            )
            self.store.save_context(context)
            return
        validation_requests: list[tuple[str, dict[str, Any], str]] = [
            (
                "get_recent_deployments",
                {"service": context.incident.service},
                "Server validation of deployment evidence",
            ),
            (
                "get_logs",
                {"service": context.incident.service, "since": 180},
                "Server validation of logs",
            ),
            (
                "get_metrics",
                {"service": context.incident.service, "metric": "*", "since": 180},
                "Server validation of metrics",
            ),
            (
                "run_health_check",
                {"service": context.incident.service, "check": "service_health"},
                "Server validation of service health",
            ),
        ]
        requested = {(item.tool_name, str(item.arguments)) for item in context.tool_calls}
        for tool_name, arguments, reason in validation_requests:
            if (tool_name, str(arguments)) in requested:
                continue
            await self._execute_tool(context, tool_name, arguments, reason=reason)
        context.hypotheses = self.hypothesis_evaluator.evaluate(
            context.hypotheses, context.evidence
        )
        if self.repository is not None:
            existing_titles = {
                item.title for item in self.repository.list_hypotheses(context.incident_id)
            }
            status_map = {
                HypothesisStatus.SUPPORTED: HypothesisValidationStatus.SUPPORTED,
                HypothesisStatus.REJECTED: HypothesisValidationStatus.CONTRADICTED,
                HypothesisStatus.INCONCLUSIVE: HypothesisValidationStatus.INCONCLUSIVE,
            }
            for item in context.hypotheses:
                if item.title in existing_titles:
                    continue
                self.repository.add_hypothesis(
                    Hypothesis(
                        incident_id=context.incident_id,
                        title=item.title,
                        description=item.description,
                        confidence=item.confidence,
                        supporting_evidence=[
                            UUID(value) for value in item.supporting_evidence if _is_uuid(value)
                        ],
                        contradicting_evidence=[
                            UUID(value) for value in item.contradicting_evidence if _is_uuid(value)
                        ],
                        validation_status=status_map.get(
                            item.status, HypothesisValidationStatus.UNVALIDATED
                        ),
                    )
                )
        if response.confidence < 0.55:
            context.errors.append("Nemotron confidence is below the safe orchestration threshold")
        self.store.save_context(context)

    async def _verify(self, context: OrchestrationContext) -> bool:
        checks = (
            ("run_health_check", {"service": context.incident.service, "check": "service_health"}),
            ("get_metrics", {"service": context.incident.service, "metric": "*", "since": 30}),
            ("get_logs", {"service": context.incident.service, "since": 30}),
            (
                "verify_resolution",
                {
                    "service": context.incident.service,
                    "checks": ["service_health", "payment_metrics", "error_logs"],
                },
            ),
        )
        context.verification_plan = [name for name, _ in checks]
        outcomes: list[bool] = []
        for tool_name, arguments in checks:
            result = await self._execute_tool(
                context,
                tool_name,
                arguments,
                reason="Post-action verification",
            )
            passed = result.status.value == ToolExecutionStatus.SUCCESS.value
            if tool_name == "run_health_check":
                passed = passed and bool(result.result.get("healthy"))
            if tool_name == "verify_resolution":
                passed = passed and bool(result.result.get("verified"))
            outcomes.append(passed)
            context.verification_results.append(
                VerificationRecord(
                    incident_id=context.incident_id,
                    check=tool_name,
                    expected_result={"passed": True},
                    actual_result=result.result,
                    status=VerificationOutcome.VERIFIED
                    if passed
                    else VerificationOutcome.NOT_VERIFIED,
                )
            )
        verified = bool(outcomes) and all(outcomes)
        context.verification_outcome = (
            VerificationOutcome.VERIFIED if verified else VerificationOutcome.NOT_VERIFIED
        )
        self._record(
            context,
            "orchestrator.verification.completed",
            "Verification completed" if verified else "Verification failed to prove resolution",
            {"status": context.verification_outcome.value},
        )
        self.store.save_context(context)
        return verified

    async def _execute_tool(
        self,
        context: OrchestrationContext,
        tool_name: str,
        arguments: dict[str, Any],
        *,
        reason: str,
        approval: ApprovalRecord | None = None,
        idempotency_key: str | None = None,
    ) -> ToolExecutionResult:
        if self.tool_runtime is None:
            raise OrchestratorOperationError("Orchestrator tool runtime is not configured")
        try:
            definition = self.tools.get(tool_name).definition
            risk_level = definition.risk_level
        except Exception:
            risk_level = RiskLevel.READ_ONLY
        call = ToolCallRecord(
            tool_name=tool_name,
            arguments=arguments,
            risk_level=risk_level,
            reason=reason,
        )
        context.tool_calls.append(call)
        self._record(context, "orchestrator.tool.requested", f"Tool requested: {tool_name}")
        result = await self.tool_runtime.execute(
            tool_name,
            arguments,
            scenario_id=context.scenario_id,
            approval=approval,
            idempotency_key=idempotency_key,
        )
        status = ToolExecutionStatus(result.status.value)
        context.tool_calls[-1] = call.model_copy(
            update={
                "status": ToolRequestStatus.EXECUTED
                if status is ToolExecutionStatus.SUCCESS
                else ToolRequestStatus.REJECTED
                if status is ToolExecutionStatus.REJECTED
                else ToolRequestStatus.FAILED
            }
        )
        normalized_evidence = [EvidenceItem.model_validate(item) for item in result.evidence]
        context.tool_results.append(
            ToolResultRecord(
                execution_id=result.execution_id,
                tool_name=result.tool_name,
                status=status,
                result=result.result,
                evidence=normalized_evidence,
                timestamp=result.timestamp,
                risk_level=result.risk_level,
            )
        )
        known = {item.id for item in context.evidence}
        context.evidence.extend(item for item in normalized_evidence if item.id not in known)
        self._record(
            context,
            "orchestrator.tool.executed"
            if status is ToolExecutionStatus.SUCCESS
            else "orchestrator.tool.rejected",
            f"Tool {tool_name}: {status.value}",
            {"tool_name": tool_name, "status": status.value},
        )
        self.store.save_context(context)
        return result

    @staticmethod
    def _set_step_status(
        context: OrchestrationContext, step_id: UUID, status: ToolRequestStatus
    ) -> None:
        if context.remediation_plan is None:
            return
        for step in context.remediation_plan.steps:
            if step.id == step_id:
                step.status = status
                break

    def _set_plan(self, context: OrchestrationContext, plan: RemediationPlan) -> None:
        context.remediation_plan = plan
        risk = plan.change_step.risk_level if plan.change_step else RiskLevel.READ_ONLY
        context.risk_level = risk
        priority, factors = self.priority_policy.calculate(
            context.incident,
            evidence_count=len(context.evidence),
            confidence=context.analysis_confidence or 0.0,
            risk=risk,
        )
        context.priority = priority
        context.priority_factors = factors
        context.updated_at = utc_now()
        self.store.save_context(context)

    def _transition(self, context: OrchestrationContext, target: AgentState, reason: str) -> None:
        machine = AgentStateMachine(context.current_state)
        machine.transition(target, reason)
        previous = context.current_state
        context.current_state = target
        context.transition_history.append(
            TransitionRecord(from_state=previous, to_state=target, reason=reason)
        )
        context.updated_at = utc_now()
        context.incident = self._update_incident_state(context.incident, target)
        self.store.save_context(context)
        self._record(
            context,
            "orchestrator.state.changed",
            f"State changed: {previous.value} → {target.value}",
        )

    def _update_incident_state(self, incident: Incident, state: AgentState) -> Incident:
        if self.repository is None:
            return incident
        status_by_state = {
            AgentState.INVESTIGATING: IncidentStatus.INVESTIGATING,
            AgentState.REMEDIATION_PROPOSED: IncidentStatus.REMEDIATION_PROPOSED,
            AgentState.WAITING_FOR_APPROVAL: IncidentStatus.REMEDIATION_PROPOSED,
            AgentState.EXECUTING: IncidentStatus.REMEDIATION_PROPOSED,
            AgentState.VERIFYING: IncidentStatus.REMEDIATION_PROPOSED,
            AgentState.RESOLVED: IncidentStatus.RESOLVED,
            AgentState.FAILED: IncidentStatus.FAILED,
            AgentState.CANCELLED: IncidentStatus.CANCELLED,
            AgentState.REQUIRES_HUMAN: IncidentStatus.REQUIRES_HUMAN,
        }
        status = status_by_state.get(state, incident.status)
        updated = incident.model_copy(
            update={"agent_state": state, "status": status, "updated_at": utc_now()}
        )
        return self.repository.update_incident(updated)

    def _record(
        self,
        context: OrchestrationContext,
        event_type: str,
        message: str,
        metadata: dict[str, str] | None = None,
    ) -> None:
        event = OrchestrationActivity(
            incident_id=context.incident_id,
            event_type=event_type,
            message=message,
            metadata=metadata or {},
        )
        context.activity.append(event)
        context.activity = context.activity[-500:]
        context.updated_at = event.created_at
        if self.repository is not None:
            self.repository.add_activity(
                ActivityEvent(
                    incident_id=context.incident_id,
                    event_type=event_type,
                    message=message,
                    metadata=metadata or {},
                    created_at=event.created_at,
                )
            )
        self.store.save_context(context)

    def _escalate(self, context: OrchestrationContext, message: str) -> OrchestrationContext:
        if message not in context.errors:
            context.errors.append(message)
        if context.current_state is not AgentState.REQUIRES_HUMAN:
            machine = AgentStateMachine(context.current_state)
            if machine.can_transition(AgentState.REQUIRES_HUMAN):
                self._transition(context, AgentState.REQUIRES_HUMAN, message)
        context.runtime_status = OrchestratorRuntimeStatus.WAITING
        self._record(context, "orchestrator.human.required", message)
        self.store.save_context(context)
        return context

    def _fail(self, context: OrchestrationContext, message: str) -> OrchestrationContext:
        context.errors.append(message)
        if context.current_state is not AgentState.FAILED:
            machine = AgentStateMachine(context.current_state)
            if machine.can_transition(AgentState.FAILED):
                self._transition(context, AgentState.FAILED, message)
        context.runtime_status = OrchestratorRuntimeStatus.FAILED
        self._record(context, "orchestrator.failed", message)
        self.store.save_context(context)
        return context

    @staticmethod
    def _safe_error(error: Exception) -> str:
        if isinstance(error, AIServiceError):
            return error.public_message
        if isinstance(error, AnalysisSourceNotFoundError):
            return str(error)
        return "Orchestrator could not safely continue"

    @staticmethod
    def _fixture_evidence(fixture: Any) -> list[EvidenceItem]:
        evidence: list[EvidenceItem] = []
        for item in fixture.state.logs:
            evidence.append(
                EvidenceItem(
                    id=str(item.id),
                    source=f"ShopFlow / {item.service}",
                    timestamp=item.timestamp,
                    type="log",
                    summary=item.message,
                    raw_reference={"scenario_id": fixture.scenario_id, "record_id": str(item.id)},
                    relevance=0.8 if item.level == "ERROR" else 0.5,
                )
            )
        for item in fixture.state.metrics:
            evidence.append(
                EvidenceItem(
                    id=f"metric:{item.service}:{item.name}",
                    source=f"ShopFlow / {item.service}",
                    timestamp=item.observed_at,
                    type="metric",
                    summary=f"{item.name}: {item.value} {item.unit}",
                    raw_reference={"scenario_id": fixture.scenario_id, "metric": item.name},
                    relevance=0.8,
                )
            )
        for item in fixture.state.deployments:
            evidence.append(
                EvidenceItem(
                    id=str(item.id),
                    source=f"ShopFlow / {item.service}",
                    timestamp=item.deployed_at,
                    type="deployment",
                    summary=f"{item.version} — {item.change_summary}",
                    raw_reference={
                        "scenario_id": fixture.scenario_id,
                        "deployment_id": str(item.id),
                    },
                    relevance=0.8,
                )
            )
        for item in fixture.state.configurations:
            evidence.append(
                EvidenceItem(
                    id=f"configuration:{item.service}:{item.key}",
                    source=f"ShopFlow / {item.service}",
                    timestamp=item.updated_at,
                    type="configuration",
                    summary=f"{item.key}: {item.value}",
                    raw_reference={"scenario_id": fixture.scenario_id, "key": item.key},
                    relevance=0.8,
                )
            )
        return evidence

    def _build_report(self, context: OrchestrationContext) -> IncidentReport:
        supported = next(
            (item for item in context.hypotheses if item.status is HypothesisStatus.SUPPORTED),
            None,
        )
        action_result = next(
            (
                item
                for item in reversed(context.tool_results)
                if item.tool_name == "execute_safe_action"
                and item.status is ToolExecutionStatus.SUCCESS
            ),
            None,
        )
        return IncidentReport(
            incident_id=context.incident_id,
            summary=context.analysis_summary or "Orchestrated incident response completed.",
            root_cause=supported.description if supported else "Supported hypothesis not recorded.",
            impact=context.incident.description,
            timeline=[item.model_dump(mode="json") for item in context.activity],
            actions=[action_result.model_dump(mode="json")] if action_result else [],
            verification=[item.model_dump(mode="json") for item in context.verification_results],
            final_status=IncidentStatus.RESOLVED,
        )


def _is_uuid(value: str) -> bool:
    try:
        UUID(value)
    except ValueError:
        return False
    return True


__all__ = [
    "AgentOrchestrator",
    "OrchestratorNotConfiguredError",
    "OrchestratorOperationError",
]
