"""
AI Workflow Simulation Engine — backend entrypoint.

Phase 1: DB schema, generators, Kanban/task REST APIs.
Phase 2: (frontend, separate app).
Phase 3: AI Project Manager + AI Teammates chat, WebSockets, Dynamic
Events Engine, Stateful Workflow rules, Meetings, Notifications,
Activity Log, Timeline, and a real APScheduler background job.
"""
from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import (
    activity, chat, companies, dev_auth, events, generate, meetings,
    notifications, projects, reviews, sprints, submissions, tasks, team, timeline, ws,
)
from app.core.config import settings
from app.services.scheduler_jobs import check_high_stress_projects

scheduler = AsyncIOScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler.add_job(check_high_stress_projects, "interval", seconds=60, id="high_stress_checkin")
    scheduler.start()
    yield
    scheduler.shutdown(wait=False)


app = FastAPI(
    title="AI Workflow Simulation Engine",
    description=(
        "Simulates a real software company internship: generates a company, "
        "project, sprints, and tasks, then drives task/Kanban state, AI "
        "manager/teammate chat, dynamic events, meetings, and notifications "
        "through a persistent PostgreSQL-backed workflow."
    ),
    version="0.3.0-phase3",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(dev_auth.router)
app.include_router(generate.router)
app.include_router(companies.router)
app.include_router(projects.router)
app.include_router(sprints.router)
app.include_router(tasks.router)
app.include_router(chat.router)
app.include_router(team.router)
app.include_router(notifications.router)
app.include_router(events.router)
app.include_router(activity.router)
app.include_router(meetings.router)
app.include_router(timeline.router)
app.include_router(submissions.router)
app.include_router(reviews.router)
app.include_router(ws.router)


@app.get("/health", tags=["System"])
def health_check():
    return {"status": "ok", "environment": settings.ENVIRONMENT}
