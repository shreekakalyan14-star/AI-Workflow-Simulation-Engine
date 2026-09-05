"""
FEATURE 7 (chat half): AI Teammates.

Generates in-character teammate replies — asking questions, offering to
pair, flagging bugs, congratulating progress — grounded in their persona
and skill level, and the current project/sprint/task context.
"""
from typing import List, Optional

from app.models.message import Message
from app.models.project import Project
from app.models.sprint import Sprint
from app.models.task import Task
from app.models.team_member import TeamMember
from app.models.project_state import ProjectState
from app.services.ai.ai_service import AIService


def _history_block(history: List[Message], limit: int = 8) -> str:
    recent = history[-limit:]
    lines = []
    for m in recent:
        speaker = "Student" if m.sender_type.value == "student" else "Teammate"
        lines.append(f"{speaker}: {m.content}")
    return "\n".join(lines) if lines else "(no previous messages)"


def _build_context(teammate: TeamMember, project: Project, sprint: Optional[Sprint],
                   task: Optional[Task], state: Optional[ProjectState],
                   blockers: List[str]) -> str:
    """Build contextual information for the teammate reply."""
    parts = [
        f"Project: {project.title}",
        f"Role: {teammate.role}",
        f"Skill Level: {teammate.skill_level}/100",
        f"Personality: {teammate.personality}",
    ]
    
    if sprint:
        parts.append(f"Current Sprint: {sprint.name} ({sprint.status.value if sprint.status else 'unknown'})")
        if sprint.goal:
            parts.append(f"Sprint Goal: {sprint.goal}")
    
    if task:
        parts.append(f"Current Task: {task.title}")
        parts.append(f"Task Status: {task.status.value if task.status else 'unknown'}")
        parts.append(f"Task Priority: {task.priority.value if task.priority else 'unknown'}")
        if task.description:
            parts.append(f"Task Description: {task.description[:200]}")
        if task.acceptance_criteria:
            parts.append(f"Acceptance Criteria: {', '.join(task.acceptance_criteria[:3])}")
    
    if state:
        parts.append(f"Project State: {state.completed_tasks} completed, {state.pending_tasks} pending, stress: {state.stress_level}/100")
    
    if blockers:
        parts.append(f"Blockers: {', '.join(blockers[:3])}")
    
    return "\n".join(parts)


async def generate_teammate_reply(
    ai_service: AIService,
    teammate: TeamMember,
    project: Project,
    history: List[Message],
    student_message: str,
    sprint: Optional[Sprint] = None,
    task: Optional[Task] = None,
    state: Optional[ProjectState] = None,
    blockers: Optional[List[str]] = None,
) -> str:
    context = _build_context(teammate, project, sprint, task, state, blockers or [])
    
    system_prompt = (
        f"You are {teammate.name}, a {teammate.role} teammate on project '{project.title}'. "
        f"Personality: {teammate.personality}. Skill level: {teammate.skill_level}/100. "
        "You are messaging your intern teammate in a company chat. Reply in 1-3 sentences, "
        "in character, referencing the real project/task context when relevant. Never break character "
        "or mention that you are an AI."
    )
    
    prompt = (
        f"CONTEXT:\n{context}\n\n"
        f"Recent conversation:\n{_history_block(history)}\n\n"
        f"Student just said: \"{student_message}\"\n\n"
        "Write your reply as the teammate, being helpful and contextual."
    )
    
    return await ai_service.generate_text(prompt=prompt, system_prompt=system_prompt)
