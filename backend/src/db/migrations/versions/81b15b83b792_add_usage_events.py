"""add usage_events table (daily usage guardrails ahead of reviewer access)

Revision ID: 81b15b83b792
Revises: b5c6d7e8f9a0
Create Date: 2026-09-21

Backs UsageService's per-user/global daily caps on chat turns, audio
(ASR+TTS), and live research evaluations, plus the admin usage dashboard's
trends. One row per metered action, written once at the moment it's allowed
to proceed; never updated or deleted.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "81b15b83b792"
down_revision: Union[str, None] = "b5c6d7e8f9a0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "usage_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("category", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["core.users.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        schema="core",
    )
    op.create_index(
        "ix_usage_events_user_category_created",
        "usage_events",
        ["user_id", "category", "created_at"],
        schema="core",
    )
    op.create_index(
        "ix_usage_events_category_created",
        "usage_events",
        ["category", "created_at"],
        schema="core",
    )


def downgrade() -> None:
    op.drop_index("ix_usage_events_category_created", table_name="usage_events", schema="core")
    op.drop_index("ix_usage_events_user_category_created", table_name="usage_events", schema="core")
    op.drop_table("usage_events", schema="core")
