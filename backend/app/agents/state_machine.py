"""Reusable state definition for the future agent orchestrator."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Final

from backend.app.models.enums import AgentState


class InvalidTransitionError(ValueError):
    """Raised when an agent attempts a transition outside the state graph."""


@dataclass(frozen=True, slots=True)
class StateTransition:
    from_state: AgentState
    to_state: AgentState
    occurred_at: datetime
    reason: str | None = None


ALLOWED_TRANSITIONS: Final[dict[AgentState, frozenset[AgentState]]] = {
    AgentState.IDLE: frozenset({AgentState.INCIDENT_RECEIVED, AgentState.CANCELLED}),
    AgentState.INCIDENT_RECEIVED: frozenset(
        {AgentState.OBSERVING, AgentState.FAILED, AgentState.CANCELLED, AgentState.REQUIRES_HUMAN}
    ),
    AgentState.OBSERVING: frozenset(
        {
            AgentState.INVESTIGATING,
            AgentState.FAILED,
            AgentState.CANCELLED,
            AgentState.REQUIRES_HUMAN,
        }
    ),
    AgentState.INVESTIGATING: frozenset(
        {
            AgentState.HYPOTHESIS_GENERATED,
            AgentState.FAILED,
            AgentState.CANCELLED,
            AgentState.REQUIRES_HUMAN,
        }
    ),
    AgentState.HYPOTHESIS_GENERATED: frozenset(
        {AgentState.VALIDATING, AgentState.FAILED, AgentState.CANCELLED, AgentState.REQUIRES_HUMAN}
    ),
    AgentState.VALIDATING: frozenset(
        {
            AgentState.REMEDIATION_PROPOSED,
            AgentState.FAILED,
            AgentState.CANCELLED,
            AgentState.REQUIRES_HUMAN,
        }
    ),
    AgentState.REMEDIATION_PROPOSED: frozenset(
        {AgentState.WAITING_FOR_APPROVAL, AgentState.REQUIRES_HUMAN, AgentState.CANCELLED}
    ),
    AgentState.WAITING_FOR_APPROVAL: frozenset(
        {AgentState.EXECUTING, AgentState.REQUIRES_HUMAN, AgentState.CANCELLED}
    ),
    AgentState.EXECUTING: frozenset(
        {AgentState.VERIFYING, AgentState.FAILED, AgentState.REQUIRES_HUMAN}
    ),
    AgentState.VERIFYING: frozenset(
        {AgentState.RESOLVED, AgentState.FAILED, AgentState.REQUIRES_HUMAN}
    ),
    AgentState.RESOLVED: frozenset(),
    AgentState.FAILED: frozenset(),
    AgentState.CANCELLED: frozenset(),
    AgentState.REQUIRES_HUMAN: frozenset(),
}


class AgentStateMachine:
    """Small, deterministic state machine with an auditable transition history."""

    def __init__(self, initial_state: AgentState = AgentState.IDLE) -> None:
        self._state = initial_state
        self._history: list[StateTransition] = []

    @property
    def state(self) -> AgentState:
        return self._state

    @property
    def history(self) -> tuple[StateTransition, ...]:
        return tuple(self._history)

    def can_transition(self, target: AgentState) -> bool:
        return target in ALLOWED_TRANSITIONS[self._state]

    def transition(self, target: AgentState, reason: str | None = None) -> AgentState:
        if not self.can_transition(target):
            raise InvalidTransitionError(
                f"Cannot transition from {self._state.value} to {target.value}"
            )
        event = StateTransition(
            from_state=self._state,
            to_state=target,
            occurred_at=datetime.now(UTC),
            reason=reason,
        )
        self._history.append(event)
        self._state = target
        return self._state
