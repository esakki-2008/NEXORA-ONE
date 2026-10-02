import pytest

from backend.app.agents.state_machine import AgentStateMachine, InvalidTransitionError
from backend.app.models.enums import AgentState


def test_happy_path_state_transitions_are_audited() -> None:
    machine = AgentStateMachine()
    for state in (
        AgentState.INCIDENT_RECEIVED,
        AgentState.OBSERVING,
        AgentState.INVESTIGATING,
        AgentState.HYPOTHESIS_GENERATED,
        AgentState.VALIDATING,
        AgentState.REMEDIATION_PROPOSED,
        AgentState.WAITING_FOR_APPROVAL,
        AgentState.EXECUTING,
        AgentState.VERIFYING,
        AgentState.RESOLVED,
    ):
        machine.transition(state, reason="test transition")

    assert machine.state is AgentState.RESOLVED
    assert len(machine.history) == 10
    assert machine.history[-1].from_state is AgentState.VERIFYING


def test_invalid_transition_is_rejected() -> None:
    machine = AgentStateMachine()

    with pytest.raises(InvalidTransitionError):
        machine.transition(AgentState.EXECUTING)


def test_human_handoff_is_terminal_until_a_future_policy_allows_resume() -> None:
    machine = AgentStateMachine(AgentState.INVESTIGATING)
    machine.transition(AgentState.REQUIRES_HUMAN, reason="confidence below threshold")

    assert machine.state is AgentState.REQUIRES_HUMAN
    assert not machine.can_transition(AgentState.EXECUTING)
