"""
Project Catalog loader and selection utilities.

Reads industry-specific project definitions from ``app/data/projects/*.json``
and selects the best match for a given role, technology stack, and difficulty.
"""
from __future__ import annotations

import json
import random
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Final, Iterable, Sequence

from app.models.enums import CompanyType, DifficultyLevel

CATALOG_DIR: Final[Path] = Path(__file__).resolve().parents[2] / "data" / "projects"

# Maps each company type to one or more catalog files (merged when multiple).
COMPANY_TYPE_CATALOG_FILES: Final[dict[CompanyType, tuple[str, ...]]] = {
    CompanyType.HEALTHCARE: ("healthcare.json",),
    CompanyType.BANKING: ("fintech.json",),
    CompanyType.EDUCATION: ("education.json",),
    CompanyType.ECOMMERCE: ("ecommerce.json",),
    CompanyType.STARTUP: ("cloud.json", "ai_ml.json", "social_media.json"),
    CompanyType.PRODUCT_COMPANY: ("enterprise.json", "cloud.json"),
    CompanyType.MNC: ("enterprise.json", "logistics.json"),
}

# Preferred catalog labels per requested difficulty (used for primary filtering).
_LEVEL_TO_CATALOG_LABELS: Final[dict[DifficultyLevel, frozenset[str]]] = {
    DifficultyLevel.BEGINNER: frozenset({"easy"}),
    DifficultyLevel.INTERMEDIATE: frozenset({"medium"}),
    DifficultyLevel.ADVANCED: frozenset({"hard"}),
    DifficultyLevel.EXPERT: frozenset({"hard"}),
}

# Expanded labels used when no exact difficulty match exists.
_LEVEL_DIFFICULTY_FALLBACK: Final[dict[DifficultyLevel, frozenset[str]]] = {
    DifficultyLevel.BEGINNER: frozenset({"easy", "medium"}),
    DifficultyLevel.INTERMEDIATE: frozenset({"medium", "easy", "hard"}),
    DifficultyLevel.ADVANCED: frozenset({"hard", "medium"}),
    DifficultyLevel.EXPERT: frozenset({"hard", "medium"}),
}

_ROLE_STOP_WORDS: Final[frozenset[str]] = frozenset(
    {"and", "the", "of", "a", "an", "senior", "junior", "lead", "staff", "principal"}
)


class ProjectCatalogError(Exception):
    """Base exception for project catalog operations."""


class ProjectCatalogNotFoundError(ProjectCatalogError):
    """Raised when no catalog file exists for a company type."""


class ProjectCatalogLoadError(ProjectCatalogError):
    """Raised when a catalog file cannot be read or parsed."""


class NoMatchingProjectError(ProjectCatalogError):
    """Raised when no project can be selected from the catalog."""


@dataclass(frozen=True, slots=True)
class CatalogModule:
    name: str
    description: str


@dataclass(frozen=True, slots=True)
class CatalogProject:
    id: str
    title: str
    industry: str
    client_name: str
    description: str
    difficulty: str
    recommended_roles: tuple[str, ...]
    technology_stack: tuple[str, ...]
    duration_weeks: int
    modules: tuple[CatalogModule, ...]
    learning_outcomes: tuple[str, ...]
    project_objectives: tuple[str, ...]


def _normalize_text(value: str) -> str:
    return value.strip().lower().replace("-", " ").replace("_", " ")


def _role_tokens(role: str) -> frozenset[str]:
    tokens = {
        token
        for token in _normalize_text(role).split()
        if token not in _ROLE_STOP_WORDS and len(token) > 2
    }
    return frozenset(tokens)


def _catalog_difficulty_label(raw: str) -> str:
    return _normalize_text(raw)


def _matches_difficulty(catalog_difficulty: str, level: DifficultyLevel, *, relaxed: bool) -> bool:
    label = _catalog_difficulty_label(catalog_difficulty)
    allowed = _LEVEL_DIFFICULTY_FALLBACK[level] if relaxed else _LEVEL_TO_CATALOG_LABELS[level]
    return label in allowed


def _role_matches(recommended_roles: Sequence[str], requested_role: str) -> bool:
    requested = _normalize_text(requested_role)
    requested_tokens = _role_tokens(requested_role)

    for catalog_role in recommended_roles:
        normalized_catalog_role = _normalize_text(catalog_role)
        if normalized_catalog_role in requested or requested in normalized_catalog_role:
            return True

        catalog_tokens = _role_tokens(catalog_role)
        if requested_tokens & catalog_tokens:
            return True

    return False


