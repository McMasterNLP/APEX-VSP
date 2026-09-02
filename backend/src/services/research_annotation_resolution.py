"""Pure derivation of a human-resolved projection from immutable predictions."""

from __future__ import annotations

from domain.models.research_annotation import (
    AuthoredRelationRevisionRecord,
    DecisionRevisionRecord,
    DimensionRatingCorrection,
    HumanAnnotationRevisionRecord,
    ReviewablePrediction,
    SpanCorrection,
    TurnLabelCorrection,
)
from domain.models.research_evaluation import (
    DimensionRating,
    ProjectedRelation,
    ProjectionProvenance,
    ResearchFinding,
    ResearchProjection,
    SpanAnnotation,
    SourceReference,
    TurnLabel,
)


def resolve_annotation_projection(
    inventory: tuple[ReviewablePrediction, ...],
    effective_decisions: tuple[DecisionRevisionRecord, ...],
    active_human_annotations: tuple[HumanAnnotationRevisionRecord, ...] = (),
    active_authored_relations: tuple[AuthoredRelationRevisionRecord, ...] = (),
) -> ResearchProjection:
    """Resolve confirmed/corrected model predictions without mutating originals."""

    decisions = {item.prediction_id: item for item in effective_decisions}
    spans: list[SpanAnnotation] = []
    turn_labels: list[TurnLabel] = []
    ratings: list[DimensionRating] = []
    findings: list[ResearchFinding] = []
    pending_relations: list[ProjectedRelation] = []

    for item in inventory:
        decision = decisions.get(item.prediction_id)
        if decision is None or decision.decision == "rejected":
            continue
        prediction = item.original_prediction
        if isinstance(prediction, SpanAnnotation):
            spans.append(_resolve_span(prediction, decision))
        elif isinstance(prediction, TurnLabel):
            turn_labels.append(_resolve_turn_label(prediction, decision))
        elif isinstance(prediction, ProjectedRelation):
            pending_relations.append(prediction)
        elif isinstance(prediction, DimensionRating):
            ratings.append(_resolve_rating(prediction, decision))
        elif isinstance(prediction, ResearchFinding):
            findings.append(prediction)

    for annotation in active_human_annotations:
        spans.append(
            SpanAnnotation(
                prediction_id=annotation.annotation_id,
                framework_identifier=inventory[0].original_prediction.framework_identifier if inventory else "human-authored",
                turn_number=annotation.turn_number,
                start_offset=annotation.start_offset,
                end_offset=annotation.end_offset,
                quoted_text=annotation.selected_text,
                label=annotation.label,
                dimension=annotation.dimension,
                source_reference=SourceReference(
                    native_result_type="human_annotation",
                    native_identifier=annotation.annotation_id,
                    native_path=f"annotations[{annotation.annotation_id}]",
                    adapter_version="1.1",
                ),
                provenance=ProjectionProvenance(method="human_annotation"),
            )
        )

    resolved_span_ids = {item.prediction_id for item in spans}
    model_relations = [
        relation
        for relation in pending_relations
        if relation.source_annotation_id in resolved_span_ids
        and relation.target_annotation_id in resolved_span_ids
    ]
    authored_relations = [
        ProjectedRelation(
            relation_id=relation.relation_id,
            framework_identifier=inventory[0].original_prediction.framework_identifier if inventory else "human-authored",
            source_annotation_id=relation.source_annotation_id,
            target_annotation_id=relation.target_annotation_id,
            relation_type=relation.relation_type,
            source_reference=SourceReference(
                native_result_type="human_annotation",
                native_identifier=relation.relation_id,
                native_path=f"relations[{relation.relation_id}]",
                adapter_version="1.1",
            ),
            provenance=ProjectionProvenance(method="human_annotation"),
        )
        for relation in active_authored_relations
        if relation.source_annotation_id in resolved_span_ids
        and relation.target_annotation_id in resolved_span_ids
    ]
    return ResearchProjection(
        spans=tuple(spans),
        turn_labels=tuple(turn_labels),
        relations=tuple(model_relations + authored_relations),
        dimension_ratings=tuple(ratings),
        findings=tuple(findings),
    )


def _resolve_span(
    prediction: SpanAnnotation,
    decision: DecisionRevisionRecord,
) -> SpanAnnotation:
    if decision.decision == "confirmed":
        return prediction
    correction = decision.correction
    if not isinstance(correction, SpanCorrection):
        raise ValueError("A corrected span requires a span correction.")
    return prediction.model_copy(
        update={
            "label": correction.corrected_label,
            "dimension": correction.corrected_dimension,
            "start_offset": correction.corrected_start_char if correction.corrected_start_char is not None else prediction.start_offset,
            "end_offset": correction.corrected_end_char if correction.corrected_end_char is not None else prediction.end_offset,
            "quoted_text": correction.corrected_text if correction.corrected_text is not None else prediction.quoted_text,
            "provenance": ProjectionProvenance(method="human_correction"),
        }
    )


def _resolve_turn_label(
    prediction: TurnLabel,
    decision: DecisionRevisionRecord,
) -> TurnLabel:
    if decision.decision == "confirmed":
        return prediction
    correction = decision.correction
    if not isinstance(correction, TurnLabelCorrection):
        raise ValueError("A corrected turn label requires a turn-label correction.")
    return prediction.model_copy(
        update={
            "label": correction.corrected_label,
            "dimension": correction.corrected_dimension,
        }
    )


def _resolve_rating(
    prediction: DimensionRating,
    decision: DecisionRevisionRecord,
) -> DimensionRating:
    if decision.decision == "confirmed":
        return prediction
    correction = decision.correction
    if not isinstance(correction, DimensionRatingCorrection):
        raise ValueError("A corrected rating requires a rating correction.")
    return prediction.model_copy(
        update={
            "score": correction.corrected_score,
            "score_status": correction.corrected_score_status,
            "assessability": correction.corrected_assessability,
            "evidence_turns": correction.corrected_evidence_turns,
        }
    )
