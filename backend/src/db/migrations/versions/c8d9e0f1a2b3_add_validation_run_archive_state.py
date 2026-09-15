"""add research validation run archive state (item 3b)

Revision ID: c8d9e0f1a2b3
Revises: b7c8d9e0f1a2
Create Date: 2026-09-15
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c8d9e0f1a2b3"
down_revision: Union[str, None] = "b7c8d9e0f1a2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "research_validation_run_archive_state",
        sa.Column("validation_run_id", sa.Uuid(), nullable=False),
        sa.Column("archived", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("archived_at", sa.DateTime(), nullable=True),
        sa.Column("archived_by_user_id", sa.Integer(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["validation_run_id"],
            ["core.research_validation_runs.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["archived_by_user_id"],
            ["core.users.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("validation_run_id"),
        schema="core",
    )


def downgrade() -> None:
    op.drop_table("research_validation_run_archive_state", schema="core")
