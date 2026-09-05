"""add simulation_task_paths table for per-student task paths

Revision ID: add_task_path_001
Revises: add_task_sequence_001
Create Date: 2026-08-17
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "add_task_path_001"
down_revision = "add_task_sequence_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "simulation_task_paths",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "simulation_id",
            UUID(as_uuid=True),
            sa.ForeignKey("simulations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "task_id",
            UUID(as_uuid=True),
            sa.ForeignKey("tasks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "backlog", "todo", "in_progress", "submitted", "under_review",
                "changes_requested", "manager_approval", "blocked", "completed",
                name="task_status_enum",
            ),
            nullable=False,
            server_default="backlog",
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_index(
        "ix_simulation_task_paths_simulation_id",
        "simulation_task_paths",
        ["simulation_id"],
    )
    op.create_index(
        "ix_simulation_task_paths_task_id",
        "simulation_task_paths",
        ["task_id"],
    )
    op.create_index(
        "ix_simulation_task_paths_simulation_sequence",
        "simulation_task_paths",
        ["simulation_id", "sequence"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_simulation_task_paths_simulation_sequence", table_name="simulation_task_paths")
    op.drop_index("ix_simulation_task_paths_task_id", table_name="simulation_task_paths")
    op.drop_index("ix_simulation_task_paths_simulation_id", table_name="simulation_task_paths")
    op.drop_table("simulation_task_paths")
    op.execute("DROP TYPE IF EXISTS task_status_enum")
