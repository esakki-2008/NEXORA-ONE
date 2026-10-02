"""Application service for the Phase 7 action lifecycle."""

from __future__ import annotations

import asyncio
from datetime import datetime
from threading import RLock
from typing import Any
from uuid import UUID

from backend.app.actions.approval import ApprovalService
from backend.app.actions.audit import AuditEvent, AuditEventType, AuditTrail
from backend.app.actions.executor import ActionExecutionError, ActionExecutor
from backend.app.actions.idempotency import ActionIdempotencyStore, IdempotencyConflictError
from backend.app.actions.models import (
    Action,
    ActionApprovalState,
    ActionCancelRequest,
    ActionCreateRequest,
    ActionDecisionRequest,
    ActionExecutionOutcome,
    ActionRejectRequest,
    ActionStatus,
    ActionVerificationRecord,
    VerificationState,
)
from backend.app.actions.planner import ActionPlanner, ActionPlannerError
from backend.app.actions.policy import ActionPolicy
from backend.app.actions.registry import ActionRegistry
from backend.app.actions.rollback import RollbackPolicy
from backend.app.actions.validators import (
    ActionValidationError,
    validate_action_fingerprint,
)
from backend.app.agents.orchestrator import AgentOrchestrator
from backend.app.agents.store import OrchestrationNotFoundError
from backend.app.database.repository import IncidentRepository
from backend.app.investigation.context import InvestigationContext
from backend.app.investigation.service import InvestigationService
from backend.app.investigation.store import InvestigationNotFoundError
from backend.app.models.domain import Evidence, IncidentReport, utc_now
from backend.app.models.enums import AgentState, ApprovalStatus, EvidenceType, IncidentStatus
from backend.app.schemas.incidents import ActivityEvent
from backend.app.verification.models import Verification, VerificationStatus
from backend.app.verification.service import (
    VerificationConflictError,
    VerificationNotFoundError,
    VerificationService,
)


class ActionNotFoundError(LookupError):
    """Raised when an action is not present."""


class ActionConflictError(ValueError):
    """Raised for invalid lifecycle, authorization, approval, or binding requests."""


