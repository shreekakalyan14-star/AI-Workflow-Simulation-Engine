"""add task difficulty column

Revision ID: add_task_difficulty_001
Revises: 0941d7f7290b
Create Date: 2026-08-10
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ENUM

revision = "add_task_difficulty_001"
down_revision = "0941d7f7290b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # difficulty_level_enum already exists (created by scenarios.difficulty)
    # Add difficulty column as nullable first
    op.add_column(
        "tasks",
        sa.Column("difficulty", sa.Enum("BEGINNER", "INTERMEDIATE", "ADVANCED", "EXPERT",
                  name="difficulty_level_enum", create_type=False), nullable=True),
    )

    # Populate existing tasks with INTERMEDIATE
    op.execute("UPDATE tasks SET difficulty = 'INTERMEDIATE'")

    # Set NOT NULL after populating
    op.alter_column("tasks", "difficulty", nullable=False)


def downgrade() -> None:
    op.drop_column("tasks", "difficulty")
