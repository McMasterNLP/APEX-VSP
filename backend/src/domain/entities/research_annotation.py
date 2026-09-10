"""Dedicated durable entities for research evaluation and human review."""

from __future__ import annotations

import uuid

from sqlalchemy import (
    CheckConstraint,
    Column,
    ForeignKey,
    Float,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    event,
)
from sqlalchemy.orm import relationship

from core.time import utc_now
from db.base import Base
from db.types import UTCDateTimeType


class ResearchEvaluationRun(Base):
    """Immutable server-generated evaluator result and transcript snapshot."""

    __tablename__ = "research_evaluation_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('success', 'failed', 'refused')",
            name="ck_research_evaluation_runs_status",
        ),
        Index("ix_research_evaluation_runs_session", "source_session_id"),
        Index("ix_research_evaluation_runs_transcript_hash", "transcript_hash"),
        {"schema": "core"},
    )

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_session_id = Column(
        Integer,
        ForeignKey("core.sessions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    item1_run_id = Column(String(64), nullable=False, index=True)
    transcript_hash = Column(String(64), nullable=False)
    transcript_projection_version = Column(String(50), nullable=False)
    transcript_snapshot_json = Column(Text, nullable=False)
    turn_count = Column(Integer, nullable=False)
    envelope_schema_version = Column(String(20), nullable=False)
    envelope_json = Column(Text, nullable=False)
    evaluator_identifier = Column(String(100), nullable=False)
    evaluator_version = Column(String(50), nullable=False)
    framework_identifier = Column(String(100), nullable=False)
    framework_version = Column(String(50), nullable=False)
    adapter_identifier = Column(String(100), nullable=False)
    adapter_version = Column(String(50), nullable=False)
    provider = Column(String(50), nullable=True)
    model_identifier = Column(String(200), nullable=True)
    rubric_version = Column(String(50), nullable=True)
    execution_mode = Column(String(20), nullable=False)
    execution_timestamp = Column(UTCDateTimeType(), nullable=False)
    runtime_ms = Column(Float, nullable=False)
    status = Column(String(20), nullable=False)
    failure_category = Column(String(100), nullable=True)
    created_by_user_id = Column(
        Integer,
        ForeignKey("core.users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    created_at = Column(UTCDateTimeType(), nullable=False, default=utc_now)

    source_session = relationship("Session", viewonly=True)
    created_by = relationship("User", foreign_keys=[created_by_user_id], viewonly=True)


class ResearchAnnotationSet(Base):
    """One reviewer's versioned review of one immutable evaluation run."""

    __tablename__ = "research_annotation_sets"
    __table_args__ = (
        CheckConstraint(
            "status IN ('draft', 'in_review', 'complete')",
            name="ck_research_annotation_sets_status",
        ),
        CheckConstraint("revision >= 0", name="ck_research_annotation_sets_revision"),
        CheckConstraint(
            "set_note IS NULL OR length(set_note) <= 1000",
            name="ck_research_annotation_sets_note_length",
        ),
        UniqueConstraint(
            "evaluation_run_id",
            "reviewer_user_id",
            "guideline_identifier",
            "guideline_version",
            name="uq_research_annotation_sets_reviewer_run_guideline",
        ),
        Index("ix_research_annotation_sets_run", "evaluation_run_id"),
        Index("ix_research_annotation_sets_reviewer", "reviewer_user_id"),
        Index("ix_research_annotation_sets_transcript_hash", "transcript_hash"),
        {"schema": "core"},
    )

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    evaluation_run_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("core.research_evaluation_runs.id", ondelete="RESTRICT"),
        nullable=False,
    )
    transcript_hash = Column(String(64), nullable=False)
    framework_identifier = Column(String(100), nullable=False)
    framework_version = Column(String(50), nullable=False)
    annotation_policy_identifier = Column(String(100), nullable=False)
    annotation_policy_version = Column(String(50), nullable=False)
    guideline_identifier = Column(String(100), nullable=False)
    guideline_version = Column(String(50), nullable=False)
    reviewer_user_id = Column(
        Integer,
        ForeignKey("core.users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    status = Column(String(20), nullable=False, default="draft")
    revision = Column(Integer, nullable=False, default=0)
    eligible_predictions_json = Column(Text, nullable=False)
    set_note = Column(Text, nullable=True)
    created_at = Column(UTCDateTimeType(), nullable=False, default=utc_now)
    updated_at = Column(UTCDateTimeType(), nullable=False, default=utc_now)
    completed_at = Column(UTCDateTimeType(), nullable=True)
    locked_at = Column(UTCDateTimeType(), nullable=True)
    reopened_at = Column(UTCDateTimeType(), nullable=True)

    evaluation_run = relationship("ResearchEvaluationRun", viewonly=True)
    reviewer = relationship("User", foreign_keys=[reviewer_user_id], viewonly=True)


class ResearchReviewDecisionRevision(Base):
    """Append-only typed decision revision for one projected prediction."""

    __tablename__ = "research_review_decision_revisions"
    __table_args__ = (
        CheckConstraint(
            "projection_type IN ('span_annotation', 'turn_label', 'relation', "
            "'dimension_rating', 'finding')",
            name="ck_research_review_decisions_projection_type",
        ),
        CheckConstraint(
            "decision IN ('confirmed', 'rejected', 'corrected', "
            "'insufficient_evidence')",
            name="ck_research_review_decisions_decision",
        ),
        CheckConstraint("revision_number >= 1", name="ck_research_review_decisions_revision"),
        CheckConstraint(
            "reviewer_note IS NULL OR length(reviewer_note) <= 1000",
            name="ck_research_review_decisions_note_length",
        ),
        UniqueConstraint(
            "annotation_set_id",
            "prediction_id",
            "revision_number",
            name="uq_research_review_decisions_prediction_revision",
        ),
        Index(
            "ix_research_review_decisions_set_prediction",
            "annotation_set_id",
            "prediction_id",
        ),
        {"schema": "core"},
    )

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    annotation_set_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("core.research_annotation_sets.id", ondelete="RESTRICT"),
        nullable=False,
    )
    prediction_id = Column(String(100), nullable=False)
    prediction_snapshot_json = Column(Text, nullable=False)
    source_reference_json = Column(Text, nullable=False)
    projection_type = Column(String(30), nullable=False)
    revision_number = Column(Integer, nullable=False)
    decision = Column(String(30), nullable=False)
    correction_json = Column(Text, nullable=True)
    reviewer_note = Column(Text, nullable=True)
    reviewer_user_id = Column(
        Integer,
        ForeignKey("core.users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    supersedes_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("core.research_review_decision_revisions.id", ondelete="RESTRICT"),
        nullable=True,
    )
    created_at = Column(UTCDateTimeType(), nullable=False, default=utc_now)

    annotation_set = relationship("ResearchAnnotationSet", viewonly=True)
    reviewer = relationship("User", foreign_keys=[reviewer_user_id], viewonly=True)
    supersedes = relationship(
        "ResearchReviewDecisionRevision",
        remote_side=[id],
        foreign_keys=[supersedes_id],
        viewonly=True,
    )


class ResearchAnnotationTransition(Base):
    """Append-only audit event for annotation-set lifecycle transitions."""

    __tablename__ = "research_annotation_transitions"
    __table_args__ = (
        CheckConstraint("set_revision >= 1", name="ck_research_annotation_transitions_revision"),
        CheckConstraint(
            "reason IS NULL OR length(reason) <= 500",
            name="ck_research_annotation_transitions_reason_length",
        ),
        UniqueConstraint(
            "annotation_set_id",
            "set_revision",
            name="uq_research_annotation_transitions_set_revision",
        ),
        Index("ix_research_annotation_transitions_set", "annotation_set_id"),
        {"schema": "core"},
    )

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    annotation_set_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("core.research_annotation_sets.id", ondelete="RESTRICT"),
        nullable=False,
    )
    from_status = Column(String(20), nullable=False)
    to_status = Column(String(20), nullable=False)
    set_revision = Column(Integer, nullable=False)
    reason = Column(Text, nullable=True)
    actor_user_id = Column(
        Integer,
        ForeignKey("core.users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    created_at = Column(UTCDateTimeType(), nullable=False, default=utc_now)

    annotation_set = relationship("ResearchAnnotationSet", viewonly=True)
    actor = relationship("User", foreign_keys=[actor_user_id], viewonly=True)


class ResearchHumanAnnotationRevision(Base):
    """Append-only complete snapshot of one human-authored span revision."""

    __tablename__ = "research_human_annotation_revisions"
    __table_args__ = (
        CheckConstraint("revision_number >= 1", name="ck_research_human_spans_revision"),
        CheckConstraint("set_revision >= 1", name="ck_research_human_spans_set_revision"),
        CheckConstraint("end_offset > start_offset", name="ck_research_human_spans_offsets"),
        CheckConstraint("status IN ('active', 'retired')", name="ck_research_human_spans_status"),
        CheckConstraint("operation IN ('create', 'relabel', 'edit_attributes', 'adjust_span', 'retire', 'restore')", name="ck_research_human_spans_operation"),
        UniqueConstraint("annotation_set_id", "annotation_id", "revision_number", name="uq_research_human_spans_object_revision"),
        Index("ix_research_human_spans_set_object", "annotation_set_id", "annotation_id"),
        {"schema": "core"},
    )

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    annotation_set_id = Column(Uuid(as_uuid=True), ForeignKey("core.research_annotation_sets.id", ondelete="RESTRICT"), nullable=False)
    annotation_id = Column(String(45), nullable=False)
    revision_number = Column(Integer, nullable=False)
    set_revision = Column(Integer, nullable=False)
    operation = Column(String(30), nullable=False)
    status = Column(String(20), nullable=False)
    transcript_hash = Column(String(64), nullable=False)
    turn_number = Column(Integer, nullable=False)
    speaker = Column(String(20), nullable=False)
    start_offset = Column(Integer, nullable=False)
    end_offset = Column(Integer, nullable=False)
    selected_text = Column(Text, nullable=False)
    label = Column(String(100), nullable=False)
    dimension = Column(String(100), nullable=True)
    attributes_json = Column(Text, nullable=False, default="[]")
    reviewer_note = Column(Text, nullable=True)
    reviewer_user_id = Column(Integer, ForeignKey("core.users.id", ondelete="RESTRICT"), nullable=False)
    policy_identifier = Column(String(100), nullable=False)
    policy_version = Column(String(50), nullable=False)
    guideline_identifier = Column(String(100), nullable=False)
    guideline_version = Column(String(50), nullable=False)
    supersedes_id = Column(Uuid(as_uuid=True), ForeignKey("core.research_human_annotation_revisions.id", ondelete="RESTRICT"), nullable=True)
    created_at = Column(UTCDateTimeType(), nullable=False, default=utc_now)


class ResearchAuthoredRelationRevision(Base):
    """Append-only complete snapshot of one human-authored relation revision."""

    __tablename__ = "research_authored_relation_revisions"
    __table_args__ = (
        CheckConstraint("revision_number >= 1", name="ck_research_authored_relations_revision"),
        CheckConstraint("set_revision >= 1", name="ck_research_authored_relations_set_revision"),
        CheckConstraint("status IN ('active', 'retired')", name="ck_research_authored_relations_status"),
        CheckConstraint("operation IN ('create', 'correct', 'retire', 'restore')", name="ck_research_authored_relations_operation"),
        UniqueConstraint("annotation_set_id", "relation_id", "revision_number", name="uq_research_authored_relations_object_revision"),
        Index("ix_research_authored_relations_set_object", "annotation_set_id", "relation_id"),
        {"schema": "core"},
    )

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    annotation_set_id = Column(Uuid(as_uuid=True), ForeignKey("core.research_annotation_sets.id", ondelete="RESTRICT"), nullable=False)
    relation_id = Column(String(49), nullable=False)
    revision_number = Column(Integer, nullable=False)
    set_revision = Column(Integer, nullable=False)
    operation = Column(String(20), nullable=False)
    status = Column(String(20), nullable=False)
    transcript_hash = Column(String(64), nullable=False)
    source_annotation_id = Column(String(45), nullable=False)
    target_annotation_id = Column(String(45), nullable=False)
    relation_type = Column(String(100), nullable=False)
    reviewer_note = Column(Text, nullable=True)
    reviewer_user_id = Column(Integer, ForeignKey("core.users.id", ondelete="RESTRICT"), nullable=False)
    policy_identifier = Column(String(100), nullable=False)
    policy_version = Column(String(50), nullable=False)
    guideline_identifier = Column(String(100), nullable=False)
    guideline_version = Column(String(50), nullable=False)
    supersedes_id = Column(Uuid(as_uuid=True), ForeignKey("core.research_authored_relation_revisions.id", ondelete="RESTRICT"), nullable=True)
    created_at = Column(UTCDateTimeType(), nullable=False, default=utc_now)


class ResearchCoverageDeclarationRevision(Base):
    """Append-only task-level coverage declaration."""

    __tablename__ = "research_coverage_declaration_revisions"
    __table_args__ = (
        CheckConstraint("coverage_revision >= 1", name="ck_research_coverage_revision"),
        CheckConstraint("set_revision >= 1", name="ck_research_coverage_set_revision"),
        CheckConstraint("coverage IN ('not_assessed', 'prediction_review_only', 'exhaustive', 'fixed_inventory_complete')", name="ck_research_coverage_value"),
        UniqueConstraint("annotation_set_id", "coverage_revision", name="uq_research_coverage_set_revision"),
        Index("ix_research_coverage_set", "annotation_set_id"),
        {"schema": "core"},
    )

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    annotation_set_id = Column(Uuid(as_uuid=True), ForeignKey("core.research_annotation_sets.id", ondelete="RESTRICT"), nullable=False)
    coverage_revision = Column(Integer, nullable=False)
    set_revision = Column(Integer, nullable=False)
    coverage = Column(String(40), nullable=False)
    reviewer_note = Column(Text, nullable=True)
    reviewer_user_id = Column(Integer, ForeignKey("core.users.id", ondelete="RESTRICT"), nullable=False)
    policy_identifier = Column(String(100), nullable=False)
    policy_version = Column(String(50), nullable=False)
    guideline_identifier = Column(String(100), nullable=False)
    guideline_version = Column(String(50), nullable=False)
    supersedes_id = Column(Uuid(as_uuid=True), ForeignKey("core.research_coverage_declaration_revisions.id", ondelete="RESTRICT"), nullable=True)
    created_at = Column(UTCDateTimeType(), nullable=False, default=utc_now)


def _prevent_mutation(mapper, connection, target) -> None:
    del mapper, connection, target
    raise ValueError("Immutable research records cannot be updated or deleted.")


for _append_only_entity in (
    ResearchEvaluationRun,
    ResearchReviewDecisionRevision,
    ResearchAnnotationTransition,
    ResearchHumanAnnotationRevision,
    ResearchAuthoredRelationRevision,
    ResearchCoverageDeclarationRevision,
):
    event.listen(_append_only_entity, "before_update", _prevent_mutation)
    event.listen(_append_only_entity, "before_delete", _prevent_mutation)
