"""
FEATURE 7 (generation half): AI Teammates.

Generates 3 AI teammates per company at simulation-creation time. Their
chat behavior (asking questions, requesting reviews, reporting bugs, etc.)
lives in ai_teammates.py — this module just creates the personas.
"""
import random
from typing import List

from sqlalchemy.orm import Session

from app.models.team_member import TeamMember

_NAMES = [
    "Jordan Lee", "Priya Nair", "Sam Okafor", "Mia Andersson", "Leo Tanaka",
    "Grace Osei", "Noah Kim", "Fatima Haidari", "Lucas Ferreira", "Ivy Chen",
]
_ROLES = ["Senior Engineer", "Backend Engineer", "Frontend Engineer", "QA Engineer", "DevOps Engineer"]
_PERSONALITIES = ["meticulous", "laid-back", "blunt", "enthusiastic", "quietly sharp"]


def generate_team_members(db: Session, company_id) -> List[TeamMember]:
    rng = random.Random()
    names = rng.sample(_NAMES, k=3)
    members = []
    for name in names:
        member = TeamMember(
            company_id=company_id,
            name=name,
            role=rng.choice(_ROLES),
            personality=rng.choice(_PERSONALITIES),
            skill_level=rng.randint(45, 95),
        )
        db.add(member)
        members.append(member)
    db.flush()
    return members
