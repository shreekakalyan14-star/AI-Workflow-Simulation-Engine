"""
FEATURE 10: Meetings.

Auto-schedules a Sprint Planning meeting at the start of each sprint and a
Sprint Review + Retrospective at the end of each sprint, with a real
agenda, participant list, and empty action-items/attendance ready to be
filled in when the meeting is "completed".

Also schedules Daily Standups for each day of the sprint.
"""
from datetime import timedelta
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
        # Sprint Planning at start
        planning = MeetingSchedule(
            project_id=project_id,
            meeting_type=MeetingType.SPRINT_PLANNING,
            scheduled_at=sprint.start_date,
            agenda=f"Plan scope and priorities for {sprint.name}.",
            participants=participants,
        )
        db.add(planning)
        meetings.append(planning)

        # Daily Standups for each day of the sprint
        if sprint.start_date and sprint.end_date:
            current = sprint.start_date
            while current <= sprint.end_date:
                # Skip weekends (5=Saturday, 6=Sunday)
                if current.weekday() < 5:
                    standup = MeetingSchedule(
                        project_id=project_id,
                        meeting_type=MeetingType.DAILY_STANDUP,
                        scheduled_at=current.replace(hour=9, minute=0, second=0, microsecond=0),
                        agenda=f"Daily standup for {sprint.name}. Quick sync: what did you do, what will you do, any blockers.",
                        participants=participants,
                    )
                    db.add(standup)
                    meetings.append(standup)
                current += timedelta(days=1)

        # Sprint Review at end
        review = MeetingSchedule(
            project_id=project_id,
            meeting_type=MeetingType.SPRINT_REVIEW,
            scheduled_at=sprint.end_date,
            agenda=f"Review completed work and demo deliverables for {sprint.name}.",
            participants=participants,
        )
        db.add(review)
        meetings.append(review)

        # Retrospective after review
        retrospective = MeetingSchedule(
            project_id=project_id,
            meeting_type=MeetingType.RETROSPECTIVE,
            scheduled_at=sprint.end_date + timedelta(hours=1),
            agenda=f"Retrospective for {sprint.name}. What went well, what didn't, and how to improve.",
            participants=participants,
        )
        db.add(retrospective)
        meetings.append(retrospective)

    db.flush()
    return meetings
