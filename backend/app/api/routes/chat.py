"""
FEATURE 6 & 7: AI Project Manager chat + AI Teammate chat.

REST for sending (so the AI reply is computed and returned synchronously)
+ a WebSocket broadcast of both messages so any other open tab/session for
this company sees them live (FEATURE 17).
"""
"""
FEATURE 6 & 7: AI Project Manager chat + AI Teammate chat.

REST for sending (so the AI reply is computed and returned synchronously)
+ a WebSocket broadcast of both messages so any other open tab/session for
this company sees them live (FEATURE 17).
"""

import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import CurrentUser, get_current_user

from app.models.company import Company
from app.models.enums import MessageSenderType, TaskStatus
from app.models.manager import Manager
from app.models.message import Message
from app.models.project import Project
from app.models.team_member import TeamMember
from app.models.project_state import ProjectState

from app.schemas.chat import (
    ChatExchange,
    ChatMessageCreate,
    MessageRead,
)

# ✅ Correct imports
from app.services.ai.ai_manager import generate_manager_reply
from app.services.ai.ai_service import AIService, get_ai_service
from app.services.ai.ai_teammates import generate_teammate_reply

from app.services.activity_log_service import log_activity
from app.websockets.manager import manager as ws_manager

router = APIRouter(prefix="/api/companies/{company_id}/chat", tags=["Chat"])


def _get_owned_company(company_id: uuid.UUID, db: Session, user: CurrentUser) -> Company:
    company = db.get(Company, company_id)
    if company is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")
    if company.student_id != user.student_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your company")
    return company


def _project_for(db: Session, company_id: uuid.UUID) -> Project:
    project = db.execute(select(Project).where(Project.company_id == company_id)).scalars().first()
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No project for this company")
    return project


