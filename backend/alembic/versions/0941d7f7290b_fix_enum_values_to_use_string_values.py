"""fix enum values to use string values

Revision ID: 0941d7f7290b
Revises: af99a31f16d3
Create Date: 2026-08-08 18:41:36.897737

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0941d7f7290b'
down_revision: Union[str, None] = 'af99a31f16d3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create new enum types with all required values
    op.execute("CREATE TYPE task_priority_enum_new AS ENUM ('low', 'medium', 'high', 'critical')")
    op.execute("CREATE TYPE task_status_enum_new AS ENUM ('backlog', 'todo', 'in_progress', 'submitted', 'under_review', 'changes_requested', 'manager_approval', 'blocked', 'completed')")
    
    # Add new columns with new enum types
    op.add_column('tasks', sa.Column('priority_new', sa.Enum('low', 'medium', 'high', 'critical', name='task_priority_enum_new'), nullable=True))
    op.add_column('tasks', sa.Column('status_new', sa.Enum('backlog', 'todo', 'in_progress', 'submitted', 'under_review', 'changes_requested', 'manager_approval', 'blocked', 'completed', name='task_status_enum_new'), nullable=True))
    
    # Copy data from old columns to new columns (converting to lowercase, mapping REVIEW -> under_review)
    op.execute("UPDATE tasks SET priority_new = LOWER(priority::text)::task_priority_enum_new")
    op.execute("UPDATE tasks SET status_new = CASE LOWER(status::text) WHEN 'review' THEN 'under_review' ELSE LOWER(status::text) END::task_status_enum_new")
    
    # Drop old columns
    op.drop_column('tasks', 'priority')
    op.drop_column('tasks', 'status')
    
    # Rename new columns to original names
    op.execute("ALTER TABLE tasks RENAME COLUMN priority_new TO priority")
    op.execute("ALTER TABLE tasks RENAME COLUMN status_new TO status")
    
    # Drop old enum types
    op.execute("DROP TYPE task_priority_enum")
    op.execute("DROP TYPE task_status_enum")
    
    # Rename new enum types to original names
    op.execute("ALTER TYPE task_priority_enum_new RENAME TO task_priority_enum")
    op.execute("ALTER TYPE task_status_enum_new RENAME TO task_status_enum")


def downgrade() -> None:
    # Create old enum types with uppercase values (matching original)
    op.execute("CREATE TYPE task_priority_enum_old AS ENUM ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')")
    op.execute("CREATE TYPE task_status_enum_old AS ENUM ('BACKLOG', 'TODO', 'IN_PROGRESS', 'REVIEW', 'BLOCKED', 'COMPLETED')")
    
    # Add new columns with old enum types
    op.add_column('tasks', sa.Column('priority_old', sa.Enum('LOW', 'MEDIUM', 'HIGH', 'CRITICAL', name='task_priority_enum_old'), nullable=True))
    op.add_column('tasks', sa.Column('status_old', sa.Enum('BACKLOG', 'TODO', 'IN_PROGRESS', 'REVIEW', 'BLOCKED', 'COMPLETED', name='task_status_enum_old'), nullable=True))
    
    # Copy data from new columns to old columns (converting to uppercase, mapping under_review -> REVIEW)
    op.execute("UPDATE tasks SET priority_old = UPPER(priority::text)::task_priority_enum_old")
    op.execute("UPDATE tasks SET status_old = CASE UPPER(status::text) WHEN 'UNDER_REVIEW' THEN 'REVIEW' ELSE UPPER(status::text) END::task_status_enum_old")
    
    # Drop new columns
    op.drop_column('tasks', 'priority')
    op.drop_column('tasks', 'status')
    
    # Rename old columns to original names
    op.execute("ALTER TABLE tasks RENAME COLUMN priority_old TO priority")
    op.execute("ALTER TABLE tasks RENAME COLUMN status_old TO status")
    
    # Drop new enum types
    op.execute("DROP TYPE task_priority_enum")
    op.execute("DROP TYPE task_status_enum")
    
    # Rename old enum types to original names
    op.execute("ALTER TYPE task_priority_enum_old RENAME TO task_priority_enum")
    op.execute("ALTER TYPE task_status_enum_old RENAME TO task_status_enum")