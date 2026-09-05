from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import CurrentUser, get_current_user
from app.models.company import Company
from app.models.enums import NotificationType, SubmissionStatus
from app.models.project import Project
from app.models.sprint import Sprint
from app.models.submission import Submission, SubmissionVersion
from app.models.task import Task
from app.services.submission.submission_service import SubmissionService
from app.services.file_storage import FileValidationError
from app.services.notification_service import notify

router = APIRouter(prefix="/api/projects/{project_id}/submissions", tags=["Submissions"])


def _get_owned_project(project_id: uuid.UUID, db: Session, user: CurrentUser) -> Project:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    company = db.get(Company, project.company_id)
    if company is None or company.student_id != user.student_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your project")
    return project


def _get_owned_task(task_id: uuid.UUID, db: Session, user: CurrentUser) -> Task:
    task = db.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    sprint = db.get(Sprint, task.sprint_id)
    project = db.get(Project, sprint.project_id)
    company = db.get(Company, project.company_id)
    if company is None or company.student_id != user.student_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your task")
    return task


def _get_owned_submission(submission_id: uuid.UUID, db: Session, user: CurrentUser) -> Submission:
    submission = db.get(Submission, submission_id)
    if submission is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Submission not found")
    task = db.get(Task, submission.task_id)
    sprint = db.get(Sprint, task.sprint_id)
    project = db.get(Project, sprint.project_id)
    company = db.get(Company, project.company_id)
    if company is None or company.student_id != user.student_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your submission")
    return submission


def _get_owned_version(version_id: uuid.UUID, db: Session, user: CurrentUser) -> SubmissionVersion:
    version = db.get(SubmissionVersion, version_id)
    if version is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Submission version not found")
    task = db.get(Task, version.submission.task_id)
    sprint = db.get(Sprint, task.sprint_id)
    project = db.get(Project, sprint.project_id)
    company = db.get(Company, project.company_id)
    if company is None or company.student_id != user.student_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your submission version")
    return version


# POST /api/tasks/{task_id}/start - Start working on a task
@router.post("/tasks/{task_id}/start", status_code=status.HTTP_200_OK)
async def start_task(
    project_id: uuid.UUID,
    task_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """Move task from BACKLOG/TODO to IN_PROGRESS."""
    project = _get_owned_project(project_id, db, user)
    task = _get_owned_task(task_id, db, user)

    sprint = db.get(Sprint, task.sprint_id)
    if sprint.project_id != project.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Task does not belong to this project")

    # Validate transition
    from app.services.engines.task_state_machine import validate_transition, can_start_task
    from app.models.enums import TaskStatus
    
    try:
        validate_transition(task.status, TaskStatus.IN_PROGRESS)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    
    if not can_start_task(task.status):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot start task from '{task.status.value}'. Must be in BACKLOG or TODO."
        )

    # Check dependencies
    from app.api.routes.tasks import _check_dependencies
    _check_dependencies(db, task)

    # Update task
    from datetime import datetime, timezone
    task.status = TaskStatus.IN_PROGRESS
    if task.started_at is None:
        task.started_at = datetime.now(timezone.utc)
    db.add(task)
    db.flush()

    # Log activity
    from app.services.activity_log_service import log_activity
    company_id = project.company_id
    log_activity(
        db,
        company_id=company_id,
        actor=user.student_id,
        action="task_started",
        detail=f"Task '{task.title}' moved to IN_PROGRESS",
        task_id=str(task.id),
        previous_status=task.status.value,
        new_status=TaskStatus.IN_PROGRESS.value,
    )

    # Trigger TASK_STARTED event
    from app.services.engines.events_engine import trigger_event
    from app.models.enums import EventType
    await trigger_event(
        db,
        project,
        EventType.TASK_STARTED,
        f"Task '{task.title}' started",
        {"task_id": str(task.id), "task_title": task.title},
    )

    db.commit()
    db.refresh(task)
    return {"status": "started", "task_id": str(task.id), "task_status": task.status.value}


