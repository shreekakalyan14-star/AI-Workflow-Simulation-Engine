from __future__ import annotations
from typing import Any, Dict


def build_review_prompt(context: Dict[str, Any]) -> str:
    task_title = context.get('task_title', 'Unknown Task')
    task_description = context.get('task_description', '')
    acceptance_criteria = context.get('acceptance_criteria', [])
    submission_content = context.get('submission_content', 'No submission content available.')
    current_submission = context.get('current_submission', {})
    
    # Company and project info
    company = context.get('company', {})
    project = context.get('project', {})
    sprint = context.get('sprint', {})
    previous_submissions = context.get('previous_submissions', [])
    
    prompt_parts = [
        "You are an expert engineering reviewer. Review the intern's submission for the following task.",
        "Analyze the actual code/content against the task requirements and acceptance criteria.",
        "Return concise, structured feedback in the exact JSON format specified below.",
        "",
        f"TASK: {task_title}",
        "",
    ]
    
    if task_description:
        prompt_parts.extend([
            "DESCRIPTION:",
            task_description,
            "",
        ])
    
    if acceptance_criteria:
        prompt_parts.extend([
            "ACCEPTANCE CRITERIA:",
            "\n".join("- " + str(c) for c in acceptance_criteria),
            "",
        ])
    
    if sprint:
        prompt_parts.extend([
            f"SPRINT: {sprint.get('name', '')} (Sprint {sprint.get('number', '?')})",
            f"SPRINT GOAL: {sprint.get('goal', 'Not specified')}",
            "",
        ])
    
    if project:
        prompt_parts.extend([
            f"PROJECT: {project.get('title', '')}",
            f"PROJECT OBJECTIVES: {', '.join(project.get('objectives', [])) or 'Not specified'}",
            f"TECHNOLOGY STACK: {', '.join(project.get('technology_stack', [])) or 'Not specified'}",
            "",
        ])
    
    if company:
        prompt_parts.extend([
            f"COMPANY: {company.get('name', '')} ({company.get('industry', '')})",
            f"COMPANY TYPE: {company.get('company_type', '')}",
            "",
        ])
    
    # Add previous submission history if available
    if previous_submissions:
        prompt_parts.extend([
            "PREVIOUS SUBMISSION HISTORY:",
            "-" * 40,
        ])
        for sub in previous_submissions[-3:]:  # Show last 3 attempts
            prompt_parts.append(f"  Version {sub.get('version_number', '?')} ({sub.get('submitted_at', 'unknown')}): {sub.get('status', 'unknown')}")
            for review in sub.get('reviews', [])[:2]:  # Show first 2 reviews per version
                prompt_parts.append(f"    Review: {review.get('result', 'unknown')} - {review.get('summary', 'No summary')[:100]}")
        prompt_parts.append("")
    
    # Current submission
    prompt_parts.extend([
        "CURRENT SUBMISSION:",
        f"  Version: {current_submission.get('version_number', '1')}",
        f"  Submitted: {current_submission.get('submitted_at', 'unknown')}",
        f"  Files: {len(current_submission.get('files', []))} file(s)",
        "",
        "SUBMISSION CONTENT:",
        "-" * 40,
        submission_content,
        "-" * 40,
        "",
    ])
    
    # Task metadata
    task_priority = context.get('task_priority', 'unknown')
    task_deadline = context.get('task_deadline', 'unknown')
    if task_priority != 'unknown':
        prompt_parts.extend([
            f"TASK PRIORITY: {task_priority}",
            f"TASK DEADLINE: {task_deadline}",
            "",
        ])
    
    prompt_parts.extend([
        "REQUIRED OUTPUT FORMAT (JSON - must match exactly):",
        "{",
        '  "result": "approved|changes_required|rejected",',
        '  "score": 85,',
        '  "summary": "Brief overall assessment (2-3 sentences)",',
        '  "strengths": ["List of things done well"],',
        '  "issues": ["List of concerns or issues found"],',
        '  "required_changes": ["Specific changes needed"],',
        '  "acceptance_criteria": [',
        '    {',
        '      "criterion": "criterion text",',
        '      "met": true,',
        '      "evidence": "evidence from submission"',
        '    }',
        '  ],',
        '  "code_quality": {',
        '    "score": 85,',
        '    "feedback": "Code quality assessment"',
        '  },',
        '  "testing": {',
        '    "score": 80,',
        '    "feedback": "Testing assessment"',
        '  },',
        '  "security": {',
        '    "score": 90,',
        '    "feedback": "Security assessment"',
        '  },',
        '  "performance": {',
        '    "score": 85,',
        '    "feedback": "Performance assessment"',
        '  }',
        "}",
        "",
        "RULES:",
        "- result must be one of: approved, changes_required, rejected",
        "- score 0-100: 90-100=excellent, 75-89=good, 60-74=needs work, <60=poor",
        "- approved = meets all acceptance criteria",
        "- changes_required = minor issues needing fixes",
        "- rejected = major issues requiring significant rework",
        "- Each acceptance criterion must have met=true/false and evidence",
        "- All fields are required; use empty arrays/strings if not applicable",
        "- Output ONLY valid JSON, no markdown, no extra text",
        "- Do NOT decide task completion; only provide technical review",
    ])
    
    return "\n".join(prompt_parts)