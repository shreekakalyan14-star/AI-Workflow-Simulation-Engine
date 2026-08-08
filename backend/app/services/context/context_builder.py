from __future__ import annotations

from typing import Any, Dict, List

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.company import Company
from app.models.project import Project
from app.models.project_state import ProjectState
from app.models.sprint import Sprint
from app.models.task import Task


def build_project_context(db: Session, project: Project) -> Dict[str, Any]:
    state = db.execute(select(ProjectState).where(ProjectState.project_id == project.id)).scalar_one_or_none()
    tasks = db.execute(
        select(Task).join(Sprint, Sprint.id == Task.sprint_id).where(Sprint.project_id == project.id)
    ).scalars().all()
    sprints = db.execute(select(Sprint).where(Sprint.project_id == project.id).order_by(Sprint.sprint_number)).scalars().all()
    company = db.get(Company, project.company_id)

    return {
        "project_id": str(project.id),
        "project_title": project.title,
        "company_name": company.name if company else "",
        "role": project.role,
        "technology_stack": list(project.technology_stack or []),
        "difficulty": project.difficulty.value if project.difficulty else None,
        "objectives": list(project.objectives or []),
        "modules": list(project.modules or []),
        "deliverables": list(project.deliverables or []),
        "status": project.status.value if project.status else None,
        "state": {
            "completed_tasks": state.completed_tasks if state else 0,
            "pending_tasks": state.pending_tasks if state else 0,
            "missed_deadlines": state.missed_deadlines if state else 0,
            "bug_count": state.bug_count if state else 0,
            "stress_level": state.stress_level if state else 0,
            "manager_satisfaction": state.manager_satisfaction if state else 0,
            "team_satisfaction": state.team_satisfaction if state else 0,
            "current_sprint_number": state.current_sprint_number if state else 1,
        },
        "sprints": [
            {
                "id": str(sprint.id),
                "name": sprint.name,
                "number": sprint.sprint_number,
                "goal": sprint.goal,
                "status": sprint.status.value if sprint.status else None,
            }
            for sprint in sprints
        ],
        "tasks": [
            {
                "id": str(task.id),
                "title": task.title,
                "status": task.status.value if task.status else None,
                "priority": task.priority.value if task.priority else None,
                "estimated_hours": task.estimated_hours,
                "deadline": task.deadline.isoformat() if task.deadline else None,
            }
            for task in tasks
        ],
    }
