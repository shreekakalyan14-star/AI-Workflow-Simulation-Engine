from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.project import Project
from app.models.project_state import ProjectState
from app.models.sprint import Sprint
from app.models.task import Task
from app.models.enums import TaskStatus


class SubmissionService:
    def __init__(self, storage_dir: Optional[str] = None):
        self.storage_dir = Path(storage_dir or os.getenv("SUBMISSION_STORAGE_DIR", "/tmp/aiwse-submissions"))
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def store_submission(
        self,
        db: Session,
        project: Project,
        files: Optional[List[Dict[str, Any]]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        metadata = metadata or {}
        files = files or []
        version = int(metadata.get("version", 1))
        submission_id = uuid.uuid4()
        folder = self.storage_dir / str(project.id) / str(submission_id)
        folder.mkdir(parents=True, exist_ok=True)

        stored_files: List[Dict[str, Any]] = []
        for index, file_data in enumerate(files):
            name = str(file_data.get("name") or f"file_{index + 1}")
            content = file_data.get("content") or ""
            destination = folder / name
            destination.write_text(content, encoding="utf-8")
            stored_files.append({"name": name, "path": str(destination), "size": len(content.encode("utf-8"))})

        state = db.query(ProjectState).filter(ProjectState.project_id == project.id).one_or_none()
        if state is not None:
            state.stress_level = min(100, state.stress_level + 3)
            db.add(state)

        return {
            "submission_id": str(submission_id),
            "project_id": str(project.id),
            "version": version,
            "stored_files": stored_files,
            "metadata": metadata,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

    def get_submission_history(self, db: Session, project: Project) -> List[Dict[str, Any]]:
        return []
