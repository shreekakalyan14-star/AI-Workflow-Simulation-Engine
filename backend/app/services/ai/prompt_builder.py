from __future__ import annotations

from typing import Any, Dict


def build_review_prompt(context: Dict[str, Any]) -> str:
    return (
        "You are an expert engineering reviewer. Review the project submission for the following internship context. "
        "Return concise, structured feedback with summary, strengths, risks, and recommended actions.\n\n"
        f"Project: {context.get('project_title', '')}\n"
        f"Company: {context.get('company_name', '')}\n"
        f"Role: {context.get('role', '')}\n"
        f"Technology stack: {', '.join(context.get('technology_stack', []))}\n"
        f"Objectives: {', '.join(context.get('objectives', []))}\n"
        f"Modules: {', '.join(context.get('modules', []))}\n"
        f"Current state: completed_tasks={context['state']['completed_tasks']}, pending_tasks={context['state']['pending_tasks']}, "
        f"stress_level={context['state']['stress_level']}, missed_deadlines={context['state']['missed_deadlines']}"
    )
