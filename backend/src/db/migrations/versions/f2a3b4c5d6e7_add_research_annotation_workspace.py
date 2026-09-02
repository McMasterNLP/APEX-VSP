"""add research annotation workspace tables

Revision ID: f2a3b4c5d6e7
Revises: a1b2c3d4e5f8
Create Date: 2026-09-01
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f2a3b4c5d6e7"
down_revision: Union[str, None] = "a1b2c3d4e5f8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "research_evaluation_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source_session_id", sa.Integer(), nullable=False),
        sa.Column("item1_run_id", sa.String(length=64), nullable=False),
        sa.Column("transcript_hash", sa.String(length=64), nullable=False),
        sa.Column("transcript_projection_version", sa.String(length=50), nullable=False),
        sa.Column("transcript_snapshot_json", sa.Text(), nullable=False),
        sa.Column("turn_count", sa.Integer(), nullable=False),
        sa.Column("envelope_schema_version", sa.String(length=20), nullable=False),
        sa.Column("envelope_json", sa.Text(), nullable=False),
        sa.Column("evaluator_identifier", sa.String(length=100), nullable=False),
        sa.Column("evaluator_version", sa.String(length=50), nullable=False),
        sa.Column("framework_identifier", sa.String(length=100), nullable=False),
        sa.Column("framework_version", sa.String(length=50), nullable=False),
        sa.Column("adapter_identifier", sa.String(length=100), nullable=False),
        sa.Column("adapter_version", sa.String(length=50), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=True),
        sa.Column("model_identifier", sa.String(length=200), nullable=True),
        sa.Column("rubric_version", sa.String(length=50), nullable=True),
        sa.Column("execution_mode", sa.String(length=20), nullable=False),
        sa.Column("execution_timestamp", sa.DateTime(), nullable=False),
        sa.Column("runtime_ms", sa.Float(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("failure_category", sa.String(length=100), nullable=True),
        sa.Column("created_by_user_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "status IN ('success', 'failed', 'refused')",
            name="ck_research_evaluation_runs_status",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"], ["core.users.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["source_session_id"], ["core.sessions.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        schema="core",
    )
    op.create_index(
        "ix_research_evaluation_runs_item1_run_id",
        "research_evaluation_runs",
        ["item1_run_id"],
        schema="core",
    )
    op.create_index(
        "ix_research_evaluation_runs_session",
        "research_evaluation_runs",
        ["source_session_id"],
        schema="core",
    )
    op.create_index(
        "ix_research_evaluation_runs_transcript_hash",
        "research_evaluation_runs",
        ["transcript_hash"],
        schema="core",
    )

    op.create_table(
        "research_annotation_sets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("evaluation_run_id", sa.Uuid(), nullable=False),
        sa.Column("transcript_hash", sa.String(length=64), nullable=False),
        sa.Column("framework_identifier", sa.String(length=100), nullable=False),
        sa.Column("framework_version", sa.String(length=50), nullable=False),
        sa.Column("annotation_policy_identifier", sa.String(length=100), nullable=False),
        sa.Column("annotation_policy_version", sa.String(length=50), nullable=False),
        sa.Column("guideline_identifier", sa.String(length=100), nullable=False),
        sa.Column("guideline_version", sa.String(length=50), nullable=False),
        sa.Column("reviewer_user_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("eligible_predictions_json", sa.Text(), nullable=False),
        sa.Column("set_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("locked_at", sa.DateTime(), nullable=True),
        sa.Column("reopened_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint(
            "status IN ('draft', 'in_review', 'complete')",
            name="ck_research_annotation_sets_status",
        ),
        sa.CheckConstraint(
            "revision >= 0", name="ck_research_annotation_sets_revision"
        ),
        sa.CheckConstraint(
            "set_note IS NULL OR length(set_note) <= 1000",
            name="ck_research_annotation_sets_note_length",
        ),
        sa.ForeignKeyConstraint(
            ["evaluation_run_id"],
            ["core.research_evaluation_runs.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["reviewer_user_id"], ["core.users.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "evaluation_run_id",
            "reviewer_user_id",
            "guideline_identifier",
            "guideline_version",
            name="uq_research_annotation_sets_reviewer_run_guideline",
        ),
        schema="core",
    )
    op.create_index(
        "ix_research_annotation_sets_run",
        "research_annotation_sets",
        ["evaluation_run_id"],
        schema="core",
    )
    op.create_index(
        "ix_research_annotation_sets_reviewer",
        "research_annotation_sets",
        ["reviewer_user_id"],
        schema="core",
    )
    op.create_index(
        "ix_research_annotation_sets_transcript_hash",
        "research_annotation_sets",
        ["transcript_hash"],
        schema="core",
    )

    op.create_table(
        "research_review_decision_revisions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("annotation_set_id", sa.Uuid(), nullable=False),
        sa.Column("prediction_id", sa.String(length=100), nullable=False),
        sa.Column("prediction_snapshot_json", sa.Text(), nullable=False),
        sa.Column("source_reference_json", sa.Text(), nullable=False),
        sa.Column("projection_type", sa.String(length=30), nullable=False),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("decision", sa.String(length=30), nullable=False),
        sa.Column("correction_json", sa.Text(), nullable=True),
        sa.Column("reviewer_note", sa.Text(), nullable=True),
        sa.Column("reviewer_user_id", sa.Integer(), nullable=False),
        sa.Column("supersedes_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "projection_type IN ('span_annotation', 'turn_label', 'relation', "
            "'dimension_rating', 'finding')",
            name="ck_research_review_decisions_projection_type",
        ),
        sa.CheckConstraint(
            "decision IN ('confirmed', 'rejected', 'corrected', "
            "'insufficient_evidence')",
            name="ck_research_review_decisions_decision",
        ),
        sa.CheckConstraint(
            "revision_number >= 1", name="ck_research_review_decisions_revision"
        ),
        sa.CheckConstraint(
            "reviewer_note IS NULL OR length(reviewer_note) <= 1000",
            name="ck_research_review_decisions_note_length",
        ),
        sa.ForeignKeyConstraint(
            ["annotation_set_id"],
            ["core.research_annotation_sets.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["reviewer_user_id"], ["core.users.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["supersedes_id"],
            ["core.research_review_decision_revisions.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "annotation_set_id",
            "prediction_id",
            "revision_number",
            name="uq_research_review_decisions_prediction_revision",
        ),
        schema="core",
    )
    op.create_index(
        "ix_research_review_decisions_set_prediction",
        "research_review_decision_revisions",
        ["annotation_set_id", "prediction_id"],
        schema="core",
    )

    op.create_table(
        "research_annotation_transitions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("annotation_set_id", sa.Uuid(), nullable=False),
        sa.Column("from_status", sa.String(length=20), nullable=False),
        sa.Column("to_status", sa.String(length=20), nullable=False),
        sa.Column("set_revision", sa.Integer(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("actor_user_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "set_revision >= 1", name="ck_research_annotation_transitions_revision"
        ),
        sa.CheckConstraint(
            "reason IS NULL OR length(reason) <= 500",
            name="ck_research_annotation_transitions_reason_length",
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"], ["core.users.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["annotation_set_id"],
            ["core.research_annotation_sets.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "annotation_set_id",
            "set_revision",
            name="uq_research_annotation_transitions_set_revision",
        ),
        schema="core",
    )
    op.create_index(
        "ix_research_annotation_transitions_set",
        "research_annotation_transitions",
        ["annotation_set_id"],
        schema="core",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_research_annotation_transitions_set",
        table_name="research_annotation_transitions",
        schema="core",
    )
    op.drop_table("research_annotation_transitions", schema="core")
    op.drop_index(
        "ix_research_review_decisions_set_prediction",
        table_name="research_review_decision_revisions",
        schema="core",
    )
    op.drop_table("research_review_decision_revisions", schema="core")
    op.drop_index(
        "ix_research_annotation_sets_transcript_hash",
        table_name="research_annotation_sets",
        schema="core",
    )
    op.drop_index(
        "ix_research_annotation_sets_reviewer",
        table_name="research_annotation_sets",
        schema="core",
    )
    op.drop_index(
        "ix_research_annotation_sets_run",
        table_name="research_annotation_sets",
        schema="core",
    )
    op.drop_table("research_annotation_sets", schema="core")
    op.drop_index(
        "ix_research_evaluation_runs_transcript_hash",
        table_name="research_evaluation_runs",
        schema="core",
    )
    op.drop_index(
        "ix_research_evaluation_runs_session",
        table_name="research_evaluation_runs",
        schema="core",
    )
    op.drop_index(
        "ix_research_evaluation_runs_item1_run_id",
        table_name="research_evaluation_runs",
        schema="core",
    )
    op.drop_table("research_evaluation_runs", schema="core")