def _stack_overlap_score(catalog_stack: Sequence[str], requested_stack: Sequence[str]) -> float:
    if not requested_stack:
        return 0.0

    catalog_normalized = {_normalize_text(item) for item in catalog_stack}
    requested_normalized = {_normalize_text(item) for item in requested_stack}

    # Direct token overlap.
    overlap = len(catalog_normalized & requested_normalized)

    # Partial matches (e.g. "postgres" ↔ "postgresql").
    for req in requested_normalized:
        for cat in catalog_normalized:
            if req in cat or cat in req:
                overlap += 1
                break

    return overlap / len(requested_normalized)


def _parse_module(raw: object) -> CatalogModule:
    if not isinstance(raw, dict):
        raise ProjectCatalogLoadError("Catalog module entry must be an object")

    name = raw.get("name")
    description = raw.get("description", "")
    if not isinstance(name, str) or not name.strip():
        raise ProjectCatalogLoadError("Catalog module entry is missing a valid 'name'")
    if not isinstance(description, str):
        raise ProjectCatalogLoadError(f"Catalog module '{name}' has an invalid 'description'")

    return CatalogModule(name=name.strip(), description=description.strip())


def _parse_project(raw: object) -> CatalogProject:
    if not isinstance(raw, dict):
        raise ProjectCatalogLoadError("Catalog project entry must be an object")

    required_str_fields = ("id", "title", "industry", "client_name", "description", "difficulty")
    for field in required_str_fields:
        value = raw.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ProjectCatalogLoadError(f"Catalog project entry is missing a valid '{field}'")

    recommended_roles_raw = raw.get("recommended_roles")
    technology_stack_raw = raw.get("technology_stack")
    modules_raw = raw.get("modules")
    learning_outcomes_raw = raw.get("learning_outcomes")
    project_objectives_raw = raw.get("project_objectives")
    duration_weeks_raw = raw.get("duration_weeks")

    if not isinstance(recommended_roles_raw, list) or not recommended_roles_raw:
        raise ProjectCatalogLoadError(f"Catalog project '{raw.get('id')}' has invalid 'recommended_roles'")
    if not isinstance(technology_stack_raw, list) or not technology_stack_raw:
        raise ProjectCatalogLoadError(f"Catalog project '{raw.get('id')}' has invalid 'technology_stack'")
    if not isinstance(modules_raw, list) or not modules_raw:
        raise ProjectCatalogLoadError(f"Catalog project '{raw.get('id')}' has invalid 'modules'")
    if not isinstance(learning_outcomes_raw, list):
        raise ProjectCatalogLoadError(f"Catalog project '{raw.get('id')}' has invalid 'learning_outcomes'")
    if not isinstance(project_objectives_raw, list) or not project_objectives_raw:
        raise ProjectCatalogLoadError(f"Catalog project '{raw.get('id')}' has invalid 'project_objectives'")
    if not isinstance(duration_weeks_raw, int) or duration_weeks_raw <= 0:
        raise ProjectCatalogLoadError(f"Catalog project '{raw.get('id')}' has invalid 'duration_weeks'")

    modules = tuple(_parse_module(item) for item in modules_raw)

    return CatalogProject(
        id=str(raw["id"]).strip(),
        title=str(raw["title"]).strip(),
        industry=str(raw["industry"]).strip(),
        client_name=str(raw["client_name"]).strip(),
        description=str(raw["description"]).strip(),
        difficulty=str(raw["difficulty"]).strip(),
        recommended_roles=tuple(str(role).strip() for role in recommended_roles_raw if str(role).strip()),
        technology_stack=tuple(str(item).strip() for item in technology_stack_raw if str(item).strip()),
        duration_weeks=duration_weeks_raw,
        modules=modules,
        learning_outcomes=tuple(str(item).strip() for item in learning_outcomes_raw if str(item).strip()),
        project_objectives=tuple(str(item).strip() for item in project_objectives_raw if str(item).strip()),
    )


