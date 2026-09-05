# AI Workflow Simulation Engine — Database Setup

## Database Version

Database Schema: V1
Database: aiwse_db
PostgreSQL: 18.x

## Backup Files

- aiwse_db_FINAL.backup — PostgreSQL Custom-format backup
- aiwse_db_FINAL.sql — Plain SQL backup

## Database Tables

The database contains the following application tables:

- activity_logs
- ai_reviews
- alembic_version
- companies
- events
- managers
- meeting_schedules
- messages
- notifications
- project_states
- projects
- review_history
- sprint_reviews
- sprints
- submission_versions
- submissions
- task_dependencies
- tasks
- team_members

Total application tables: 19

## Restore Using pgAdmin 4

1. Install PostgreSQL 18.x.
2. Open pgAdmin 4.
3. Create an empty database named `aiwse_db`.
4. Right-click `aiwse_db`.
5. Select `Restore`.
6. Select format `Custom or tar`.
7. Select `aiwse_db_FINAL.backup`.
8. Start the restore.
9. Refresh the database.
10. Verify that all 19 tables are present.

## Application Configuration

Create a local `.env` file.

Do not copy another developer's password or secrets.

Example:

POSTGRES_USER=postgres
POSTGRES_PASSWORD=<local-password>
POSTGRES_DB=aiwse_db
POSTGRES_HOST=localhost
POSTGRES_PORT=5432

DATABASE_URL=postgresql://postgres:<local-password>@localhost:5432/aiwse_db

## Important

This database is Database Schema V1.

Do not manually modify tables, columns, constraints, indexes, or relationships through pgAdmin.

Any future schema change must be implemented through an Alembic migration and coordinated with the project owner.

## Current Verified Data

The final database backup was restored and verified successfully.

Current verified records:

- companies: 31
- managers: 31
- projects: 31
- project_states: 31
- sprints: 124
- tasks: 349
- task_dependencies: 225
- team_members: 93
- meeting_schedules: 248
- submissions: 16
- submission_versions: 16
- activity_logs: 41
- messages: 10
- ai_reviews: 0
- review_history: 0
- sprint_reviews: 0
- events: 0
- notifications: 0

## Database Status

Schema V1: FROZEN

The database backup has been restore-tested against a separate PostgreSQL database.