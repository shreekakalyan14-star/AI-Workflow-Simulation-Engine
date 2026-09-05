"""
Simulation Task Workflow State Machine - centralized lifecycle validation.

Required states:
- ASSIGNED
- STARTED
- IN_PROGRESS
- SUBMITTED
- UNDER_EVALUATION
- COMPLETED
- REWORK_REQUIRED

Valid transitions:
ASSIGNED -> STARTED
STARTED -> IN_PROGRESS
IN_PROGRESS -> SUBMITTED
SUBMITTED -> UNDER_EVALUATION
UNDER_EVALUATION -> COMPLETED
UNDER_EVALUATION -> REWORK_REQUIRED
REWORK_REQUIRED -> IN_PROGRESS
"""
from enum import Enum


class SimulationTaskState(str, Enum):
    """Simulation task states - separate from project TaskStatus."""
    ASSIGNED = "assigned"
    STARTED = "started"
    IN_PROGRESS = "in_progress"
    SUBMITTED = "submitted"
    UNDER_EVALUATION = "under_evaluation"
    COMPLETED = "completed"
    REWORK_REQUIRED = "rework_required"


class InvalidSimulationTaskTransitionError(Exception):
    """Raised when a simulation task state transition is not allowed."""
    pass


# Valid transitions: from_state -> list of allowed to_state
VALID_SIMULATION_TASK_TRANSITIONS: dict[SimulationTaskState, list[SimulationTaskState]] = {
    SimulationTaskState.ASSIGNED: [SimulationTaskState.STARTED],
    SimulationTaskState.STARTED: [SimulationTaskState.IN_PROGRESS],
    SimulationTaskState.IN_PROGRESS: [SimulationTaskState.SUBMITTED],
    SimulationTaskState.SUBMITTED: [SimulationTaskState.UNDER_EVALUATION],
    SimulationTaskState.UNDER_EVALUATION: [
        SimulationTaskState.COMPLETED,
        SimulationTaskState.REWORK_REQUIRED
    ],
    SimulationTaskState.REWORK_REQUIRED: [SimulationTaskState.IN_PROGRESS],
    SimulationTaskState.COMPLETED: [],  # Terminal state
}


def validate_simulation_task_transition(
    from_state: SimulationTaskState,
    to_state: SimulationTaskState
) -> None:
    """Validate that the simulation task transition is allowed by the state machine."""
    if from_state == to_state:
        return  # No-op transition is allowed

    allowed = VALID_SIMULATION_TASK_TRANSITIONS.get(from_state, [])
    if to_state not in allowed:
        allowed_str = ", ".join(s.value for s in allowed) if allowed else "none"
        raise InvalidSimulationTaskTransitionError(
            f"Invalid simulation task transition from '{from_state.value}' to '{to_state.value}'. "
            f"Allowed: {allowed_str}"
        )


def can_start_simulation_task(current_state: SimulationTaskState) -> bool:
    """Check if simulation task can be started (moved to STARTED)."""
    return current_state == SimulationTaskState.ASSIGNED


def can_submit_simulation_task(current_state: SimulationTaskState) -> bool:
    """Check if simulation task can be submitted for evaluation."""
    return current_state == SimulationTaskState.IN_PROGRESS


def is_terminal_simulation_task_state(state: SimulationTaskState) -> bool:
    """Check if state is terminal (no further transitions)."""
    return state == SimulationTaskState.COMPLETED


def get_simulation_task_transition_action(
    from_state: SimulationTaskState,
    to_state: SimulationTaskState
) -> str:
    """Get a human-readable action name for the transition."""
    actions = {
        (SimulationTaskState.ASSIGNED, SimulationTaskState.STARTED): "task_started",
        (SimulationTaskState.STARTED, SimulationTaskState.IN_PROGRESS): "task_in_progress",
        (SimulationTaskState.IN_PROGRESS, SimulationTaskState.SUBMITTED): "task_submitted",
        (SimulationTaskState.SUBMITTED, SimulationTaskState.UNDER_EVALUATION): "task_entered_evaluation",
        (SimulationTaskState.UNDER_EVALUATION, SimulationTaskState.COMPLETED): "task_completed",
        (SimulationTaskState.UNDER_EVALUATION, SimulationTaskState.REWORK_REQUIRED): "task_rework_required",
        (SimulationTaskState.REWORK_REQUIRED, SimulationTaskState.IN_PROGRESS): "task_rework_started",
    }
    return actions.get(
        (from_state, to_state),
        f"simulation_task_status_changed_{from_state.value}_to_{to_state.value}"
    )


# Mapping from simulation task state to existing project TaskStatus
SIMULATION_TO_PROJECT_STATUS_MAP = {
    SimulationTaskState.ASSIGNED: "todo",  # Maps to TaskStatus.TODO
    SimulationTaskState.STARTED: "in_progress",  # Maps to TaskStatus.IN_PROGRESS
    SimulationTaskState.IN_PROGRESS: "in_progress",  # Maps to TaskStatus.IN_PROGRESS
    SimulationTaskState.SUBMITTED: "submitted",  # Maps to TaskStatus.SUBMITTED
    SimulationTaskState.UNDER_EVALUATION: "under_review",  # Maps to TaskStatus.UNDER_REVIEW
    SimulationTaskState.COMPLETED: "completed",  # Maps to TaskStatus.COMPLETED
    SimulationTaskState.REWORK_REQUIRED: "changes_requested",  # Maps to TaskStatus.CHANGES_REQUESTED
}


def get_project_status_for_simulation_state(
    simulation_state: SimulationTaskState
) -> str:
    """Get the corresponding project TaskStatus for a simulation task state."""
    return SIMULATION_TO_PROJECT_STATUS_MAP.get(simulation_state, "todo")