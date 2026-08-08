"""
FEATURE 2: Project Generator.

Generates a realistic Project (title, objectives, modules, deliverables,
duration) by selecting from the dynamic Project Catalog based on company
type, role, technology stack, and difficulty. Persists a ProjectState row
(FEATURE 8 groundwork) alongside it.
"""
from __future__ import annotations

import random
import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.company import Company
from app.models.enums import CompanyType, DifficultyLevel
from app.models.project import Project
from app.models.project_state import ProjectState
from app.services.generators.project_catalog import (
    CatalogProject,
    NoMatchingProjectError,
    ProjectCatalogError,
    ProjectCatalogNotFoundError,
    select_catalog_project,
)

_DEFAULT_DELIVERABLES: tuple[str, ...] = (
    "Fully functional REST API with Swagger docs",
    "Deployed staging environment",
    "Unit and integration test suite",
    "Technical design document",
    "Working UI connected to live data",
    "CI pipeline configuration",
    "Final demo & handover documentation",
)


class ProjectGenerationError(Exception):
    """Raised when project generation fails."""


def _resolve_company_type(
    db: Session,
    company_id: uuid.UUID,
    company_type: Optional[CompanyType] = None,
) -> CompanyType:
    if company_type is not None:
        return company_type

    company = db.get(Company, company_id)
    if company is None:
        raise ProjectGenerationError(f"Company '{company_id}' was not found")

    return company.company_type


def _build_objectives(catalog_project: CatalogProject, technology_stack: List[str]) -> List[str]:
    stack_str = ", ".join(technology_stack)
    objectives = list(catalog_project.project_objectives)

    objectives.insert(
        0,
        f"Design and implement {catalog_project.title} for {catalog_project.client_name} using {stack_str}.",
    )
    objectives.append(
        f"Deliver a production-ready solution aligned with {catalog_project.industry} domain requirements."
    )
    return objectives


def _build_modules(catalog_project: CatalogProject) -> List[str]:
    return [module.name for module in catalog_project.modules]


def _build_deliverables(catalog_project: CatalogProject) -> List[str]:
    if catalog_project.learning_outcomes:
        return list(catalog_project.learning_outcomes)

    module_deliverables = [
        f"Completed module: {module.name}" for module in catalog_project.modules
    ]
    if module_deliverables:
        return module_deliverables

    return list(_DEFAULT_DELIVERABLES[:3])


def generate_project(
    db: Session,
    company_id: uuid.UUID,
    role: str,
    technology_stack: List[str],
    difficulty: DifficultyLevel,
    company_type: Optional[CompanyType] = None,
) -> Project:
    """
    Select a catalog project and persist it as a Project ORM entity.

    ``company_type`` is optional; when omitted the value is resolved from the
    company record referenced by ``company_id``.
    """
    if not role.strip():
        raise ProjectGenerationError("Role must be a non-empty string")
    if not technology_stack:
        raise ProjectGenerationError("technology_stack must contain at least one item")

    rng = random.Random()

    try:
        resolved_company_type = _resolve_company_type(db, company_id, company_type)
        catalog_project = select_catalog_project(
            company_type=resolved_company_type,
            role=role,
            technology_stack=technology_stack,
            difficulty=difficulty,
            rng=rng,
        )
    except ProjectCatalogNotFoundError as exc:
        raise ProjectGenerationError(str(exc)) from exc
    except ProjectCatalogError as exc:
        raise ProjectGenerationError(str(exc)) from exc
    except NoMatchingProjectError as exc:
        raise ProjectGenerationError(str(exc)) from exc

    duration_weeks = catalog_project.duration_weeks
    start = datetime.now(timezone.utc)
    end = start + timedelta(weeks=duration_weeks)

    project = Project(
        company_id=company_id,
        title=catalog_project.title,
        role=role,
        technology_stack=technology_stack,
        difficulty=difficulty,
        objectives=_build_objectives(catalog_project, technology_stack),
        modules=_build_modules(catalog_project),
        deliverables=_build_deliverables(catalog_project),
        duration_weeks=duration_weeks,
        start_date=start,
        end_date=end,
    )
    db.add(project)
    db.flush()

    project_state = ProjectState(project_id=project.id)
    db.add(project_state)
    db.flush()

    return project
