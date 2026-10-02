"""Bounded executor and verification bridge for registered simulator handlers."""

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
from backend.app.models.enums import VerificationStatus
from backend.app.verification.contracts import (
    VerificationRequest,
    VerificationResult,
)


class ActionExecutionError(RuntimeError):
    """Raised when a registered action cannot safely execute."""


class ActionVerificationRunner:
    """Use the existing verification request/result contract for simulator checks."""

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
            status=VerificationStatus.PASSED if passed else VerificationStatus.FAILED,
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
        timeout_seconds: float = 5.0,
        max_attempts: int = 2,
    ) -> None:
        if timeout_seconds <= 0 or timeout_seconds > 60:
            raise ValueError("Action timeout must be bounded between 0 and 60 seconds")
        if max_attempts < 1 or max_attempts > 2:
            raise ValueError("Action attempts must be bounded between 1 and 2")
        self.registry = registry
        self.idempotency = idempotency
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
                result, _evidence = await asyncio.wait_for(
                    self.registry.execute(
                        action.action_name,
                        scenario_id=action.scenario_id,
                        parameters=parsed,
                        idempotency_key=action.idempotency_key,
                    ),
                    timeout=self.timeout_seconds,
                )
                before_state = dict(result.get("before_state", {}))
                after_state = dict(result.get("after_state", {}))
                target = dict(result.get("verification_target", {}))
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
                if verification.status is VerificationStatus.PASSED:
                    outcome = ActionExecutionOutcome(
                        action_id=action.action_id,
                        status=ActionStatus.COMPLETED,
                        execution_attempts=attempts,
                        result=result,
                        before_state=before_state,
                        after_state=after_state,
                        verification_status=VerificationState.PASSED,
                        verification_details=verification.details,
                    )
                    self.idempotency.save_execution(
                        action.idempotency_key, outcome.model_dump(mode="json")
                    )
                    return outcome
                rollback = self._rollback_after_verification_failure(
                    action, parsed, before_state, attempts, result, verification.details
                )
                self.idempotency.save_execution(
                    action.idempotency_key, rollback.model_dump(mode="json")
                )
                return rollback
            except TimeoutError:
                last_error = "Registered action timed out"
            except Exception as exc:
                last_error = str(exc)[:500] or "Registered action failed safely"
        outcome = ActionExecutionOutcome(
            action_id=action.action_id,
            status=ActionStatus.REQUIRES_HUMAN,
            execution_attempts=attempts,
            result={"reason": last_error},
            verification_status=VerificationState.REQUIRES_HUMAN,
            verification_details="Execution did not complete within bounded retry limits.",
        )
        self.idempotency.save_execution(action.idempotency_key, outcome.model_dump(mode="json"))
        return outcome

    def _rollback_after_verification_failure(
        self,
        action: Action,
        parsed: Any,
        before_state: dict[str, Any],
        attempts: int,
        result: dict[str, Any],
        details: str,
    ) -> ActionExecutionOutcome:
        if not action.rollback_supported:
            return ActionExecutionOutcome(
                action_id=action.action_id,
                status=ActionStatus.REQUIRES_HUMAN,
                execution_attempts=attempts,
                result=result,
                before_state=before_state,
                after_state=dict(result.get("after_state", {})),
                verification_status=VerificationState.FAILED,
                verification_details=details,
                rollback_attempted=False,
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
                verification_status=VerificationState.FAILED,
                verification_details=(
                    f"{details} Rollback was verified."
                    if rollback_verified
                    else f"{details} Rollback could not be verified."
                ),
                rollback_attempted=True,
                rollback_verified=rollback_verified,
            )
        except Exception as exc:
            return ActionExecutionOutcome(
                action_id=action.action_id,
                status=ActionStatus.REQUIRES_HUMAN,
                execution_attempts=attempts,
                result={**result, "rollback_error": str(exc)[:500]},
                before_state=before_state,
                after_state=dict(result.get("after_state", {})),
                verification_status=VerificationState.FAILED,
                verification_details=f"{details} Rollback failed and requires human review.",
                rollback_attempted=True,
                rollback_verified=False,
            )


__all__ = ["ActionExecutionError", "ActionExecutor", "ActionVerificationRunner"]
