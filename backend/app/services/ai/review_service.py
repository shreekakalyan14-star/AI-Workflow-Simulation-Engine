from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import ReviewResult, ReviewStatus, ReviewSeverity
from app.models.project import Project
from app.models.project_state import ProjectState
from app.models.task import Task
from app.models.sprint import Sprint
from app.services.ai.ai_service import AIService
from app.services.ai.prompt_builder import build_review_prompt
from app.services.context.context_builder import build_project_context


class ReviewService:
    def __init__(self, ai_service: AIService):
        self.ai_service = ai_service

    async def review_submission(
        self,
        db: Session,
        project: Project,
        submission_payload: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        context = build_project_context(db, project)
        prompt = build_review_prompt(context)
        system_prompt = "You are a senior engineering reviewer. Produce deterministic JSON with summary, strengths, risks, actions, status, severity, and score."

        raw = await self.ai_service.generate_json(prompt=prompt, system_prompt=system_prompt)
        review_payload = self._coerce_review_payload(raw, context)

        state = db.execute(select(ProjectState).where(ProjectState.project_id == project.id)).scalar_one_or_none()
        if state is not None:
            state.stress_level = min(100, state.stress_level + 5)
            db.add(state)

        return {
            "project_id": str(project.id),
            "status": review_payload["status"],
            "severity": review_payload["severity"],
            "summary": review_payload["summary"],
            "strengths": review_payload["strengths"],
            "risks": review_payload["risks"],
            "actions": review_payload["actions"],
            "score": review_payload["score"],
            "raw": review_payload,
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
        }
