from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import ReviewResult, ReviewStatus, ReviewSeverity, SubmissionStatus, TaskStatus, EventType
from app.models.manager import Manager
from app.models.project import Project
from app.models.project_state import ProjectState
from app.models.submission import AIReview, ReviewHistory, SubmissionVersion
from app.models.task import Task
from app.schemas.review import AIManagerDecision, AIReviewResponse
from app.services.ai.ai_manager import review_ai_evaluation
from app.services.ai.ai_service import AIService
from app.services.ai.prompt_builder import build_review_prompt
from app.services.content_extraction import extract_all_submission_files
from app.services.context.context_builder import build_review_context
from app.services.engines.events_engine import trigger_event
from app.services.file_storage import FileStorageService
from app.services.notification_service import notify


class ReviewService:
    def __init__(self, ai_service: AIService):
        self.ai_service = ai_service
        self.storage_service = FileStorageService()

    async def review_submission_version(
        self,
        db: Session,
        version: SubmissionVersion,
    ) -> Dict[str, Any]:
        # Build complete context for the review (includes project, task, submission history, current content)
        context = build_review_context(db, version)

        # Set version and task to UNDER_REVIEW when review starts
        version.status = SubmissionStatus.UNDER_REVIEW
        task = version.submission.task
        task.status = TaskStatus.UNDER_REVIEW
        db.add(version)
        db.add(task)
        db.flush()

        # Trigger REVIEW_STARTED event
        project = task.sprint.project
        await trigger_event(
            db,
            project,
            EventType.REVIEW_STARTED,
            f"AI review started for task '{task.title}' (version {version.version_number})",
            {"task_id": str(task.id), "version_id": str(version.id), "version": version.version_number},
        )

        prompt = build_review_prompt(context)
        system_prompt = (
            "You are a senior engineering reviewer. Analyze the submitted code/files against the task requirements. "
            "Produce deterministic JSON with summary, strengths, risks, actions, status, severity, and score."
        )

        # Retry logic for AI response validation
        max_retries = 2
        review_payload = None
        for attempt in range(max_retries + 1):
            try:
                raw = await self.ai_service.generate_json(prompt=prompt, system_prompt=system_prompt)
                # Validate with Pydantic schema
                validated = AIReviewResponse.model_validate(raw)
                review_payload = validated.model_dump()
                break
            except Exception as e:
                if attempt < max_retries:
                    # Add error context to prompt for retry
                    prompt = prompt + f"\n\nPREVIOUS RESPONSE WAS INVALID: {e}\nPlease fix and respond with valid JSON only."
                    continue
                else:
                    raise ValueError(f"AI review validation failed after {max_retries + 1} attempts: {e}")

        # Create the AIReview record
        ai_review = AIReview(
            version_id=version.id,
            status=ReviewStatus.COMPLETED,
            result=ReviewResult(review_payload["result"]),
            severity=ReviewSeverity(review_payload["severity"]),
            summary=review_payload["summary"],
            strengths=review_payload.get("strengths", []),
            risks=review_payload.get("risks", review_payload.get("issues", [])),
            actions=review_payload.get("actions", review_payload.get("required_changes", [])),
            score=review_payload["score"],
            raw_payload=review_payload,
            completed_at=None,  # will be set after commit
        )
        db.add(ai_review)
        db.flush()

        # Create initial ReviewHistory entry
        history = ReviewHistory(
            review_id=ai_review.id,
            action="created",
            previous_status=None,
            new_status=ReviewStatus.COMPLETED,
            previous_result=None,
            new_result=ai_review.result,
            changed_by="ai_reviewer",
            notes="Initial AI review completed",
            payload_snapshot=review_payload,
        )
        db.add(history)

        # Update the version status based on the review result
        if ai_review.result == ReviewResult.APPROVED:
            version.status = SubmissionStatus.APPROVED
            task.status = TaskStatus.MANAGER_APPROVAL
        elif ai_review.result == ReviewResult.CHANGES_REQUIRED:
            version.status = SubmissionStatus.CHANGES_REQUESTED
            task.status = TaskStatus.CHANGES_REQUESTED
        else:  # REJECTED
            version.status = SubmissionStatus.REJECTED
            task.status = TaskStatus.CHANGES_REQUESTED

        db.add(version)
        db.add(task)

        # Also update the parent submission status
        submission = version.submission
        submission.status = version.status
        db.add(submission)

        # Update project state stress level
        project = task.sprint.project
        state = db.execute(
            select(ProjectState).where(ProjectState.project_id == project.id)
        ).scalar_one_or_none()
        if state is not None:
            state.stress_level = min(100, state.stress_level + 5)
            db.add(state)

        db.flush()

        # Activity log for AI review completion
        from app.services.activity_log_service import log_activity
        log_activity(
            db,
            company_id=project.company_id,
            actor="ai_reviewer",
            action="ai_review_completed",
            detail=f"AI review completed for task '{task.title}' (version {version.version_number}): {ai_review.result.value}",
            task_id=str(task.id),
            review_id=str(ai_review.id),
            result=ai_review.result.value,
        )

        # Trigger AI_REVIEW_COMPLETED event
        await trigger_event(
            db,
            project,
            EventType.AI_REVIEW_COMPLETED,
            f"AI review completed for task '{task.title}': {ai_review.result.value}",
            {"task_id": str(task.id), "review_id": str(ai_review.id), "result": ai_review.result.value, "score": ai_review.score},
        )

        # If CHANGES_REQUESTED or REJECTED, trigger CHANGES_REQUESTED event
        if ai_review.result in (ReviewResult.CHANGES_REQUIRED, ReviewResult.REJECTED):
            await trigger_event(
                db,
                project,
                EventType.CHANGES_REQUESTED,
                f"Changes requested for task '{task.title}': {ai_review.result.value}",
                {"task_id": str(task.id), "review_id": str(ai_review.id), "result": ai_review.result.value},
            )

        db.commit()
        db.refresh(version)
        db.refresh(task)
        db.refresh(submission)
        db.refresh(ai_review)

        return {
            "review_id": str(ai_review.id),
            "version_id": str(version.id),
            "project_id": str(project.id),
            "status": ai_review.status.value,
            "result": ai_review.result.value,
            "severity": ai_review.severity.value,
            "summary": ai_review.summary,
            "strengths": ai_review.strengths,
            "risks": ai_review.risks,
            "actions": ai_review.actions,
            "score": ai_review.score,
            "raw": review_payload,
        }

    async def review_by_manager(
        self,
        db: Session,
        version: SubmissionVersion,
    ) -> Dict[str, Any]:
        """
        AI Engineering Manager reviews the AI evaluation and makes final decision.
        This is the second layer of review - only proceeds if AI review exists.
        """
        project = version.submission.task.sprint.project
        task = version.submission.task

        # Get the latest AI review for this version
        ai_review = db.execute(
            select(AIReview)
            .where(AIReview.version_id == version.id)
            .order_by(AIReview.created_at.desc())
        ).scalar_one_or_none()

        if not ai_review:
            raise ValueError("No AI review found for this version. Run AI review first.")

        # Get manager and project state
        manager = db.execute(
            select(Manager).where(Manager.company_id == project.company_id)
        ).scalar_one_or_none()

        state = db.execute(
            select(ProjectState).where(ProjectState.project_id == project.id)
        ).scalar_one_or_none()

        if not manager or not state:
            raise ValueError("Manager or project state not found")

        # Build submission content summary from version files
        submission_summary = f"Version {version.version_number} with {len(version.files)} file(s)"
        if version.version_metadata:
            submission_summary += f", metadata: {version.version_metadata}"

        # Call AI Manager review with validation
        max_retries = 2
        manager_decision = None
        for attempt in range(max_retries + 1):
            try:
                manager_review = await review_ai_evaluation(
                    ai_service=self.ai_service,
                    manager=manager,
                    project=project,
                    state=state,
                    ai_review_summary=ai_review.summary,
                    ai_review_result=ai_review.result.value,
                    ai_review_score=ai_review.score,
                    submission_content_summary=submission_summary,
                )
                # Validate with Pydantic schema
                validated = AIManagerDecision.model_validate(manager_review)
                manager_decision = validated.model_dump()
                break
            except Exception as e:
                if attempt < max_retries:
                    continue
                else:
                    raise ValueError(f"AI Manager validation failed after {max_retries + 1} attempts: {e}")

        # Create ReviewHistory entry for manager review
        history = ReviewHistory(
            review_id=ai_review.id,
            action="manager_review",
            previous_status=ReviewStatus.COMPLETED,
            new_status=ReviewStatus.COMPLETED,
            previous_result=ai_review.result,
            new_result=ReviewResult(manager_decision["decision"]),
            changed_by="ai_manager",
            notes=manager_decision.get("feedback", "Manager review completed"),
            payload_snapshot=manager_decision,
        )
        db.add(history)

        # Update AI review with manager's decision (overrides AI if different)
        final_result = ReviewResult(manager_decision["decision"])
        ai_review.result = final_result
        ai_review.severity = ReviewSeverity(manager_decision["severity"])
        ai_review.summary = manager_decision["summary"]
        ai_review.raw_payload = {**ai_review.raw_payload, "manager_review": manager_decision}
        db.add(ai_review)

        # Update version and task status based on FINAL manager decision
        if final_result == ReviewResult.APPROVED:
            version.status = SubmissionStatus.APPROVED
            task.status = TaskStatus.COMPLETED
        elif final_result == ReviewResult.CHANGES_REQUESTED:
            version.status = SubmissionStatus.CHANGES_REQUESTED
            task.status = TaskStatus.CHANGES_REQUESTED
        else:  # REJECTED
            version.status = SubmissionStatus.REJECTED
            task.status = TaskStatus.CHANGES_REQUESTED

        db.add(version)
        db.add(task)

        # Update parent submission status
        submission = version.submission
        submission.status = version.status
        db.add(submission)

        db.flush()

        # If task was approved and completed, trigger simulation progression
        if final_result == ReviewResult.APPROVED:
            from app.models.simulation import Simulation
            from app.services.simulation.progression_service import progress_to_next_task
            simulation = db.execute(
                select(Simulation).where(Simulation.current_task_id == task.id)
            ).scalar_one_or_none()
            if simulation:
                await progress_to_next_task(db, simulation, task, "ai_manager")

        # Create notifications, events, activity logs for manager review completion
        company_id = project.company_id
        
        # Activity log
        from app.services.activity_log_service import log_activity
        log_activity(
            db,
            company_id=company_id,
            actor="ai_manager",
            action="manager_review_completed",
            detail=f"Manager review completed for task '{task.title}' (version {version.version_number}): {final_result.value}",
            task_id=str(task.id),
            review_id=str(ai_review.id),
            result=final_result.value,
        )
        
        # Notification based on decision
        if final_result == ReviewResult.APPROVED:
            notify(
                db,
                company_id=company_id,
                notification_type="task_approved",
                message=f"Task '{task.title}' approved by manager. Task completed!",
            )
            # Trigger MANAGER_APPROVED event
            await trigger_event(
                db,
                project,
                EventType.MANAGER_APPROVED,
                f"Manager approved submission for '{task.title}'",
                {"task_id": str(task.id), "review_id": str(ai_review.id), "result": final_result.value},
            )
            # Trigger TASK_COMPLETED event
            await trigger_event(
                db,
                project,
                EventType.TASK_COMPLETED,
                f"Task '{task.title}' completed after manager approval",
                {"task_id": str(task.id), "review_id": str(ai_review.id)},
            )
        else:
            notify(
                db,
                company_id=company_id,
                notification_type="changes_requested",
                message=f"Changes requested for '{task.title}': {manager_decision.get('feedback', '')}",
            )
            await trigger_event(
                db,
                project,
                EventType.CHANGES_REQUESTED,
                f"Manager requested changes for '{task.title}'",
                {"task_id": str(task.id), "review_id": str(ai_review.id), "result": final_result.value},
            )

        db.commit()
        db.refresh(version)
        db.refresh(task)
        db.refresh(submission)
        db.refresh(ai_review)

        return {
            "review_id": str(ai_review.id),
            "version_id": str(version.id),
            "project_id": str(project.id),
            "ai_result": ai_review.result.value,
            "manager_result": final_result.value,
            "manager_severity": manager_decision["severity"],
            "manager_summary": manager_decision["summary"],
            "manager_feedback": manager_decision.get("feedback", ""),
            "final_task_status": task.status.value,
        }

    def _coerce_review_payload(self, raw: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "status": str(raw.get("status", ReviewStatus.COMPLETED.value)).lower(),
            "severity": str(raw.get("severity", ReviewSeverity.WARNING.value)).lower(),
            "summary": str(raw.get("summary", "Review completed successfully.")),
            "strengths": [str(item) for item in raw.get("strengths", []) or []],
            "risks": [str(item) for item in raw.get("risks", []) or []],
            "actions": [str(item) for item in raw.get("actions", []) or []],
            "score": int(raw.get("score", 78)),
            "result": str(raw.get("result", ReviewResult.CHANGES_REQUIRED.value)).lower(),
        }

    def get_review_history(self, db: Session, version_id: uuid.UUID) -> List[Dict[str, Any]]:
        version = db.get(SubmissionVersion, version_id)
        if not version:
            return []

        reviews = db.execute(
            select(AIReview).where(AIReview.version_id == version_id)
        ).scalars().all()

        result = []
        for review in reviews:
            history = db.execute(
                select(ReviewHistory).where(ReviewHistory.review_id == review.id)
            ).scalars().all()

            result.append({
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
                "history": [
                    {
                        "action": h.action,
                        "previous_status": h.previous_status.value if h.previous_status else None,
                        "new_status": h.new_status.value,
                        "previous_result": h.previous_result.value if h.previous_result else None,
                        "new_result": h.new_result.value,
                        "changed_by": h.changed_by,
                        "notes": h.notes,
                        "payload_snapshot": h.payload_snapshot,
                        "created_at": h.created_at.isoformat(),
                    }
                    for h in history
                ],
            })
        return result