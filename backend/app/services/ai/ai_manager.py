"""
FEATURE 6: AI Project Manager.

Generates in-character manager responses given the manager's personality,
the live ProjectState, and recent chat history — grounded in real project
data, not generic chatbot filler.

Also provides AI Manager review of submissions (FEATURE 8+): reviews AI
evaluations and makes final approval decisions.
"""
from typing import List

from sqlalchemy.orm import Session

from app.models.enums import ReviewResult, ReviewSeverity
from app.models.manager import Manager
from app.models.message import Message
from app.models.project import Project
from app.models.project_state import ProjectState
from app.services.ai.ai_service import AIService

_PERSONALITY_VOICE = {
    "strict": "Strict and demanding. Short sentences. No small talk. You hold people to deadlines and call out slipping quality directly, but you are fair, not cruel.",
    "friendly": "Warm, encouraging, and approachable. You coach rather than command, and you celebrate wins genuinely.",
    "corporate": "Polished, diplomatic, slightly formal corporate register. You reference process, stakeholders, and 'alignment'.",
    "startup_founder": "High-energy, informal, impatient with process, obsessed with shipping fast. You use words like 'let's ship it' and talk about the mission.",
}


def _state_summary(state: ProjectState) -> str:
    return (
        f"completed_tasks={state.completed_tasks}, pending_tasks={state.pending_tasks}, "
        f"missed_deadlines={state.missed_deadlines}, bug_count={state.bug_count}, "
        f"manager_satisfaction={state.manager_satisfaction}/100, "
        f"team_satisfaction={state.team_satisfaction}/100, "
        f"stress_level={state.stress_level}/100, current_sprint={state.current_sprint_number}/4"
    )


def _history_block(history: List[Message], limit: int = 8) -> str:
    recent = history[-limit:]
    lines = []
    for m in recent:
        speaker = "Student" if m.sender_type.value == "student" else "You (Manager)"
        lines.append(f"{speaker}: {m.content}")
    return "\n".join(lines) if lines else "(no previous messages)"


async def generate_manager_reply(
    ai_service: AIService,
    manager: Manager,
    project: Project,
    state: ProjectState,
    history: List[Message],
    student_message: str,
) -> str:
    voice = _PERSONALITY_VOICE.get(manager.personality.value, _PERSONALITY_VOICE["corporate"])

    system_prompt = (
        f"You are {manager.name}, {manager.title}, the manager on project '{project.title}'. "
        f"Personality: {voice} "
        "You are messaging your intern in a company chat. Reply in 1-4 sentences, "
        "in character, referencing the real project state when relevant. Never break character "
        "or mention that you are an AI."
    )

    prompt = (
        f"Project state: {_state_summary(state)}\n\n"
        f"Recent conversation:\n{_history_block(history)}\n\n"
        f"Student just said: \"{student_message}\"\n\n"
        "Write your reply as the manager."
    )

    return await ai_service.generate_text(prompt=prompt, system_prompt=system_prompt)


async def review_ai_evaluation(
    ai_service: AIService,
    manager: Manager,
    project: Project,
    state: ProjectState,
    ai_review_summary: str,
    ai_review_result: str,
    ai_review_score: int,
    submission_content_summary: str,
) -> dict:
    """
    AI Engineering Manager reviews the AI evaluation and makes final decision.
    
    Returns dict with: decision (approved/changes_required), 
    severity, summary, feedback
    """
    voice = _PERSONALITY_VOICE.get(manager.personality.value, _PERSONALITY_VOICE["corporate"])

    system_prompt = (
        f"You are {manager.name}, {manager.title}, the engineering manager on project '{project.title}'. "
        f"Personality: {voice} "
        "You are reviewing an AI code review of your intern's submission. "
        "The AI has provided a summary, result, and score. "
        "You must make the FINAL decision: approve or request changes. "
        "Consider: Does the AI's assessment align with project standards? "
        "Is the score fair? Are the required changes reasonable? "
        "You cannot reject - only approve or request changes. "
        "Respond with JSON: decision, severity, summary, feedback."
    )

    prompt = (
        f"Project state: {_state_summary(state)}\n\n"
        f"Intern's submission summary: {submission_content_summary}\n\n"
        f"AI Review Summary: {ai_review_summary}\n"
        f"AI Review Result: {ai_review_result}\n"
        f"AI Review Score: {ai_review_score}/100\n\n"
        "Provide your final manager review decision as JSON with keys: "
        "decision (approved|changes_required), "
        "severity (info|warning|error|critical), "
        "summary (1-2 sentences), "
        "feedback (specific guidance for the intern)."
    )

    return await ai_service.generate_json(prompt=prompt, system_prompt=system_prompt)
