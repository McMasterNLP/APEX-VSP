"""add research validation runs (item 3a)

Revision ID: b7c8d9e0f1a2
Revises: 1fc6c6467582
Create Date: 2026-09-10
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b7c8d9e0f1a2"
down_revision: Union[str, None] = "1fc6c6467582"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "research_validation_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("evaluation_run_id", sa.Uuid(), nullable=False),
        sa.Column("annotation_set_id", sa.Uuid(), nullable=False),
        sa.Column("annotation_set_revision_at_validation", sa.Integer(), nullable=False),
        sa.Column("transcript_hash", sa.String(length=64), nullable=False),
        sa.Column("evaluator_identifier", sa.String(length=100), nullable=False),
        sa.Column("evaluator_version", sa.String(length=50), nullable=False),
        sa.Column("matching_policy_identifier", sa.String(length=100), nullable=False),
        sa.Column("matching_policy_version", sa.String(length=50), nullable=False),
        sa.Column("metric_implementation_version", sa.String(length=100), nullable=False),
        sa.Column("coverage_level", sa.String(length=40), nullable=False),
        sa.Column("results_json", sa.Text(), nullable=False),
        sa.Column("warnings_json", sa.Text(), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "annotation_set_revision_at_validation >= 0",
            name="ck_research_validation_runs_revision",
        ),
        sa.ForeignKeyConstraint(
            ["evaluation_run_id"],
            ["core.research_evaluation_runs.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["annotation_set_id"],
            ["core.research_annotation_sets.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["core.users.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        schema="core",
    )
    op.create_index(
        "ix_research_validation_runs_evaluation_run",
        "research_validation_runs",
        ["evaluation_run_id"],
        schema="core",
    )
    op.create_index(
        "ix_research_validation_runs_annotation_set",
        "research_validation_runs",
        ["annotation_set_id"],
        schema="core",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_research_validation_runs_annotation_set",
        table_name="research_validation_runs",
        schema="core",
    )
    op.drop_index(
        "ix_research_validation_runs_evaluation_run",
        table_name="research_validation_runs",
        schema="core",
    )
    op.drop_table("research_validation_runs", schema="core")
