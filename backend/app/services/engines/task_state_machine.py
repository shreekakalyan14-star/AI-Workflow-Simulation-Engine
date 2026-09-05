"""
Task State Machine - strict lifecycle validation.
"""
from app.models.enums import TaskStatus


class InvalidTransitionError(Exception):
    """Raised when a task status transition is not allowed."""
    pass


# Valid transitions: from_status -> list of allowed to_status
VALID_TRANSITIONS: dict[TaskStatus, list[TaskStatus]] = {
    TaskStatus.BACKLOG: [TaskStatus.TODO, TaskStatus.IN_PROGRESS],
    TaskStatus.TODO: [TaskStatus.IN_PROGRESS, TaskStatus.BACKLOG],
    TaskStatus.IN_PROGRESS: [TaskStatus.SUBMITTED, TaskStatus.TODO, TaskStatus.BLOCKED],
    TaskStatus.SUBMITTED: [TaskStatus.UNDER_REVIEW, TaskStatus.IN_PROGRESS],
    TaskStatus.UNDER_REVIEW: [TaskStatus.MANAGER_APPROVAL, TaskStatus.CHANGES_REQUESTED],
    TaskStatus.MANAGER_APPROVAL: [TaskStatus.COMPLETED],
    TaskStatus.CHANGES_REQUESTED: [TaskStatus.IN_PROGRESS],
    TaskStatus.BLOCKED: [TaskStatus.IN_PROGRESS, TaskStatus.TODO, TaskStatus.BACKLOG],
    TaskStatus.COMPLETED: [],  # Terminal state
}


def validate_transition(from_status: TaskStatus, to_status: TaskStatus) -> None:
    """Validate that the transition is allowed by the state machine."""
    if from_status == to_status:
        return  # No-op transition is allowed

    allowed = VALID_TRANSITIONS.get(from_status, [])
    if to_status not in allowed:
        allowed_str = ", ".join(s.value for s in allowed) if allowed else "none"
        raise InvalidTransitionError(
            f"Invalid transition from '{from_status.value}' to '{to_status.value}'. "
            f"Allowed: {allowed_str}"
        )


def can_start_task(current_status: TaskStatus) -> bool:
    """Check if task can be started (moved to IN_PROGRESS)."""
    return current_status in (TaskStatus.TODO, TaskStatus.BACKLOG)


def can_submit_task(current_status: TaskStatus) -> bool:
    """Check if task can be submitted for review."""
    return current_status == TaskStatus.IN_PROGRESS


def is_terminal_status(status: TaskStatus) -> bool:
    """Check if status is terminal (no further transitions)."""
    return status == TaskStatus.COMPLETED


def get_transition_action(from_status: TaskStatus, to_status: TaskStatus) -> str:
    """Get a human-readable action name for the transition."""
    actions = {
        (TaskStatus.BACKLOG, TaskStatus.TODO): "task_moved_to_todo",
        (TaskStatus.BACKLOG, TaskStatus.IN_PROGRESS): "task_started_from_backlog",
        (TaskStatus.TODO, TaskStatus.IN_PROGRESS): "task_started",
        (TaskStatus.TODO, TaskStatus.BACKLOG): "task_moved_to_backlog",
        (TaskStatus.IN_PROGRESS, TaskStatus.SUBMITTED): "task_submitted",
        (TaskStatus.IN_PROGRESS, TaskStatus.TODO): "task_paused",
        (TaskStatus.IN_PROGRESS, TaskStatus.BLOCKED): "task_blocked",
        (TaskStatus.SUBMITTED, TaskStatus.UNDER_REVIEW): "task_entered_review",
        (TaskStatus.SUBMITTED, TaskStatus.IN_PROGRESS): "task_unsubmitted",
        (TaskStatus.UNDER_REVIEW, TaskStatus.MANAGER_APPROVAL): "task_approved",
        (TaskStatus.UNDER_REVIEW, TaskStatus.CHANGES_REQUESTED): "task_changes_requested",
        (TaskStatus.MANAGER_APPROVAL, TaskStatus.COMPLETED): "task_completed",
        (TaskStatus.CHANGES_REQUESTED, TaskStatus.IN_PROGRESS): "task_rework_started",
        (TaskStatus.BLOCKED, TaskStatus.IN_PROGRESS): "task_unblocked",
        (TaskStatus.BLOCKED, TaskStatus.TODO): "task_unblocked_to_todo",
        (TaskStatus.BLOCKED, TaskStatus.BACKLOG): "task_unblocked_to_backlog",
    }
    return actions.get((from_status, to_status), f"task_status_changed_{from_status.value}_to_{to_status.value}")