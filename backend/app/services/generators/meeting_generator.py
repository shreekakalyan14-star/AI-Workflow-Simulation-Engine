"""
FEATURE 10: Meetings.

Auto-schedules a Sprint Planning meeting at the start of each sprint and a
Sprint Review + Retrospective at the end of each sprint, with a real
agenda, participant list, and empty action-items/attendance ready to be
filled in when the meeting is "completed".
"""
from typing import List

from sqlalchemy.orm import Session

from app.models.enums import MeetingType
from app.models.manager import Manager
from app.models.meeting import MeetingSchedule
from app.models.sprint import Sprint
from app.models.team_member import TeamMember


def generate_meetings_for_sprints(
    db: Session, project_id, sprints: List[Sprint], manager: Manager, team_members: List[TeamMember]
) -> List[MeetingSchedule]:
    participants = [manager.name] + [t.name for t in team_members] + ["You"]
    meetings: List[MeetingSchedule] = []

    for sprint in sprints:
        planning = MeetingSchedule(
            project_id=project_id,
            meeting_type=MeetingType.SPRINT_PLANNING,
            scheduled_at=sprint.start_date,
            agenda=f"Plan scope and priorities for {sprint.name}.",
            participants=participants,
        )
        db.add(planning)
        meetings.append(planning)

        review = MeetingSchedule(
            project_id=project_id,
            meeting_type=MeetingType.SPRINT_REVIEW,
            scheduled_at=sprint.end_date,
            agenda=f"Review completed work and demo deliverables for {sprint.name}.",
            participants=participants,
        )
        db.add(review)
        meetings.append(review)

    db.flush()
    return meetings
