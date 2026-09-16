"""add plugin_promotion_requests table (plugin-registry-refactor phase 4)

Revision ID: f3a4b5c6d7e8
Revises: e2f3a4b5c6d7
Create Date: 2026-09-16

Adds the request/review workflow on top of the phase 1 plugin_registrations
table. RegistryService.promote()/deprecate() still perform the actual stage
change (their promoted_at/deprecated_at bookkeeping is untouched); this table
adds an audit trail of who requested a stage change and who approved/
rejected it, gating a real UI-driven promotion process rather than only the
direct in-code stage flip phases 1-2 used at migration/seed time.

No existing data is seeded here -- there is nothing to seed; this is a new,
empty workflow table.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f3a4b5c6d7e8"
down_revision: Union[str, None] = "e2f3a4b5c6d7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


PLUGIN_STAGES = (
    "draft",
    "experimental",
    "under_review",
    "promoted",
    "deprecated",
    "retired",
)
PROMOTION_REQUEST_STATUSES = ("pending", "approved", "rejected", "withdrawn")


def upgrade() -> None:
    op.create_table(
        "plugin_promotion_requests",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("registration_id", sa.Integer(), nullable=False),
        sa.Column("requested_stage", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("requested_by_user_id", sa.Integer(), nullable=True),
        sa.Column("request_notes", sa.Text(), nullable=True),
        sa.Column("reviewed_by_user_id", sa.Integer(), nullable=True),
        sa.Column("review_notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint(
            f"requested_stage IN {PLUGIN_STAGES!r}",
            name="ck_plugin_promotion_requests_requested_stage",
        ),
        sa.CheckConstraint(
            f"status IN {PROMOTION_REQUEST_STATUSES!r}",
            name="ck_plugin_promotion_requests_status",
        ),
        sa.ForeignKeyConstraint(
            ["registration_id"],
            ["core.plugin_registrations.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["requested_by_user_id"],
            ["core.users.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["reviewed_by_user_id"],
            ["core.users.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        schema="core",
    )
    op.create_index(
        "ix_plugin_promotion_requests_registration_id",
        "plugin_promotion_requests",
        ["registration_id"],
        schema="core",
    )
    # At most one pending request per registration at a time.
    op.create_index(
        "uq_plugin_promotion_requests_one_pending",
        "plugin_promotion_requests",
        ["registration_id"],
        unique=True,
        schema="core",
        postgresql_where=sa.text("status = 'pending'"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_plugin_promotion_requests_one_pending",
        table_name="plugin_promotion_requests",
        schema="core",
    )
    op.drop_index(
        "ix_plugin_promotion_requests_registration_id",
        table_name="plugin_promotion_requests",
        schema="core",
    )
    op.drop_table("plugin_promotion_requests", schema="core")
