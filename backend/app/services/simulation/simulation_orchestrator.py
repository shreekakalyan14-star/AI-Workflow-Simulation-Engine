from __future__ import annotations

from typing import Any, Dict, List

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.company import Company
from app.models.manager import Manager
from app.models.project import Project
from app.models.project_state import ProjectState
from app.models.sprint import Sprint
from app.models.task import Task
from app.models.team_member import TeamMember
from app.services.engines.sprint_engine import generate_sprints_and_tasks
from app.services.engines.task_engine import generate_tasks_for_project
from app.services.generators.company_generator import generate_company
from app.services.generators.meeting_generator import generate_meetings_for_sprints
from app.services.generators.project_generator import generate_project
from app.services.generators.team_generator import generate_team_members


async def orchestrate_internship_simulation(
    db: Session,
    student_id: str,
    role: str,
    technology_stack: List[str],
    difficulty: Any,
    company_type: Any,
    ai_service,
) -> Dict[str, Any]:
    company, manager = await generate_company(
        db=db,
        student_id=student_id,
        company_type=company_type,
        role=role,
        ai_service=ai_service,
    )
    project = generate_project(
        db=db,
        company_id=company.id,
        role=role,
        technology_stack=technology_stack,
        difficulty=difficulty,
    )
    sprints = generate_sprints_and_tasks(db=db, project=project)
    tasks = generate_tasks_for_project(
        db=db,
        project=project,
        role=role,
        technology_stack=technology_stack,
        difficulty=difficulty,
        student_id=student_id,
    )
    team_members = generate_team_members(db=db, company_id=company.id)
    generate_meetings_for_sprints(db=db, project_id=project.id, sprints=sprints, manager=manager, team_members=team_members)

    state = db.execute(select(ProjectState).where(ProjectState.project_id == project.id)).scalar_one_or_none()
    if state is None:
        state = ProjectState(project_id=project.id)
        db.add(state)
        db.flush()
    state.current_sprint_number = 1
    state.pending_tasks = len(tasks)
    db.add(state)
    db.flush()

    db.commit()
    return {
        "company_id": str(company.id),
        "project_id": str(project.id),
        "sprint_ids": [str(sprint.id) for sprint in sprints],
        "task_count": len(tasks),
    }
