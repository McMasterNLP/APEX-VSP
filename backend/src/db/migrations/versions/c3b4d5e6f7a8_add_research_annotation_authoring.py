"""add research annotation authoring revision tables

Revision ID: c3b4d5e6f7a8
Revises: f2a3b4c5d6e7
Create Date: 2026-09-02
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c3b4d5e6f7a8"
down_revision: Union[str, None] = "f2a3b4c5d6e7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _audit_columns() -> tuple[sa.Column, ...]:
    return (
        sa.Column("reviewer_note", sa.Text(), nullable=True),
        sa.Column("reviewer_user_id", sa.Integer(), nullable=False),
        sa.Column("policy_identifier", sa.String(length=100), nullable=False),
        sa.Column("policy_version", sa.String(length=50), nullable=False),
        sa.Column("guideline_identifier", sa.String(length=100), nullable=False),
        sa.Column("guideline_version", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["reviewer_user_id"], ["core.users.id"], ondelete="RESTRICT"),
    )


def upgrade() -> None:
    op.create_table(
        "research_human_annotation_revisions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("annotation_set_id", sa.Uuid(), nullable=False),
        sa.Column("annotation_id", sa.String(length=45), nullable=False),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("set_revision", sa.Integer(), nullable=False),
        sa.Column("operation", sa.String(length=30), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("transcript_hash", sa.String(length=64), nullable=False),
        sa.Column("turn_number", sa.Integer(), nullable=False),
        sa.Column("speaker", sa.String(length=20), nullable=False),
        sa.Column("start_offset", sa.Integer(), nullable=False),
        sa.Column("end_offset", sa.Integer(), nullable=False),
        sa.Column("selected_text", sa.Text(), nullable=False),
        sa.Column("label", sa.String(length=100), nullable=False),
        sa.Column("dimension", sa.String(length=100), nullable=True),
        sa.Column("attributes_json", sa.Text(), nullable=False),
        *_audit_columns(),
        sa.Column("supersedes_id", sa.Uuid(), nullable=True),
        sa.CheckConstraint("revision_number >= 1", name="ck_research_human_spans_revision"),
        sa.CheckConstraint("set_revision >= 1", name="ck_research_human_spans_set_revision"),
        sa.CheckConstraint("end_offset > start_offset", name="ck_research_human_spans_offsets"),
        sa.CheckConstraint("status IN ('active', 'retired')", name="ck_research_human_spans_status"),
        sa.CheckConstraint("operation IN ('create', 'relabel', 'edit_attributes', 'adjust_span', 'retire', 'restore')", name="ck_research_human_spans_operation"),
        sa.ForeignKeyConstraint(["annotation_set_id"], ["core.research_annotation_sets.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["supersedes_id"], ["core.research_human_annotation_revisions.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("annotation_set_id", "annotation_id", "revision_number", name="uq_research_human_spans_object_revision"),
        schema="core",
    )
    op.create_index("ix_research_human_spans_set_object", "research_human_annotation_revisions", ["annotation_set_id", "annotation_id"], schema="core")

    op.create_table(
        "research_authored_relation_revisions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("annotation_set_id", sa.Uuid(), nullable=False),
        sa.Column("relation_id", sa.String(length=49), nullable=False),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("set_revision", sa.Integer(), nullable=False),
        sa.Column("operation", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("transcript_hash", sa.String(length=64), nullable=False),
        sa.Column("source_annotation_id", sa.String(length=45), nullable=False),
        sa.Column("target_annotation_id", sa.String(length=45), nullable=False),
        sa.Column("relation_type", sa.String(length=100), nullable=False),
        *_audit_columns(),
        sa.Column("supersedes_id", sa.Uuid(), nullable=True),
        sa.CheckConstraint("revision_number >= 1", name="ck_research_authored_relations_revision"),
        sa.CheckConstraint("set_revision >= 1", name="ck_research_authored_relations_set_revision"),
        sa.CheckConstraint("status IN ('active', 'retired')", name="ck_research_authored_relations_status"),
        sa.CheckConstraint("operation IN ('create', 'correct', 'retire', 'restore')", name="ck_research_authored_relations_operation"),
        sa.ForeignKeyConstraint(["annotation_set_id"], ["core.research_annotation_sets.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["supersedes_id"], ["core.research_authored_relation_revisions.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("annotation_set_id", "relation_id", "revision_number", name="uq_research_authored_relations_object_revision"),
        schema="core",
    )
    op.create_index("ix_research_authored_relations_set_object", "research_authored_relation_revisions", ["annotation_set_id", "relation_id"], schema="core")

    op.create_table(
        "research_coverage_declaration_revisions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("annotation_set_id", sa.Uuid(), nullable=False),
        sa.Column("coverage_revision", sa.Integer(), nullable=False),
        sa.Column("set_revision", sa.Integer(), nullable=False),
        sa.Column("coverage", sa.String(length=40), nullable=False),
        *_audit_columns(),
        sa.Column("supersedes_id", sa.Uuid(), nullable=True),
        sa.CheckConstraint("coverage_revision >= 1", name="ck_research_coverage_revision"),
        sa.CheckConstraint("set_revision >= 1", name="ck_research_coverage_set_revision"),
        sa.CheckConstraint("coverage IN ('not_assessed', 'prediction_review_only', 'exhaustive', 'fixed_inventory_complete')", name="ck_research_coverage_value"),
        sa.ForeignKeyConstraint(["annotation_set_id"], ["core.research_annotation_sets.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["supersedes_id"], ["core.research_coverage_declaration_revisions.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("annotation_set_id", "coverage_revision", name="uq_research_coverage_set_revision"),
        schema="core",
    )
    op.create_index("ix_research_coverage_set", "research_coverage_declaration_revisions", ["annotation_set_id"], schema="core")


def downgrade() -> None:
    op.drop_index("ix_research_coverage_set", table_name="research_coverage_declaration_revisions", schema="core")
    op.drop_table("research_coverage_declaration_revisions", schema="core")
    op.drop_index("ix_research_authored_relations_set_object", table_name="research_authored_relation_revisions", schema="core")
    op.drop_table("research_authored_relation_revisions", schema="core")
    op.drop_index("ix_research_human_spans_set_object", table_name="research_human_annotation_revisions", schema="core")
    op.drop_table("research_human_annotation_revisions", schema="core")