class ActionService:
    """Own the action lifecycle while reusing existing incident/investigation records."""

    def __init__(
        self,
        repository: IncidentRepository,
        registry: ActionRegistry,
        *,
        orchestrator: AgentOrchestrator | None = None,
        investigation_service: InvestigationService | None = None,
        approval_service: ApprovalService | None = None,
        audit: AuditTrail | None = None,
        idempotency: ActionIdempotencyStore | None = None,
        policy: ActionPolicy | None = None,
        executor: ActionExecutor | None = None,
        verification_service: VerificationService | None = None,
    ) -> None:
        self.repository = repository
        self.registry = registry
        self.orchestrator = orchestrator
        self.investigation_service = investigation_service
        self.approvals = approval_service or ApprovalService()
        self.audit_trail = audit or AuditTrail()
        self.idempotency = idempotency or ActionIdempotencyStore()
        self.policy = policy or ActionPolicy()
        self.planner = ActionPlanner(registry)
        self.verification_service = verification_service
        self.executor = executor or ActionExecutor(
            registry,
            self.idempotency,
            verification_service=verification_service,
        )
        if verification_service is not None and self.executor.verification_service is None:
            self.executor.verification_service = verification_service
        self.rollback_policy = RollbackPolicy()
        self._lock = RLock()
        self._actions: dict[UUID, Action] = {}
        self._execution_locks: dict[UUID, asyncio.Lock] = {}

    def definitions(self) -> list[dict[str, Any]]:
        return [definition.response_dict() for definition in self.registry.list_definitions()]

    def create(
        self, request: ActionCreateRequest, *, tenant_id: str = "reference-tenant"
    ) -> Action:
        incident = self.repository.get_incident(request.incident_id)
        if incident is None or incident.tenant_id != tenant_id:
            raise ActionNotFoundError(f"Incident {request.incident_id} was not found")
        investigation = self._investigation(
            request.investigation_id,
            request.incident_id,
            tenant_id=tenant_id,
        )
        orchestration = self._orchestration(request.incident_id, tenant_id=tenant_id)
        effective_scenario = (
            request.scenario_id
            or (investigation.scenario_id if investigation is not None else None)
            or (orchestration.scenario_id if orchestration is not None else None)
        )
        if (
            investigation is not None
            and investigation.scenario_id is not None
            and effective_scenario != investigation.scenario_id
        ):
            raise ActionConflictError(
                "Action scenario is bound to a different investigation scenario"
            )
        if (
            orchestration is not None
            and orchestration.scenario_id is not None
            and effective_scenario != orchestration.scenario_id
        ):
            raise ActionConflictError(
                "Action scenario is bound to a different orchestration scenario"
            )
        try:
            proposal = self.planner.plan(
                incident,
                scenario_id=effective_scenario,
                investigation=investigation,
                orchestration=orchestration,
                action_name=request.action_name,
                recommended_action=request.recommended_action,
                parameters=request.parameters if request.parameters else None,
                root_cause_candidate=request.root_cause_candidate,
                requested_by=request.requested_by,
                idempotency_key=request.idempotency_key,
            )
        except ActionPlannerError:
            raise
        with self._lock:
            try:
                record = self.idempotency.bind(
                    proposal.idempotency_key,
                    proposal.action_fingerprint,
                    proposal.action_id,
                )
            except IdempotencyConflictError as exc:
                raise ActionConflictError(str(exc)) from exc
            existing = self._actions.get(record.action_id)
            if existing is not None:
                return existing.model_copy(deep=True)
            base = Action(
                action_id=proposal.action_id,
                tenant_id=incident.tenant_id,
                incident_id=proposal.incident_id,
                action_name=proposal.action_name,
                normalized_parameters=proposal.normalized_parameters,
                risk_level=proposal.risk_level,
                expected_impact=proposal.expected_impact,
                rollback_plan=proposal.rollback_plan,
                status=ActionStatus.PENDING_APPROVAL,
                requested_by=proposal.requested_by,
                approval_status=ActionApprovalState.PENDING,
                action_fingerprint=proposal.action_fingerprint,
                idempotency_key=proposal.idempotency_key,
                audit_reference=f"audit:{proposal.action_id}",
                rollback_supported=proposal.rollback_supported,
                rollback_action=proposal.rollback_action,
                rollback_parameters=proposal.rollback_parameters,
                rollback_conditions=proposal.rollback_conditions,
                verification_strategy=proposal.verification_strategy,
                scenario_id=proposal.scenario_id,
                evidence_ids=proposal.evidence_ids,
                planning_summary=proposal.planning_summary,
            )
            approval = self.approvals.request(base)
            action = base.model_copy(
                update={
                    "approval_id": approval.approval_id,
                    "approval_status": ActionApprovalState.PENDING,
                }
            )
            self._actions[action.action_id] = action
            self._audit(
                action,
                AuditEventType.ACTION_CREATED,
                actor=request.requested_by,
                metadata={
                    "action_name": action.action_name,
                    "risk_level": action.risk_level.value,
                    "simulated": "true",
                },
            )
            self._audit(
                action,
                AuditEventType.APPROVAL_REQUESTED,
                actor=request.requested_by,
                metadata={"approval_id": str(approval.approval_id)},
            )
            return action.model_copy(deep=True)

    def list_actions(
        self, status: ActionStatus | None = None, *, tenant_id: str | None = None
    ) -> list[Action]:
        with self._lock:
            actions = [self._synchronize_expiry(item) for item in self._actions.values()]
            if tenant_id is not None:
                actions = [item for item in actions if item.tenant_id == tenant_id]
            if status is not None:
                actions = [item for item in actions if item.status is status]
            return sorted(
                (item.model_copy(deep=True) for item in actions),
                key=lambda item: item.created_at,
                reverse=True,
            )

    def get(self, action_id: UUID, *, tenant_id: str | None = None) -> Action:
        with self._lock:
            action = self._actions.get(action_id)
            if action is None or (tenant_id is not None and action.tenant_id != tenant_id):
                raise ActionNotFoundError(f"Action {action_id} was not found")
            return self._synchronize_expiry(action).model_copy(deep=True)

    def approve(self, action_id: UUID, request: ActionDecisionRequest) -> Action:
        action = self.get(action_id)
        self._check_integrity(action)
        authorization = self.policy.authorize_actor(request.requested_by)
        if not authorization.allowed:
            raise ActionConflictError(authorization.reason)
        if request.auto_execute:
            raise ActionConflictError(
                "Approval and execution are separate controls; use the execute endpoint explicitly"
            )
        if action.status is ActionStatus.APPROVED:
            return action
        if action.status is not ActionStatus.PENDING_APPROVAL or action.approval_id is None:
            raise ActionConflictError("Action is not pending approval")
        approval = self.approvals.get(action.approval_id)
        if approval is None:
            raise ActionConflictError("Action approval record is unavailable")
        decision = self.policy.evaluate_approval(
            action, approval, request.requested_by, fingerprint_valid=True
        )
        if not decision.allowed:
            raise ActionConflictError(decision.reason)
        try:
            approved = self.approvals.approve(approval, request.requested_by, request.reason)
        except ValueError as exc:
            self._expire_if_needed(action, approval)
            raise ActionConflictError(str(exc)) from exc
        action = self._update(
            action,
            status=ActionStatus.APPROVED,
            approval_status=ActionApprovalState.APPROVED,
            approved_by=approved.approved_by,
            updated_at=utc_now(),
        )
        self._audit(
            action,
            AuditEventType.ACTION_APPROVED,
            actor=request.requested_by,
            metadata={"approval_id": str(approved.approval_id)},
        )
        return action

    def reject(self, action_id: UUID, request: ActionRejectRequest) -> Action:
        action = self.get(action_id)
        self._check_integrity(action)
        authorization = self.policy.authorize_actor(request.requested_by)
        if not authorization.allowed:
            raise ActionConflictError(authorization.reason)
        if action.status is ActionStatus.REJECTED:
            return action
        if action.status is not ActionStatus.PENDING_APPROVAL or action.approval_id is None:
            raise ActionConflictError("Action is not pending approval")
        approval = self.approvals.get(action.approval_id)
        if approval is None:
            raise ActionConflictError("Action approval record is unavailable")
        try:
            rejected = self.approvals.reject(approval, request.requested_by, request.reason)
        except ValueError as exc:
            raise ActionConflictError(str(exc)) from exc
        action = self._update(
            action,
            status=ActionStatus.REJECTED,
            approval_status=ActionApprovalState.REJECTED,
            failure_reason=request.reason or "Human approval rejected",
            updated_at=utc_now(),
        )
        self._audit(
            action,
            AuditEventType.ACTION_REJECTED,
            actor=request.requested_by,
            metadata={"approval_id": str(rejected.approval_id)},
        )
        self._escalate_incident(action, "Controlled action rejected by a human operator")
        return action

    def cancel(self, action_id: UUID, request: ActionCancelRequest) -> Action:
        action = self.get(action_id)
        self._check_integrity(action)
        authorization = self.policy.authorize_actor(request.requested_by)
        if not authorization.allowed:
            raise ActionConflictError(authorization.reason)
        if action.status is ActionStatus.CANCELLED:
            return action
        if action.status in {
            ActionStatus.APPROVED,
            ActionStatus.COMPLETED,
            ActionStatus.ROLLED_BACK,
            ActionStatus.EXECUTING,
        }:
            raise ActionConflictError("Action cannot be cancelled in its current state")
        if action.approval_id is not None:
            approval = self.approvals.get(action.approval_id)
            if approval is not None:
                self.approvals.cancel(approval, request.requested_by, request.reason)
        action = self._update(
            action,
            status=ActionStatus.CANCELLED,
            approval_status=ActionApprovalState.CANCELLED,
            failure_reason=request.reason or "Action cancelled by operator",
            updated_at=utc_now(),
        )
        self._audit(
            action,
            AuditEventType.ACTION_CANCELLED,
            actor=request.requested_by,
            metadata={},
        )
        return action

    async def execute(self, action_id: UUID, request: ActionDecisionRequest) -> Action:
        """Serialize execution per action before consulting idempotency."""
        lock = self._execution_locks.setdefault(action_id, asyncio.Lock())
        async with lock:
            return await self._execute(action_id, request)

    async def _execute(self, action_id: UUID, request: ActionDecisionRequest) -> Action:
        action = self.get(action_id)
        self._check_integrity(action)
        if action.status in {ActionStatus.COMPLETED, ActionStatus.ROLLED_BACK}:
            return action
        if action.status is ActionStatus.REQUIRES_HUMAN:
            raise ActionConflictError("Action requires human review before another execution")
        approval = self.approvals.get(action.approval_id) if action.approval_id else None
        decision = self.policy.evaluate_execution(
            action,
            approval,
            request.requested_by,
            fingerprint_valid=True,
            auto_execute=request.auto_execute,
        )
        if not decision.allowed:
            raise ActionConflictError(decision.reason)
        cached = self.idempotency.execution(action.idempotency_key)
        if cached is not None:
            return self._apply_outcome(
                action, ActionExecutionOutcome.model_validate(cached), request.requested_by
            )
        action = self._update(action, status=ActionStatus.EXECUTING, updated_at=utc_now())
        self._audit(
            action,
            AuditEventType.EXECUTION_STARTED,
            actor=request.requested_by,
            metadata={"attempt_limit": str(self.executor.max_attempts)},
        )
        self._audit(
            action,
            AuditEventType.VERIFICATION_STARTED,
            actor="phase7.executor",
            metadata={"strategy": action.verification_strategy},
        )
        try:
            outcome = await self.executor.execute(action)
        except ActionExecutionError as exc:
            outcome = ActionExecutionOutcome(
                action_id=action.action_id,
                status=ActionStatus.REQUIRES_HUMAN,
                execution_attempts=action.execution_attempts,
                result={"reason": str(exc)},
                verification_status=VerificationState.REQUIRES_HUMAN,
                verification_details="Action validation failed before controlled execution.",
            )
            self.idempotency.save_execution(action.idempotency_key, outcome.model_dump(mode="json"))
        action = self._apply_outcome(action, outcome, request.requested_by)
        if outcome.status is ActionStatus.COMPLETED:
            self._audit(
                action,
                AuditEventType.EXECUTION_COMPLETED,
                actor=request.requested_by,
                metadata={"verification": outcome.verification_status.value},
            )
            self._audit(
                action,
                AuditEventType.VERIFICATION_COMPLETED,
                actor="phase7.verifier",
                metadata={"status": outcome.verification_status.value},
            )
            self._resolve_incident(action, outcome)
        elif outcome.rollback_attempted and outcome.rollback_verified:
            self._audit(
                action,
                AuditEventType.EXECUTION_FAILED,
                actor="phase7.executor",
                metadata={"reason": outcome.verification_details},
            )
            self._audit(
                action,
                AuditEventType.ROLLBACK_STARTED,
                actor="phase7.rollback",
                metadata={"condition": "verification_failed"},
            )
            self._audit(
                action,
                AuditEventType.ROLLBACK_COMPLETED,
                actor="phase7.rollback",
                metadata={"verified": "true"},
            )
            self._audit(
                action,
                AuditEventType.VERIFICATION_COMPLETED,
                actor="phase7.verifier",
                metadata={"status": "FAILED_MAIN_ROLLBACK_VERIFIED"},
            )
            self._escalate_incident(action, "Verification failed; controlled rollback was verified")
        else:
            self._audit(
                action,
                AuditEventType.EXECUTION_FAILED,
                actor="phase7.executor",
                metadata={"reason": outcome.verification_details},
            )
            self._audit(
                action,
                AuditEventType.HUMAN_ESCALATION,
                actor="phase7.policy",
                metadata={"reason": outcome.verification_details},
            )
            self._escalate_incident(action, outcome.verification_details)
        return action

    def rollback(self, action_id: UUID, request: ActionDecisionRequest) -> Action:
        action = self.get(action_id)
        self._check_integrity(action)
        authorization = self.policy.authorize_actor(request.requested_by)
        if not authorization.allowed:
            raise ActionConflictError(authorization.reason)
        decision = self.rollback_policy.evaluate(action)
        if not decision.allowed:
            raise ActionConflictError(decision.reason)
        if action.scenario_id is None:
            raise ActionConflictError("Rollback requires a controlled simulator scenario")
        try:
            definition, parsed = self.registry.validate_parameters(
                action.action_name, action.normalized_parameters
            )
            if not definition.rollback_supported:
                raise ActionConflictError("Registered action does not support rollback")
            result, _ = self.registry.restore(
                action_name=action.action_name,
                scenario_id=action.scenario_id,
                parameters=parsed,
                before_state=action.execution_before_state,
                idempotency_key=f"rollback:{action.action_id}:explicit",
            )
            verified = self.registry.runtime.verify_phase7_rollback(
                scenario_id=action.scenario_id,
                action_name=action.action_name,
                parameters=action.normalized_parameters,
                before_state=action.execution_before_state,
            )
        except Exception as exc:
            action = self._update(
                action,
                status=ActionStatus.REQUIRES_HUMAN,
                rollback_verification_status=VerificationState.FAILED,
                failure_reason=f"Rollback failed: {str(exc)[:500]}",
                updated_at=utc_now(),
            )
            self._audit(
                action,
                AuditEventType.HUMAN_ESCALATION,
                actor="phase7.rollback",
                metadata={"reason": action.failure_reason or "unknown"},
            )
            return action
        action = self._update(
            action,
            status=ActionStatus.ROLLED_BACK if verified else ActionStatus.REQUIRES_HUMAN,
            rollback_verification_status=VerificationState.PASSED
            if verified
            else VerificationState.FAILED,
            execution_result={**action.execution_result, "explicit_rollback": result},
            updated_at=utc_now(),
        )
        self._audit(
            action, AuditEventType.ROLLBACK_STARTED, actor=request.requested_by, metadata={}
        )
        self._audit(
            action,
            AuditEventType.ROLLBACK_COMPLETED,
            actor="phase7.rollback",
            metadata={"verified": str(verified).lower()},
        )
        if not verified:
            self._audit(
                action,
                AuditEventType.HUMAN_ESCALATION,
                actor="phase7.rollback",
                metadata={"reason": "Rollback verification failed"},
            )
            self._escalate_incident(action, "Rollback verification failed")
        else:
            self._escalate_incident(action, "Action rolled back; incident remains for human review")
        return action

    def audit(self, action_id: UUID) -> list[AuditEvent]:
        self.get(action_id)
        self.audit_trail.require_integrity(action_id)
        return self.audit_trail.list(action_id)

    def verification(self, action_id: UUID) -> ActionVerificationRecord:
        action = self.get(action_id)
        if self.verification_service is not None:
            try:
                record = self.verification_service.get_for_action(action.action_id)
            except VerificationNotFoundError:
                record = None
            if record is not None:
                evidence = [
                    item.model_dump(mode="json")
                    for item in self.verification_service.evidence(record.verification_id)
                ]
                return self._verification_view(action, record, evidence)
        details = action.failure_reason or (
            "Verification passed after controlled execution."
            if action.verification_status is VerificationState.PASSED
            else "Verification has not completed."
        )
        return ActionVerificationRecord(
            action_id=action.action_id,
            incident_id=action.incident_id,
            verification_id=action.verification_id,
            status=action.verification_status,
            details=details,
            verification_strategy=action.verification_strategy,
            before_state=action.execution_before_state,
            after_state=action.execution_after_state,
            rollback_status=action.rollback_verification_status,
            timestamp=action.updated_at,
        )

    @staticmethod
    def _verification_view(
        action: Action,
        record: Verification,
        evidence: list[dict[str, Any]],
    ) -> ActionVerificationRecord:
        return ActionVerificationRecord(
            action_id=action.action_id,
            incident_id=action.incident_id,
            verification_id=record.verification_id,
            status=VerificationState(record.status.value),
            details=record.failure_reason
            or (
                "Verification passed after controlled execution."
                if record.status is VerificationStatus.PASSED
                else "Verification has not completed."
            ),
            verification_strategy=action.verification_strategy,
            strategy=[item.value for item in record.strategy],
            attempt=record.attempt,
            max_attempts=record.max_attempts,
            expected_state=record.expected_state,
            actual_state=record.actual_state,
            checks=[item.model_dump(mode="json") for item in record.checks],
            evidence_ids=record.evidence_ids,
            evidence=evidence,
            confidence=record.confidence,
            confidence_factors=record.confidence_factors,
            failure_reason=record.failure_reason,
            recovery_recommended=record.recovery_recommended,
            recovery_action_id=record.recovery_action_id,
            escalation=record.escalation.model_dump(mode="json")
            if record.escalation is not None
            else None,
            before_state=action.execution_before_state,
            after_state=record.actual_state or action.execution_after_state,
            rollback_status=action.rollback_verification_status,
            started_at=record.started_at,
            completed_at=record.completed_at,
            created_at=record.created_at,
            updated_at=record.updated_at,
            timestamp=record.updated_at,
        )

    def audit_integrity(self, action_id: UUID) -> bool:
        self.get(action_id)
        return self.audit_trail.verify(action_id)

    def _investigation(
        self,
        investigation_id: UUID | None,
        incident_id: UUID,
        *,
        tenant_id: str,
    ) -> InvestigationContext | None:
        if investigation_id is None:
            return None
        if self.investigation_service is None:
            raise ActionConflictError("Investigation service is not configured")
        try:
            context = self.investigation_service.get(investigation_id, tenant_id=tenant_id)
        except InvestigationNotFoundError as exc:
            raise ActionNotFoundError(str(exc)) from exc
        if context.incident_id != incident_id:
            raise ActionConflictError("Investigation is bound to a different incident")
        return context

    def _orchestration(self, incident_id: UUID, *, tenant_id: str) -> Any:
        if self.orchestrator is None:
            return None
        try:
            return self.orchestrator.context(incident_id, tenant_id=tenant_id)
        except OrchestrationNotFoundError:
            return None

    def _get_approval(self, action: Action) -> Any:
        return self.approvals.get(action.approval_id) if action.approval_id else None

    def _synchronize_expiry(self, action: Action) -> Action:
        if action.status is ActionStatus.PENDING_APPROVAL and action.approval_id is not None:
            approval = self.approvals.get(action.approval_id)
            if approval is not None and approval.status is ApprovalStatus.EXPIRED:
                action = self._update(
                    action,
                    status=ActionStatus.EXPIRED,
                    approval_status=ActionApprovalState.EXPIRED,
                    failure_reason="Approval expired before execution",
                    updated_at=utc_now(),
                )
                self._audit(
                    action, AuditEventType.ACTION_EXPIRED, actor="phase7.policy", metadata={}
                )
        return action

    def _expire_if_needed(self, action: Action, approval: Any) -> None:
        if approval.status is ApprovalStatus.EXPIRED:
            self._update(
                action,
                status=ActionStatus.EXPIRED,
                approval_status=ActionApprovalState.EXPIRED,
                failure_reason="Approval expired before execution",
                updated_at=utc_now(),
            )
            self._audit(action, AuditEventType.ACTION_EXPIRED, actor="phase7.policy", metadata={})

    def _check_integrity(self, action: Action) -> None:
        try:
            validate_action_fingerprint(action)
        except ActionValidationError as exc:
            raise ActionConflictError(str(exc)) from exc

    def _update(self, action: Action, **updates: Any) -> Action:
        updated = action.model_copy(update=updates, deep=True)
        with self._lock:
            self._actions[action.action_id] = updated
        return updated

    def _apply_outcome(self, action: Action, outcome: ActionExecutionOutcome, actor: str) -> Action:
        del actor
        evidence_ids = list(action.evidence_ids)
        evidence_ids.extend(
            str(item.get("id"))
            for item in outcome.evidence
            if isinstance(item, dict) and item.get("id")
        )
        self._persist_action_evidence(action, outcome)
        if self.verification_service is not None and outcome.verification_id is not None:
            try:
                verification = self.verification_service.get(outcome.verification_id)
                evidence_ids.extend(verification.evidence_ids)
                self._persist_verification_evidence(verification)
            except (VerificationNotFoundError, VerificationConflictError):
                # The strict resolution gate below still rejects a missing or
                # modified proof.  Do not manufacture a replacement record.
                pass
        return self._update(
            action,
            status=outcome.status,
            execution_attempts=outcome.execution_attempts,
            verification_id=outcome.verification_id,
            verification_attempts=outcome.verification_attempts,
            verification_confidence=outcome.verification_confidence,
            verification_status=outcome.verification_status,
            recovery_required=outcome.recovery_required,
            human_escalation=outcome.human_escalation,
            execution_before_state=outcome.before_state,
            execution_after_state=outcome.after_state,
            execution_result=outcome.result,
            evidence_ids=list(dict.fromkeys(evidence_ids))[:100],
            rollback_verification_status=(
                VerificationState.PASSED
                if outcome.rollback_verified
                else VerificationState.FAILED
                if outcome.rollback_attempted
                else None
            ),
            failure_reason=(
                None if outcome.status is ActionStatus.COMPLETED else outcome.verification_details
            ),
            updated_at=utc_now(),
        )

    def _persist_action_evidence(self, action: Action, outcome: ActionExecutionOutcome) -> None:
        """Copy bounded execution and before/after references into the incident ledger."""

        timestamp = utc_now()
        for raw in outcome.evidence:
            if not isinstance(raw, dict) or not raw.get("id"):
                continue
            raw_type = str(raw.get("type", "system_event"))
            try:
                evidence_type = EvidenceType(raw_type)
            except ValueError:
                evidence_type = EvidenceType.SYSTEM_EVENT
            raw_timestamp = raw.get("timestamp")
            if isinstance(raw_timestamp, str):
                try:
                    raw_timestamp = datetime.fromisoformat(raw_timestamp.replace("Z", "+00:00"))
                except ValueError:
                    raw_timestamp = timestamp
            if not isinstance(raw_timestamp, datetime):
                raw_timestamp = timestamp
            raw_reference = raw.get("raw_reference", {})
            if not isinstance(raw_reference, dict):
                raw_reference = {}
            relevance = max(0.0, min(1.0, float(raw.get("relevance", 1.0))))
            self.repository.add_evidence(
                Evidence(
                    tenant_id=action.tenant_id,
                    type=evidence_type,
                    evidence_id=str(raw["id"]),
                    incident_id=action.incident_id,
                    source=str(raw.get("source", "ShopFlow simulator")),
                    timestamp=raw_timestamp,
                    summary=str(raw.get("summary", "Controlled action evidence"))[:2_000],
                    raw_reference={str(key): str(value) for key, value in raw_reference.items()},
                    relevance=relevance,
                    confidence=1.0,
                    collected_by="phase8.action.execution_boundary",
                    collection_status="COLLECTED",
                    metadata={"simulated": "true", "action_id": str(action.action_id)},
                    simulated=True,
                    data={"action_id": str(action.action_id)},
                )
            )
        for phase, state in (("before", outcome.before_state), ("after", outcome.after_state)):
            if not state:
                continue
            self.repository.add_evidence(
                Evidence(
                    tenant_id=action.tenant_id,
                    type=EvidenceType.SYSTEM_EVENT,
                    evidence_id=f"action:{action.action_id}:{phase}_state",
                    incident_id=action.incident_id,
                    source="ShopFlow simulator / action execution",
                    timestamp=timestamp,
                    summary=(
                        f"Captured {phase}-state for {action.action_name} "
                        "(SIMULATED / CONTROLLED DEMONSTRATION)"
                    ),
                    raw_reference={
                        "action_id": str(action.action_id),
                        "phase": phase,
                    },
                    relevance=1.0,
                    confidence=1.0,
                    collected_by="phase8.action.execution_boundary",
                    collection_status="COLLECTED",
                    metadata={"simulated": "true", "phase": phase},
                    simulated=True,
                    data=state,
                )
            )

    def _persist_verification_evidence(self, verification: Verification) -> None:
        """Expose Phase 8 evidence through the existing incident evidence ledger."""

        if self.verification_service is None:
            return
        for item in self.verification_service.evidence(verification.verification_id):
            try:
                evidence_type = EvidenceType(item.source.rsplit("/", maxsplit=1)[-1])
            except ValueError:
                strategy = str(item.comparison).lower()
                evidence_type = (
                    EvidenceType.METRIC
                    if "less_than" in strategy or "count" in strategy
                    else EvidenceType.HEALTH_CHECK
                )
            timestamp = item.timestamp
            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=utc_now().tzinfo)
            self.repository.add_evidence(
                Evidence(
                    tenant_id=verification.tenant_id,
                    type=evidence_type,
                    evidence_id=item.evidence_id,
                    incident_id=item.incident_id,
                    source=item.source,
                    timestamp=timestamp,
                    summary=(
                        f"Phase 8 {item.comparison}: {item.result.value} "
                        "(SIMULATED / CONTROLLED DEMONSTRATION)"
                    ),
                    raw_reference={
                        "verification_id": str(item.verification_id),
                        "action_id": str(item.action_id),
                        "evidence_id": item.evidence_id,
                    },
                    relevance=1.0 if item.result.value == "PASSED" else 0.5,
                    confidence=verification.confidence,
                    collected_by=item.collector,
                    collection_status=item.result.value,
                    metadata={
                        "trust": item.trust.value,
                        "comparison": item.comparison,
                        "simulated": str(item.simulated).lower(),
                    },
                    simulated=item.simulated,
                    data={"expected": item.expected_value, "actual": item.actual_value},
                )
            )

    def _audit(
        self,
        action: Action,
        event_type: AuditEventType,
        *,
        actor: str,
        metadata: dict[str, Any],
    ) -> AuditEvent:
        return self.audit_trail.append(
            event_type=event_type,
            action_id=action.action_id,
            incident_id=action.incident_id,
            tenant_id=action.tenant_id,
            actor=actor,
            metadata=metadata,
        )

    def _resolve_incident(self, action: Action, outcome: ActionExecutionOutcome) -> None:
        verification_record: Verification | None = None
        if self.verification_service is not None:
            if outcome.verification_id is None:
                self._escalate_incident(
                    action, "Resolution gate rejected an action without verification"
                )
                return
            try:
                verification_record = self.verification_service.get(outcome.verification_id)
            except (VerificationNotFoundError, VerificationConflictError) as exc:
                self._escalate_incident(
                    action, f"Resolution gate could not load verification: {exc}"
                )
                return
            if not self.verification_service.can_resolve(action, verification_record):
                self._escalate_incident(
                    action,
                    "Resolution gate rejected execution success because verification "
                    "proof was insufficient",
                )
                return
            self.verification_service.mark_incident_resolved(verification_record)
        incident = self.repository.get_incident(action.incident_id)
        if incident is None:
            return
        resolved = incident.model_copy(
            update={
                "status": IncidentStatus.RESOLVED,
                "agent_state": AgentState.RESOLVED,
                "updated_at": utc_now(),
            }
        )
        self.repository.update_incident(resolved)
        self._audit(
            action,
            AuditEventType.INCIDENT_RESOLVED,
            actor="phase7.resolution",
            metadata={"simulated": "true"},
        )
        self.repository.add_activity(
            ActivityEvent(
                tenant_id=action.tenant_id,
                incident_id=action.incident_id,
                event_type="action.incident.resolved",
                message="Incident resolved only after controlled action verification succeeded.",
                metadata={"action_id": str(action.action_id), "simulated": "true"},
            )
        )
        self.repository.add_report(
            IncidentReport(
                tenant_id=action.tenant_id,
                incident_id=action.incident_id,
                summary="Controlled action completed and verification passed.",
                root_cause=action.planning_summary,
                impact=action.expected_impact,
                timeline=[event.model_dump(mode="json") for event in self.audit(action.action_id)],
                actions=[action.model_dump(mode="json")],
                verification=[
                    verification_record.model_dump(mode="json")
                    if verification_record is not None
                    else {
                        "status": outcome.verification_status.value,
                        "details": outcome.verification_details,
                    }
                ],
                final_status=IncidentStatus.RESOLVED,
            )
        )

    def _escalate_incident(self, action: Action, message: str) -> None:
        incident = self.repository.get_incident(action.incident_id)
        if incident is None or incident.status is IncidentStatus.CLOSED:
            return
        updated = incident.model_copy(
            update={
                "status": IncidentStatus.REQUIRES_HUMAN,
                "agent_state": AgentState.REQUIRES_HUMAN,
                "updated_at": utc_now(),
            }
        )
        self.repository.update_incident(updated)
        self.repository.add_activity(
            ActivityEvent(
                tenant_id=action.tenant_id,
                incident_id=action.incident_id,
                event_type="action.human.required",
                message=message,
                metadata={"action_id": str(action.action_id)},
            )
        )


__all__ = ["ActionConflictError", "ActionNotFoundError", "ActionService"]
