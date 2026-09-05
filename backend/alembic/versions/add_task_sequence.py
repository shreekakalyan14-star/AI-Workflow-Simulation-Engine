"""add task sequence column for deterministic ordering

Revision ID: add_task_sequence_001
Revises: add_task_difficulty_001
Create Date: 2026-08-17
"""
from alembic import op
import sqlalchemy as sa

revision = "add_task_sequence_001"
down_revision = "add_task_difficulty_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add sequence column as nullable first
    op.add_column(
        "tasks",
        sa.Column("sequence", sa.Integer(), nullable=True),
    )

    # Populate existing tasks with deterministic ordering based on created_at within each sprint
    op.execute("""
        UPDATE tasks SET sequence = sub.rn - 1
        FROM (
            SELECT id, ROW_NUMBER() OVER (PARTITION BY sprint_id ORDER BY created_at, id) AS rn
            FROM tasks
        ) AS sub
        WHERE tasks.id = sub.id
    """)

    # Set NOT NULL after populating
    op.alter_column("tasks", "sequence", nullable=False, server_default="0")

    # Add composite index for efficient ordering within sprints
    op.create_index(
        "ix_tasks_sprint_sequence",
        "tasks",
        ["sprint_id", "sequence"],
    )


def downgrade() -> None:
    op.drop_index("ix_tasks_sprint_sequence", table_name="tasks")
    op.drop_column("tasks", "sequence")