# POST /api/tasks/{task_id}/submit - Submit task for review
@router.post("/tasks/{task_id}/submit", status_code=status.HTTP_201_CREATED)
async def submit_task(
    project_id: uuid.UUID,
    task_id: uuid.UUID,
    files: List[UploadFile] = File(default=[]),
    metadata: Optional[str] = Form(default=None),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """Submit files for a task (includes file upload and status transition to SUBMITTED)."""
    project = _get_owned_project(project_id, db, user)
    task = _get_owned_task(task_id, db, user)

    sprint = db.get(Sprint, task.sprint_id)
    if sprint.project_id != project.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Task does not belong to this project")

    # Validate transition
    from app.services.engines.task_state_machine import validate_transition
    from app.models.enums import TaskStatus
    
    try:
        validate_transition(task.status, TaskStatus.SUBMITTED)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    if task.status != TaskStatus.IN_PROGRESS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot submit task from '{task.status.value}'. Must be IN_PROGRESS."
        )

    # Parse metadata
    import json
    meta_dict = {}
    if metadata:
        try:
            meta_dict = json.loads(metadata)
        except json.JSONDecodeError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid metadata JSON")

    # Prepare file data for storage service
    file_data = []
    for upload_file in files:
        content = await upload_file.read()
        import io
        file_data.append({
            "file": io.BytesIO(content),
            "filename": upload_file.filename,
            "content_type": upload_file.content_type,
        })

    service = SubmissionService()
    try:
        result = service.store_submission(
            db=db,
            project=project,
            task=task,
            files=file_data,
            metadata=meta_dict,
        )
    except FileValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    # Log activity
    from app.services.activity_log_service import log_activity
    log_activity(
        db,
        company_id=project.company_id,
        actor=user.student_id,
        action="task_submitted",
        detail=f"Task '{task.title}' submitted for review",
        task_id=str(task.id),
        previous_status=TaskStatus.IN_PROGRESS.value,
        new_status=TaskStatus.SUBMITTED.value,
        submission_id=result.get("submission_id"),
        version_id=result.get("version_id"),
    )

    notify(
        db,
        company_id=project.company_id,
        notification_type=NotificationType.TASK_SUBMITTED,
        message=f"Task '{task.title}' submitted for review",
    )

    # Trigger SUBMISSION_CREATED and SUBMISSION_VERSION_CREATED events
    from app.services.engines.events_engine import trigger_event
    from app.models.enums import EventType
    await trigger_event(
        db,
        project,
        EventType.SUBMISSION_CREATED,
        f"Submission created for task '{task.title}'",
        {"task_id": str(task.id), "submission_id": result.get("submission_id"), "version_id": result.get("version_id")},
    )
    await trigger_event(
        db,
        project,
        EventType.SUBMISSION_VERSION_CREATED,
        f"Submission version {result.get('version')} created for task '{task.title}'",
        {"task_id": str(task.id), "version_id": result.get("version_id"), "version": result.get("version")},
    )

    db.commit()
    return result


