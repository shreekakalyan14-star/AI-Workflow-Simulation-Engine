"""
POST /api/generate

The single entry point described in the spec: receives
student_id, role, technology_stack, difficulty, company_type
and generates an entire internship simulation (company, manager,
project, 4 sprints, and all their tasks with dependencies) in one
atomic transaction.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import CurrentUser, get_current_user
from app.models.project_state import ProjectState
from app.schemas.generation import GenerationRequest, GenerationResponse
from app.services.ai.ai_service import AIService, get_ai_service
from app.services.generators.company_generator import generate_company
from app.services.generators.meeting_generator import generate_meetings_for_sprints
from app.services.generators.project_generator import generate_project
from app.services.engines.sprint_engine import generate_sprints_and_tasks
from app.services.engines.task_engine import generate_tasks_for_project
from app.services.generators.team_generator import generate_team_members

router = APIRouter(prefix="/api/generate", tags=["Generation"])


@router.post("", response_model=GenerationResponse, status_code=status.HTTP_201_CREATED)
async def generate_internship_simulation(
    payload: GenerationRequest,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
    ai_service: AIService = Depends(get_ai_service),
):
    if payload.student_id != user.student_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="student_id in request body must match the authenticated token subject",
        )

    try:
        company, manager = await generate_company(
            db=db,
            student_id=payload.student_id,
            company_type=payload.company_type,
            role=payload.role,
            ai_service=ai_service,
        )

        project = generate_project(
            db=db,
            company_id=company.id,
            role=payload.role,
            technology_stack=payload.technology_stack,
            difficulty=payload.difficulty,
        )

        sprints = generate_sprints_and_tasks(db=db, project=project)

        tasks = generate_tasks_for_project(
            db=db,
            project=project,
            role=payload.role,
            technology_stack=payload.technology_stack,
            difficulty=payload.difficulty,
            student_id=payload.student_id,
        )

        team_members = generate_team_members(db=db, company_id=company.id)
        generate_meetings_for_sprints(
            db=db, project_id=project.id, sprints=sprints, manager=manager, team_members=team_members
        )

        # Ensure a project state exists and reflects the initial sprint context.
        state = db.execute(select(ProjectState).where(ProjectState.project_id == project.id)).scalar_one_or_none()
        if state is None:
            state = ProjectState(project_id=project.id)
            db.add(state)
            db.flush()
        state.current_sprint_number = 1
        state.pending_tasks = len(tasks)
        db.add(state)
        db.flush()

        task_count = len(tasks)

        db.commit()
    except Exception:
        db.rollback()
        raise

    return GenerationResponse(
        company_id=company.id,
        project_id=project.id,
        sprint_ids=[s.id for s in sprints],
        task_count=task_count,
    )
