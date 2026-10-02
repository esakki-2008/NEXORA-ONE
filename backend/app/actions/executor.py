"""Bounded action executor with the Phase 8 automatic verification hook."""

from __future__ import annotations

import asyncio
from typing import Any

from backend.app.actions.idempotency import ActionIdempotencyStore
from backend.app.actions.models import (
    Action,
    ActionExecutionOutcome,
    ActionStatus,
    VerificationState,
)
from backend.app.actions.registry import ActionRegistry
from backend.app.models.enums import VerificationStatus as LegacyVerificationStatus
from backend.app.verification.contracts import VerificationRequest, VerificationResult
from backend.app.verification.models import VerificationStatus
from backend.app.verification.service import VerificationService


class ActionExecutionError(RuntimeError):
    """Raised when a registered action cannot safely execute."""


class ActionVerificationRunner:
    """Backward-compatible adapter for the original Phase 7 verification port."""

    def __init__(self, registry: ActionRegistry) -> None:
        self.registry = registry

    async def verify(self, request: VerificationRequest) -> VerificationResult:
        expected = request.expected_state
        action_name = str(expected.get("action_name", ""))
        parameters = expected.get("parameters", {})
        target = expected.get("verification_target", {})
        result = self.registry.runtime.verify_phase7_action(
            scenario_id=str(expected["scenario_id"]),
            action_name=action_name,
            parameters=dict(parameters),
            verification_target=dict(target),
        )
        passed = bool(result.get("verified"))
        return VerificationResult(
            incident_id=request.incident_id,
            check=request.check,
            before_state={},
            after_state=result.get("checks", {}),
            status=LegacyVerificationStatus.PASSED if passed else LegacyVerificationStatus.FAILED,
            details=(
                "Registered simulator verification passed."
                if passed
                else "Registered simulator verification did not prove the expected state."
            ),
        )