# GET /api/tasks/{task_id}/submissions - Get all submissions for a task
@router.get("/tasks/{task_id}", response_model=List[Dict[str, Any]])
def get_submissions_for_task(
    project_id: uuid.UUID,
    task_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """Get all submission versions for a task."""
    project = _get_owned_project(project_id, db, user)
    task = _get_owned_task(task_id, db, user)

    sprint = db.get(Sprint, task.sprint_id)
    if sprint.project_id != project.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Task does not belong to this project")

    service = SubmissionService()
    submission = service.get_submission_by_task(db, task_id)
    if submission is None:
        return []
    return [submission]  # Return as list for consistency


# GET /api/submissions/{submission_id} - Get submission by ID
@router.get("/{submission_id}")
def get_submission(
    project_id: uuid.UUID,
    submission_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """Get a specific submission with all its versions."""
    project = _get_owned_project(project_id, db, user)
    submission = _get_owned_submission(submission_id, db, user)

    # Verify submission belongs to this project
    task = db.get(Task, submission.task_id)
    sprint = db.get(Sprint, task.sprint_id)
    if sprint.project_id != project.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Submission does not belong to this project")

    service = SubmissionService()
    return service.get_submission_by_task(db, task.id)


# GET /api/submissions/{submission_id}/versions - Get all versions of a submission
@router.get("/{submission_id}/versions")
def get_submission_versions(
    project_id: uuid.UUID,
    submission_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """Get all versions of a specific submission."""
    project = _get_owned_project(project_id, db, user)
    submission = _get_owned_submission(submission_id, db, user)

    task = db.get(Task, submission.task_id)
    sprint = db.get(Sprint, task.sprint_id)
    if sprint.project_id != project.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Submission does not belong to this project")

    versions = db.execute(
        select(SubmissionVersion)
        .where(SubmissionVersion.submission_id == submission_id)
        .order_by(SubmissionVersion.version_number)
    ).scalars().all()

    return [
        {
            "version_id": str(v.id),
            "version_number": v.version_number,
            "status": v.status.value,
            "files": v.files,
            "metadata": v.version_metadata,
            "submitted_at": v.submitted_at.isoformat() if v.submitted_at else None,
            "created_at": v.created_at.isoformat(),
        }
        for v in versions
    ]


# GET /api/submission-versions/{version_id} - Get specific version
@router.get("/versions/{version_id}")
def get_submission_version(
    project_id: uuid.UUID,
    version_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """Get a specific submission version with full details."""
    project = _get_owned_project(project_id, db, user)
    version = _get_owned_version(version_id, db, user)

    task = db.get(Task, version.submission.task_id)
    sprint = db.get(Sprint, task.sprint_id)
    if sprint.project_id != project.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Version does not belong to this project")

    return {
        "version_id": str(version.id),
        "submission_id": str(version.submission_id),
        "version_number": version.version_number,
        "status": version.status.value,
        "files": version.files,
        "metadata": version.version_metadata,
        "submitted_at": version.submitted_at.isoformat() if version.submitted_at else None,
        "created_at": version.created_at.isoformat(),
    }


# GET /api/submission-versions/{version_id}/review - Get review for a version
@router.get("/versions/{version_id}/review")
def get_version_review(
    project_id: uuid.UUID,
    version_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """Get the AI review for a specific submission version."""
    project = _get_owned_project(project_id, db, user)
    version = _get_owned_version(version_id, db, user)

    task = db.get(Task, version.submission.task_id)
    sprint = db.get(Sprint, task.sprint_id)
    if sprint.project_id != project.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Version does not belong to this project")

    from app.models.submission import AIReview
    review = db.execute(
        select(AIReview)
        .where(AIReview.version_id == version_id)
        .order_by(AIReview.created_at.desc())
    ).scalar_one_or_none()

    if not review:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No review found for this version")

    return {
        "review_id": str(review.id),
        "version_id": str(review.version_id),
        "status": review.status.value,
        "result": review.result.value,
        "severity": review.severity.value,
        "summary": review.summary,
        "strengths": review.strengths,
        "risks": review.risks,
        "actions": review.actions,
        "score": review.score,
        "raw_payload": review.raw_payload,
        "completed_at": review.completed_at.isoformat() if review.completed_at else None,
        "created_at": review.created_at.isoformat(),
    }


# POST /api/submission-versions/{version_id}/resubmit - Create new version
@router.post("/versions/{version_id}/resubmit", status_code=status.HTTP_201_CREATED)
async def resubmit_version(
    project_id: uuid.UUID,
    version_id: uuid.UUID,
    files: List[UploadFile] = File(default=[]),
    metadata: Optional[str] = Form(default=None),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """Submit a new version of an existing submission."""
    project = _get_owned_project(project_id, db, user)
    version = _get_owned_version(version_id, db, user)

    task = db.get(Task, version.submission.task_id)
    sprint = db.get(Sprint, task.sprint_id)
    if sprint.project_id != project.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Version does not belong to this project")

    # Only allow resubmit if previous version was CHANGES_REQUESTED or REJECTED
    from app.models.enums import SubmissionStatus
    if version.status not in (SubmissionStatus.CHANGES_REQUESTED, SubmissionStatus.REJECTED):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Can only resubmit when previous version is CHANGES_REQUESTED or REJECTED. Current: {version.status.value}"
        )

    # Parse metadata
    import json
    meta_dict = {}
    if metadata:
        try:
            meta_dict = json.loads(metadata)
        except json.JSONDecodeError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid metadata JSON")

    # Prepare file data
    file_data = []
    for upload_file in files:
        content = await upload_file.read()
        import io
        file_data.append({
            "file": io.BytesIO(content),
            "filename": upload_file.filename,
            "content_type": upload_file.content_type,
        })

    service = SubmissionService()
    try:
        result = service.store_submission(
            db=db,
            project=project,
            task=task,
            files=file_data,
            metadata=meta_dict,
        )
    except FileValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    # Log activity
    from app.services.activity_log_service import log_activity
    log_activity(
        db,
        company_id=project.company_id,
        actor=user.student_id,
        action="task_resubmitted",
        detail=f"Task '{task.title}' resubmitted (version {result['version']})",
        task_id=str(task.id),
        previous_version=version.version_number,
        new_version=result["version"],
    )

    # Trigger SUBMISSION_RESUBMITTED event
    from app.services.engines.events_engine import trigger_event
    from app.models.enums import EventType
    await trigger_event(
        db,
        project,
        EventType.SUBMISSION_RESUBMITTED,
        f"Task '{task.title}' resubmitted as version {result['version']}",
        {"task_id": str(task.id), "previous_version": version.version_number, "new_version": result["version"], "version_id": result.get("version_id")},
    )

    db.commit()
    return result


# POST /api/tasks/{task_id} - Alias for submit (multipart form)
@router.post("/tasks/{task_id}", status_code=status.HTTP_201_CREATED)
async def create_submission(
    project_id: uuid.UUID,
    task_id: uuid.UUID,
    files: List[UploadFile] = File(default=[]),
    metadata: Optional[str] = Form(default=None),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """
    Submit files for a task (multipart/form-data).
    
    Accepts:
    - files: list of files to upload
    - metadata: optional JSON string with additional metadata
    """
    return await submit_task(project_id, task_id, files, metadata, db, user)


@router.get("", response_model=List[Dict[str, Any]])
def list_submissions(
    project_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    project = _get_owned_project(project_id, db, user)
    service = SubmissionService()
    return service.get_submission_history(db, project)