@router.get("/manager", response_model=List[MessageRead])
def get_manager_chat_history(
    company_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    _get_owned_company(company_id, db, user)
    stmt = (
        select(Message)
        .where(
            Message.company_id == company_id,
            Message.sender_type.in_([MessageSenderType.STUDENT, MessageSenderType.MANAGER]),
        )
        .order_by(Message.created_at)
    )
    return db.execute(stmt).scalars().all()


@router.post("/manager", response_model=ChatExchange, status_code=status.HTTP_201_CREATED)
async def send_manager_message(
    company_id: uuid.UUID,
    payload: ChatMessageCreate,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
    ai_service: AIService = Depends(get_ai_service),
):
    company = _get_owned_company(company_id, db, user)
    project = _project_for(db, company_id)
    manager_row = db.execute(select(Manager).where(Manager.company_id == company_id)).scalar_one()

    from app.models.project_state import ProjectState
    state = db.execute(select(ProjectState).where(ProjectState.project_id == project.id)).scalar_one()

    history = db.execute(
        select(Message)
        .where(
            Message.company_id == company_id,
            Message.sender_type.in_([MessageSenderType.STUDENT, MessageSenderType.MANAGER]),
        )
        .order_by(Message.created_at)
    ).scalars().all()

    student_msg = Message(
        company_id=company_id, sender_type=MessageSenderType.STUDENT,
        sender_id=user.student_id, content=payload.content,
    )
    db.add(student_msg)
    db.flush()

    reply_text = await generate_manager_reply(ai_service, manager_row, project, state, history, payload.content)

    reply_msg = Message(
        company_id=company_id, sender_type=MessageSenderType.MANAGER,
        sender_id=str(manager_row.id), content=reply_text,
    )
    db.add(reply_msg)

    state.communication_frequency += 1
    db.add(state)
    log_activity(db, company_id, actor=user.student_id, action="chat:manager", detail=payload.content[:200])

    db.commit()
    db.refresh(student_msg)
    db.refresh(reply_msg)

    for msg in (student_msg, reply_msg):
        await ws_manager.broadcast(str(company_id), "chat_message", {
            "channel": "manager", "id": str(msg.id), "sender_type": msg.sender_type.value,
            "content": msg.content, "created_at": msg.created_at.isoformat(),
        })

    return ChatExchange(student_message=student_msg, reply=reply_msg)


@router.get("/team/{team_member_id}", response_model=List[MessageRead])
def get_team_chat_history(
    company_id: uuid.UUID,
    team_member_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """
    NOTE: the `messages` table (from Phase 1's schema) is one stream per
    company, not one thread per conversation partner — a student message
    doesn't record which teammate it was aimed at. So this currently
    returns every student + team_member message for the company, not
    strictly this teammate's thread. Good enough for a single active
    teammate conversation; a real per-thread inbox would need a
    `recipient_id` column on Message (straightforward follow-up).
    """
    _get_owned_company(company_id, db, user)
    stmt = (
        select(Message)
        .where(
            Message.company_id == company_id,
            Message.sender_type.in_([MessageSenderType.STUDENT, MessageSenderType.TEAM_MEMBER]),
        )
        .order_by(Message.created_at)
    )
    return db.execute(stmt).scalars().all()


@router.post("/team/{team_member_id}", response_model=ChatExchange, status_code=status.HTTP_201_CREATED)
async def send_team_message(
    company_id: uuid.UUID,
    team_member_id: uuid.UUID,
    payload: ChatMessageCreate,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
    ai_service: AIService = Depends(get_ai_service),
):
    company = _get_owned_company(company_id, db, user)
    project = _project_for(db, company_id)
    teammate = db.get(TeamMember, team_member_id)
    if teammate is None or teammate.company_id != company_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Teammate not found")

    history = db.execute(
        select(Message)
        .where(
            Message.company_id == company_id,
            Message.sender_type.in_([MessageSenderType.STUDENT, MessageSenderType.TEAM_MEMBER]),
        )
        .order_by(Message.created_at)
    ).scalars().all()

    student_msg = Message(
        company_id=company_id, sender_type=MessageSenderType.STUDENT,
        sender_id=user.student_id, content=payload.content,
    )
    db.add(student_msg)
    db.flush()

    # Get current sprint, task, state, and blockers for context
    from app.models.project_state import ProjectState
    from app.models.sprint import Sprint
    from app.models.task import Task
    
    state = db.execute(select(ProjectState).where(ProjectState.project_id == project.id)).scalar_one_or_none()
    sprint = None
    task = None
    blockers = []
    
    # Find current task if mentioned or from project state
    if state and state.current_sprint_number:
        sprint = db.execute(
            select(Sprint).where(Sprint.project_id == project.id, Sprint.sprint_number == state.current_sprint_number)
        ).scalar_one_or_none()
    
    # Try to find task from message content or current work
    if sprint:
        task = db.execute(
            select(Task)
            .join(Sprint, Sprint.id == Task.sprint_id)
            .where(Sprint.project_id == project.id, Task.status.in_([TaskStatus.IN_PROGRESS, TaskStatus.UNDER_REVIEW]))
        ).scalars().first()
    
    if task:
        blockers = [task.blocked_reason] if task.blocked_reason else []
    
    reply_text = await generate_teammate_reply(
        ai_service=ai_service,
        teammate=teammate,
        project=project,
        history=history,
        student_message=payload.content,
        sprint=sprint,
        task=task,
        state=state,
        blockers=blockers,
    )

    reply_msg = Message(
        company_id=company_id, sender_type=MessageSenderType.TEAM_MEMBER,
        sender_id=str(teammate.id), content=reply_text,
    )
    db.add(reply_msg)
    log_activity(db, company_id, actor=user.student_id, action="chat:team", detail=payload.content[:200])
    db.commit()
    db.refresh(student_msg)
    db.refresh(reply_msg)

    for msg in (student_msg, reply_msg):
        await ws_manager.broadcast(str(company_id), "chat_message", {
            "channel": f"team:{team_member_id}", "id": str(msg.id), "sender_type": msg.sender_type.value,
            "content": msg.content, "created_at": msg.created_at.isoformat(),
        })

    return ChatExchange(student_message=student_msg, reply=reply_msg)
