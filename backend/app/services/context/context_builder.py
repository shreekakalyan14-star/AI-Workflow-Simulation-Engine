from __future__ import annotations

from typing import Any, Dict, List

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.company import Company
from app.models.project import Project
from app.models.project_state import ProjectState
from app.models.sprint import Sprint
from app.models.submission import Submission, SubmissionVersion
from app.models.task import Task


def build_project_context(db: Session, project: Project) -> Dict[str, Any]:
    """Build project-level context (without task-specific info)."""
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
        "company_industry": company.industry if company else "",
        "company_type": company.company_type.value if company and company.company_type else "",
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
                "sprint_id": str(task.sprint_id),
            }
            for task in tasks
        ],
    }


def build_task_context(db: Session, task: Task) -> Dict[str, Any]:
    """Build task-specific context including sprint info and submission history."""
    sprint = db.get(Sprint, task.sprint_id)
    project = db.get(Project, sprint.project_id) if sprint else None
    company = db.get(Company, project.company_id) if project else None
    
    # Get submission history for this task
    submissions = db.execute(
        select(Submission).where(Submission.task_id == task.id)
    ).scalars().all()
    
    submission_history = []
    for submission in submissions:
        versions = db.execute(
            select(SubmissionVersion)
            .where(SubmissionVersion.submission_id == submission.id)
            .order_by(SubmissionVersion.version_number)
        ).scalars().all()
        
        for version in versions:
            # Get AI reviews for this version
            from app.models.submission import AIReview
            reviews = db.execute(
                select(AIReview).where(AIReview.version_id == version.id)
            ).scalars().all()
            
            review_feedback = []
            for review in reviews:
                review_feedback.append({
                    "result": review.result.value,
                    "severity": review.severity.value,
                    "summary": review.summary,
                    "strengths": review.strengths,
                    "issues": review.issues if hasattr(review, 'issues') else [],
                    "required_changes": review.required_changes if hasattr(review, 'required_changes') else [],
                    "score": review.score,
                    "created_at": review.created_at.isoformat(),
                })
            
            submission_history.append({
                "version_number": version.version_number,
                "status": version.status.value,
                "submitted_at": version.submitted_at.isoformat() if version.submitted_at else None,
                "files": version.files,
                "metadata": version.version_metadata,
                "reviews": review_feedback,
            })
    
    return {
        "task_id": str(task.id),
        "task_title": task.title,
        "task_description": task.description,
        "acceptance_criteria": list(task.acceptance_criteria or []),
        "task_priority": task.priority.value if task.priority else None,
        "task_deadline": task.deadline.isoformat() if task.deadline else None,
        "sprint": {
            "id": str(sprint.id) if sprint else None,
            "name": sprint.name if sprint else "",
            "number": sprint.sprint_number if sprint else 0,
            "goal": sprint.goal if sprint else "",
            "status": sprint.status.value if sprint and sprint.status else None,
        } if sprint else {},
        "project": {
            "id": str(project.id) if project else None,
            "title": project.title if project else "",
            "objectives": list(project.objectives or []) if project else [],
            "technology_stack": list(project.technology_stack or []) if project else [],
        } if project else {},
        "company": {
            "name": company.name if company else "",
            "industry": company.industry if company else "",
            "company_type": company.company_type.value if company and company.company_type else "",
        } if company else {},
        "previous_submissions": submission_history,
    }


def build_review_context(db: Session, version: "SubmissionVersion") -> Dict[str, Any]:
    """Build complete context for AI review of a specific submission version."""
    task = version.submission.task
    
    # Get project context
    project_context = build_project_context(db, task.sprint.project)
    
    # Get task context with submission history
    task_context = build_task_context(db, task)
    
    # Extract current submission content
    from app.services.content_extraction import extract_all_submission_files
    from app.services.file_storage import FileStorageService
    storage_service = FileStorageService()
    current_content = extract_all_submission_files(version.files, storage_service) if version.files else "No files submitted."
    
    # Merge all contexts
    context = {**project_context, **task_context}
    context.update({
        "current_submission": {
            "version_number": version.version_number,
            "submitted_at": version.submitted_at.isoformat() if version.submitted_at else None,
            "files": version.files,
            "metadata": version.version_metadata,
            "content": current_content,
        },
        "submission_content": current_content,  # For backward compatibility with prompt builder
    })
    
    return context
