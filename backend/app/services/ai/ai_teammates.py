"""
FEATURE 7 (chat half): AI Teammates.

Generates in-character teammate replies — asking questions, offering to
pair, flagging bugs, congratulating progress — grounded in their persona
and skill level.
"""
from typing import List

from app.models.message import Message
from app.models.project import Project
from app.models.team_member import TeamMember
from app.services.ai.ai_service import AIService


def _history_block(history: List[Message], limit: int = 8) -> str:
    recent = history[-limit:]
    lines = []
    for m in recent:
        speaker = "Student" if m.sender_type.value == "student" else "Teammate"
        lines.append(f"{speaker}: {m.content}")
    return "\n".join(lines) if lines else "(no previous messages)"


async def generate_teammate_reply(
    ai_service: AIService,
    teammate: TeamMember,
    project: Project,
    history: List[Message],
    student_message: str,
) -> str:
    system_prompt = (
        f"You are {teammate.name}, a {teammate.role} teammate on project '{project.title}'. "
        f"Personality: {teammate.personality}. Skill level: {teammate.skill_level}/100. "
        "You are messaging your intern teammate in a company chat. Reply in 1-3 sentences, "
        "in character. Never break character or mention that you are an AI."
    )
    prompt = (
        f"Recent conversation:\n{_history_block(history)}\n\n"
        f"Student just said: \"{student_message}\"\n\n"
        "Write your reply as the teammate."
    )
    return await ai_service.generate_text(prompt=prompt, system_prompt=system_prompt)