@lru_cache(maxsize=16)
def _load_catalog_file(filename: str) -> tuple[CatalogProject, ...]:
    catalog_path = CATALOG_DIR / filename
    if not catalog_path.is_file():
        raise ProjectCatalogNotFoundError(f"Project catalog file not found: {catalog_path}")

    try:
        raw_text = catalog_path.read_text(encoding="utf-8")
        payload = json.loads(raw_text)
    except OSError as exc:
        raise ProjectCatalogLoadError(f"Unable to read catalog file '{filename}': {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ProjectCatalogLoadError(f"Invalid JSON in catalog file '{filename}': {exc}") from exc

    if not isinstance(payload, list):
        raise ProjectCatalogLoadError(f"Catalog file '{filename}' must contain a JSON array")

    try:
        return tuple(_parse_project(item) for item in payload)
    except ProjectCatalogLoadError:
        raise
    except Exception as exc:  # pragma: no cover - defensive guard for malformed entries
        raise ProjectCatalogLoadError(f"Failed to parse catalog file '{filename}': {exc}") from exc


def load_projects_for_company_type(company_type: CompanyType) -> tuple[CatalogProject, ...]:
    """Load and merge all catalog projects applicable to the given company type."""
    filenames = COMPANY_TYPE_CATALOG_FILES.get(company_type)
    if not filenames:
        raise ProjectCatalogNotFoundError(f"No project catalog mapping for company type '{company_type.value}'")

    projects: list[CatalogProject] = []
    for filename in filenames:
        projects.extend(_load_catalog_file(filename))

    if not projects:
        raise ProjectCatalogNotFoundError(
            f"Project catalog for company type '{company_type.value}' contains no projects"
        )

    return tuple(projects)


def _filter_candidates(
    projects: Iterable[CatalogProject],
    *,
    role: str,
    technology_stack: Sequence[str],
    difficulty: DifficultyLevel,
    require_role: bool,
    require_stack: bool,
    relaxed_difficulty: bool,
) -> list[CatalogProject]:
    candidates: list[CatalogProject] = []

    for project in projects:
        if not _matches_difficulty(project.difficulty, difficulty, relaxed=relaxed_difficulty):
            continue
        if require_role and not _role_matches(project.recommended_roles, role):
            continue
        if require_stack and _stack_overlap_score(project.technology_stack, technology_stack) <= 0:
            continue
        candidates.append(project)

    return candidates


def _rank_candidates(
    candidates: Sequence[CatalogProject],
    *,
    role: str,
    technology_stack: Sequence[str],
) -> list[CatalogProject]:
    def sort_key(project: CatalogProject) -> tuple[float, float, str]:
        stack_score = _stack_overlap_score(project.technology_stack, technology_stack)
        role_score = 1.0 if _role_matches(project.recommended_roles, role) else 0.0
        return (stack_score, role_score, project.id)

    return sorted(candidates, key=sort_key, reverse=True)


def select_catalog_project(
    company_type: CompanyType,
    role: str,
    technology_stack: Sequence[str],
    difficulty: DifficultyLevel,
    rng: random.Random | None = None,
) -> CatalogProject:
    """
    Select the best catalog project for the given criteria.

    Applies progressively relaxed filters when no exact match is available.
    """
    randomizer = rng or random.Random()
    all_projects = load_projects_for_company_type(company_type)

    filter_steps: tuple[tuple[bool, bool, bool], ...] = (
        (False, True, True),   # exact difficulty + role + stack overlap
        (False, True, False),  # exact difficulty + role
        (False, False, True),  # exact difficulty + stack overlap
        (False, False, False), # exact difficulty only
        (True, True, False), # relaxed difficulty + role
        (True, False, False),# relaxed difficulty only
    )

    for relaxed_difficulty, require_role, require_stack in filter_steps:
        candidates = _filter_candidates(
            all_projects,
            role=role,
            technology_stack=technology_stack,
            difficulty=difficulty,
            require_role=require_role,
            require_stack=require_stack,
            relaxed_difficulty=relaxed_difficulty,
        )
        if not candidates:
            continue

        ranked = _rank_candidates(candidates, role=role, technology_stack=technology_stack)
        top_score = _stack_overlap_score(ranked[0].technology_stack, technology_stack)
        top_tier = [
            project
            for project in ranked
            if _stack_overlap_score(project.technology_stack, technology_stack) == top_score
        ]
        return randomizer.choice(top_tier)

    raise NoMatchingProjectError(
        f"No catalog project found for company_type={company_type.value!r}, "
        f"role={role!r}, difficulty={difficulty.value!r}"
    )