class ActionExecutor:
    """Execute only registry handlers with bounded attempts and verification."""

    def __init__(
        self,
        registry: ActionRegistry,
        idempotency: ActionIdempotencyStore,
        *,
        verification_runner: ActionVerificationRunner | None = None,
        verification_service: VerificationService | None = None,
        timeout_seconds: float = 5.0,
        max_attempts: int = 2,
    ) -> None:
        if timeout_seconds <= 0 or timeout_seconds > 60:
            raise ValueError("Action timeout must be bounded between 0 and 60 seconds")
        if max_attempts < 1 or max_attempts > 2:
            raise ValueError("Action attempts must be bounded between 1 and 2")
        self.registry = registry
        self.idempotency = idempotency
        self.verification_service = verification_service
        self.verification_runner = verification_runner or ActionVerificationRunner(registry)
        self.timeout_seconds = timeout_seconds
        self.max_attempts = max_attempts

    async def execute(self, action: Action) -> ActionExecutionOutcome:
        if action.scenario_id is None:
            raise ActionExecutionError("Controlled actions require an explicit ShopFlow scenario")
        try:
            definition, parsed = self.registry.validate_parameters(
                action.action_name, action.normalized_parameters
            )
        except ValueError as exc:
            raise ActionExecutionError(str(exc)) from exc
        if definition.risk_level is not action.risk_level:
            raise ActionExecutionError("Registered risk does not match the action record")
        attempts = action.execution_attempts
        last_error = "Registered action failed safely"
        for _ in range(self.max_attempts):
            attempts += 1
            try:
                result, execution_evidence = await asyncio.wait_for(
                    self.registry.execute(
                        action.action_name,
                        scenario_id=action.scenario_id,
                        parameters=parsed,
                        idempotency_key=action.idempotency_key,
                    ),
                    timeout=self.timeout_seconds,
                )
            except TimeoutError:
                last_error = "Registered action timed out"
                continue
            except Exception as exc:
                last_error = str(exc)[:500] or "Registered action failed safely"
                continue

            before_state = dict(result.get("before_state", {}))
            after_state = dict(result.get("after_state", {}))
            target = dict(result.get("verification_target", {}))
            if self.verification_service is not None:
                try:
                    phase8_verification = await self.verification_service.run_for_action(
                        action,
                        execution_result=result,
                        attempts=1,
                    )
                except Exception as exc:
                    outcome = ActionExecutionOutcome(
                        action_id=action.action_id,
                        status=ActionStatus.REQUIRES_HUMAN,
                        execution_attempts=attempts,
                        result=result,
                        before_state=before_state,
                        after_state=after_state,
                        evidence=list(execution_evidence),
                        verification_status=VerificationState.REQUIRES_HUMAN,
                        verification_details=(
                            f"Verification could not establish a reliable state: {str(exc)[:500]}"
                        ),
                        recovery_required=True,
                        human_escalation=True,
                    )
                    self.idempotency.save_execution(
                        action.idempotency_key, outcome.model_dump(mode="json")
                    )
                    return outcome
                if phase8_verification.status is VerificationStatus.PASSED:
                    outcome = ActionExecutionOutcome(
                        action_id=action.action_id,
                        status=ActionStatus.COMPLETED,
                        execution_attempts=attempts,
                        result=result,
                        before_state=before_state,
                        after_state=after_state,
                        evidence=list(execution_evidence),
                        verification_status=VerificationState.PASSED,
                        verification_details="All required verification checks passed.",
                        verification_id=phase8_verification.verification_id,
                        verification_attempts=phase8_verification.attempt,
                        verification_confidence=phase8_verification.confidence,
                    )
                    self.idempotency.save_execution(
                        action.idempotency_key, outcome.model_dump(mode="json")
                    )
                    return outcome
                rolled_back = self._rollback_after_verification_failure(
                    action,
                    parsed,
                    before_state,
                    attempts,
                    result,
                    phase8_verification.failure_reason or "Verification failed.",
                    evidence=list(execution_evidence),
                )
                outcome = rolled_back.model_copy(
                    update={
                        "verification_id": phase8_verification.verification_id,
                        "verification_attempts": phase8_verification.attempt,
                        "verification_confidence": phase8_verification.confidence,
                        "verification_status": self._verification_state(phase8_verification.status),
                        "recovery_required": phase8_verification.recovery_recommended,
                        "human_escalation": phase8_verification.status
                        is VerificationStatus.REQUIRES_HUMAN,
                    }
                )
                self.idempotency.save_execution(
                    action.idempotency_key, outcome.model_dump(mode="json")
                )
                return outcome

            # Legacy fallback is retained for direct Phase 7 callers that do
            # not inject the Phase 8 service.  The application factory always
            # supplies the dedicated verification service.
            verification = await self.verification_runner.verify(
                VerificationRequest(
                    incident_id=action.incident_id,
                    check=action.verification_strategy,
                    expected_state={
                        "scenario_id": action.scenario_id,
                        "action_name": action.action_name,
                        "parameters": action.normalized_parameters,
                        "verification_target": target,
                    },
                )
            )
            if verification.status is LegacyVerificationStatus.PASSED:
                outcome = ActionExecutionOutcome(
                    action_id=action.action_id,
                    status=ActionStatus.COMPLETED,
                    execution_attempts=attempts,
                    result=result,
                    before_state=before_state,
                    after_state=after_state,
                    evidence=list(execution_evidence),
                    verification_status=VerificationState.PASSED,
                    verification_details=verification.details,
                )
                self.idempotency.save_execution(
                    action.idempotency_key, outcome.model_dump(mode="json")
                )
                return outcome
            rollback = self._rollback_after_verification_failure(
                action,
                parsed,
                before_state,
                attempts,
                result,
                verification.details,
                evidence=list(execution_evidence),
            )
            self.idempotency.save_execution(
                action.idempotency_key, rollback.model_dump(mode="json")
            )
            return rollback

        outcome = ActionExecutionOutcome(
            action_id=action.action_id,
            status=ActionStatus.REQUIRES_HUMAN,
            execution_attempts=attempts,
            result={"reason": last_error},
            verification_status=VerificationState.REQUIRES_HUMAN,
            verification_details="Execution did not complete within bounded retry limits.",
            recovery_required=True,
            human_escalation=True,
        )
        self.idempotency.save_execution(action.idempotency_key, outcome.model_dump(mode="json"))
        return outcome

    @staticmethod
    def _verification_state(status: VerificationStatus) -> VerificationState:
        mapping = {
            VerificationStatus.PENDING: VerificationState.PENDING,
            VerificationStatus.RUNNING: VerificationState.RUNNING,
            VerificationStatus.PASSED: VerificationState.PASSED,
            VerificationStatus.FAILED: VerificationState.FAILED,
            VerificationStatus.INCONCLUSIVE: VerificationState.INCONCLUSIVE,
            VerificationStatus.RETRYING: VerificationState.RETRYING,
            VerificationStatus.RECOVERY_REQUIRED: VerificationState.RECOVERY_REQUIRED,
            VerificationStatus.REQUIRES_HUMAN: VerificationState.REQUIRES_HUMAN,
            VerificationStatus.CANCELLED: VerificationState.CANCELLED,
        }
        return mapping[status]

    def _rollback_after_verification_failure(
        self,
        action: Action,
        parsed: Any,
        before_state: dict[str, Any],
        attempts: int,
        result: dict[str, Any],
        details: str,
        *,
        evidence: list[dict[str, Any]] | None = None,
    ) -> ActionExecutionOutcome:
        if not action.rollback_supported:
            return ActionExecutionOutcome(
                action_id=action.action_id,
                status=ActionStatus.REQUIRES_HUMAN,
                execution_attempts=attempts,
                result=result,
                before_state=before_state,
                after_state=dict(result.get("after_state", {})),
                evidence=list(evidence or []),
                verification_status=VerificationState.FAILED,
                verification_details=details,
                rollback_attempted=False,
                recovery_required=True,
                human_escalation=True,
            )
        try:
            rollback_result, _ = self.registry.restore(
                action_name=action.action_name,
                scenario_id=action.scenario_id or "",
                parameters=parsed,
                before_state=before_state,
                idempotency_key=f"rollback:{action.action_id}",
            )
            rollback_verified = self.registry.runtime.verify_phase7_rollback(
                scenario_id=action.scenario_id or "",
                action_name=action.action_name,
                parameters=action.normalized_parameters,
                before_state=before_state,
            )
            return ActionExecutionOutcome(
                action_id=action.action_id,
                status=ActionStatus.ROLLED_BACK
                if rollback_verified
                else ActionStatus.REQUIRES_HUMAN,
                execution_attempts=attempts,
                result={**result, "rollback": rollback_result},
                before_state=before_state,
                after_state=dict(result.get("after_state", {})),
                evidence=list(evidence or []),
                verification_status=VerificationState.FAILED,
                verification_details=(
                    f"{details} Rollback was verified."
                    if rollback_verified
                    else f"{details} Rollback could not be verified."
                ),
                rollback_attempted=True,
                rollback_verified=rollback_verified,
                recovery_required=True,
                human_escalation=not rollback_verified,
            )
        except Exception as exc:
            return ActionExecutionOutcome(
                action_id=action.action_id,
                status=ActionStatus.REQUIRES_HUMAN,
                execution_attempts=attempts,
                result={**result, "rollback_error": str(exc)[:500]},
                before_state=before_state,
                after_state=dict(result.get("after_state", {})),
                evidence=list(evidence or []),
                verification_status=VerificationState.FAILED,
                verification_details=f"{details} Rollback failed and requires human review.",
                rollback_attempted=True,
                rollback_verified=False,
                recovery_required=True,
                human_escalation=True,
            )


__all__ = ["ActionExecutionError", "ActionExecutor", "ActionVerificationRunner"]
