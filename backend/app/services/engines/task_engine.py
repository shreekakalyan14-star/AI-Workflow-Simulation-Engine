"""
FEATURE 3: Task Engine.

Generates sprint-scoped tasks from a project's module backlog, assigns story
points (via estimated_hours), priorities, deadlines, and dependencies, then
persists everything with db.flush() (caller commits).
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Final, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import DifficultyLevel, SprintStatus, TaskPriority, TaskStatus
from app.models.project import Project
from app.models.sprint import Sprint
from app.models.task import Task, TaskDependency

_STORY_POINTS_BY_DIFFICULTY: Final[dict[DifficultyLevel, tuple[int, ...]]] = {
    DifficultyLevel.BEGINNER: (1, 2, 3),
    DifficultyLevel.INTERMEDIATE: (2, 3, 5),
    DifficultyLevel.ADVANCED: (3, 5, 8),
    DifficultyLevel.EXPERT: (5, 8, 13),
}

_TASKS_PER_MODULE: Final[dict[DifficultyLevel, tuple[int, int]]] = {
    DifficultyLevel.BEGINNER: (2, 3),
    DifficultyLevel.INTERMEDIATE: (2, 4),
    DifficultyLevel.ADVANCED: (3, 5),
    DifficultyLevel.EXPERT: (4, 6),
}

_ROLE_VERBS: Final[dict[str, tuple[str, ...]]] = {
    "frontend": ("Design UI for", "Implement components for", "Style", "Add responsiveness to", "Write E2E tests for"),
    "backend": ("Design schema for", "Implement API for", "Write unit tests for", "Integrate service for", "Optimize queries for"),
    "full stack": ("Implement end-to-end feature for", "Connect frontend to API for", "Write integration tests for", "Refactor module for"),
    "ai": ("Train model for", "Evaluate metrics for", "Build inference pipeline for", "Prepare dataset for"),
    "data": ("Design pipeline for", "Transform data for", "Build ETL for", "Validate data quality for"),
    "devops": ("Setup CI/CD for", "Containerize", "Configure monitoring for", "Provision infrastructure for"),
    "mobile": ("Build mobile screen for", "Integrate native API for", "Add offline support for", "Write UI tests for"),
    "cybersecurity": ("Audit security for", "Harden authentication for", "Scan vulnerabilities in", "Document threat model for"),
}

_DEFAULT_VERBS: Final[tuple[str, ...]] = (
    "Implement functionality for",
    "Write unit tests for",
    "Integrate",
    "Refactor",
    "Document",
)

_FALLBACK_MODULES: Final[tuple[str, ...]] = (
    "Foundation Setup",
    "Core Functionality",
    "Integration",
    "Deployment",
)


class TaskEngineError(Exception):
    """Raised when task generation fails."""


@dataclass(frozen=True, slots=True)
class _ModuleTaskPlan:
    sprint: Sprint
    module: str
    task_count: int


def generate_tasks_for_project(
    db: Session,
    project: Project,
    role: str,
    technology_stack: Sequence[str],
    difficulty: DifficultyLevel,
    student_id: str,
) -> list[Task]:
    """
    Read the project module backlog, generate tasks across sprints, and persist them.

    Story points are stored in ``Task.estimated_hours`` using Fibonacci-scale values.
    """
    if not role.strip():
        raise TaskEngineError("role must be a non-empty string")
    if not technology_stack:
        raise TaskEngineError("technology_stack must contain at least one item")
    if not student_id.strip():
        raise TaskEngineError("student_id must be a non-empty string")
    if project.id is None:
        raise TaskEngineError("project must be flushed before generating tasks")

    try:
        rng = random.Random(f"{project.id}-{student_id}-{role}-{difficulty.value}")
        backlog = _read_project_backlog(project)
        sprints = _resolve_sprints(db, project)
        plans = _build_module_plans(sprints, backlog, difficulty, rng)

        tasks: list[Task] = []
        for plan in plans:
            module_tasks = _create_module_tasks(
                db=db,
                plan=plan,
                role=role,
                technology_stack=technology_stack,
                difficulty=difficulty,
                rng=rng,
            )
            _assign_module_dependencies(db, module_tasks)
            tasks.extend(module_tasks)

        db.flush()
        return tasks
    except TaskEngineError:
        raise
    except Exception as exc:
        raise TaskEngineError(f"Failed to generate tasks for project '{project.id}': {exc}") from exc


def _read_project_backlog(project: Project) -> list[str]:
    modules = [module.strip() for module in project.modules if module.strip()]
    return modules or list(_FALLBACK_MODULES)


def _resolve_sprints(db: Session, project: Project) -> list[Sprint]:
    if project.sprints:
        return sorted(project.sprints, key=lambda sprint: sprint.sprint_number)

    sprints = list(
        db.scalars(
            select(Sprint)
            .where(Sprint.project_id == project.id)
            .order_by(Sprint.sprint_number)
        ).all()
    )
    if sprints:
        return sprints

    return _create_default_sprints(db, project)


def _create_default_sprints(db: Session, project: Project) -> list[Sprint]:
    start = project.start_date or datetime.now(timezone.utc)
    duration_weeks = project.duration_weeks or 4
    sprint_duration = timedelta(weeks=max(duration_weeks // 4, 1))
    cursor = start
    sprints: list[Sprint] = []

    for index in range(4):
        end = cursor + sprint_duration
        sprint = Sprint(
            project_id=project.id,
            sprint_number=index + 1,
            name=f"Sprint {index + 1}",
            goal=f"Deliver sprint {index + 1} objectives for {project.title}.",
            status=SprintStatus.ACTIVE if index == 0 else SprintStatus.PLANNED,
            start_date=cursor,
            end_date=end,
        )
        db.add(sprint)
        sprints.append(sprint)
        cursor = end

    db.flush()
    return sprints


def _build_module_plans(
    sprints: Sequence[Sprint],
    backlog: Sequence[str],
    difficulty: DifficultyLevel,
    rng: random.Random,
) -> list[_ModuleTaskPlan]:
    if not sprints:
        raise TaskEngineError("At least one sprint is required to generate tasks")

    count_min, count_max = _TASKS_PER_MODULE[difficulty]
    plans: list[_ModuleTaskPlan] = []

    for index, module in enumerate(backlog):
        sprint = sprints[index % len(sprints)]
        task_count = rng.randint(count_min, count_max)
        plans.append(_ModuleTaskPlan(sprint=sprint, module=module, task_count=task_count))

    return plans


def _verbs_for_role(role: str) -> tuple[str, ...]:
    role_lower = role.lower()
    for key, verbs in _ROLE_VERBS.items():
        if key in role_lower:
            return verbs
    return _DEFAULT_VERBS


def _create_module_tasks(
    db: Session,
    plan: _ModuleTaskPlan,
    role: str,
    technology_stack: Sequence[str],
    difficulty: DifficultyLevel,
    rng: random.Random,
) -> list[Task]:
    verbs = _verbs_for_role(role)
    stack_label = ", ".join(technology_stack)
    story_points = _STORY_POINTS_BY_DIFFICULTY[difficulty]
    tasks: list[Task] = []

    for index in range(plan.task_count):
        verb = rng.choice(verbs)
        task = Task(
            sprint_id=plan.sprint.id,
            title=f"{verb} {plan.module}",
            description=(
                f"Implement work for the '{plan.module}' module.\n"
                f"Role: {role}\n"
                f"Technology stack: {stack_label}\n"
                f"Difficulty: {difficulty.value}"
            ),
            acceptance_criteria=[
                f"Implementation for '{plan.module}' meets functional requirements.",
                "Automated tests are included and passing.",
                "Code follows project architecture and review standards.",
            ],
            priority=_assign_priority(index, plan.sprint.sprint_number, rng),
            status=TaskStatus.BACKLOG,
            estimated_hours=float(rng.choice(story_points)),
            deadline=_assign_deadline(plan.sprint, rng),
        )
        db.add(task)
        tasks.append(task)

    db.flush()
    return tasks


def _assign_priority(task_index: int, sprint_number: int, rng: random.Random) -> TaskPriority:
    if task_index == 0 and sprint_number <= 2:
        return TaskPriority.CRITICAL
    if task_index == 0:
        return TaskPriority.HIGH
    return rng.choices(
        population=[TaskPriority.CRITICAL, TaskPriority.HIGH, TaskPriority.MEDIUM, TaskPriority.LOW],
        weights=[0.05, 0.15, 0.65, 0.15],
        k=1,
    )[0]


def _assign_deadline(sprint: Sprint, rng: random.Random) -> datetime | None:
    if sprint.start_date is None or sprint.end_date is None:
        return None

    sprint_days = max((sprint.end_date - sprint.start_date).days, 1)
    offset_days = rng.randint(1, sprint_days)
    return sprint.start_date + timedelta(days=offset_days)


def _assign_module_dependencies(db: Session, module_tasks: Sequence[Task]) -> None:
    if len(module_tasks) < 2:
        return

    anchor = module_tasks[0]
    for dependent in module_tasks[1:]:
        db.add(
            TaskDependency(
                task_id=dependent.id,
                depends_on_task_id=anchor.id,
            )
        )
