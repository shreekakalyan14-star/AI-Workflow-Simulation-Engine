"""
FEATURE 3: Sprint Engine.

Splits a Project into 4 sprints, assigns dates and goals, and persists them.
Task generation has been offloaded to the Task Engine.
"""
from datetime import datetime, timedelta, timezone
from typing import List

from sqlalchemy.orm import Session

from app.models.enums import SprintStatus
from app.models.project import Project
from app.models.sprint import Sprint

_SPRINT_NAMES = ["Foundation & Setup", "Core Feature Build", "Integration & Hardening", "Polish & Launch"]


def _chunk_modules(modules: List[str], n: int) -> List[List[str]]:
    """Distribute modules as evenly as possible across n sprints."""
    chunks: List[List[str]] = [[] for _ in range(n)]
    for i, module in enumerate(modules):
        chunks[i % n].append(module)
    return chunks


def generate_sprints_and_tasks(db: Session, project: Project) -> List[Sprint]:
    """
    Preserved API name for backward compatibility. 
    Currently only responsible for generating and returning Sprints.
    Task generation belongs to the Task Engine.
    """
    n_sprints = 4
    module_chunks = _chunk_modules(project.modules, n_sprints)

    sprint_duration = timedelta(weeks=max(project.duration_weeks // n_sprints, 1))
    cursor_start = project.start_date or datetime.now(timezone.utc)

    sprints: List[Sprint] = []

    for i in range(n_sprints):
        sprint_start = cursor_start
        sprint_end = sprint_start + sprint_duration

        sprint = Sprint(
            project_id=project.id,
            sprint_number=i + 1,
            name=f"Sprint {i + 1}: {_SPRINT_NAMES[i]}",
            goal=(
                f"Deliver {', '.join(module_chunks[i]) or 'planning & housekeeping tasks'} "
                f"for {project.title}."
            ),
            status=SprintStatus.ACTIVE if i == 0 else SprintStatus.PLANNED,
            start_date=sprint_start,
            end_date=sprint_end,
        )
        sprints.append(sprint)
        db.add(sprint)
        
        cursor_start = sprint_end

    db.flush()

    return sprints
