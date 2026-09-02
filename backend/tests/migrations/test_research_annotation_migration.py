"""Structural checks for the research annotation migration and metadata."""

from pathlib import Path

from domain.entities.research_annotation import (
    ResearchAnnotationSet,
    ResearchAnnotationTransition,
    ResearchEvaluationRun,
    ResearchReviewDecisionRevision,
)


def test_research_annotation_tables_and_constraints_are_registered():
    tables = (
        ResearchEvaluationRun.__table__,
        ResearchAnnotationSet.__table__,
        ResearchReviewDecisionRevision.__table__,
        ResearchAnnotationTransition.__table__,
    )
    assert {table.name for table in tables} == {
        "research_evaluation_runs",
        "research_annotation_sets",
        "research_review_decision_revisions",
        "research_annotation_transitions",
    }
    assert any(
        constraint.name == "uq_research_annotation_sets_reviewer_run_guideline"
        for constraint in ResearchAnnotationSet.__table__.constraints
    )
    assert any(
        constraint.name == "uq_research_review_decisions_prediction_revision"
        for constraint in ResearchReviewDecisionRevision.__table__.constraints
    )


def test_research_annotation_migration_is_reversible_and_restrictive():
    migration = Path(
        "src/db/migrations/versions/f2a3b4c5d6e7_add_research_annotation_workspace.py"
    ).read_text(encoding="utf-8")
    assert "def upgrade()" in migration
    assert "def downgrade()" in migration
    assert migration.count('ondelete="RESTRICT"') >= 8
    assert migration.count('schema="core"') >= 12
    assert "drop_table(\"research_evaluation_runs\"" in migration
